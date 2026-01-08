"""
analysis/statistics.py

Statistics collector and analyzer for the traffic simulation system.
Collects detailed performance metrics for passengers and vehicles,
generates comprehensive reports, and creates visualizations.

Enhanced with periodic sampling to ensure continuous vehicle tracking.
"""

import logging
import json
import csv
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

# Configure logger
logger = logging.getLogger(__name__)


class Statistics:
    """
    Statistics collector and analyzer for the simulation system.
    
    Collects detailed performance metrics for passengers and vehicles,
    generates comprehensive reports, and creates visualizations.
    
    Enhanced Features:
        - Periodic vehicle state sampling for continuous tracking
        - Data consistency validation
        - Detailed vehicle state history
    
    Attributes:
        passenger_records (List[Dict]): Complete records of all passengers
        vehicle_records (Dict[str, Dict]): Records for each vehicle
        system_events (List[Dict]): System-level events timeline
        simulation_start_time (datetime): Simulation start time
        simulation_end_time (datetime): Simulation end time
        simulation_duration (float): Total simulation duration in seconds
        sampling_interval (float): Time interval for periodic sampling (seconds)
    """
    
    def __init__(self, simulation_start_time: datetime, simulation_end_time: datetime, 
                 sampling_interval: float = 30.0):
        """
        Initialize the Statistics collector.
        
        Args:
            simulation_start_time: Datetime when simulation starts
            simulation_end_time: Datetime when simulation ends
            sampling_interval: Time interval (seconds) for periodic vehicle state sampling
        """
        logger.info("Initializing Statistics collector...")
        
        # Store simulation time bounds
        self.simulation_start_time = simulation_start_time
        self.simulation_end_time = simulation_end_time
        self.simulation_duration = (simulation_end_time - simulation_start_time).total_seconds()
        
        # Sampling configuration
        self.sampling_interval = sampling_interval
        self.last_sample_time: Dict[str, float] = {}  # Track last sampling time per vehicle
        
        # Initialize data structures
        self.passenger_records: List[Dict] = []
        self.vehicle_records: Dict[str, Dict] = {}
        self.system_events: List[Dict] = []
        
        logger.info(
            f"Statistics collector initialized. "
            f"Simulation duration: {self.simulation_duration}s "
            f"({self.simulation_duration/3600:.2f} hours), "
            f"Sampling interval: {sampling_interval}s"
        )
    
    def record_passenger(self, passenger: 'Passenger') -> None:
        """
        Record a passenger's complete journey information.
        
        Called when:
        - Passenger arrives at destination
        - Passenger abandons waiting
        - Simulation ends (for still-waiting passengers)
        
        Args:
            passenger: Passenger object with complete state
        
        Records:
            - All timing information
            - Origin and destination
            - Final status
            - Assigned vehicle (if any)
        """
        try:
            # Calculate derived metrics
            wait_time = None
            travel_time = None
            total_time = None
            
            # Use pickup_time instead of board_time
            if passenger.pickup_time is not None:
                wait_time = passenger.pickup_time - passenger.appear_time
            
            if passenger.pickup_time is not None and passenger.arrival_time is not None:
                travel_time = passenger.arrival_time - passenger.pickup_time
            
            if passenger.arrival_time is not None:
                total_time = passenger.arrival_time - passenger.appear_time
            
            # Create passenger record
            record = {
                "passenger_id": passenger.passenger_id,
                "origin": passenger.origin_station_id,
                "destination": passenger.destination_station_id,
                "appear_time": passenger.appear_time,
                "board_time": passenger.pickup_time,  # Map pickup_time to board_time
                "arrival_time": passenger.arrival_time,
                "status": passenger.status,
                "wait_time": wait_time,
                "travel_time": travel_time,
                "total_time": total_time,
                "assigned_vehicle": passenger.assigned_vehicle_id
            }
            
            # Add to records
            self.passenger_records.append(record)
            
            logger.debug(
                f"Recorded passenger {passenger.passenger_id}: "
                f"status={passenger.status}, wait={wait_time}, travel={travel_time}"
            )
        
        except Exception as e:
            logger.error(f"Error recording passenger {passenger.passenger_id}: {e}", exc_info=True)
    
    def record_vehicle_state_periodic(
        self,
        vehicle_id: str,
        current_time: float,
        occupancy: int,
        location: str,
        vehicle_type: str = "Bus"
    ) -> None:
        """
        Record vehicle state at regular intervals for continuous tracking.
        
        This method should be called periodically (e.g., every 30 seconds) to ensure
        continuous occupancy tracking even when no boarding/alighting events occur.
        
        Args:
            vehicle_id: Unique vehicle identifier
            current_time: Current simulation time in seconds
            occupancy: Current number of passengers on board
            location: Current station or location identifier
            vehicle_type: Type of vehicle ("Bus" or "Minibus")
        
        Note:
            Automatically throttles recording based on sampling_interval to avoid
            excessive data points.
        """
        try:
            # Check if enough time has passed since last sample
            last_time = self.last_sample_time.get(vehicle_id, -float('inf'))
            
            if current_time - last_time < self.sampling_interval:
                return  # Skip sampling if interval not reached
            
            # Update last sample time
            self.last_sample_time[vehicle_id] = current_time
            
            # Initialize vehicle record if first time
            if vehicle_id not in self.vehicle_records:
                self.vehicle_records[vehicle_id] = {
                    "vehicle_type": vehicle_type,
                    "route": [],
                    "total_passengers_served": 0,
                    "total_distance": 0.0,
                    "occupancy_over_time": [],
                    "location_over_time": [],  # NEW: Track location history
                    "boarding_events": [],
                    "alighting_events": [],
                    "state_changes": []  # NEW: Track all state changes
                }
            
            vehicle_record = self.vehicle_records[vehicle_id]
            
            # Record occupancy
            vehicle_record["occupancy_over_time"].append((current_time, occupancy))
            
            # Record location
            vehicle_record["location_over_time"].append((current_time, location))
            
            # Record state change
            vehicle_record["state_changes"].append({
                "time": current_time,
                "type": "PERIODIC_SAMPLE",
                "occupancy": occupancy,
                "location": location
            })
            
            logger.debug(
                f"Periodic sample for {vehicle_id} at {current_time}s: "
                f"occupancy={occupancy}, location={location}"
            )
        
        except Exception as e:
            logger.error(
                f"Error recording periodic state for {vehicle_id}: {e}",
                exc_info=True
            )
    def record_vehicle_event(
        self,
        vehicle_id: str,
        event_type: str,
        event_data: Dict,
        current_time: float
    ) -> None:
        """
        Record a vehicle event (boarding, alighting, arrival, etc.).
        
        Args:
            vehicle_id: Unique vehicle identifier
            event_type: Type of event ("BOARDING", "ALIGHTING", "ARRIVAL", "DEPARTURE")
            event_data: Dictionary with event-specific data
            current_time: Current simulation time in seconds
        
        Event data examples:
            BOARDING: {"station": "A", "count": 3, "occupancy": 5}  # occupancy AFTER boarding
            ALIGHTING: {"station": "B", "count": 2, "occupancy": 3}  # occupancy AFTER alighting
            ARRIVAL: {"station": "C", "occupancy": 5}
        
        IMPORTANT: The 'occupancy' field in event_data MUST represent the vehicle state
                AFTER the event has occurred:
                - BOARDING: occupancy = previous_occupancy + count
                - ALIGHTING: occupancy = previous_occupancy - count
        """
        try:
            # Initialize vehicle record if first event
            if vehicle_id not in self.vehicle_records:
                self.vehicle_records[vehicle_id] = {
                    "vehicle_type": "Minibus" if vehicle_id.startswith("MINIBUS") else "Bus",
                    "route": [],
                    "total_passengers_served": 0,
                    "total_distance": 0.0,
                    "occupancy_over_time": [],
                    "location_over_time": [],
                    "boarding_events": [],
                    "alighting_events": [],
                    "state_changes": []
                }
            
            vehicle_record = self.vehicle_records[vehicle_id]
            
            # Record occupancy (always for event-based tracking)
            # NOTE: This records the occupancy AFTER the event
            if "occupancy" in event_data:
                vehicle_record["occupancy_over_time"].append(
                    (current_time, event_data["occupancy"])
                )
            
            # Record location if available
            if "station" in event_data:
                vehicle_record["location_over_time"].append(
                    (current_time, event_data["station"])
                )
            
            # Handle specific event types
            if event_type == "BOARDING":
                # Validate: occupancy should have increased
                if "count" in event_data and "occupancy" in event_data:
                    count = event_data.get("count", 0)
                    occupancy = event_data.get("occupancy")
                    
                    # WARNING: Check if occupancy is consistent with boarding count
                    # If this is not the first record, verify the increase
                    if vehicle_record["occupancy_over_time"]:
                        prev_occupancy = vehicle_record["occupancy_over_time"][-2][1] if len(vehicle_record["occupancy_over_time"]) > 1 else 0
                        expected_occupancy = prev_occupancy + count
                        
                        if occupancy != expected_occupancy:
                            logger.warning(
                                f"BOARDING occupancy mismatch for {vehicle_id} at {current_time}s: "
                                f"previous={prev_occupancy}, count={count}, "
                                f"expected={expected_occupancy}, actual={occupancy}"
                            )
                
                vehicle_record["boarding_events"].append({
                    "time": current_time,
                    "station": event_data.get("station"),
                    "count": event_data.get("count", 0)
                })
                vehicle_record["total_passengers_served"] += event_data.get("count", 0)
                
                # Record state change
                vehicle_record["state_changes"].append({
                    "time": current_time,
                    "type": "BOARDING",
                    "station": event_data.get("station"),
                    "count": event_data.get("count", 0),
                    "occupancy": event_data.get("occupancy")
                })
            
            elif event_type == "ALIGHTING":
                # Validate: occupancy should have decreased
                if "count" in event_data and "occupancy" in event_data:
                    count = event_data.get("count", 0)
                    occupancy = event_data.get("occupancy")
                    
                    # WARNING: Check if occupancy is consistent with alighting count
                    if vehicle_record["occupancy_over_time"]:
                        prev_occupancy = vehicle_record["occupancy_over_time"][-2][1] if len(vehicle_record["occupancy_over_time"]) > 1 else 0
                        expected_occupancy = prev_occupancy - count
                        
                        if occupancy != expected_occupancy:
                            logger.warning(
                                f"ALIGHTING occupancy mismatch for {vehicle_id} at {current_time}s: "
                                f"previous={prev_occupancy}, count={count}, "
                                f"expected={expected_occupancy}, actual={occupancy}"
                            )
                
                vehicle_record["alighting_events"].append({
                    "time": current_time,
                    "station": event_data.get("station"),
                    "count": event_data.get("count", 0)
                })
                
                # Record state change
                vehicle_record["state_changes"].append({
                    "time": current_time,
                    "type": "ALIGHTING",
                    "station": event_data.get("station"),
                    "count": event_data.get("count", 0),
                    "occupancy": event_data.get("occupancy")
                })
            
            elif event_type == "ARRIVAL":
                station = event_data.get("station")
                
                # Add station to route only if it's new (avoid duplicates)
                if station and station not in vehicle_record["route"]:
                    vehicle_record["route"].append(station)
                
                # Record state change
                vehicle_record["state_changes"].append({
                    "time": current_time,
                    "type": "ARRIVAL",
                    "station": station,
                    "occupancy": event_data.get("occupancy")
                })
            
            elif event_type == "DEPARTURE":
                # Record state change
                vehicle_record["state_changes"].append({
                    "time": current_time,
                    "type": "DEPARTURE",
                    "station": event_data.get("station"),
                    "occupancy": event_data.get("occupancy")
                })
            
            logger.debug(
                f"Recorded {event_type} event for {vehicle_id} at {current_time}s"
            )
        
        except Exception as e:
            logger.error(
                f"Error recording vehicle event for {vehicle_id}: {e}",
                exc_info=True
            )
    
    def validate_vehicle_data(self, vehicle_id: str) -> List[str]:
        """
        Validate data consistency for a specific vehicle.
        
        Args:
            vehicle_id: Vehicle to validate
        
        Returns:
            List of validation issues found (empty if all checks pass)
        
        Checks:
            - Total boardings should equal total alightings (for completed routes)
            - Occupancy should never be negative
            - Occupancy changes should match boarding/alighting events
            - Passengers served should equal total boardings
        """
        issues = []
        
        try:
            if vehicle_id not in self.vehicle_records:
                issues.append(f"Vehicle {vehicle_id} not found in records")
                return issues
            
            record = self.vehicle_records[vehicle_id]
            
            # Check 1: Boarding vs Alighting balance
            total_boarded = sum(e["count"] for e in record["boarding_events"])
            total_alighted = sum(e["count"] for e in record["alighting_events"])
            
            # For vehicles that completed their route, these should match
            # Allow small imbalance if vehicle still has passengers at end
            if abs(total_boarded - total_alighted) > 0:
                current_occupancy = 0
                if record["occupancy_over_time"]:
                    current_occupancy = record["occupancy_over_time"][-1][1]
                
                expected_diff = total_boarded - total_alighted
                if current_occupancy != expected_diff:
                    issues.append(
                        f"Boarding/alighting mismatch: {total_boarded} boarded, "
                        f"{total_alighted} alighted, final occupancy={current_occupancy} "
                        f"(expected {expected_diff})"
                    )
            
            # Check 2: Negative occupancy
            for time, occupancy in record["occupancy_over_time"]:
                if occupancy < 0:
                    issues.append(f"Negative occupancy ({occupancy}) at time {time}s")
            
            # Check 3: Passengers served should match total boardings
            if record["total_passengers_served"] != total_boarded:
                issues.append(
                    f"Passengers served mismatch: recorded={record['total_passengers_served']}, "
                    f"actual boardings={total_boarded}"
                )
            
            # Check 4: Data point consistency
            if len(record["occupancy_over_time"]) == 0 and total_boarded > 0:
                issues.append("No occupancy data despite boarding events")
            
            # Check 5: Empty vehicle with passengers served
            if record["total_passengers_served"] == 0 and len(record["route"]) > 0:
                issues.append(
                    f"Vehicle traveled route {record['route']} but served 0 passengers"
                )
            
        except Exception as e:
            issues.append(f"Validation error: {str(e)}")
            logger.error(f"Error validating vehicle {vehicle_id}: {e}", exc_info=True)
        
        return issues
    
    def validate_all_vehicles(self) -> Dict[str, List[str]]:
        """
        Validate data consistency for all vehicles.
        
        Returns:
            Dictionary mapping vehicle_id to list of issues
            Only includes vehicles with issues
        """
        logger.info("Validating data consistency for all vehicles...")
        
        all_issues = {}
        
        for vehicle_id in self.vehicle_records.keys():
            issues = self.validate_vehicle_data(vehicle_id)
            if issues:
                all_issues[vehicle_id] = issues
                logger.warning(f"Validation issues for {vehicle_id}: {issues}")
        
        if not all_issues:
            logger.info("All vehicle data passed validation ✓")
        else:
            logger.warning(f"Found issues in {len(all_issues)} vehicles")
        
        return all_issues
    
    def record_system_event(
        self,
        event_type: str,
        description: str,
        current_time: float
    ) -> None:
        """
        Record a system-level event.
        
        Args:
            event_type: Event type string
            description: Human-readable description
            current_time: Current simulation time in seconds
        
        Used for tracking major simulation events for timeline analysis.
        """
        try:
            event = {
                "time": current_time,
                "event_type": event_type,
                "description": description
            }
            self.system_events.append(event)
            
            logger.debug(f"Recorded system event: {event_type} at {current_time}s")
        
        except Exception as e:
            logger.error(f"Error recording system event: {e}", exc_info=True)
    
    def calculate_passenger_metrics(self) -> Dict[str, float]:
        """
        Calculate aggregate passenger performance metrics.
        
        Returns:
            Dictionary containing:
                - total_passengers: Total number of passengers
                - arrived_passengers: Number who reached destination
                - abandoned_passengers: Number who gave up
                - service_rate: Percentage who arrived (0-100)
                - avg_wait_time: Average waiting time (seconds)
                - avg_travel_time: Average travel time (seconds)
                - avg_total_time: Average total time (seconds)
                - max_wait_time: Maximum waiting time
                - min_wait_time: Minimum waiting time
                - std_wait_time: Standard deviation of wait times
                - percentile_90_wait: 90th percentile wait time
                - percentile_95_wait: 95th percentile wait time
        """
        logger.info("Calculating passenger metrics...")
        
        try:
            total_passengers = len(self.passenger_records)
            
            # Handle empty dataset
            if total_passengers == 0:
                logger.warning("No passenger records found")
                return {
                    "total_passengers": 0,
                    "arrived_passengers": 0,
                    "abandoned_passengers": 0,
                    "service_rate": 0.0,
                    "avg_wait_time": 0.0,
                    "avg_travel_time": 0.0,
                    "avg_total_time": 0.0,
                    "max_wait_time": 0.0,
                    "min_wait_time": 0.0,
                    "std_wait_time": 0.0,
                    "percentile_90_wait": 0.0,
                    "percentile_95_wait": 0.0
                }
            
            # Count by status
            arrived_passengers = sum(
                1 for p in self.passenger_records if p["status"] == "ARRIVED"
            )
            abandoned_passengers = sum(
                1 for p in self.passenger_records if p["status"] == "ABANDONED"
            )
            
            # Calculate service rate
            service_rate = (arrived_passengers / total_passengers * 100) if total_passengers > 0 else 0.0
            
            # Extract wait times (for all passengers who boarded or are still waiting)
            wait_times = [
                p["wait_time"] for p in self.passenger_records 
                if p["wait_time"] is not None
            ]
            
            # Extract travel times (for passengers who arrived)
            travel_times = [
                p["travel_time"] for p in self.passenger_records 
                if p["travel_time"] is not None
            ]
            
            # Extract total times (for passengers who arrived)
            total_times = [
                p["total_time"] for p in self.passenger_records 
                if p["total_time"] is not None
            ]
            
            # Calculate wait time statistics
            if wait_times:
                wait_times_array = np.array(wait_times)
                avg_wait_time = float(np.mean(wait_times_array))
                max_wait_time = float(np.max(wait_times_array))
                min_wait_time = float(np.min(wait_times_array))
                std_wait_time = float(np.std(wait_times_array))
                percentile_90_wait = float(np.percentile(wait_times_array, 90))
                percentile_95_wait = float(np.percentile(wait_times_array, 95))
            else:
                avg_wait_time = max_wait_time = min_wait_time = 0.0
                std_wait_time = percentile_90_wait = percentile_95_wait = 0.0
            
            # Calculate travel time statistics
            avg_travel_time = float(np.mean(travel_times)) if travel_times else 0.0
            
            # Calculate total time statistics
            avg_total_time = float(np.mean(total_times)) if total_times else 0.0
            
            metrics = {
                "total_passengers": total_passengers,
                "arrived_passengers": arrived_passengers,
                "abandoned_passengers": abandoned_passengers,
                "service_rate": service_rate,
                "avg_wait_time": avg_wait_time,
                "avg_travel_time": avg_travel_time,
                "avg_total_time": avg_total_time,
                "max_wait_time": max_wait_time,
                "min_wait_time": min_wait_time,
                "std_wait_time": std_wait_time,
                "percentile_90_wait": percentile_90_wait,
                "percentile_95_wait": percentile_95_wait
            }
            
            logger.info(f"Calculated passenger metrics: service_rate={service_rate:.1f}%")
            return metrics
        
        except Exception as e:
            logger.error(f"Error calculating passenger metrics: {e}", exc_info=True)
            return {}
    
    def calculate_vehicle_metrics(self) -> Dict[str, Dict]:
        """
        Calculate aggregate vehicle performance metrics.
        
        Returns:
            Dictionary with vehicle_id as key:
            {
                "BUS_1": {
                    "total_passengers": int,
                    "avg_occupancy": float,
                    "max_occupancy": int,
                    "occupancy_rate": float,  # avg_occupancy / capacity
                    "total_boardings": int,
                    "total_alightings": int,
                    "stations_served": int,
                    "idle_time": float,  # Time with 0 occupancy
                    "service_time": float  # Time with >0 occupancy
                }
            }
        """
        logger.info("Calculating vehicle metrics...")
        
        try:
            metrics = {}
            
            for vehicle_id, record in self.vehicle_records.items():
                # Extract occupancy data
                occupancy_data = record["occupancy_over_time"]
                
                if occupancy_data:
                    # Calculate time-weighted average occupancy
                    total_weighted_occupancy = 0.0
                    total_time = 0.0
                    idle_time = 0.0
                    service_time = 0.0
                    
                    for i in range(len(occupancy_data) - 1):
                        time1, occ1 = occupancy_data[i]
                        time2, occ2 = occupancy_data[i + 1]
                        duration = time2 - time1
                        total_weighted_occupancy += occ1 * duration
                        total_time += duration
                        
                        # Track idle vs service time
                        if occ1 == 0:
                            idle_time += duration
                        else:
                            service_time += duration
                    
                    avg_occupancy = total_weighted_occupancy / total_time if total_time > 0 else 0.0
                    max_occupancy = max(occ for _, occ in occupancy_data)
                else:
                    avg_occupancy = 0.0
                    max_occupancy = 0
                    idle_time = 0.0
                    service_time = 0.0
                
                # Determine capacity based on vehicle type
                vehicle_type = record.get("vehicle_type", "Bus")
                default_capacity = 6 if vehicle_type == "Minibus" else 80
                occupancy_rate = avg_occupancy / default_capacity if default_capacity > 0 else 0.0
                
                # Count boardings and alightings
                total_boardings = sum(
                    event["count"] for event in record["boarding_events"]
                )
                total_alightings = sum(
                    event["count"] for event in record["alighting_events"]
                )

                metrics[vehicle_id] = {
                    "total_passengers": record["total_passengers_served"],
                    "avg_occupancy": avg_occupancy,
                    "max_occupancy": max_occupancy,
                    "occupancy_rate": occupancy_rate,
                    "total_boardings": total_boardings,
                    "total_alightings": total_alightings,
                    "stations_served": len(record["route"]),
                    "idle_time": idle_time,
                    "service_time": service_time
                }
            
            logger.info(f"Calculated metrics for {len(metrics)} vehicles")
            return metrics
        
        except Exception as e:
            logger.error(f"Error calculating vehicle metrics: {e}", exc_info=True)
            return {}
    
    def calculate_system_metrics(self) -> Dict[str, Any]:
        """
        Calculate overall system performance metrics.
        
        Returns:
            Dictionary containing:
                - simulation_duration: Total duration in seconds
                - total_vehicles: Number of vehicles
                - total_passengers: Total passenger demand
                - system_service_rate: Overall service success rate
                - avg_system_wait_time: System-wide average wait
                - total_passenger_km: Total passenger-kilometers (placeholder)
                - avg_occupancy_all_vehicles: Average across all vehicles
        """
        logger.info("Calculating system-wide metrics...")
        
        try:
            passenger_metrics = self.calculate_passenger_metrics()
            vehicle_metrics = self.calculate_vehicle_metrics()
            
            # Calculate average occupancy across all vehicles
            if vehicle_metrics:
                avg_occupancy_all = np.mean([
                    v["avg_occupancy"] for v in vehicle_metrics.values()
                ])
            else:
                avg_occupancy_all = 0.0
            
            # Count vehicles that actually served passengers
            active_vehicles = sum(
                1 for v in vehicle_metrics.values() if v["total_passengers"] > 0
            )
            
            # Count buses and minibuses separately
            total_buses = sum(1 for v in self.vehicle_records.values() 
                            if v.get("vehicle_type") == "Bus")
            total_minibuses = sum(1 for v in self.vehicle_records.values() 
                                if v.get("vehicle_type") == "Minibus")
            active_buses = sum(1 for vid, v in vehicle_metrics.items() 
                            if self.vehicle_records[vid].get("vehicle_type") == "Bus" 
                            and v["total_passengers"] > 0)
            active_minibuses = sum(1 for vid, v in vehicle_metrics.items() 
                                if self.vehicle_records[vid].get("vehicle_type") == "Minibus" 
                                and v["total_passengers"] > 0)

            system_metrics = {
                "simulation_duration": self.simulation_duration,
                "total_vehicles": len(self.vehicle_records),
                "total_buses": total_buses,
                "total_minibuses": total_minibuses,
                "active_vehicles": active_vehicles,
                "active_buses": active_buses,
                "active_minibuses": active_minibuses,
                "total_passengers": passenger_metrics.get("total_passengers", 0),
                "system_service_rate": passenger_metrics.get("service_rate", 0.0),
                "avg_system_wait_time": passenger_metrics.get("avg_wait_time", 0.0),
                "avg_occupancy_all_vehicles": avg_occupancy_all,
                "total_passenger_km": 0.0  # Placeholder - needs distance data
            }
            
            logger.info(
                f"System metrics calculated: "
                f"{system_metrics['active_vehicles']}/{system_metrics['total_vehicles']} vehicles active"
            )
            return system_metrics
        
        except Exception as e:
            logger.error(f"Error calculating system metrics: {e}", exc_info=True)
            return {}
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate a comprehensive text report of simulation results.
        
        Args:
            output_file: Optional file path to save report. If None, print to console.
        
        Returns:
            String containing the formatted report
        
        Report sections:
            1. Simulation Overview
            2. Passenger Statistics
            3. Vehicle Performance
            4. Data Validation Results
            5. System-wide Metrics
            6. Key Findings and Recommendations
        """
        logger.info("Generating simulation report...")
        
        try:
            # Calculate all metrics
            passenger_metrics = self.calculate_passenger_metrics()
            vehicle_metrics = self.calculate_vehicle_metrics()
            system_metrics = self.calculate_system_metrics()
            
            # Validate data
            validation_issues = self.validate_all_vehicles()
            
            # Build report string
            lines = []
            lines.append("=" * 80)
            lines.append("                    SIMULATION STATISTICS REPORT")
            lines.append("=" * 80)
            lines.append("")
            
            # Section 1: Simulation Overview
            lines.append("SIMULATION OVERVIEW")
            lines.append("-" * 80)
            lines.append(f"Start Time:           {self.simulation_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"End Time:             {self.simulation_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Duration:             {self.simulation_duration/3600:.1f} hours ({self.simulation_duration:.0f} seconds)")
            lines.append(f"Sampling Interval:    {self.sampling_interval}s")
            lines.append(f"Total Vehicles:       {system_metrics.get('total_vehicles', 0)} "
                        f"(Buses: {system_metrics.get('total_buses', 0)}, "
                        f"Minibuses: {system_metrics.get('total_minibuses', 0)})")
            lines.append(f"Total Passengers:     {system_metrics.get('total_passengers', 0)}")
            lines.append("")
            
            # Section 2: Passenger Statistics
            lines.append("PASSENGER STATISTICS")
            lines.append("-" * 80)
            total = passenger_metrics.get("total_passengers", 0)
            arrived = passenger_metrics.get("arrived_passengers", 0)
            abandoned = passenger_metrics.get("abandoned_passengers", 0)
            service_rate = passenger_metrics.get("service_rate", 0.0)
            
            lines.append(f"Service Rate:         {service_rate:.1f}% ({arrived}/{total} passengers arrived)")
            lines.append(f"Abandoned:            {100*abandoned/total if total > 0 else 0:.1f}% ({abandoned}/{total} passengers)")
            lines.append("")
            lines.append("Wait Time Statistics:")
            lines.append(f"  Average:            {passenger_metrics.get('avg_wait_time', 0):.1f} seconds ({passenger_metrics.get('avg_wait_time', 0)/60:.1f} minutes)")
            lines.append(f"  Minimum:            {passenger_metrics.get('min_wait_time', 0):.1f} seconds")
            lines.append(f"  Maximum:            {passenger_metrics.get('max_wait_time', 0):.1f} seconds")
            lines.append(f"  Std Dev:            {passenger_metrics.get('std_wait_time', 0):.1f} seconds")
            lines.append(f"  90th Percentile:    {passenger_metrics.get('percentile_90_wait', 0):.1f} seconds")
            lines.append(f"  95th Percentile:    {passenger_metrics.get('percentile_95_wait', 0):.1f} seconds")
            lines.append("")
            lines.append("Travel Time Statistics:")
            lines.append(f"  Average:            {passenger_metrics.get('avg_travel_time', 0):.1f} seconds ({passenger_metrics.get('avg_travel_time', 0)/60:.1f} minutes)")
            lines.append("")
            lines.append("Total Time Statistics:")
            lines.append(f"  Average:            {passenger_metrics.get('avg_total_time', 0):.1f} seconds ({passenger_metrics.get('avg_total_time', 0)/60:.1f} minutes)")
            lines.append("")
            
            # Section 3: Vehicle Performance
            lines.append("VEHICLE PERFORMANCE")
            lines.append("-" * 80)
            
            # Separate buses and minibuses
            bus_metrics = {k: v for k, v in vehicle_metrics.items() 
                        if self.vehicle_records[k].get("vehicle_type") == "Bus"}
            minibus_metrics = {k: v for k, v in vehicle_metrics.items() 
                            if self.vehicle_records[k].get("vehicle_type") == "Minibus"}

            # Display buses
            if bus_metrics:
                lines.append("BUSES:")
                for vehicle_id in sorted(bus_metrics.keys()):
                    v_metrics = bus_metrics[vehicle_id]
                    lines.append(f"{vehicle_id}:")
                    lines.append(f"  Passengers Served:  {v_metrics['total_passengers']}")
                    lines.append(f"  Avg Occupancy:      {v_metrics['avg_occupancy']:.2f} ({v_metrics['occupancy_rate']*100:.1f}%)")
                    lines.append(f"  Max Occupancy:      {v_metrics['max_occupancy']}")
                    lines.append(f"  Stations Served:    {v_metrics['stations_served']}")
                    lines.append(f"  Idle Time:          {v_metrics['idle_time']:.0f}s ({v_metrics['idle_time']/60:.1f} min)")
                    lines.append(f"  Service Time:       {v_metrics['service_time']:.0f}s ({v_metrics['service_time']/60:.1f} min)")
                    lines.append("")

            # Display minibuses
            if minibus_metrics:
                lines.append("MINIBUSES:")
                for vehicle_id in sorted(minibus_metrics.keys()):
                    v_metrics = minibus_metrics[vehicle_id]
                    lines.append(f"{vehicle_id}:")
                    lines.append(f"  Passengers Served:  {v_metrics['total_passengers']}")
                    lines.append(f"  Avg Occupancy:      {v_metrics['avg_occupancy']:.2f} ({v_metrics['occupancy_rate']*100:.1f}%)")
                    lines.append(f"  Max Occupancy:      {v_metrics['max_occupancy']}")
                    lines.append(f"  Stations Served:    {v_metrics['stations_served']}")
                    lines.append(f"  Idle Time:          {v_metrics['idle_time']:.0f}s ({v_metrics['idle_time']/60:.1f} min)")
                    lines.append(f"  Service Time:       {v_metrics['service_time']:.0f}s ({v_metrics['service_time']/60:.1f} min)")
                    lines.append("")

            # Section 4: Data Validation
            lines.append("DATA VALIDATION")
            lines.append("-" * 80)
            if validation_issues:
                lines.append(f"⚠ Found issues in {len(validation_issues)} vehicle(s):")
                lines.append("")
                for vehicle_id, issues in sorted(validation_issues.items()):
                    lines.append(f"{vehicle_id}:")
                    for issue in issues:
                        lines.append(f"  • {issue}")
                    lines.append("")
            else:
                lines.append("✓ All vehicle data passed validation checks")
                lines.append("")
            
            # Section 5: System-wide Metrics
            lines.append("SYSTEM-WIDE METRICS")
            lines.append("-" * 80)
            lines.append(f"Avg Vehicle Occupancy: {system_metrics.get('avg_occupancy_all_vehicles', 0):.2f} passengers")
            lines.append(f"Vehicle Utilization:   {system_metrics.get('active_vehicles', 0)}/{system_metrics.get('total_vehicles', 0)} vehicles served passengers")
            lines.append(f"  - Buses:             {system_metrics.get('active_buses', 0)}/{system_metrics.get('total_buses', 0)}")
            lines.append(f"  - Minibuses:         {system_metrics.get('active_minibuses', 0)}/{system_metrics.get('total_minibuses', 0)}")
            lines.append("")
            
            # Section 6: Key Findings
            lines.append("KEY FINDINGS")
            lines.append("-" * 80)
            
            # Generate findings based on metrics
            findings = []
            
            if service_rate >= 90:
                findings.append("✓ Excellent service rate (>90%)")
            elif service_rate >= 70:
                findings.append("✓ Good service rate (70-90%)")
            else:
                findings.append("⚠ Low service rate (<70%)")
            
            active_rate = system_metrics.get('active_vehicles', 0) / max(system_metrics.get('total_vehicles', 1), 1)
            if active_rate < 0.5:
                findings.append(f"⚠ Low vehicle utilization (only {system_metrics.get('active_vehicles', 0)} of {system_metrics.get('total_vehicles', 0)} vehicles used)")
            
            if passenger_metrics.get('std_wait_time', 0) > 300:
                findings.append(f"⚠ High wait time variance ({passenger_metrics.get('min_wait_time', 0):.0f}s - {passenger_metrics.get('max_wait_time', 0):.0f}s)")
            
            if passenger_metrics.get('avg_wait_time', 0) > 600:
                findings.append("⚠ High average wait time (>10 minutes)")
            
            if validation_issues:
                findings.append(f"⚠ Data consistency issues detected in {len(validation_issues)} vehicle(s)")
            
            for finding in findings:
                lines.append(finding)
            
            lines.append("")
            lines.append("=" * 80)
            
            # Join all lines
            report = "\n".join(lines)
            
            # Save to file if specified
            if output_file:
                try:
                    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(report)
                    logger.info(f"Report saved to {output_file}")
                except Exception as e:
                    logger.error(f"Error saving report to file: {e}")
            
            # Print to console
            print(report)
            
            return report
        
        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            return ""
    
    def plot_wait_time_distribution(self, output_file: str = "wait_time_dist.png") -> None:
        """
        Create a histogram of passenger wait times.
        
        Args:
            output_file: Path to save the plot
        
        Creates:
            - Histogram with bins
            - Mean line
            - Median line
            - 90th percentile line
        """
        logger.info("Creating wait time distribution plot...")
        
        try:
            # Extract wait times
            wait_times = [
                p["wait_time"] for p in self.passenger_records 
                if p["wait_time"] is not None
            ]
            
            if not wait_times:
                logger.warning("No wait time data available for plotting")
                return
            
            wait_times_array = np.array(wait_times)
            
            # Calculate statistics
            mean_wait = np.mean(wait_times_array)
            median_wait = np.median(wait_times_array)
            p90_wait = np.percentile(wait_times_array, 90)
            
            # Create plot
            plt.figure(figsize=(10, 6))
            
            # Histogram
            n, bins, patches = plt.hist(
                wait_times_array,
                bins=30,
                alpha=0.7,
                color='skyblue',
                edgecolor='black'
            )
            
            # Add statistical lines
            plt.axvline(mean_wait, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_wait:.1f}s')
            plt.axvline(median_wait, color='green', linestyle='--', linewidth=2, label=f'Median: {median_wait:.1f}s')
            plt.axvline(p90_wait, color='orange', linestyle='--', linewidth=2, label=f'90th %ile: {p90_wait:.1f}s')
            
            # Labels and title
            plt.xlabel('Wait Time (seconds)', fontsize=12)
            plt.ylabel('Number of Passengers', fontsize=12)
            plt.title('Passenger Wait Time Distribution', fontsize=14, fontweight='bold')
            plt.legend(fontsize=10)
            plt.grid(axis='y', alpha=0.3)
            
            # Save plot
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Wait time distribution plot saved to {output_file}")
        
        except Exception as e:
            logger.error(f"Error creating wait time plot: {e}", exc_info=True)
    
    def plot_occupancy_over_time(
        self,
        vehicle_id: Optional[str] = None,
        output_file: str = "occupancy_timeline.png"
    ) -> None:
        """
        Plot vehicle occupancy over time.
        
        Args:
            vehicle_id: Specific vehicle to plot. If None, plot all vehicles.
            output_file: Path to save the plot
        
        Creates:
            - Line plot of occupancy vs time
            - Different color for each vehicle
            - Capacity line (if single vehicle)
        """
        logger.info("Creating occupancy timeline plot...")
        
        try:
            plt.figure(figsize=(14, 6))
            
            # Determine which vehicles to plot
            if vehicle_id:
                vehicles_to_plot = {vehicle_id: self.vehicle_records.get(vehicle_id)}
                if vehicles_to_plot[vehicle_id] is None:
                    logger.warning(f"Vehicle {vehicle_id} not found in records")
                    return
            else:
                vehicles_to_plot = self.vehicle_records
            
            for vid, record in vehicles_to_plot.items():
                occupancy_data = record["occupancy_over_time"]
                vehicle_type = record.get("vehicle_type", "Bus")
                
                if occupancy_data:
                    times = [t for t, _ in occupancy_data]
                    occupancies = [o for _, o in occupancy_data]
                    
                    # Use different styles for buses vs minibuses
                    linestyle = '-' if vehicle_type == "Bus" else '--'
                    marker = 'o' if vehicle_type == "Bus" else 's'
                    
                    plt.plot(
                        times,
                        occupancies,
                        marker=marker,
                        markersize=3,
                        label=f"{vid} ({vehicle_type})",
                        linewidth=1.5,
                        linestyle=linestyle
                    )
            
            # Add capacity lines
            if vehicle_id and len(vehicles_to_plot) == 1:
                vehicle_type = list(vehicles_to_plot.values())[0].get("vehicle_type", "Bus")
                capacity = 6 if vehicle_type == "Minibus" else 80
                plt.axhline(y=capacity, color='red', linestyle='--', linewidth=1, 
                           label=f'Capacity ({capacity})')
            
            # Labels and title
            plt.xlabel('Simulation Time (seconds)', fontsize=12)
            plt.ylabel('Occupancy (passengers)', fontsize=12)
            
            if vehicle_id:
                plt.title(f'Occupancy Over Time - {vehicle_id}', fontsize=14, fontweight='bold')
            else:
                plt.title('Occupancy Over Time - All Vehicles', fontsize=14, fontweight='bold')
            
            plt.legend(fontsize=9, loc='best')
            plt.grid(True, alpha=0.3)
            
            # Save plot
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Occupancy timeline plot saved to {output_file}")
        
        except Exception as e:
            logger.error(f"Error creating occupancy plot: {e}", exc_info=True)
    
    def plot_service_rate_by_hour(self, output_file: str = "service_rate_hourly.png") -> None:
        """
        Plot service rate (arrived vs abandoned) by hour of day.
        
        Args:
            output_file: Path to save the plot
        
        Creates:
            - Bar chart showing hourly service rates
            - X-axis: Hour of day
            - Y-axis: Percentage
        """
        logger.info("Creating hourly service rate plot...")
        
        try:
            # Group passengers by hour
            hourly_data = defaultdict(lambda: {"arrived": 0, "abandoned": 0, "total": 0})
            
            for passenger in self.passenger_records:
                # Calculate hour of appearance
                appear_time = passenger["appear_time"]
                hour = int((appear_time / 3600) % 24)
                
                # Add simulation start hour
                start_hour = self.simulation_start_time.hour
                actual_hour = (start_hour + hour) % 24
                
                hourly_data[actual_hour]["total"] += 1
                
                if passenger["status"] == "ARRIVED":
                    hourly_data[actual_hour]["arrived"] += 1
                elif passenger["status"] == "ABANDONED":
                    hourly_data[actual_hour]["abandoned"] += 1
            
            if not hourly_data:
                logger.warning("No passenger data available for hourly service rate plot")
                return
            
            # Calculate service rates
            hours = sorted(hourly_data.keys())
            service_rates = [
                (hourly_data[h]["arrived"] / hourly_data[h]["total"] * 100) if hourly_data[h]["total"] > 0 else 0
                for h in hours
            ]
            
            # Create plot
            plt.figure(figsize=(12, 6))
            
            bars = plt.bar(hours, service_rates, color='steelblue', edgecolor='black', alpha=0.7)
            
            # Color bars based on service rate
            for bar, rate in zip(bars, service_rates):
                if rate >= 90:
                    bar.set_color('green')
                elif rate >= 70:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')
            
            # Labels and title
            plt.xlabel('Hour of Day', fontsize=12)
            plt.ylabel('Service Rate (%)', fontsize=12)
            plt.title('Hourly Service Rate (% Passengers Arrived)', fontsize=14, fontweight='bold')
            plt.xticks(hours)
            plt.ylim(0, 105)
            plt.grid(axis='y', alpha=0.3)
            
            # Add horizontal reference line at 80%
            plt.axhline(y=80, color='gray', linestyle='--', linewidth=1, alpha=0.5)
            
            # Save plot
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Hourly service rate plot saved to {output_file}")
        
        except Exception as e:
            logger.error(f"Error creating hourly service rate plot: {e}", exc_info=True)
    
    def export_to_csv(self, output_dir: str = "results/") -> None:
        """
        Export all statistics to CSV files for further analysis.
        
        Args:
            output_dir: Directory to save CSV files
        
        Creates:
            - passengers.csv: All passenger records
            - vehicles.csv: Vehicle summary statistics
            - vehicle_states.csv: Detailed vehicle state history
            - events.csv: All system events
            - validation.csv: Data validation results
        """
        logger.info("Exporting statistics to CSV files...")
        
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Export passengers.csv
            passengers_file = output_path / "passengers.csv"
            with open(passengers_file, 'w', newline='', encoding='utf-8') as f:
                if self.passenger_records:
                    fieldnames = self.passenger_records[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.passenger_records)
            logger.info(f"Exported {len(self.passenger_records)} passenger records to {passengers_file}")
            
            # Export vehicles.csv
            vehicles_file = output_path / "vehicles.csv"
            vehicle_metrics = self.calculate_vehicle_metrics()
            
            with open(vehicles_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    "vehicle_id", "type", "total_passengers", "avg_occupancy",
                    "max_occupancy", "occupancy_rate", "total_boardings",
                    "total_alightings", "stations_served", "idle_time", "service_time"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for vehicle_id, metrics in vehicle_metrics.items():
                    row = {
                        "vehicle_id": vehicle_id,
                        "type": self.vehicle_records[vehicle_id]["vehicle_type"],
                        **metrics
                    }
                    writer.writerow(row)
            logger.info(f"Exported {len(vehicle_metrics)} vehicle records to {vehicles_file}")
            
            # Export vehicle_states.csv (detailed state history)
            states_file = output_path / "vehicle_states.csv"
            with open(states_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ["vehicle_id", "time", "type", "occupancy", "location", "count"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for vehicle_id, record in self.vehicle_records.items():
                    for state in record.get("state_changes", []):
                        row = {
                            "vehicle_id": vehicle_id,
                            "time": state.get("time"),
                            "type": state.get("type"),
                            "occupancy": state.get("occupancy"),
                            "location": state.get("location") or state.get("station"),
                            "count": state.get("count", "")
                        }
                        writer.writerow(row)
            logger.info(f"Exported detailed vehicle state history to {states_file}")
            
            # Export events.csv
            events_file = output_path / "events.csv"
            with open(events_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ["time", "event_type", "description"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.system_events)
            logger.info(f"Exported {len(self.system_events)} system events to {events_file}")
            
            # Export validation.csv
            validation_file = output_path / "validation.csv"
            validation_issues = self.validate_all_vehicles()
            
            with open(validation_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ["vehicle_id", "issue"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for vehicle_id, issues in validation_issues.items():
                    for issue in issues:
                        writer.writerow({"vehicle_id": vehicle_id, "issue": issue})
            logger.info(f"Exported validation results to {validation_file}")
            
            logger.info(f"All CSV exports completed in directory: {output_dir}")
        
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}", exc_info=True)