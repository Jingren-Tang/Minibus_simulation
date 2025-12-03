"""
simulation/engine.py

Core simulation engine for the mixed traffic simulation system.
Implements discrete event simulation to drive buses and manage passengers.
"""

import heapq
import logging
import csv
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional


import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from simulation.event import Event
from network.station import Station
from network.network import TransitNetwork
from demand.passenger import Passenger
from vehicles.bus import Bus
from demand.od_matrix import ODMatrixManager

# Configure logger
logger = logging.getLogger(__name__)


class SimulationEngine:
    """
    Core simulation engine that drives the entire simulation using discrete event simulation.
    
    Current stage: Only implements bus functionality. Minibus and optimizer will be added in stage 4.
    
    Attributes:
        current_time: Current simulation time in seconds from start
        simulation_start_time: Actual datetime when simulation begins
        simulation_end_time: Actual datetime when simulation ends
        duration: Total simulation duration in seconds
        event_queue: Priority queue of events (using heapq)
        network: Transit network object containing stations and travel times
        buses: Dictionary of all buses {bus_id: Bus object}
        minibuses: Dictionary of all minibuses (stage 4)
        all_passengers: Record of all passengers {passenger_id: Passenger object}
        pending_requests: Pool of unassigned passenger requests
        od_manager: OD matrix manager for passenger generation
        statistics: Statistics collector (stage 6, currently None)
        config: Configuration parameters
    """
    
    def __init__(self, config: dict):
        """
        Initialize the simulation engine.
        
        Args:
            config: Configuration dictionary containing simulation parameters
        """
        logger.info("Initializing SimulationEngine...")
        
        # Save configuration
        self.config = config
        
        # Initialize time tracking
        self.current_time: float = 0.0
        
        # Parse time strings to datetime objects
        sim_date = datetime.strptime(config["simulation_date"], "%Y-%m-%d")
        start_time = datetime.strptime(config["simulation_start_time"], "%H:%M:%S").time()
        end_time = datetime.strptime(config["simulation_end_time"], "%H:%M:%S").time()
        
        self.simulation_start_time = datetime.combine(sim_date, start_time)
        self.simulation_end_time = datetime.combine(sim_date, end_time)
        self.duration = (self.simulation_end_time - self.simulation_start_time).total_seconds()
        
        # Initialize event queue (priority queue using heapq)
        self.event_queue: List[Event] = []
        
        # Initialize network (will be loaded in initialize())
        self.network: Optional[TransitNetwork] = None
        
        # Initialize vehicle containers
        self.buses: Dict[str, Bus] = {}
        self.minibuses: Dict[str, 'Minibus'] = {}  # Stage 4
        
        # Initialize passenger tracking
        self.all_passengers: Dict[str, Passenger] = {}
        self.pending_requests: List[Passenger] = []
        
        # Initialize OD matrix manager (will be loaded in initialize() if needed)
        self.od_manager: Optional[ODMatrixManager] = None
        
        # Statistics collector (stage 6)
        self.statistics = None
        
        logger.info(
            f"SimulationEngine initialized. "
            f"Start: {self.simulation_start_time}, "
            f"End: {self.simulation_end_time}, "
            f"Duration: {self.duration}s"
        )
    
    def initialize(self) -> None:
        """
        Core initialization method. Loads network, creates vehicles, and sets up initial events.
        
        Steps:
            1. Load transit network
            2. Initialize OD matrix manager (if using OD-based passenger generation)
            3. Load and create buses from schedule
            4. Add initial bus arrival events
            5. Generate passengers (based on configured method)
            6. Add simulation end event
        """
        logger.info("Starting simulation initialization...")
        
        # Step 1: Load transit network
        logger.info("Loading transit network...")
        self.network = TransitNetwork(
            stations_file=self.config["stations_file"],
            matrix_path=self.config["travel_time_matrix"],
            metadata_path=self.config["matrix_metadata"]
        )
        logger.info(f"Transit network loaded with {len(self.network.stations)} stations")
        
        # Step 2: Initialize OD matrix manager if using OD-based generation
        passenger_method = self.config.get("passenger_generation_method", "test")
        if passenger_method == "od_matrix":
            logger.info("Initializing OD matrix manager...")
            self.od_manager = ODMatrixManager(
                od_matrix_path=self.config["od_matrix_file"],
                metadata_path=self.config["od_metadata_file"]
            )
            logger.info("OD matrix manager initialized")
        
        # Step 3: Load and create buses
        logger.info("Loading buses from schedule...")
        self.buses = self._load_buses_from_schedule()
        logger.info(f"Loaded {len(self.buses)} buses")
        
        # Step 4: Add initial bus arrival events
        logger.info("Adding initial bus arrival events...")
        for bus_id, bus in self.buses.items():
            if bus.next_arrival_time is not None:
                self.add_event(Event(
                    time=bus.next_arrival_time,
                    event_type=Event.BUS_ARRIVAL,
                    data={"bus_id": bus_id}
                ))
                logger.debug(f"Added initial arrival event for {bus_id} at {bus.next_arrival_time}s")
        
        # Step 5: Generate passengers based on configured method
        logger.info("Generating passengers...")
        self._generate_passengers()
        
        # Step 6: Add simulation end event
        self.add_event(Event(
            time=self.duration,
            event_type=Event.SIMULATION_END,
            data={}
        ))
        logger.info(f"Added simulation end event at {self.duration}s")
        
        # Log initialization summary
        logger.info(
            f"Initialization complete. "
            f"Buses: {len(self.buses)}, "
            f"Test passengers: {len(self.all_passengers)}, "
            f"Initial events: {len(self.event_queue)}"
        )
    
    def _load_buses_from_schedule(self) -> Dict[str, Bus]:
        """
        Load buses from CSV schedule file.
        
        CSV format:
            bus_id,route_name,stop_sequence,station_id,arrival_time
            BUS_1,Route1,0,A,08:00:00
            BUS_1,Route1,1,B,08:05:00
            ...
        
        Returns:
            Dictionary of buses {bus_id: Bus object}
        
        Raises:
            FileNotFoundError: If schedule file doesn't exist
            ValueError: If CSV format is invalid
        """
        buses = {}
        bus_schedules = {}  # Temporary storage: {bus_id: [(station_id, arrival_time_seconds), ...]}
        
        try:
            with open(self.config["bus_schedule_file"], 'r') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    bus_id = row["bus_id"]
                    station_id = row["station_id"]
                    arrival_time_str = row["arrival_time"]
                    stop_sequence = int(row["stop_sequence"])
                    route_name = row["route_name"]
                    
                    # Convert time string to seconds from simulation start
                    arrival_time_seconds = self._time_str_to_seconds(arrival_time_str)
                    
                    # Build schedule for each bus
                    if bus_id not in bus_schedules:
                        bus_schedules[bus_id] = {
                            "route": route_name,
                            "stops": []
                        }
                    
                    bus_schedules[bus_id]["stops"].append({
                        "sequence": stop_sequence,
                        "station_id": station_id,
                        "arrival_time": arrival_time_seconds
                    })
            
            # Sort stops by sequence and create Bus objects
            for bus_id, schedule_data in bus_schedules.items():
                # Sort stops by sequence
                schedule_data["stops"].sort(key=lambda x: x["sequence"])
                
                # Extract route and schedule
                route = [stop["station_id"] for stop in schedule_data["stops"]]
                schedule_dict = {stop["station_id"]: stop["arrival_time"] for stop in schedule_data["stops"]}
                
                # Create Bus object (note: Bus.__init__ expects route and schedule as Dict)
                bus = Bus(
                    bus_id=bus_id,
                    route=route,
                    schedule=schedule_dict,
                    capacity=self.config.get("bus_capacity", 50)
                )
                
                buses[bus_id] = bus
                logger.debug(
                    f"Created bus {bus_id} with route {schedule_data['route']}, "
                    f"{len(route)} stops, first departure at {schedule_dict[route[0]]}s"
                )
            
            logger.info(f"Successfully loaded {len(buses)} buses from schedule file")
            return buses
            
        except FileNotFoundError:
            logger.error(f"Bus schedule file not found: {self.config['bus_schedule_file']}")
            raise
        except KeyError as e:
            logger.error(f"Missing required column in bus schedule CSV: {e}")
            raise ValueError(f"Invalid CSV format: missing column {e}")
        except Exception as e:
            logger.error(f"Error loading bus schedule: {e}")
            raise
    
    def _generate_passengers(self) -> None:
        """
        Generate passengers based on the configured method.
        
        Methods:
            - "od_matrix": Generate from OD matrix using Poisson process
            - "test": Generate hardcoded test passengers
            - "file": Load from file (future)
        """
        method = self.config.get("passenger_generation_method", "test")
        
        logger.info(f"Using passenger generation method: {method}")
        
        if method == "od_matrix" and self.od_manager is not None:
            self._generate_passengers_from_od_matrix()
        elif method == "test":
            self._generate_hardcoded_test_passengers()
        else:
            logger.warning(f"Unknown or unsupported passenger generation method: {method}")
            logger.warning("Falling back to hardcoded test passengers")
            self._generate_hardcoded_test_passengers()
    
    def _generate_passengers_from_od_matrix(self) -> None:
        """
        Generate passengers for the entire simulation period using OD matrix.
        
        Uses Poisson sampling to generate realistic passenger arrival patterns
        based on the demand specified in the OD matrix.
        """
        logger.info("Generating passengers from OD matrix...")
        
        # Use random state for reproducibility
        random_seed = self.config.get("random_seed", 42)
        random_state = np.random.RandomState(random_seed)
        logger.info(f"Using random seed: {random_seed}")
        
        # Generate passengers for each time slot
        n_time_slots = self.od_manager.n_time_slots
        slot_duration = self.od_manager.time_slot_duration
        total_passengers = 0
        
        for slot_idx in range(n_time_slots):
            slot_start_time = slot_idx * slot_duration
            
            # Check if slot is within simulation period
            if slot_start_time >= self.duration:
                logger.info(f"Stopping passenger generation at time slot {slot_idx} (exceeds simulation duration)")
                break
            
            # Generate passengers for this slot
            passengers = self.od_manager.generate_passengers_for_slot(
                time_slot_start=slot_start_time,
                random_state=random_state
            )
            
            # Create passenger objects and events
            for origin_id, dest_id, appear_time in passengers:
                # Check if appear_time is within simulation period
                if appear_time >= self.duration:
                    continue
                
                passenger_id = f"P{total_passengers + 1}"
                
                # Create Passenger object
                passenger = Passenger(
                    passenger_id=passenger_id,
                    origin=origin_id,
                    destination=dest_id,
                    appear_time=appear_time,
                    max_wait_time=self.config.get("passenger_max_wait_time", 900.0)
                )
                
                # Add to tracking
                self.all_passengers[passenger_id] = passenger
                
                # Create appearance event
                event = Event(
                    time=appear_time,
                    event_type=Event.PASSENGER_APPEAR,
                    data={
                        "id": passenger_id,
                        "origin": origin_id,
                        "dest": dest_id,
                        "passenger": passenger
                    }
                )
                self.add_event(event)
                total_passengers += 1
            
            # Log progress every 10 time slots
            if (slot_idx + 1) % 10 == 0:
                logger.info(
                    f"Generated passengers for time slot {slot_idx + 1}/{n_time_slots}, "
                    f"total passengers so far: {total_passengers}"
                )
        
        logger.info(f"Successfully generated {total_passengers} passengers from OD matrix")
    
    def _generate_hardcoded_test_passengers(self) -> None:
        """
        Generate hardcoded test passengers (original method).
        Uses real station IDs from the loaded network.
        """
        logger.info("Generating hardcoded test passengers...")
        
        # Get real station IDs from the network
        station_ids = list(self.network.stations.keys())
        
        if len(station_ids) < 5:
            logger.warning(f"Not enough stations ({len(station_ids)}) to create test passengers")
            return
        
        # Create test passengers using real station IDs
        test_passengers_data = [
            {"id": "P1", "origin": station_ids[0], "dest": station_ids[2], "appear_time": 0.0},
            {"id": "P2", "origin": station_ids[0], "dest": station_ids[3], "appear_time": 0.0},
            {"id": "P3", "origin": station_ids[1], "dest": station_ids[3], "appear_time": 150.0},
            {"id": "P4", "origin": station_ids[4], "dest": station_ids[2], "appear_time": 250.0},
            {"id": "P5", "origin": station_ids[0], "dest": station_ids[4], "appear_time": 580.0},
            {"id": "P6", "origin": station_ids[2], "dest": station_ids[4], "appear_time": 590.0},
            {"id": "P7", "origin": station_ids[4], "dest": station_ids[1], "appear_time": 250.0},
        ]
        
        for pax_data in test_passengers_data:
            # Create Passenger object
            passenger = Passenger(
                passenger_id=pax_data["id"],
                origin=pax_data["origin"],
                destination=pax_data["dest"],
                appear_time=pax_data["appear_time"],
                max_wait_time=self.config.get("passenger_max_wait_time", 900.0)
            )
            
            # Add to tracking
            self.all_passengers[pax_data["id"]] = passenger
            
            # Add passenger appear event
            self.add_event(Event(
                time=pax_data["appear_time"],
                event_type=Event.PASSENGER_APPEAR,
                data=pax_data
            ))
            
            logger.debug(
                f"Added test passenger {pax_data['id']}: "
                f"{pax_data['origin']} -> {pax_data['dest']} at {pax_data['appear_time']}s"
            )
        
        logger.info(f"Added {len(test_passengers_data)} hardcoded test passengers")
    
    def add_event(self, event: Event) -> None:
        """
        Add an event to the priority queue.
        
        Args:
            event: Event object to add
        """
        heapq.heappush(self.event_queue, event)
        logger.debug(f"Event added: {event.event_type} at {event.time}s")
    
    def run(self) -> None:
        """
        Main simulation loop. Processes events in chronological order until queue is empty.
        
        The loop:
            1. Pop earliest event from queue
            2. Advance simulation time
            3. Process the event
            4. Log progress periodically
        """
        logger.info("=" * 60)
        logger.info("STARTING SIMULATION")
        logger.info("=" * 60)
        
        event_count = 0
        
        try:
            while self.event_queue:
                # Pop earliest event
                event = heapq.heappop(self.event_queue)
                
                # Advance simulation time
                self.current_time = event.time
                
                # Process the event
                self.process_event(event)
                
                # Check for passenger timeouts after each event
                self.check_passenger_timeouts()
                
                event_count += 1
                
                # Log progress every 100 events
                if event_count % 100 == 0:
                    time_str = self._seconds_to_time_str(self.current_time)
                    logger.info(
                        f"Progress: Processed {event_count} events, "
                        f"simulation time = {self.current_time:.1f}s ({time_str})"
                    )
            
            logger.info("=" * 60)
            logger.info(f"SIMULATION COMPLETED - Processed {event_count} total events")
            logger.info("=" * 60)
            
            # Finalize simulation
            self.finalize()
            
        except Exception as e:
            logger.error(f"Error during simulation: {e}", exc_info=True)
            raise
    
    def process_event(self, event: Event) -> None:
        """
        Event dispatcher. Routes events to appropriate handlers based on event type.
        
        Args:
            event: Event to process
        """
        logger.debug(
            f"Processing event: {event.event_type} at {self.current_time}s "
            f"(priority={event.priority})"
        )
        
        try:
            if event.event_type == Event.BUS_ARRIVAL:
                self.handle_bus_arrival(event)
            elif event.event_type == Event.PASSENGER_APPEAR:
                self.handle_passenger_appear(event)
            elif event.event_type == Event.SIMULATION_END:
                self.handle_simulation_end(event)
            # MINIBUS_ARRIVAL and OPTIMIZE_CALL will be added in stage 4
            # elif event.event_type == Event.MINIBUS_ARRIVAL:
            #     self.handle_minibus_arrival(event)
            # elif event.event_type == Event.OPTIMIZE_CALL:
            #     self.handle_optimize_call(event)
            else:
                logger.warning(f"Unknown event type: {event.event_type}")
        
        except Exception as e:
            logger.error(
                f"Error processing event {event.event_type} at {self.current_time}s: {e}",
                exc_info=True
            )
            # Continue simulation despite error
    
    def handle_bus_arrival(self, event: Event) -> None:
        """
        Handle bus arrival at a station.
        
        Steps:
            1. Get bus and station objects
            2. Call bus.arrive_at_station()
            3. Process boarding and alighting
            4. Update station waiting passengers
            5. Schedule next arrival event or log completion
        
        Args:
            event: Bus arrival event containing bus_id
        """
        bus_id = event.data["bus_id"]
        
        try:
            # Get bus object
            bus = self.buses.get(bus_id)
            if bus is None:
                logger.error(f"Bus {bus_id} not found in buses dictionary")
                return
            
            # Get current station
            station = self.network.get_station(bus.next_station_id)
            if station is None:
                logger.error(f"Station {bus.next_station_id} not found in network")
                return
            
            logger.info(
                f"Bus {bus_id} arriving at station {station.station_id} "
                f"at {self._seconds_to_time_str(self.current_time)}"
            )
            
            # Process arrival (handles boarding and alighting)
            # Bus.arrive_at_station() returns a dictionary with keys: boarded, alighted, rejected
            result = bus.arrive_at_station(station, self.current_time)
            
            boarded = result["boarded"]
            alighted = result["alighted"]
            rejected = result["rejected"]
            
            # Note: Station.remove_waiting_passenger() is already called in bus.arrive_at_station()
            # So we only need to remove from pending_requests
            for passenger in boarded:
                # Remove from pending requests if present
                if passenger in self.pending_requests:
                    self.pending_requests.remove(passenger)
            
            # Log boarding and alighting summary
            logger.info(
                f"Bus {bus_id} at {station.station_id}: "
                f"{len(boarded)} boarded, {len(alighted)} alighted, "
                f"{len(rejected)} rejected, "
                f"occupancy: {len(bus.passengers)}/{bus.capacity}"
            )
            
            # Schedule next arrival if bus has more stops
            if bus.next_arrival_time is not None:
                self.add_event(Event(
                    time=bus.next_arrival_time,
                    event_type=Event.BUS_ARRIVAL,
                    data={"bus_id": bus_id}
                ))
                logger.debug(
                    f"Scheduled next arrival for {bus_id} at station "
                    f"{bus.next_station_id} at {bus.next_arrival_time}s"
                )
            else:
                logger.info(f"Bus {bus_id} completed its route")
        
        except Exception as e:
            logger.error(f"Error handling bus arrival for {bus_id}: {e}", exc_info=True)
    
    def handle_passenger_appear(self, event: Event) -> None:
        """
        Handle passenger appearance in the system.
        
        Steps:
            1. Get or create Passenger object
            2. Add to pending_requests list (if not already added)
            3. Add to origin station's waiting list
        
        Args:
            event: Passenger appear event containing passenger data
        """
        try:
            # Get passenger object (may already exist from _generate_passengers_from_od_matrix)
            if "passenger" in event.data:
                passenger = event.data["passenger"]
            else:
                # Create new passenger (for test passengers)
                pax_id = event.data["id"]
                origin = event.data["origin"]
                destination = event.data["dest"]
                
                passenger = Passenger(
                    passenger_id=pax_id,
                    origin=origin,
                    destination=destination,
                    appear_time=self.current_time,
                    max_wait_time=self.config.get("passenger_max_wait_time", 900.0)
                )
                
                # Add to tracking structures
                self.all_passengers[pax_id] = passenger
            
            # Add to pending requests
            if passenger not in self.pending_requests:
                self.pending_requests.append(passenger)
            
            # Add to origin station's waiting list
            station = self.network.get_station(passenger.origin_station_id)
            if station is None:
                logger.error(
                    f"Origin station {passenger.origin_station_id} not found for "
                    f"passenger {passenger.passenger_id}"
                )
                return
            
            station.add_waiting_passenger(passenger)
            
            logger.info(
                f"Passenger {passenger.passenger_id} appeared at station {passenger.origin_station_id}, "
                f"destination {passenger.destination_station_id}, "
                f"time {self._seconds_to_time_str(self.current_time)}"
            )
            logger.debug(
                f"Total passengers: {len(self.all_passengers)}, "
                f"Pending: {len(self.pending_requests)}"
            )
        
        except Exception as e:
            logger.error(f"Error handling passenger appear: {e}", exc_info=True)
    
    def handle_simulation_end(self, event: Event) -> None:
        """
        Handle simulation end event.
        
        Args:
            event: Simulation end event
        """
        logger.info("=" * 60)
        logger.info("SIMULATION END EVENT REACHED")
        logger.info("=" * 60)
        
        # Clear remaining events (simulation is over)
        self.event_queue.clear()
    
    def check_passenger_timeouts(self) -> None:
        """
        Check all waiting passengers for timeouts.
        
        Passengers who have exceeded their max wait time are marked as ABANDONED.
        This should be called periodically or after each event.
        """
        abandoned_passengers = []
        
        for passenger in self.pending_requests[:]:  # Use slice to avoid modification during iteration
            if passenger.status == Passenger.WAITING:
                # Check if passenger has timed out
                if passenger.check_timeout(self.current_time):
                    passenger.abandon(self.current_time)
                    abandoned_passengers.append(passenger)
                    self.pending_requests.remove(passenger)
                    
                    # Remove from station waiting list
                    station = self.network.get_station(passenger.origin_station_id)
                    if station:
                        station.remove_waiting_passenger(passenger)
        
        if abandoned_passengers:
            logger.warning(
                f"{len(abandoned_passengers)} passengers abandoned due to timeout at "
                f"{self._seconds_to_time_str(self.current_time)}"
            )
            for pax in abandoned_passengers:
                logger.debug(
                    f"Passenger {pax.passenger_id} abandoned: "
                    f"waited {self.current_time - pax.appear_time:.1f}s"
                )
   
    def finalize(self) -> None:
        """
        Clean up and generate final reports after simulation completes.
        
        Steps:
            1. Check remaining pending requests
            2. Print summary statistics
            3. Generate detailed report if statistics collector exists
        """
        logger.info("=" * 60)
        logger.info("FINALIZING SIMULATION")
        logger.info("=" * 60)
        
        # Count passenger states
        total_passengers = len(self.all_passengers)
        arrived = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ARRIVED)
        abandoned = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ABANDONED)
        waiting = sum(1 for p in self.all_passengers.values() if p.status == Passenger.WAITING)
        onboard = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ONBOARD)
        
        # Print summary statistics
        logger.info("SIMULATION SUMMARY:")
        logger.info(f"  Total passengers: {total_passengers}")
        logger.info(f"  Arrived: {arrived} ({100*arrived/total_passengers if total_passengers > 0 else 0:.1f}%)")
        logger.info(f"  Abandoned: {abandoned} ({100*abandoned/total_passengers if total_passengers > 0 else 0:.1f}%)")
        logger.info(f"  Still waiting: {waiting}")
        logger.info(f"  Still onboard: {onboard}")
        logger.info(f"  Pending requests: {len(self.pending_requests)}")
        
        # Bus summary
        logger.info(f"  Total buses: {len(self.buses)}")
        for bus_id, bus in self.buses.items():
            logger.info(
                f"    {bus_id}: served {bus.total_passengers_served} passengers, "
                f"current occupancy: {len(bus.passengers)}/{bus.capacity}"
            )
        
        # Generate detailed report if statistics collector exists (stage 6)
        if self.statistics is not None:
            logger.info("Generating detailed statistics report...")
            self.statistics.generate_report()
        
        logger.info("=" * 60)
        logger.info("FINALIZATION COMPLETE")
        logger.info("=" * 60)
    
    def _time_str_to_seconds(self, time_str: str) -> float:
        """
        Convert time string (HH:MM:SS) to seconds from simulation start.
        
        Args:
            time_str: Time string in format "HH:MM:SS"
        
        Returns:
            Seconds from simulation start
        
        Examples:
            "08:00:00" -> 0.0 (if simulation starts at 08:00:00)
            "08:05:30" -> 330.0
        """
        try:
            # Parse time string
            time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
            
            # Combine with simulation date
            full_datetime = datetime.combine(self.simulation_start_time.date(), time_obj)
            
            # Calculate seconds from simulation start
            delta = full_datetime - self.simulation_start_time
            seconds = delta.total_seconds()
            
            return seconds
        
        except ValueError as e:
            logger.error(f"Invalid time string format: {time_str}. Expected HH:MM:SS")
            raise
    
    def _seconds_to_time_str(self, seconds: float) -> str:
        """
        Convert seconds from simulation start to time string (HH:MM:SS).
        
        Args:
            seconds: Seconds from simulation start
        
        Returns:
            Time string in format "HH:MM:SS"
        
        Examples:
            0.0 -> "08:00:00" (if simulation starts at 08:00:00)
            330.0 -> "08:05:30"
        """
        try:
            # Calculate actual datetime
            actual_time = self.simulation_start_time + timedelta(seconds=seconds)
            
            # Format as time string
            return actual_time.strftime("%H:%M:%S")
        
        except Exception as e:
            logger.error(f"Error converting seconds to time string: {e}")
            return f"{seconds:.1f}s"