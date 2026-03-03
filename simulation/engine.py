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
from typing import List, Dict, Optional, Tuple

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
        self.pending_bus_requests: List[Passenger] = []  # NEW: Bus passengers only
        self.pending_minibus_requests: List[Passenger] = []  # NEW: Minibus passengers only
        # Keep old attribute for backward compatibility (deprecated)
        self.pending_requests: List[Passenger] = []  # DEPRECATED: Will be removed
        
        
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

        # Step 7: Schedule first periodic sampling event
        sampling_interval = self.config.get("sampling_interval", 30.0)
        if sampling_interval > 0:
            self.add_event(Event(
                time=sampling_interval,
                event_type=Event.PERIODIC_SAMPLE,
                data={}
            ))
            logger.info(f"Scheduled first periodic sampling at {sampling_interval}s")
        
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
        
        Returns:
            Dictionary of buses {bus_id: Bus object}
        """
        buses = {}
        bus_schedules = {}
        
        try:
            with open(self.config["bus_schedule_file"], 'r') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    bus_id = row["bus_id"]
                    station_id = row["station_id"]
                    arrival_time_str = row["arrival_time"]
                    stop_sequence = int(row["stop_sequence"])
                    route_name = row["route_name"]
                    
                    arrival_time_seconds = self._time_str_to_seconds(arrival_time_str)
                    
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
                
                # CHANGED: Create both route list and schedule list
                route = [stop["station_id"] for stop in schedule_data["stops"]]
                schedule_list = [stop["arrival_time"] for stop in schedule_data["stops"]]  # NEW: List instead of Dict
                
                # Create Bus object with List schedule
                bus = Bus(
                    bus_id=bus_id,
                    route=route,
                    schedule=schedule_list,  # CHANGED: Pass list instead of dict
                    capacity=self.config.get("bus_capacity", 50)
                )
                
                buses[bus_id] = bus
                logger.debug(
                    f"Created bus {bus_id} with route {schedule_data['route']}, "
                    f"{len(route)} stops, first departure at {schedule_list[0]}s"
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
        MODIFIED: Generate passengers with service mode assignment and time window filtering.
        Generate passengers based on the OD matrix using a Poisson process.
        """
        logger.info("Generating passengers from OD matrix...")
        
        # Use random state for reproducibility
        random_seed = self.config.get("random_seed", 42)
        random_state = np.random.RandomState(random_seed)
        logger.info(f"Using random seed: {random_seed}")
        
        # NEW: Get time window configuration
        time_window = self.config.get("passenger_generation_time_window", None)
        window_start_seconds = 0.0
        window_end_seconds = self.duration
        
        if time_window is not None:
            try:
                window_start_str, window_end_str = time_window
                window_start_seconds = self._time_str_to_seconds(window_start_str)
                window_end_seconds = self._time_str_to_seconds(window_end_str)
                logger.info(
                    f"Passenger generation time window: {window_start_str} to {window_end_str} "
                    f"({window_start_seconds:.1f}s to {window_end_seconds:.1f}s)"
                )
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Invalid time window configuration: {time_window}, "
                    f"generating passengers for entire simulation duration"
                )
                window_start_seconds = 0.0
                window_end_seconds = self.duration
        
        # Generate passengers for each time slot
        n_time_slots = self.od_manager.n_time_slots
        slot_duration = self.od_manager.time_slot_duration
        total_passengers = 0
        minibus_passengers = 0
        bus_passengers = 0
        filtered_passengers = 0  # NEW: Count filtered passengers
        
        for slot_idx in range(n_time_slots):
            slot_start_time = slot_idx * slot_duration
            
            if slot_start_time >= self.duration:
                logger.info(f"Stopping passenger generation at slot {slot_idx}")
                break
            
            # Generate passengers for this slot
            passengers = self.od_manager.generate_passengers_for_slot(
                time_slot_start=slot_start_time,
                random_state=random_state
            )
            
            # Create passenger objects with service mode assignment
            for origin_id, dest_id, appear_time in passengers:
                if appear_time >= self.duration:
                    continue
                
                # NEW: Filter by time window
                if appear_time < window_start_seconds or appear_time >= window_end_seconds:
                    filtered_passengers += 1
                    continue
                
                passenger_id = f"P{total_passengers + 1}"
                
                # Determine service mode based on appear_time
                minibus_ratio = self._get_minibus_ratio_at_time(appear_time)
                is_minibus = random_state.random() < minibus_ratio
                service_mode = Passenger.SERVICE_MODE_MINIBUS if is_minibus else Passenger.SERVICE_MODE_BUS
                
                # Create Passenger object with service_mode
                passenger = Passenger(
                    passenger_id=passenger_id,
                    origin=origin_id,
                    destination=dest_id,
                    appear_time=appear_time,
                    max_wait_time=self.config.get("passenger_max_wait_time", 900.0),
                    service_mode=service_mode
                )
                
                # Add to tracking
                self.all_passengers[passenger_id] = passenger
                
                # Count by mode
                if is_minibus:
                    minibus_passengers += 1
                else:
                    bus_passengers += 1
                
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
            
            # Log progress
            if (slot_idx + 1) % 10 == 0:
                logger.info(
                    f"Generated passengers for slot {slot_idx + 1}/{n_time_slots}, "
                    f"total: {total_passengers} ({bus_passengers} bus, {minibus_passengers} minibus), "
                    f"filtered: {filtered_passengers}"
                )
        
        # Log final statistics
        logger.info(
            f"Passenger generation complete: {total_passengers} total "
            f"({bus_passengers} bus [{100*bus_passengers/total_passengers:.1f}%], "
            f"{minibus_passengers} minibus [{100*minibus_passengers/total_passengers:.1f}%])"
        )
        if filtered_passengers > 0:
            logger.info(
                f"Filtered out {filtered_passengers} passengers outside time window "
                f"({window_start_seconds:.1f}s to {window_end_seconds:.1f}s)"
            )

    def _generate_hardcoded_test_passengers(self) -> None:
        """
        MODIFIED: Generate hardcoded test passengers with service mode.
        """
        logger.info("Generating hardcoded test passengers...")
        
        # Get real station IDs from the network
        station_ids = list(self.network.stations.keys())
        
        if len(station_ids) < 5:
            logger.warning(f"Not enough stations ({len(station_ids)})")
            return
        
        # NEW: Use random state for reproducible service mode assignment
        random_seed = self.config.get("random_seed", 42)
        random_state = np.random.RandomState(random_seed)
        
        # Create test passengers
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
            # NEW: Determine service mode
            minibus_ratio = self._get_minibus_ratio_at_time(pax_data["appear_time"])
            is_minibus = random_state.random() < minibus_ratio
            service_mode = Passenger.SERVICE_MODE_MINIBUS if is_minibus else Passenger.SERVICE_MODE_BUS
            
            # Create Passenger object
            passenger = Passenger(
                passenger_id=pax_data["id"],
                origin=pax_data["origin"],
                destination=pax_data["dest"],
                appear_time=pax_data["appear_time"],
                max_wait_time=self.config.get("passenger_max_wait_time", 900.0),
                service_mode=service_mode  # NEW
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
                f"{pax_data['origin']} -> {pax_data['dest']}, "
                f"mode={service_mode}, time={pax_data['appear_time']}s"
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
            elif event.event_type == Event.PERIODIC_SAMPLE:
                self.handle_periodic_sample(event)
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
                        # "occupancy": len(bus.passengers)
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
                        # "occupancy": len(bus.passengers)
                    },
                    current_time=self.current_time
                )
            
            # MODIFIED: Remove boarded passengers from pending_bus_requests
            # for passenger in boarded:
            #     if passenger in self.pending_bus_requests:
            #         self.pending_bus_requests.remove(passenger)

            for passenger in boarded:
                if passenger in self.pending_bus_requests:
                    self.pending_bus_requests.remove(passenger)
                # If a minibus-mode passenger boarded the bus instead,
                # remove them from the minibus pending list as well.
                if passenger in self.pending_minibus_requests:
                    self.pending_minibus_requests.remove(passenger)
                    logger.info(
                        f"Passenger {passenger.passenger_id} (minibus mode) boarded "
                        f"{bus_id} instead - removed from pending_minibus_requests"
                    )
                    logger.debug(
                        f"Removed {passenger.passenger_id} from pending_bus_requests "
                        f"(boarded {bus_id})"
                    )
            
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
        MODIFIED: Add passengers to mode-specific pending lists.
        """
        try:
            # Get passenger object
            if "passenger" in event.data:
                passenger = event.data["passenger"]
            else:
                # Create new passenger (for test passengers)
                pax_id = event.data["id"]
                origin = event.data["origin"]
                destination = event.data["dest"]
                
                # NEW: Determine service mode
                minibus_ratio = self._get_minibus_ratio_at_time(self.current_time)
                random_seed = self.config.get("random_seed", 42)
                random_state = np.random.RandomState(random_seed + hash(pax_id) % 10000)
                is_minibus = random_state.random() < minibus_ratio
                service_mode = Passenger.SERVICE_MODE_MINIBUS if is_minibus else Passenger.SERVICE_MODE_BUS
                
                passenger = Passenger(
                    passenger_id=pax_id,
                    origin=origin,
                    destination=destination,
                    appear_time=self.current_time,
                    max_wait_time=self.config.get("passenger_max_wait_time", 900.0),
                    service_mode=service_mode
                )
                
                # Add to tracking
                self.all_passengers[pax_id] = passenger
            
            # NEW: Add to mode-specific pending list
            if passenger.service_mode == Passenger.SERVICE_MODE_MINIBUS:
                if passenger not in self.pending_minibus_requests:
                    self.pending_minibus_requests.append(passenger)
                    logger.debug(f"Added {passenger.passenger_id} to pending_minibus_requests")
            else:  # BUS mode
                if passenger not in self.pending_bus_requests:
                    self.pending_bus_requests.append(passenger)
                    logger.debug(f"Added {passenger.passenger_id} to pending_bus_requests")
            
            # REMOVED: No longer add to self.pending_requests
            
            # Add to station waiting list
            station = self.network.get_station(passenger.origin_station_id)
            if station is None:
                logger.error(
                    f"Origin station {passenger.origin_station_id} not found for "
                    f"passenger {passenger.passenger_id}"
                )
                return
            
            station.add_waiting_passenger(passenger)
            
            logger.info(
                f"Passenger {passenger.passenger_id} appeared at {passenger.origin_station_id}, "
                f"destination {passenger.destination_station_id}, "
                f"mode={passenger.service_mode}, time={self._seconds_to_time_str(self.current_time)}"
            )
            logger.debug(
                f"Pending: {len(self.pending_bus_requests)} bus, "
                f"{len(self.pending_minibus_requests)} minibus"
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
        MODIFIED: Check timeouts for both bus and minibus passengers.
        """
        abandoned_passengers = []
        
        # NEW: Check bus passengers
        for passenger in self.pending_bus_requests[:]:
            if passenger.status == Passenger.WAITING:
                if passenger.check_timeout(self.current_time):
                    passenger.abandon(self.current_time)
                    abandoned_passengers.append(passenger)
                    self.pending_bus_requests.remove(passenger)
                    
                    # Remove from station
                    station = self.network.get_station(passenger.origin_station_id)
                    if station:
                        station.remove_waiting_passenger(passenger)
        
        # NEW: Check minibus passengers
        for passenger in self.pending_minibus_requests[:]:
            if passenger.status == Passenger.WAITING:
                if passenger.check_timeout(self.current_time):
                    passenger.abandon(self.current_time)
                    abandoned_passengers.append(passenger)
                    self.pending_minibus_requests.remove(passenger)
                    
                    # Remove from station
                    station = self.network.get_station(passenger.origin_station_id)
                    if station:
                        station.remove_waiting_passenger(passenger)
        
        # REMOVED: No cleanup of self.pending_requests
        
        if abandoned_passengers:
            logger.warning(
                f"{len(abandoned_passengers)} passengers abandoned due to timeout at "
                f"{self._seconds_to_time_str(self.current_time)}"
            )
            
            # Record statistics
            self.statistics.record_system_event(
                event_type="PASSENGERS_ABANDONED",
                description=f"{len(abandoned_passengers)} passengers abandoned due to timeout",
                current_time=self.current_time
            )
            
            for pax in abandoned_passengers:
                logger.debug(
                    f"Passenger {pax.passenger_id} (mode={pax.service_mode}) abandoned: "
                    f"waited {self.current_time - pax.appear_time:.1f}s"
                )
                
    def finalize(self) -> None:
        """
        MODIFIED: Statistics separated by service mode.
        """
        logger.info("=" * 60)
        logger.info("FINALIZING SIMULATION")
        logger.info("=" * 60)
        
        # Count passenger states
        total_passengers = len(self.all_passengers)
        
        # NEW: Count by service mode
        bus_passengers = [p for p in self.all_passengers.values() if p.service_mode == Passenger.SERVICE_MODE_BUS]
        minibus_passengers = [p for p in self.all_passengers.values() if p.service_mode == Passenger.SERVICE_MODE_MINIBUS]
        
        # Overall statistics
        arrived = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ARRIVED)
        abandoned = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ABANDONED)
        waiting = sum(1 for p in self.all_passengers.values() if p.status == Passenger.WAITING)
        onboard = sum(1 for p in self.all_passengers.values() if p.status == Passenger.ONBOARD)
        
        # NEW: Statistics by mode
        bus_arrived = sum(1 for p in bus_passengers if p.status == Passenger.ARRIVED)
        bus_abandoned = sum(1 for p in bus_passengers if p.status == Passenger.ABANDONED)
        minibus_arrived = sum(1 for p in minibus_passengers if p.status == Passenger.ARRIVED)
        minibus_abandoned = sum(1 for p in minibus_passengers if p.status == Passenger.ABANDONED)
        
        # Print summary
        logger.info("SIMULATION SUMMARY:")
        logger.info(f"  Total passengers: {total_passengers}")
        logger.info(f"  Arrived: {arrived} ({100*arrived/total_passengers if total_passengers > 0 else 0:.1f}%)")
        logger.info(f"  Abandoned: {abandoned} ({100*abandoned/total_passengers if total_passengers > 0 else 0:.1f}%)")
        logger.info(f"  Still waiting: {waiting}")
        logger.info(f"  Still onboard: {onboard}")
        
        # NEW: Mode-specific statistics
        logger.info(f"\n  BUS SERVICE ({len(bus_passengers)} passengers):")
        logger.info(f"    Arrived: {bus_arrived} ({100*bus_arrived/len(bus_passengers) if len(bus_passengers) > 0 else 0:.1f}%)")
        logger.info(f"    Abandoned: {bus_abandoned} ({100*bus_abandoned/len(bus_passengers) if len(bus_passengers) > 0 else 0:.1f}%)")
        logger.info(f"    Pending: {len(self.pending_bus_requests)}")
        
        logger.info(f"\n  MINIBUS SERVICE ({len(minibus_passengers)} passengers):")
        logger.info(f"    Arrived: {minibus_arrived} ({100*minibus_arrived/len(minibus_passengers) if len(minibus_passengers) > 0 else 0:.1f}%)")
        logger.info(f"    Abandoned: {minibus_abandoned} ({100*minibus_abandoned/len(minibus_passengers) if len(minibus_passengers) > 0 else 0:.1f}%)")
        logger.info(f"    Pending: {len(self.pending_minibus_requests)}")
        
        # Vehicle summaries
        logger.info(f"\n  Total buses: {len(self.buses)}")
        for bus_id, bus in self.buses.items():
            logger.info(
                f"    {bus_id}: served {bus.total_passengers_served} passengers, "
                f"current occupancy: {len(bus.passengers)}/{bus.capacity}"
            )
        
        if len(self.minibuses) > 0:
            logger.info(f"\n  Total minibuses: {len(self.minibuses)}")
            for minibus_id, minibus in self.minibuses.items():
                logger.info(
                    f"    {minibus_id}: served {minibus.total_passengers_served} passengers, "
                    f"current occupancy: {minibus.get_occupancy()}/{minibus.capacity}"
                )
        
        # Generate reports 
        if self.statistics is not None:
            logger.info("Recording passenger data to statistics...")
            
            for passenger in self.all_passengers.values():
                self.statistics.record_passenger(passenger)
            
            logger.info("Generating detailed statistics report...")
            
            output_dir = self.config.get("output_dir", "results")
            
            self.statistics.generate_report(
                output_file=f"{output_dir}/simulation_report.txt"
            )
            
            self.statistics.plot_wait_time_distribution(
                output_file=f"{output_dir}/wait_time_dist.png"
            )
            
            self.statistics.plot_occupancy_over_time(
                output_file=f"{output_dir}/occupancy_timeline.png"
            )
            
            self.statistics.plot_service_rate_by_hour(
                output_file=f"{output_dir}/service_rate_hourly.png"
            )
            
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
        [FIXED VERSION] Prevents 'time travel' by ignoring stale events.
        Also handles passenger removal from pending lists upon boarding.
        """
        minibus_id = event.data["minibus_id"]
        
        try:
            # 1. Get minibus object
            minibus = self.minibuses.get(minibus_id)
            if minibus is None:
                logger.error(f"Minibus {minibus_id} not found in minibuses dictionary")
                return
            
            # ===================================================================
            # CRITICAL FIX: Stale Event Detection (Ghost Event Filter)
            # ===================================================================
            # If minibus is IDLE or has no next stop, but an event fired, ignore it.
            if minibus.next_arrival_time is None:
                logger.info(f"Ignoring stale event for {minibus_id} (bus is IDLE/No Plan)")
                return

            # Check if this event matches the minibus's current schedule.
            # Allow a tiny floating-point tolerance (e.g., 0.001s)
            time_diff = abs(event.time - minibus.next_arrival_time)
            if time_diff > 0.001:
                logger.debug(
                    f"Ignoring stale event for {minibus_id}: "
                    f"Event Time={event.time:.1f}s != Current Plan={minibus.next_arrival_time:.1f}s"
                )
                return
            # ===================================================================
            
            # 2. Check validity of next station
            if minibus.next_station_id is None:
                logger.warning(
                    f"Minibus {minibus_id} arrival triggered but next_station_id is None. "
                    f"Inconsistent state."
                )
                return
            
            # 3. Get current station
            station = self.network.get_station(minibus.next_station_id)
            if station is None:
                logger.error(
                    f"Station {minibus.next_station_id} not found for {minibus_id}"
                )
                return
            
            logger.info(
                f"Minibus {minibus_id} arrived at {station.station_id} "
                f"at {self._seconds_to_time_str(self.current_time)}"
            )
            
            # 4. Process arrival (handles boarding and alighting)
            result = minibus.arrive_at_station(station, self.current_time)
            
            boarded = result["boarded"]
            alighted = result["alighted"]
            action_type = result["action_type"]
            
            # 5. Record Statistics & Update State
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
            
            # Handle Boarding (CRITICAL: Remove passengers from pending list here)
            if len(boarded) > 0:
                self.statistics.record_vehicle_event(
                    vehicle_id=minibus_id,
                    event_type="BOARDING",
                    event_data={
                        "station": station.station_id,
                        "count": len(boarded),
                        "passenger_ids": [p.passenger_id for p in boarded]
                    },
                    current_time=self.current_time
                )
                
                # Remove boarded passengers from pending_minibus_requests
                for passenger in boarded:
                    if passenger in self.pending_minibus_requests:
                        self.pending_minibus_requests.remove(passenger)
                        logger.debug(f"Removed {passenger.passenger_id} from pending minibus requests (Boarded)")
                    # Also check legacy list if used
                    if passenger in self.pending_requests:
                        self.pending_requests.remove(passenger)

            # Handle Alighting
            if len(alighted) > 0:
                self.statistics.record_vehicle_event(
                    vehicle_id=minibus_id,
                    event_type="ALIGHTING",
                    event_data={
                        "station": station.station_id,
                        "count": len(alighted),
                        "passenger_ids": [p.passenger_id for p in alighted]
                    },
                    current_time=self.current_time
                )
            
            logger.info(
                f"Minibus {minibus_id} at {station.station_id}: "
                f"action={action_type}, "
                f"{len(boarded)} boarded, {len(alighted)} alighted, "
                f"occupancy: {minibus.get_occupancy()}/{minibus.capacity}"
            )
            
            # 6. Schedule Next Arrival (if any)
            if minibus.next_arrival_time is not None:
                if minibus.next_station_id is None:
                    logger.error(
                        f"Minibus {minibus_id} has next_arrival_time={minibus.next_arrival_time} "
                        f"but next_station_id is None. This is inconsistent state."
                    )
                else:
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
    # def handle_optimize_call(self, event: Event) -> None:
    #     """
    #     Handle periodic optimizer call event.
        
    #     Optimization strategy:
    #     1. Only update routes when necessary (avoid interrupting identical ongoing tasks)
    #     2. Unified passenger assignment logic
    #     3. Clear state transition management
    #     """
    #     try:
    #         if not self.config.get("enable_minibus", False):
    #             logger.warning("OPTIMIZE_CALL event but minibus not enabled")
    #             return
            
    #         if self.route_optimizer is None:
    #             logger.error("OPTIMIZE_CALL event but route_optimizer is None")
    #             return
            
    #         logger.info(f"Optimizer call at {self._seconds_to_time_str(self.current_time)}")
    #         logger.info(f"State: {len(self.pending_requests)} pending, {len(self.minibuses)} minibuses")
            
    #         # Prepare minibus states
    #         minibus_states = [mb.get_minibus_info() for mb in self.minibuses.values()]
            
    #         # Call optimizer
    #         # logger.info("Calling route optimizer...")
    #         new_plans = self.route_optimizer.optimize(
    #             pending_requests=self.pending_requests,
    #             minibus_states=minibus_states,
    #             network=self.network,
    #             current_time=self.current_time
    #         )
            
    #         # logger.info(f"Optimizer returned plans for {len(new_plans)} minibuses")
            
    #         # Track statistics
    #         stats = {
    #             'plans_updated': 0,
    #             'plans_skipped': 0,
    #             'events_scheduled': 0,
    #             'newly_assigned_passengers': set()
    #         }
            
    #         # Apply new route plans
    #         for minibus_id, new_route_plan in new_plans.items():
    #             minibus = self.minibuses.get(minibus_id)
    #             if minibus is None:
    #                 logger.warning(f"Unknown minibus {minibus_id}, skipping")
    #                 continue
                
    #             # Process route update for this minibus
    #             self._process_minibus_route_update(
    #                 minibus=minibus,
    #                 minibus_id=minibus_id,
    #                 new_route_plan=new_route_plan,
    #                 stats=stats
    #             )
            
    #         # Remove assigned passengers from pending queue
    #         self._cleanup_assigned_passengers(stats['newly_assigned_passengers'])
            
    #         # Log statistics
    #         logger.info(
    #             f"Complete: {stats['plans_updated']} plans updated, "
    #             f"{stats['plans_skipped']} skipped, "
    #             f"{stats['events_scheduled']} events scheduled, "
    #             f"{len(stats['newly_assigned_passengers'])} passengers assigned"
    #         )
            
    #         self.statistics.record_system_event(
    #             event_type="OPTIMIZER_CALL",
    #             description=f"Optimizer: {len(self.pending_requests)} pending, "
    #                     f"{len(stats['newly_assigned_passengers'])} assigned",
    #             current_time=self.current_time
    #         )
            
    #         # Schedule next optimization
    #         self._schedule_next_optimizer_call()
        
    #     except Exception as e:
    #         logger.error(f"Error in optimizer call: {e}", exc_info=True)
    #         self.statistics.record_system_event(
    #             event_type="OPTIMIZER_ERROR",
    #             description=f"Optimizer failed: {str(e)}",
    #             current_time=self.current_time
    #         )


    # def _process_minibus_route_update(
    #     self, 
    #     minibus, 
    #     minibus_id: str, 
    #     new_route_plan: List[Dict],
    #     stats: Dict
    # ) -> None:
    #     """
    #     Process route update for a single minibus.
        
    #     Args:
    #         minibus: Minibus object
    #         minibus_id: Minibus ID
    #         new_route_plan: New route plan returned by optimizer
    #         stats: Statistics dictionary (will be modified)
    #     """
    #     current_plan = minibus.route_plan
        
    #     # Determine if route update is needed
    #     should_update, reason = self._should_update_route(
    #         minibus=minibus,
    #         current_plan=current_plan,
    #         new_plan=new_route_plan
    #     )
        
    #     if not should_update:
    #         logger.debug(f"{minibus_id}: {reason}, skipping update")
    #         stats['plans_skipped'] += 1
            
    #         # Even if skipping update, handle passenger assignment
    #         # (optimizer may have reassigned passengers)
    #         self._collect_assigned_passengers(new_route_plan, minibus_id, stats)
    #         return
        
    #     # Execute route update
    #     logger.info(f"Updating {minibus_id}: {len(new_route_plan)} stops ({reason})")
        
    #     try:
    #         # Update route
    #         minibus.update_route_plan(new_route_plan, self.current_time)
    #         stats['plans_updated'] += 1
            
    #         # Collect assigned passengers
    #         self._collect_assigned_passengers(new_route_plan, minibus_id, stats)
            
    #         # Schedule next arrival event
    #         if minibus.next_arrival_time is not None:
    #             self.add_event(Event(
    #                 time=minibus.next_arrival_time,
    #                 event_type=Event.MINIBUS_ARRIVAL,
    #                 data={"minibus_id": minibus_id}
    #             ))
    #             stats['events_scheduled'] += 1
    #             logger.debug(
    #                 f"{minibus_id} next arrival: station {minibus.next_station_id} "
    #                 f"at {minibus.next_arrival_time:.1f}s"
    #             )
        
    #     except Exception as e:
    #         logger.error(f"Failed to update {minibus_id}: {e}", exc_info=True)


    # def _should_update_route(
    #     self,
    #     minibus,
    #     current_plan: List[Dict],
    #     new_plan: List[Dict]
    # ) -> Tuple[bool, str]:
    #     """
    #     Determine if minibus route needs to be updated.
        
    #     Returns:
    #         (should_update, reason): Whether to update and reason
    #     """
    #     # Case 1: New plan is empty
    #     if len(new_plan) == 0:
    #         if len(current_plan) == 0 and minibus.status == minibus.IDLE:
    #             # Already idle, no update needed
    #             return False, "already idle with no plan"
    #         else:
    #             # Need to clear route or transition to idle
    #             return True, "clearing route to idle"
        
    #     # Case 2: Current plan is empty, new plan is not
    #     if len(current_plan) == 0:
    #         return True, "assigning new route to idle minibus"
        
    #     # Case 3: Minibus is en route, compare remaining path
    #     if minibus.status == minibus.EN_ROUTE:
    #         remaining_plan = self._get_remaining_route(minibus, current_plan)
            
    #         if self._routes_are_equivalent(remaining_plan, new_plan):
    #             # Remaining path matches new path, no update needed
    #             return False, f"already executing same route (at station {minibus.next_station_id})"
    #         else:
    #             # Route changed, update needed
    #             return True, "route changed"
        
    #     # Case 4: Minibus in other state (BOARDING, etc.), compare full route
    #     if self._routes_are_equivalent(current_plan, new_plan):
    #         return False, f"same route (status: {minibus.status})"
    #     else:
    #         return True, "route changed"


    # def _get_remaining_route(self, minibus, current_plan: List[Dict]) -> List[Dict]:
    #     """
    #     Get remaining route for minibus (from next station onwards).
        
    #     Args:
    #         minibus: Minibus object
    #         current_plan: Current complete route
            
    #     Returns:
    #         List of remaining route stops
    #     """
    #     if minibus.next_station_id is None:
    #         return []
        
    #     # Find position of next station in current plan
    #     for i, stop in enumerate(current_plan):
    #         if stop["station_id"] == minibus.next_station_id:
    #             return current_plan[i:]  # Return all stops from next station
        
    #     # If not found (should not happen), return full plan
    #     logger.warning(
    #         f"Minibus next_station_id {minibus.next_station_id} not found in current_plan"
    #     )
    #     return current_plan


    # def _routes_are_equivalent(self, route1: List[Dict], route2: List[Dict]) -> bool:
    #     """
    #     Check if two routes are equivalent.
        
    #     Note: Only compares stations, actions, and passengers, not estimated arrival times.
        
    #     Args:
    #         route1: First route
    #         route2: Second route
            
    #     Returns:
    #         Whether the two routes are equivalent
    #     """
    #     if len(route1) != len(route2):
    #         return False
        
    #     for stop1, stop2 in zip(route1, route2):
    #         # Compare station IDs
    #         if stop1["station_id"] != stop2["station_id"]:
    #             return False
            
    #         # Compare action types
    #         if stop1["action"] != stop2["action"]:
    #             return False
            
    #         # Compare passenger sets (order-independent)
    #         passengers1 = set(stop1.get("passenger_ids", []))
    #         passengers2 = set(stop2.get("passenger_ids", []))
    #         if passengers1 != passengers2:
    #             return False
        
    #     return True


    # def _collect_assigned_passengers(
    #     self,
    #     route_plan: List[Dict],
    #     minibus_id: str,
    #     stats: Dict
    # ) -> None:
    #     """
    #     Collect assigned passengers in route and update their assignment status.
        
    #     Args:
    #         route_plan: Route plan
    #         minibus_id: Minibus ID
    #         stats: Statistics dictionary (will be modified)
    #     """
    #     for stop in route_plan:
    #         if stop["action"] == "PICKUP":
    #             for passenger_id in stop["passenger_ids"]:
    #                 # Add to assigned set
    #                 stats['newly_assigned_passengers'].add(passenger_id)
                    
    #                 # Update passenger object's assignment status
    #                 self._assign_passenger_to_minibus(passenger_id, minibus_id)


    # def _assign_passenger_to_minibus(self, passenger_id: str, minibus_id: str) -> None:
    #     """
    #     Assign passenger to minibus (update passenger object's assigned_vehicle_id).
        
    #     Args:
    #         passenger_id: Passenger ID
    #         minibus_id: Minibus ID
    #     """
    #     for passenger in self.pending_requests:
    #         if passenger.passenger_id == passenger_id:
    #             if passenger.assigned_vehicle_id is None:
    #                 # First assignment
    #                 passenger.assigned_vehicle_id = minibus_id
    #                 logger.debug(f"Assigned passenger {passenger_id} to {minibus_id}")
    #             elif passenger.assigned_vehicle_id != minibus_id:
    #                 # Reassignment (transferred from another vehicle)
    #                 logger.warning(
    #                     f"Passenger {passenger_id} reassigned from "
    #                     f"{passenger.assigned_vehicle_id} to {minibus_id}"
    #                 )
    #                 passenger.assigned_vehicle_id = minibus_id
    #             # else: already assigned to this vehicle, no action needed
    #             break


    # def _cleanup_assigned_passengers(self, assigned_passenger_ids: set) -> None:
    #     """
    #     Remove assigned passengers from pending queue.
        
    #     Args:
    #         assigned_passenger_ids: Set of assigned passenger IDs
    #     """
    #     original_count = len(self.pending_requests)
        
    #     self.pending_requests = [
    #         passenger for passenger in self.pending_requests
    #         if passenger.passenger_id not in assigned_passenger_ids
    #     ]
        
    #     removed_count = original_count - len(self.pending_requests)
        
    #     if removed_count > 0:
    #         logger.info(f"Removed {removed_count} assigned passengers from pending queue")


    # def _schedule_next_optimizer_call(self) -> None:
    #     """Schedule next optimizer call."""
    #     optimizer_interval = self.config.get("optimization_interval", 30.0)
    #     next_time = self.current_time + optimizer_interval
        
    #     if next_time < self.duration:
    #         self.add_event(Event(
    #             time=next_time,
    #             event_type=Event.OPTIMIZE_CALL,
    #             data={}
    #         ))
    #         logger.info(f"Next optimizer call scheduled at {next_time:.1f}s")
    #     else:
    #         logger.info("No more optimizer calls (simulation ending)")

    def _ensure_onboard_dropoffs(self, minibus, route_plan):
        """
        Mandatory Guarantee: Ensures every passenger currently on board has a 
        corresponding DROPOFF action in the route_plan for their destination.
        """
        if not getattr(minibus, "passengers", None):
            return route_plan

        # 1) Group onboard passengers by their destination stations
        dest_to_pids = {}
        for p in minibus.passengers:
            dest_to_pids.setdefault(p.destination_station_id, []).append(p.passenger_id)

        # 2) Index existing dropoffs in the plan (station_id -> set of passenger_ids)
        dropoff_idx = {}
        for stop in route_plan:
            if stop.get("action") == "DROPOFF":
                st = stop["station_id"]
                dropoff_idx.setdefault(st, set()).update(stop.get("passenger_ids", []))

        # 3) Supplement missing dropoffs
        for dest, pids in dest_to_pids.items():
            # Identify passengers who are on board but missing from the dropoff plan for this destination
            missing = [pid for pid in pids if pid not in dropoff_idx.get(dest, set())]
            if not missing:
                continue

            # If a dropoff stop for this station already exists, merge the missing IDs into it
            inserted = False
            for stop in route_plan:
                if stop.get("action") == "DROPOFF" and stop["station_id"] == dest:
                    stop["passenger_ids"] = list(set(stop.get("passenger_ids", []) + missing))
                    inserted = True
                    break

            # Otherwise, append a new dropoff stop to the end of the route (safest fallback)
            if not inserted:
                route_plan.append({
                    "station_id": dest,
                    "action": "DROPOFF",
                    "passenger_ids": missing
                })

        return route_plan
    
    def handle_optimize_call(self, event: Event) -> None:
        """
        Handle periodic optimizer call event.
        [FIXED VERSION] Includes:
        1. Task Locking: Prevents rerouting vehicles that are already en-route.
        2. Persistent Requests: Keeps passengers in pending list until boarded.
        3. Safe Scheduling: Relying on arrival event validation to filter duplicates.
        """
        try:
            if not self.config.get("enable_minibus", False):
                logger.warning("OPTIMIZE_CALL event but minibus not enabled")
                return
            
            if self.route_optimizer is None:
                logger.error("OPTIMIZE_CALL event but route_optimizer is None")
                return
            
            # Log state
            logger.info(f"Optimizer call at {self._seconds_to_time_str(self.current_time)}")
            logger.info(
                f"Pending requests: {len(self.pending_bus_requests)} bus, "
                f"{len(self.pending_minibus_requests)} minibus, "
                f"{len(self.minibuses)} minibuses"
            )
            
            # Prepare inputs
            # minibus_states = [mb.get_minibus_info() for mb in self.minibuses.values()]


            minibus_states = []
            for mb in self.minibuses.values():
                state = mb.get_minibus_info()

                # Attach real pickup_time and origin for each onboard passenger.
                # The optimizer uses these to compute accurate detour times for
                # passengers already riding — no approximations needed.
                onboard_details = {}
                for pid in state["passenger_ids"]:
                    pax = self.all_passengers.get(pid)
                    if pax and pax.pickup_time is not None:
                        onboard_details[pid] = {
                            "pickup_time": pax.pickup_time,
                            "origin_station_id": pax.origin_station_id,
                            "destination_station_id": pax.destination_station_id
                        }
                state["onboard_passenger_details"] = onboard_details
                minibus_states.append(state)
                        
            # Call optimizer
            logger.info("Calling route optimizer with minibus passengers only...")
            new_plans = self.route_optimizer.optimize(
                pending_requests=self.pending_minibus_requests,
                minibus_states=minibus_states,
                network=self.network,
                current_time=self.current_time
            )
            
            logger.info(f"Optimizer returned plans for {len(new_plans)} minibuses")
            
            # # Collect all passenger IDs that appear in the new plans as PICKUP
            # all_planned_pickup_ids = set()
            # for route_plan in new_plans.values():
            #     for stop in route_plan:
            #         if stop["action"] == "PICKUP":
            #             all_planned_pickup_ids.update(stop["passenger_ids"])

            # # If a passenger was previously assigned but is no longer in any plan,
            # # the optimizer has dropped them - clear their assignment so buses can pick them up
            # for passenger in self.pending_minibus_requests:
            #     if (passenger.assigned_vehicle_id is not None and
            #             passenger.passenger_id not in all_planned_pickup_ids):
            #         logger.info(
            #             f"Passenger {passenger.passenger_id} dropped by optimizer "
            #             f"(waited {self.current_time - passenger.appear_time:.0f}s), "
            #             f"clearing assignment so bus can pick them up"
            #         )
            #         passenger.assigned_vehicle_id = None



            all_planned_pickup_ids = set()
            for route_plan in new_plans.values():
                for stop in route_plan:
                    if stop["action"] == "PICKUP":
                        all_planned_pickup_ids.update(stop["passenger_ids"])

            passengers_to_transfer = []
            for passenger in self.pending_minibus_requests:
                if (passenger.assigned_vehicle_id is not None and
                        passenger.passenger_id not in all_planned_pickup_ids):
                    logger.info(
                        f"Passenger {passenger.passenger_id} dropped by optimizer, "
                        f"transferring to bus service"
                    )
                    passenger.assigned_vehicle_id = None
                    passenger.service_mode = Passenger.SERVICE_MODE_BUS
                    passengers_to_transfer.append(passenger)

            for passenger in passengers_to_transfer:
                self.pending_minibus_requests.remove(passenger)
                self.pending_bus_requests.append(passenger)

            # Track statistics
            newly_assigned_ids = set()
            plans_updated = 0
            events_scheduled = 0
            
            # Apply new route plans
            for minibus_id, route_plan in new_plans.items():
                minibus = self.minibuses.get(minibus_id)
                if minibus is None:
                    logger.warning(f"Unknown minibus {minibus_id}, skipping")
                    continue
                
                # ===============================================================
                # 1. TASK LOCKING (CRITICAL FIX)
                # Prevents the optimizer from rerouting a minibus while it is 
                # already en route, which could prevent it from ever reaching its destination.
                # ===============================================================
                if minibus.status == minibus.EN_ROUTE and len(minibus.route_plan) > 0:
                    current_task = minibus.route_plan[0]
                    
                    # Check if the new plan alters the current active task target.
                    # Condition: If the new plan is empty, or the first station differs from the current target.
                    if len(route_plan) == 0 or route_plan[0]["station_id"] != current_task["station_id"]:
                        logger.info(
                            f"Task Lock: {minibus_id} is en route to {current_task['station_id']}, "
                            f"forcing retention of current task."
                        )
                        # Forcefully insert the currently executing task at the beginning of the new plan.
                        route_plan.insert(0, current_task)

                # Skip if effectively no change (optimization)
                # Check if route is same to avoid unnecessary updates
                current_plan = minibus.route_plan
                if (len(current_plan) == 0 and len(route_plan) == 0):
                    continue
                    
                if (minibus.status == minibus.EN_ROUTE and 
                    self._routes_are_same(current_plan, route_plan)):
                    # Route is identical, no update needed
                    continue

                if len(route_plan) > 0:
                    logger.info(f"Updating {minibus_id}: {len(route_plan)} stops")
                else:
                    logger.info(f"{minibus_id}: plan cleared (IDLE)")
                
                try:
                    # 2. Execute route update
                    # This updates minibus.next_arrival_time based on current calculation
                    route_plan = self._ensure_onboard_dropoffs(minibus, route_plan)
                    minibus.update_route_plan(route_plan, self.current_time)
                    plans_updated += 1
                    
                    # 3. Track assigned passengers (Metadata only - do NOT remove from list)
                    if len(route_plan) > 0:
                        for stop in route_plan:
                            if stop["action"] == "PICKUP":
                                for pid in stop["passenger_ids"]:
                                    newly_assigned_ids.add(pid)
                                    
                                    # Update passenger object's assignment status
                                    for pax in self.pending_minibus_requests:
                                        if pax.passenger_id == pid:
                                            if pax.assigned_vehicle_id != minibus_id:
                                                pax.assigned_vehicle_id = minibus_id
                                                logger.debug(f"Assigned {pid} to {minibus_id}")
                                            break
                    
                    # 4. Schedule next arrival event
                    # We ALWAYS add a new event here if the route expects one.
                    # The 'handle_minibus_arrival' method will filter out any stale events
                    # from previous plans by comparing timestamps.
                    if minibus.next_arrival_time is not None:
                        if minibus.next_station_id is not None:
                            self.add_event(Event(
                                time=minibus.next_arrival_time,
                                event_type=Event.MINIBUS_ARRIVAL,
                                data={"minibus_id": minibus_id}
                            ))
                            events_scheduled += 1
                        else:
                            logger.error(
                                f"Minibus {minibus_id} has arrival_time but no next_station_id! Plan: {route_plan}"
                            )

                except Exception as e:
                    logger.error(f"Failed to update {minibus_id}: {e}", exc_info=True)
            
            # Count currently assigned passengers for logging
            # (We do NOT remove them from self.pending_minibus_requests anymore)
            assigned_count = sum(1 for p in self.pending_minibus_requests if p.assigned_vehicle_id is not None)
            
            logger.info(
                f"Complete: {plans_updated} plans updated, {events_scheduled} events scheduled. "
                f"Currently assigned/pending: {assigned_count}/{len(self.pending_minibus_requests)}"
            )
            
            # Record stats
            self.statistics.record_system_event(
                event_type="OPTIMIZER_CALL",
                description=f"Optimizer: {len(self.pending_minibus_requests)} pending, {assigned_count} assigned",
                current_time=self.current_time
            )
            
            # Schedule next call
            optimizer_interval = self.config.get("optimization_interval", 30.0)
            next_time = self.current_time + optimizer_interval
            
            if next_time < self.duration:
                self.add_event(Event(
                    time=next_time,
                    event_type=Event.OPTIMIZE_CALL,
                    data={}
                ))
            else:
                logger.info("No more optimizer calls")
        
        except Exception as e:
            logger.error(f"Error in optimizer call: {e}", exc_info=True)

    def _routes_are_same(self, route1: List[Dict], route2: List[Dict]) -> bool:
        """
        Check if two route plans are the same.
        
        Args:
            route1: First route plan
            route2: Second route plan
            
        Returns:
            True if routes are equivalent
        """
        if len(route1) != len(route2):
            return False
        
        for stop1, stop2 in zip(route1, route2):
            if (stop1["station_id"] != stop2["station_id"] or
                stop1["action"] != stop2["action"] or
                set(stop1["passenger_ids"]) != set(stop2["passenger_ids"])):
                return False
        
        return True

    def _parse_time_to_seconds(self, time_str: str) -> float:
        """
        NEW: Parse time string to seconds from simulation start.
        
        Args:
            time_str: Time string in format "HH:MM:SS"
        
        Returns:
            Seconds from simulation start (00:00:00)
        
        Examples:
            "15:00:00" -> 54000.0 (15 hours * 3600)
            "17:30:00" -> 63000.0
        """
        try:
            parts = time_str.split(":")
            if len(parts) != 3:
                raise ValueError(f"Invalid time format: {time_str}")
            
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            
            total_seconds = hours * 3600 + minutes * 60 + seconds
            
            return float(total_seconds)
        
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing time string '{time_str}': {e}")
            raise ValueError(f"Invalid time format '{time_str}', expected HH:MM:SS")


    def _get_minibus_ratio_at_time(self, appear_time: float) -> float:
        """
        NEW: Get minibus passenger ratio based on time and configuration.
        
        Supports two modes:
        1. Schedule-based: Different ratios for different time periods
        2. Fixed: Single ratio for entire simulation
        
        Args:
            appear_time: Passenger appearance time (seconds from simulation start)
        
        Returns:
            Ratio of passengers that should use minibus (0.0 to 1.0)
        """
        # Check if schedule-based configuration exists
        schedule = self.config.get("minibus_passenger_ratio_schedule", None)
        
        if schedule is not None and len(schedule) > 0:
            # Schedule-based mode
            # Convert appear_time to absolute time for comparison
            absolute_time = self.simulation_start_time + timedelta(seconds=appear_time)
            absolute_seconds = (
                absolute_time.hour * 3600 + 
                absolute_time.minute * 60 + 
                absolute_time.second
            )
            
            # Find matching time period
            for period in schedule:
                start_time_str = period.get("start_time")
                end_time_str = period.get("end_time")
                ratio = period.get("ratio")
                
                if start_time_str is None or end_time_str is None or ratio is None:
                    logger.warning(f"Invalid schedule period: {period}, skipping")
                    continue
                
                try:
                    start_seconds = self._parse_time_to_seconds(start_time_str)
                    end_seconds = self._parse_time_to_seconds(end_time_str)
                    
                    # Check if absolute_seconds falls within this period
                    if start_seconds <= absolute_seconds < end_seconds:
                        logger.debug(
                            f"Passenger at {appear_time:.1f}s ({absolute_time.strftime('%H:%M:%S')}) "
                            f"matches period {start_time_str}-{end_time_str}, ratio={ratio}"
                        )
                        return float(ratio)
                
                except ValueError as e:
                    logger.warning(f"Error parsing time period {period}: {e}")
                    continue
            
            # If no matching period found, use default
            logger.debug(
                f"No matching schedule period for time {appear_time:.1f}s, "
                f"using default ratio"
            )
            default_ratio = self.config.get("minibus_passenger_ratio", 0.3)
            return float(default_ratio)
        
        else:
            # Fixed ratio mode
            fixed_ratio = self.config.get("minibus_passenger_ratio", 0.3)
            logger.debug(f"Using fixed minibus ratio: {fixed_ratio}")
            return float(fixed_ratio)

    def _get_bus_location(self, bus: Bus) -> str:

            if bus.is_at_terminal():

                if len(bus.route) > 0:
                    return f"TERMINAL_{bus.route[-1]}"
                else:
                    return "TERMINAL"
            elif bus.current_route_index == 0:

                if len(bus.route) > 0:
                    return f"START_{bus.route[0]}"
                else:
                    return "START"
            else:

                return bus.route[bus.current_route_index - 1]
        
    
    def handle_periodic_sample(self, event: Event) -> None:

        try:
            sampling_count = 0
            
            # Bus
            for bus_id, bus in self.buses.items():
                location = self._get_bus_location(bus)
                self.statistics.record_vehicle_state_periodic(
                    vehicle_id=bus_id,
                    current_time=self.current_time,
                    occupancy=bus.get_occupancy(),
                    location=location,
                    vehicle_type="Bus"
                )
                sampling_count += 1
            
            # Minibus
            for minibus_id, minibus in self.minibuses.items():
                self.statistics.record_vehicle_state_periodic(
                    vehicle_id=minibus_id,
                    current_time=self.current_time,
                    occupancy=minibus.get_occupancy(),
                    location=minibus.current_location_id,
                    vehicle_type="Minibus"
                )
                sampling_count += 1
            
            logger.debug(
                f"Periodic sampling complete: sampled {sampling_count} vehicles "
                f"at {self.current_time}s"
            )
            
            # next sampling
            sampling_interval = self.config.get("sampling_interval", 30.0)
            next_sample_time = self.current_time + sampling_interval
            
            if next_sample_time < self.duration:
                self.add_event(Event(
                    time=next_sample_time,
                    event_type=Event.PERIODIC_SAMPLE,
                    data={}
                ))
                logger.debug(f"Scheduled next periodic sampling at {next_sample_time}s")
        
        except Exception as e:
            logger.error(f"Error in periodic sampling: {e}", exc_info=True)