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
from utils.statistics import Statistics

from vehicles.minibus import Minibus  
from optimizer.route_optimizer import RouteOptimizer  

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
        statistics: Statistics collector for performance metrics
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
        
        # Initialize Statistics collector
        self.statistics = Statistics(
            simulation_start_time=self.simulation_start_time,
            simulation_end_time=self.simulation_end_time
        )
        logger.info("Statistics collector initialized")

        self.route_optimizer: Optional[RouteOptimizer] = None # Stage 4
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
        
        # Step 3.5: Load and create minibuses (stage 4)
        if self.config.get("enable_minibus", False):
            logger.info("Loading minibuses...")
            self.minibuses = self._load_minibuses_from_config()
            logger.info(f"Loaded {len(self.minibuses)} minibuses")
            
            # Initialize route optimizer
            logger.info("Initializing route optimizer...")
            optimizer_type = self.config.get("optimizer_type", "dummy")
            optimizer_config = self.config.get("optimizer_config", {})
            self.route_optimizer = RouteOptimizer(
                optimizer_type=optimizer_type,
                config=optimizer_config
            )
            logger.info(f"Route optimizer initialized: type={optimizer_type}")

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

        # Step 4.5: Add initial minibus events (stage 4)
        if self.config.get("enable_minibus", False):
            logger.info("Adding initial minibus events...")
            for minibus_id, minibus in self.minibuses.items():
                if minibus.next_arrival_time is not None:
                    self.add_event(Event(
                        time=minibus.next_arrival_time,
                        event_type=Event.MINIBUS_ARRIVAL,
                        data={"minibus_id": minibus_id}
                    ))
            
            # Add first optimizer call event
            optimizer_interval = self.config.get("optimization_interval", 30.0)
            self.add_event(Event(
                time=optimizer_interval,
                event_type=Event.OPTIMIZE_CALL,
                data={}
            ))
            logger.info(f"Scheduled first optimizer call at {optimizer_interval}s")


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
        
        # Record simulation start event
        self.statistics.record_system_event(
            event_type="SIMULATION_START",
            description=f"Simulation initialized: {len(self.all_passengers)} passengers, {len(self.buses)} buses",
            current_time=0.0
        )
        
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
            elif event.event_type == Event.MINIBUS_ARRIVAL:
                self.handle_minibus_arrival(event)
            elif event.event_type == Event.OPTIMIZE_CALL:
                self.handle_optimize_call(event)
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
            4. Record statistics for vehicle events
            5. Update station waiting passengers
            6. Schedule next arrival event or log completion
        
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
            
            # Record statistics - ARRIVAL event
            self.statistics.record_vehicle_event(
                vehicle_id=bus_id,
                event_type="ARRIVAL",
                event_data={
                    "station": station.station_id,
                    "occupancy": len(bus.passengers)
                },
                current_time=self.current_time
            )
            
            # Record statistics - BOARDING event
            if len(boarded) > 0:
                self.statistics.record_vehicle_event(
                    vehicle_id=bus_id,
                    event_type="BOARDING",
                    event_data={
                        "station": station.station_id,
                        "count": len(boarded),
                        "occupancy": len(bus.passengers)
                    },
                    current_time=self.current_time
                )
            
            # Record statistics - ALIGHTING event
            if len(alighted) > 0:
                self.statistics.record_vehicle_event(
                    vehicle_id=bus_id,
                    event_type="ALIGHTING",
                    event_data={
                        "station": station.station_id,
                        "count": len(alighted),
                        "occupancy": len(bus.passengers)
                    },
                    current_time=self.current_time
                )
            
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
                
                # Record bus route completion event
                self.statistics.record_system_event(
                    event_type="BUS_ROUTE_COMPLETED",
                    description=f"{bus_id} completed route, served {bus.total_passengers_served} passengers",
                    current_time=self.current_time
                )
        
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
        
        # Record simulation end event
        arrived = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ARRIVED)
        abandoned = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ABANDONED)
        
        self.statistics.record_system_event(
            event_type="SIMULATION_END",
            description=f"Simulation completed: {arrived} arrived, {abandoned} abandoned out of {len(self.all_passengers)} total passengers",
            current_time=self.current_time
        )
        
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
            
            # Record passenger abandonment event
            self.statistics.record_system_event(
                event_type="PASSENGERS_ABANDONED",
                description=f"{len(abandoned_passengers)} passengers abandoned due to timeout",
                current_time=self.current_time
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
            1. Record all passenger data to statistics
            2. Print summary statistics
            3. Generate detailed report and visualizations
            4. Export data to CSV files
            5. Create HTML dashboard
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

        # Minibus summary (stage 4)
        if len(self.minibuses) > 0:
            logger.info(f"  Total minibuses: {len(self.minibuses)}")
            for minibus_id, minibus in self.minibuses.items():
                logger.info(
                    f"    {minibus_id}: served {minibus.total_passengers_served} passengers, "
                    f"current occupancy: {minibus.get_occupancy()}/{minibus.capacity}"
                )
            
        # Generate detailed statistics report
        if self.statistics is not None:
            logger.info("Recording passenger data to statistics...")
            
            # Record all passenger data
            for passenger in self.all_passengers.values():
                self.statistics.record_passenger(passenger)
            
            logger.info("Generating detailed statistics report and visualizations...")
            
            # Get output directory from config
            output_dir = self.config.get("output_dir", "results")
            
            # Generate text report
            logger.info("Generating text report...")
            self.statistics.generate_report(
                output_file=f"{output_dir}/simulation_report.txt"
            )
            
            # Generate visualizations
            logger.info("Generating wait time distribution plot...")
            self.statistics.plot_wait_time_distribution(
                output_file=f"{output_dir}/wait_time_dist.png"
            )
            
            logger.info("Generating occupancy timeline plot...")
            self.statistics.plot_occupancy_over_time(
                output_file=f"{output_dir}/occupancy_timeline.png"
            )
            
            logger.info("Generating hourly service rate plot...")
            self.statistics.plot_service_rate_by_hour(
                output_file=f"{output_dir}/service_rate_hourly.png"
            )

            if len(self.minibuses) > 0:
                logger.info("Generating minibus comparison plot...")
                self.statistics.plot_minibus_vs_bus_comparison(
                    output_file=f"{output_dir}/vehicle_comparison.png"
                )
            
            # Export CSV data
            logger.info("Exporting data to CSV files...")
            self.statistics.export_to_csv(output_dir=f"{output_dir}/")
            
            
            logger.info(f"All statistics outputs saved to {output_dir}/")
        
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
            
    def _load_minibuses_from_config(self) -> Dict[str, 'Minibus']:
        """
        Load and create minibuses from configuration.
        
        Reads minibus fleet configuration and creates Minibus objects with
        initial locations either specified or randomly assigned.
        
        Configuration format:
            {
                "num_minibuses": int,
                "minibus_capacity": int,
                "minibus_initial_locations": List[str] or "random"
            }
        
        Returns:
            Dictionary of minibuses {minibus_id: Minibus object}
            
        Raises:
            ValueError: If configuration is invalid or inconsistent
        """
        logger.info("Loading minibuses from configuration...")
        
        minibuses = {}
        
        try:
            # Get minibus count from config
            num_minibuses = self.config.get("num_minibuses", 0)
            
            if num_minibuses <= 0:
                logger.warning("num_minibuses is 0 or not set, no minibuses will be created")
                return minibuses
            
            # Get capacity
            capacity = self.config.get("minibus_capacity", 6)
            if capacity <= 0:
                raise ValueError(f"minibus_capacity must be positive, got {capacity}")
            
            # Get initial locations
            initial_locations = self.config.get("minibus_initial_locations", "random")
            
            # Prepare location assignment
            if isinstance(initial_locations, list):
                # User provided explicit locations
                if len(initial_locations) != num_minibuses:
                    logger.warning(
                        f"Number of initial locations ({len(initial_locations)}) "
                        f"does not match num_minibuses ({num_minibuses}). "
                        f"Will use locations cyclically or randomly fill."
                    )
                locations = initial_locations
            elif initial_locations == "random":
                # Random assignment from available stations
                logger.info("Using random initial locations for minibuses")
                locations = None  # Will assign randomly below
            else:
                raise ValueError(
                    f"minibus_initial_locations must be a list or 'random', "
                    f"got {type(initial_locations)}"
                )
            
            # Get available stations for random assignment
            available_stations = list(self.network.stations.keys())
            if len(available_stations) == 0:
                raise ValueError("Network has no stations, cannot create minibuses")
            
            # Create random state for reproducible random locations
            random_seed = self.config.get("random_seed", 42)
            random_state = np.random.RandomState(random_seed)
            
            # Create minibuses
            for i in range(num_minibuses):
                minibus_id = f"MINIBUS_{i + 1}"
                
                # Determine initial location for this minibus
                if locations is not None:
                    # Use provided locations (cyclically if not enough)
                    initial_location = locations[i % len(locations)]
                    
                    # Validate that the location exists in network
                    if initial_location not in self.network.stations:
                        logger.warning(
                            f"Initial location {initial_location} for {minibus_id} "
                            f"not found in network, using random station instead"
                        )
                        initial_location = random_state.choice(available_stations)
                else:
                    # Random assignment
                    initial_location = random_state.choice(available_stations)
                
                # Create Minibus object
                minibus = Minibus(
                    minibus_id=minibus_id,
                    capacity=capacity,
                    initial_location=initial_location,
                    network=self.network
                )
                
                minibuses[minibus_id] = minibus
                
                logger.debug(
                    f"Created {minibus_id} with capacity={capacity} "
                    f"at initial location={initial_location}"
                )
            
            logger.info(
                f"Successfully created {len(minibuses)} minibuses "
                f"(capacity={capacity} each)"
            )
            
            return minibuses
        
        except KeyError as e:
            logger.error(f"Missing required configuration key: {e}")
            raise ValueError(f"Invalid minibus configuration: missing key {e}")
        
        except Exception as e:
            logger.error(f"Error loading minibuses from config: {e}", exc_info=True)
            raise


    def handle_minibus_arrival(self, event: Event) -> None:
        """
        Handle minibus arrival at a station.
        
        This method processes a minibus arriving at a station, executes the
        planned action (PICKUP or DROPOFF), updates passenger states, records
        statistics, and schedules the next arrival event if applicable.
        
        Steps:
            1. Get minibus and station objects
            2. Call minibus.arrive_at_station()
            3. Process boarding and alighting passengers
            4. Record statistics for vehicle events
            5. Update pending_requests list
            6. Schedule next arrival event or mark minibus as idle
        
        Args:
            event: Minibus arrival event containing minibus_id
        """
        minibus_id = event.data["minibus_id"]
        
        try:
            # Get minibus object
            minibus = self.minibuses.get(minibus_id)
            if minibus is None:
                logger.error(f"Minibus {minibus_id} not found in minibuses dictionary")
                return
            
            # Get current station
            station = self.network.get_station(minibus.next_station_id)
            if station is None:
                logger.error(
                    f"Station {minibus.next_station_id} not found in network "
                    f"for minibus {minibus_id}"
                )
                return
            
            logger.info(
                f"Minibus {minibus_id} arriving at station {station.station_id} "
                f"at {self._seconds_to_time_str(self.current_time)}"
            )
            
            # Process arrival (handles boarding and alighting)
            # Minibus.arrive_at_station() returns a dictionary with keys:
            # boarded, alighted, action_type
            result = minibus.arrive_at_station(station, self.current_time)
            
            boarded = result["boarded"]
            alighted = result["alighted"]
            action_type = result["action_type"]
            
            # Record statistics - ARRIVAL event
            self.statistics.record_vehicle_event(
                vehicle_id=minibus_id,
                event_type="ARRIVAL",
                event_data={
                    "station": station.station_id,
                    "occupancy": minibus.get_occupancy(),
                    "action": action_type
                },
                current_time=self.current_time
            )
            
            # Record statistics - BOARDING event
            if len(boarded) > 0:
                self.statistics.record_vehicle_event(
                    vehicle_id=minibus_id,
                    event_type="BOARDING",
                    event_data={
                        "station": station.station_id,
                        "count": len(boarded),
                        "occupancy": minibus.get_occupancy(),
                        "passenger_ids": [p.passenger_id for p in boarded]
                    },
                    current_time=self.current_time
                )
                
                # Remove boarded passengers from pending_requests
                for passenger in boarded:
                    if passenger in self.pending_requests:
                        self.pending_requests.remove(passenger)
                        logger.debug(
                            f"Removed passenger {passenger.passenger_id} "
                            f"from pending_requests"
                        )
            
            # Record statistics - ALIGHTING event
            if len(alighted) > 0:
                self.statistics.record_vehicle_event(
                    vehicle_id=minibus_id,
                    event_type="ALIGHTING",
                    event_data={
                        "station": station.station_id,
                        "count": len(alighted),
                        "occupancy": minibus.get_occupancy(),
                        "passenger_ids": [p.passenger_id for p in alighted]
                    },
                    current_time=self.current_time
                )
            
            # Log boarding and alighting summary
            logger.info(
                f"Minibus {minibus_id} at {station.station_id}: "
                f"action={action_type}, "
                f"{len(boarded)} boarded, {len(alighted)} alighted, "
                f"occupancy: {minibus.get_occupancy()}/{minibus.capacity}"
            )
            
            # Schedule next arrival if minibus has more stops
            if minibus.next_arrival_time is not None:
                self.add_event(Event(
                    time=minibus.next_arrival_time,
                    event_type=Event.MINIBUS_ARRIVAL,
                    data={"minibus_id": minibus_id}
                ))
                logger.debug(
                    f"Scheduled next arrival for {minibus_id} at station "
                    f"{minibus.next_station_id} at {minibus.next_arrival_time}s "
                    f"({self._seconds_to_time_str(minibus.next_arrival_time)})"
                )
            else:
                logger.info(
                    f"Minibus {minibus_id} completed current route plan, now IDLE"
                )
                
                # Record minibus idle event
                self.statistics.record_system_event(
                    event_type="MINIBUS_IDLE",
                    description=f"{minibus_id} completed route plan at {station.station_id}",
                    current_time=self.current_time
                )
        
        except Exception as e:
            logger.error(
                f"Error handling minibus arrival for {minibus_id}: {e}", 
                exc_info=True
            )

    def handle_optimize_call(self, event: Event) -> None:
        """ß
        Handle periodic optimizer call event.
        
        This method is triggered at regular intervals to invoke the route optimizer,
        which generates new route plans for all minibuses based on current system
        state and pending passenger requests.
        
        Steps:
            1. Check if minibus system is enabled
            2. Prepare current minibus states
            3. Call route optimizer
            4. Apply new route plans to minibuses
            5. Mark assigned passengers to prevent buses from picking them up
            6. Schedule arrival events for minibuses with new routes
            7. Schedule next optimizer call
            8. Record statistics
        
        Args:
            event: Optimize call event (typically contains no data)
        """
        try:
            # Check if minibus is enabled
            if not self.config.get("enable_minibus", False):
                logger.warning(
                    "OPTIMIZE_CALL event received but minibus is not enabled, ignoring"
                )
                return
            
            # Check if optimizer exists
            if self.route_optimizer is None:
                logger.error(
                    "OPTIMIZE_CALL event received but route_optimizer is None, "
                    "cannot proceed"
                )
                return
            
            logger.info(
                f"Optimizer call triggered at {self._seconds_to_time_str(self.current_time)}"
            )
            logger.info(
                f"System state: {len(self.pending_requests)} pending requests, "
                f"{len(self.minibuses)} minibuses"
            )
            
            # Prepare minibus states for optimizer
            minibus_states = [
                minibus.get_minibus_info() 
                for minibus in self.minibuses.values()
            ]
            
            logger.debug(f"Prepared states for {len(minibus_states)} minibuses")
            
            # Call the optimizer
            logger.info("Calling route optimizer...")
            new_plans = self.route_optimizer.optimize(
                pending_requests=self.pending_requests,
                minibus_states=minibus_states,
                network=self.network,
                current_time=self.current_time
            )
            
            logger.info(f"Optimizer returned plans for {len(new_plans)} minibuses")
            
            # Apply new route plans to minibuses
            plans_updated = 0
            events_scheduled = 0
            passengers_assigned = 0
            
            for minibus_id, route_plan in new_plans.items():
                # Get minibus object
                minibus = self.minibuses.get(minibus_id)
                if minibus is None:
                    logger.warning(
                        f"Optimizer returned plan for unknown minibus {minibus_id}, "
                        f"skipping"
                    )
                    continue
                
                # Log route plan details
                if len(route_plan) > 0:
                    logger.info(
                        f"Updating {minibus_id} with new route plan: "
                        f"{len(route_plan)} stops"
                    )
                    logger.debug(f"Route plan: {route_plan}")
                else:
                    logger.info(f"{minibus_id} received empty route plan (remain idle)")
                
                try:
                    # Update the minibus route plan
                    minibus.update_route_plan(route_plan, self.current_time)
                    plans_updated += 1
                    
                    # Mark passengers as assigned to this minibus to prevent buses from picking them up
                    if len(route_plan) > 0:
                        for stop in route_plan:
                            if stop["action"] == "PICKUP":
                                for passenger_id in stop["passenger_ids"]:
                                    # Find the passenger in pending_requests
                                    passenger_found = False
                                    for passenger in self.pending_requests:
                                        if passenger.passenger_id == passenger_id:
                                            # Only assign if not already assigned to another vehicle
                                            if passenger.assigned_vehicle_id is None:
                                                passenger.assigned_vehicle_id = minibus_id
                                                passengers_assigned += 1
                                                logger.debug(
                                                    f"Assigned passenger {passenger_id} to {minibus_id}"
                                                )
                                            elif passenger.assigned_vehicle_id != minibus_id:
                                                logger.warning(
                                                    f"Passenger {passenger_id} already assigned to "
                                                    f"{passenger.assigned_vehicle_id}, optimizer assigned to {minibus_id}"
                                                )
                                            passenger_found = True
                                            break
                                    
                                    if not passenger_found:
                                        logger.warning(
                                            f"Passenger {passenger_id} assigned by optimizer but not found "
                                            f"in pending_requests (may have already boarded a vehicle)"
                                        )
                    
                    # If minibus has a next arrival time, schedule the arrival event
                    if minibus.next_arrival_time is not None:
                        self.add_event(Event(
                            time=minibus.next_arrival_time,
                            event_type=Event.MINIBUS_ARRIVAL,
                            data={"minibus_id": minibus_id}
                        ))
                        events_scheduled += 1
                        logger.debug(
                            f"Scheduled arrival event for {minibus_id} at "
                            f"{minibus.next_station_id} at {minibus.next_arrival_time}s "
                            f"({self._seconds_to_time_str(minibus.next_arrival_time)})"
                        )
                
                except Exception as e:
                    logger.error(
                        f"Failed to update route plan for {minibus_id}: {e}",
                        exc_info=True
                    )
                    # Continue with other minibuses despite error
            
            logger.info(
                f"Route plan update complete: "
                f"{plans_updated}/{len(new_plans)} plans updated, "
                f"{events_scheduled} arrival events scheduled, "
                f"{passengers_assigned} passengers assigned"
            )
            
            # Record optimizer call statistics
            self.statistics.record_system_event(
                event_type="OPTIMIZER_CALL",
                description=(
                    f"Optimizer called: {len(self.pending_requests)} pending requests, "
                    f"{plans_updated} plans updated, {events_scheduled} events scheduled, "
                    f"{passengers_assigned} passengers assigned"
                ),
                current_time=self.current_time
            )
            
            # Schedule next optimizer call
            optimizer_interval = self.config.get("optimization_interval", 30.0)
            next_optimize_time = self.current_time + optimizer_interval
            
            # Only schedule next call if within simulation duration
            if next_optimize_time < self.duration:
                self.add_event(Event(
                    time=next_optimize_time,
                    event_type=Event.OPTIMIZE_CALL,
                    data={}
                ))
                logger.info(
                    f"Scheduled next optimizer call at {next_optimize_time}s "
                    f"({self._seconds_to_time_str(next_optimize_time)})"
                )
            else:
                logger.info(
                    f"Next optimizer call would be at {next_optimize_time}s, "
                    f"which exceeds simulation duration ({self.duration}s), not scheduled"
                )
        
        except Exception as e:
            logger.error(
                f"Error handling optimizer call at {self.current_time}s: {e}",
                exc_info=True
            )
            
            # Record error event
            self.statistics.record_system_event(
                event_type="OPTIMIZER_ERROR",
                description=f"Optimizer call failed: {str(e)}",
                current_time=self.current_time
            )