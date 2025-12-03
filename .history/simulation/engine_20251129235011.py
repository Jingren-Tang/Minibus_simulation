"""
simulation/engine.py

Core simulation engine for the mixed traffic simulation system.
Implements discrete event simulation to drive buses and manage passengers.
"""

import heapq
import logging
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from event import Event
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from network.station import Station
from network.network import TransitNetwork
from demand.passenger import Passenger
from vehicles.bus import Bus

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
        event_queue: Priority queue of events (using heapq)
        network: Transit network object containing stations and travel times
        buses: Dictionary of all buses {bus_id: Bus object}
        minibuses: Dictionary of all minibuses (stage 4)
        all_passengers: Record of all passengers {passenger_id: Passenger object}
        pending_requests: Pool of unassigned passenger requests
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
        
        # Statistics collector (stage 6)
        self.statistics = None
        
        logger.info(
            f"SimulationEngine initialized. "
            f"Start: {self.simulation_start_time}, "
            f"End: {self.simulation_end_time}, "
            f"Duration: {(self.simulation_end_time - self.simulation_start_time).total_seconds()}s"
        )
    
    def initialize(self) -> None:
        """
        Core initialization method. Loads network, creates vehicles, and sets up initial events.
        
        Steps:
            1. Load transit network
            2. Load and create buses from schedule
            3. Add initial bus arrival events
            4. Add test passengers (stage 5 will use demand generator)
            5. Add simulation end event
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
        
        # Step 2: Load and create buses
        logger.info("Loading buses from schedule...")
        self.buses = self._load_buses_from_schedule()
        logger.info(f"Loaded {len(self.buses)} buses")
        
        # Step 3: Add initial bus arrival events
        logger.info("Adding initial bus arrival events...")
        for bus_id, bus in self.buses.items():
            if bus.next_arrival_time is not None:
                self.add_event(Event(
                    time=bus.next_arrival_time,
                    event_type=Event.BUS_ARRIVAL,
                    data={"bus_id": bus_id}
                ))
                logger.debug(f"Added initial arrival event for {bus_id} at {bus.next_arrival_time}s")
        
        # Step 4: Add test passengers (temporary, stage 5 will use demand generator)
        logger.info("Adding test passengers...")
        self._add_test_passengers()
        
        # Step 5: Add simulation end event
        end_time_seconds = (self.simulation_end_time - self.simulation_start_time).total_seconds()
        self.add_event(Event(
            time=end_time_seconds,
            event_type=Event.SIMULATION_END,
            data={}
        ))
        logger.info(f"Added simulation end event at {end_time_seconds}s")
        
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
    
    def _add_test_passengers(self) -> None:
        """
        Temporary method to manually add test passengers.
        
        This will be replaced by demand generator in stage 5.
        Creates 5 test passengers with different origins, destinations, and appear times.
        """
        test_passengers_data = [
            {"id": "P1", "origin": "A", "dest": "C", "appear_time": 100.0},
            {"id": "P2", "origin": "B", "dest": "D", "appear_time": 300.0},
            {"id": "P3", "origin": "A", "dest": "D", "appear_time": 500.0},
            {"id": "P4", "origin": "C", "dest": "E", "appear_time": 700.0},
            {"id": "P5", "origin": "E", "dest": "A", "appear_time": 900.0}
        ]
        
        for pax_data in test_passengers_data:
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
        
        logger.info(f"Added {len(test_passengers_data)} test passengers")
    
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
            boarded, alighted = bus.arrive_at_station(station, self.current_time)
            
            # Update station waiting passengers (remove boarded passengers)
            for passenger in boarded:
                station.remove_waiting_passenger(passenger)
                # Remove from pending requests if present
                if passenger in self.pending_requests:
                    self.pending_requests.remove(passenger)
            
            # Log boarding and alighting
            logger.info(
                f"Bus {bus_id} at {station.station_id}: "
                f"{len(boarded)} boarded, {len(alighted)} alighted, "
                f"occupancy: {len(bus.passengers)}/{bus.capacity}"  # Changed here
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
                # Optional: Reset bus to start of route for循环运行
                # bus.reset_to_start()
                # self.add_event(Event(...))
        
        except Exception as e:
            logger.error(f"Error handling bus arrival for {bus_id}: {e}", exc_info=True)
    
    def handle_passenger_appear(self, event: Event) -> None:
        """
        Handle passenger appearance in the system.
        
        Steps:
            1. Create Passenger object
            2. Add to all_passengers dictionary
            3. Add to pending_requests list
            4. Add to origin station's waiting list
        
        Args:
            event: Passenger appear event containing passenger data
        """
        try:
            # Extract passenger data
            pax_id = event.data["id"]
            origin = event.data["origin"]
            destination = event.data["dest"]
            
            # Create Passenger object
            passenger = Passenger(
                passenger_id=pax_id,
                origin=origin,
                destination=destination,
                appear_time=self.current_time,
                max_wait_time=self.config.get("passenger_max_wait_time", 900.0)
            )
            
            # Add to tracking structures
            self.all_passengers[pax_id] = passenger
            self.pending_requests.append(passenger)
            
            # Add to origin station's waiting list
            station = self.network.get_station(origin)
            if station is None:
                logger.error(f"Origin station {origin} not found for passenger {pax_id}")
                return
            
            station.add_waiting_passenger(passenger)
            
            logger.info(
                f"Passenger {pax_id} appeared at station {origin}, "
                f"destination {destination}, time {self._seconds_to_time_str(self.current_time)}"
            )
            logger.debug(f"Total passengers: {len(self.all_passengers)}, Pending: {len(self.pending_requests)}")
        
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
                f"current occupancy: {bus.current_occupancy}"
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