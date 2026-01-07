"""
vehicles/minibus.py - ENHANCED WITH LAYER 3 DEFENSE

LAYER 3: Defensive execution at the vehicle level.
This ensures that even if invalid route plans are received,
the minibus will not execute impossible operations.

Key enhancements:
1. execute_dropoff validates passengers are actually onboard
2. execute_pickup validates capacity before boarding
3. Detailed logging for all operations
"""

import logging
from typing import List, Dict, Optional, Any

from demand.passenger import Passenger
from network.station import Station
from network.network import TransitNetwork

logger = logging.getLogger(__name__)

DEBUG_LOG_FILE = "minibus_travel_debug.txt"


def init_debug_log():
    """Initialize debug log file."""
    with open(DEBUG_LOG_FILE, 'w') as f:
        f.write("="*80 + "\n")
        f.write("MINIBUS TRAVEL TIME DEBUG LOG\n")
        f.write("="*80 + "\n\n")


def log_travel_calculation(minibus_id, method, from_station, to_station, 
                          travel_time, current_time, next_arrival, occupancy, capacity):
    """Write travel time calculation to log file."""
    with open(DEBUG_LOG_FILE, 'a') as f:
        f.write(f"[{method:15}] {minibus_id}: {from_station:>10} -> {to_station:<10} | "
                f"travel={travel_time:>6.1f}s | occ={occupancy:>2}/{capacity} | "
                f"t={current_time:>7.1f}s | arrive={next_arrival:>7.1f}s\n")


class Minibus:
    """
    Represents a minibus with flexible routing and defensive execution.
    
    LAYER 3 DEFENSE: All execute_* methods validate state before performing actions.
    """
    
    # Status constants
    IDLE = "IDLE"
    EN_ROUTE = "EN_ROUTE"
    SERVING = "SERVING"
    
    # Action constants
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    
    def __init__(
        self, 
        minibus_id: str, 
        capacity: int, 
        initial_location: str,
        network: TransitNetwork
    ):
        """Initialize a new Minibus instance."""
        if capacity <= 0:
            raise ValueError(f"Capacity must be positive, got {capacity}")
        
        self.minibus_id = minibus_id
        self.capacity = capacity
        self.current_location_id = initial_location
        self.passengers: List[Passenger] = []
        self.route_plan: List[Dict[str, Any]] = []
        self.status = self.IDLE
        self.next_station_id: Optional[str] = None
        self.next_arrival_time: Optional[float] = None
        self.total_distance = 0.0
        self.idle_time = 0.0
        self.network = network
        
        # Performance tracking
        self.total_passengers_served = 0
        self.total_distance_traveled = 0.0
        self.total_service_time = 0.0
        
        logger.info(
            f"Initialized {self.minibus_id} with capacity={capacity} "
            f"at location={initial_location}"
        )
        
        # Initialize debug log (only for first minibus)
        if minibus_id == "MINIBUS_1":
            init_debug_log()
    
    def update_route_plan(
        self, 
        new_plan: List[Dict[str, Any]], 
        current_time: float
    ) -> None:
        """
        Update the minibus route plan with validation.
        
        Args:
            new_plan: New route plan from optimizer
            current_time: Current simulation time
            
        Raises:
            ValueError: If route plan format is invalid
        """
        # Validate the new plan format
        if not self.validate_route_plan(new_plan):
            raise ValueError(f"Invalid route plan format for {self.minibus_id}")
        
        # Replace the route plan
        self.route_plan = new_plan.copy()
        
        logger.info(
            f"{self.minibus_id} received new route plan with {len(new_plan)} stops"
        )
        
        # Update next station and status
        if len(self.route_plan) > 0:
            self.next_station_id = self.route_plan[0]["station_id"]
            
            # Query travel time
            travel_time = self.network.get_travel_time(
                self.current_location_id,
                self.next_station_id,
                current_time
            )
            
            # Track distance
            distance = (travel_time / 3600) * 30  # Assuming 30 km/h
            self.total_distance_traveled += distance
            
            # Calculate arrival time
            self.next_arrival_time = current_time + travel_time
            self.status = self.EN_ROUTE
            
            # Debug logging
            log_travel_calculation(
                self.minibus_id, 
                "UPDATE_ROUTE",
                self.current_location_id,
                self.next_station_id,
                travel_time,
                current_time,
                self.next_arrival_time,
                self.get_occupancy(),
                self.capacity
            )
            
            logger.info(
                f"{self.minibus_id} en route to {self.next_station_id}, "
                f"ETA={self.next_arrival_time:.2f}s"
            )
        else:
            # Empty plan - become idle
            self.next_station_id = None
            self.next_arrival_time = None
            self.status = self.IDLE
            
            logger.info(f"{self.minibus_id} has empty route plan, now IDLE")
    
    def arrive_at_station(
        self, 
        station: Station,
        current_time: float
    ) -> Dict[str, Any]:
        """
        Process arrival at a station and execute planned actions.
        
        Args:
            station: The station object where the minibus arrived
            current_time: Current simulation time
            
        Returns:
            Dictionary containing boarded and alighted passengers
            
        Raises:
            ValueError: If arrival station doesn't match expected station
        """
        # Verify this is the expected station
        if station.station_id != self.next_station_id:
            raise ValueError(
                f"{self.minibus_id} arrived at {station.station_id} but "
                f"expected {self.next_station_id}"
            )
        
        # Update current location
        self.current_location_id = station.station_id
        self.status = self.SERVING
        
        logger.info(
            f"{self.minibus_id} arrived at {station.station_id} "
            f"at time={current_time:.2f}s"
        )
        
        # Get the current station's plan
        if not self.route_plan:
            raise ValueError(f"{self.minibus_id} has empty route_plan at arrival")
        
        current_stop = self.route_plan[0]
        action_type = current_stop["action"]
        passenger_ids = current_stop["passenger_ids"]
        
        # Execute the action with defensive validation
        boarded = []
        alighted = []
        
        if action_type == self.PICKUP:
            boarded = self.execute_pickup(passenger_ids, station, current_time)
            logger.info(
                f"{self.minibus_id} picked up {len(boarded)}/{len(passenger_ids)} "
                f"passengers at {station.station_id}"
            )
        elif action_type == self.DROPOFF:
            alighted = self.execute_dropoff(passenger_ids, current_time)
            logger.info(
                f"{self.minibus_id} dropped off {len(alighted)}/{len(passenger_ids)} "
                f"passengers at {station.station_id}"
            )
        else:
            logger.error(f"Unknown action type: {action_type}")
        
        # Remove this stop from the route plan
        self.route_plan.pop(0)
        
        # Update next station and status
        if len(self.route_plan) > 0:
            self.next_station_id = self.route_plan[0]["station_id"]
            
            # Query travel time
            travel_time = self.network.get_travel_time(
                self.current_location_id,
                self.next_station_id,
                current_time
            )
            
            # Track distance
            distance = (travel_time / 3600) * 30
            self.total_distance_traveled += distance
            
            # Calculate next arrival time
            self.next_arrival_time = current_time + travel_time
            self.status = self.EN_ROUTE
            
            # Debug logging
            log_travel_calculation(
                self.minibus_id,
                "ARRIVE",
                self.current_location_id,
                self.next_station_id,
                travel_time,
                current_time,
                self.next_arrival_time,
                self.get_occupancy(),
                self.capacity
            )
            
            logger.info(
                f"{self.minibus_id} proceeding to {self.next_station_id}, "
                f"ETA={self.next_arrival_time:.2f}s"
            )
        else:
            # No more stops - become idle
            self.next_station_id = None
            self.next_arrival_time = None
            self.status = self.IDLE
            
            logger.info(f"{self.minibus_id} completed route plan, now IDLE")
        
        return {
            "boarded": boarded,
            "alighted": alighted,
            "action_type": action_type
        }
    
    def execute_pickup(
        self, 
        passenger_ids: List[str], 
        station: Station,
        current_time: float
    ) -> List[Passenger]:
        """
        LAYER 3 DEFENSE: Execute pickup with validation.
        
        Validates:
        1. Vehicle is not at capacity
        2. Passenger exists at the station
        3. No duplicate passenger boarding
        
        Args:
            passenger_ids: List of passenger IDs to pick up
            station: Station where pickup occurs
            current_time: Current simulation time
            
        Returns:
            List of passengers that successfully boarded
        """
        boarded_passengers = []
        
        # Get set of passengers already onboard for duplicate check
        onboard_ids = {p.passenger_id for p in self.passengers}
        
        for passenger_id in passenger_ids:
            # CHECK 1: Capacity constraint
            if self.is_full():
                logger.warning(
                    f"❌ {self.minibus_id} is full ({len(self.passengers)}/{self.capacity}), "
                    f"cannot pick up {passenger_id}"
                )
                continue
            
            # CHECK 2: Passenger already onboard
            if passenger_id in onboard_ids:
                logger.error(
                    f"❌ {self.minibus_id}: Passenger {passenger_id} ALREADY onboard! "
                    f"Skipping duplicate pickup."
                )
                continue
            
            # CHECK 3: Find passenger at station
            passenger = None
            for p in station.waiting_passengers:
                if p.passenger_id == passenger_id:
                    passenger = p
                    break
            
            if passenger is None:
                logger.warning(
                    f"❌ Passenger {passenger_id} not found at station {station.station_id}, "
                    f"may have been picked up by another vehicle or timed out"
                )
                continue
            
            # All checks passed - board the passenger
            if passenger.assigned_vehicle_id is None:
                passenger.assigned_vehicle_id = self.minibus_id
            
            passenger.board_vehicle(current_time)
            self.passengers.append(passenger)
            station.waiting_passengers.remove(passenger)
            boarded_passengers.append(passenger)
            onboard_ids.add(passenger_id)  # Update tracking set
            
            self.total_passengers_served += 1
            
            logger.debug(
                f"✅ Passenger {passenger_id} boarded {self.minibus_id} "
                f"at {station.station_id} (occupancy: {len(self.passengers)}/{self.capacity})"
            )
        
        return boarded_passengers
    
    def execute_dropoff(
        self, 
        passenger_ids: List[str], 
        current_time: float
    ) -> List[Passenger]:
        """
        LAYER 3 DEFENSE: Execute dropoff with validation.
        
        Validates:
        1. Passenger is actually onboard
        2. No duplicate dropoff
        
        This is the CRITICAL function where negative occupancy was happening!
        
        Args:
            passenger_ids: List of passenger IDs to drop off
            current_time: Current simulation time
            
        Returns:
            List of passengers that successfully alighted
        """
        alighted_passengers = []
        
        # Create set of passengers currently onboard for efficient lookup
        passengers_onboard = {p.passenger_id: p for p in self.passengers}
        
        logger.debug(
            f"{self.minibus_id} attempting dropoff at {self.current_location_id}: "
            f"requested={passenger_ids}, onboard={list(passengers_onboard.keys())}"
        )
        
        for passenger_id in passenger_ids:
            # CHECK: Passenger must be onboard
            if passenger_id not in passengers_onboard:
                logger.error(
                    f"❌ {self.minibus_id}: Cannot dropoff {passenger_id} - "
                    f"NOT ONBOARD! Current passengers: {list(passengers_onboard.keys())}"
                )
                # CRITICAL: Do NOT execute the dropoff
                continue
            
            # Passenger is onboard - proceed with dropoff
            passenger = passengers_onboard[passenger_id]
            
            passenger.arrive_at_destination(current_time)
            self.passengers.remove(passenger)
            alighted_passengers.append(passenger)
            
            logger.debug(
                f"✅ Passenger {passenger_id} alighted from {self.minibus_id} "
                f"at {self.current_location_id} (occupancy: {len(self.passengers)}/{self.capacity})"
            )
        
        # Report if some dropoffs failed
        failed_count = len(passenger_ids) - len(alighted_passengers)
        if failed_count > 0:
            logger.warning(
                f"⚠️  {self.minibus_id}: {failed_count}/{len(passenger_ids)} "
                f"dropoffs FAILED due to passengers not being onboard"
            )
        
        return alighted_passengers
    
    def is_available(self) -> bool:
        """Check if the minibus is available for new task assignment."""
        return self.status == self.IDLE or len(self.route_plan) == 0
    
    def is_full(self) -> bool:
        """Check if the minibus is at full capacity."""
        return len(self.passengers) >= self.capacity
    
    def get_occupancy(self) -> int:
        """Get the current number of passengers on board."""
        return len(self.passengers)
    
    def get_remaining_capacity(self) -> int:
        """Get the remaining passenger capacity."""
        return self.capacity - len(self.passengers)
    
    def get_assigned_passenger_ids(self) -> List[str]:
        """
        Get all passenger IDs assigned to this minibus.
        
        Returns:
            List of passenger IDs (onboard + in route plan)
        """
        assigned_ids = set()
        
        # Add passengers already on board
        for passenger in self.passengers:
            assigned_ids.add(passenger.passenger_id)
        
        # Add passengers in route plan
        for stop in self.route_plan:
            assigned_ids.update(stop["passenger_ids"])
        
        return list(assigned_ids)
    
    def validate_route_plan(self, plan: List[Dict[str, Any]]) -> bool:
        """
        Validate that a route plan has the correct format.
        
        Args:
            plan: Route plan to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(plan, list):
            logger.error("Route plan must be a list")
            return False
        
        for i, stop in enumerate(plan):
            if not isinstance(stop, dict):
                logger.error(f"Stop {i} is not a dictionary")
                return False
            
            # Check required fields
            required_fields = ["station_id", "action", "passenger_ids"]
            for field in required_fields:
                if field not in stop:
                    logger.error(f"Stop {i} missing '{field}' field")
                    return False
            
            # Validate action type
            if stop["action"] not in [self.PICKUP, self.DROPOFF]:
                logger.error(
                    f"Stop {i} has invalid action '{stop['action']}', "
                    f"must be '{self.PICKUP}' or '{self.DROPOFF}'"
                )
                return False
            
            # Validate passenger_ids is a list
            if not isinstance(stop["passenger_ids"], list):
                logger.error(f"Stop {i} 'passenger_ids' must be a list")
                return False
        
        return True
    
    def get_current_task(self) -> Optional[Dict[str, Any]]:
        """Get the current task being executed."""
        if len(self.route_plan) > 0:
            return self.route_plan[0].copy()
        return None
    
    def get_minibus_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the minibus current state.
        
        Returns:
            Dictionary containing all relevant minibus state information
        """
        return {
            "minibus_id": self.minibus_id,
            "capacity": self.capacity,
            "current_location_id": self.current_location_id,
            "status": self.status,
            "occupancy": self.get_occupancy(),
            "remaining_capacity": self.get_remaining_capacity(),
            "passenger_ids": [p.passenger_id for p in self.passengers],
            "route_plan": self.route_plan.copy(),
            "next_station_id": self.next_station_id,
            "next_arrival_time": self.next_arrival_time,
            "total_distance": self.total_distance,
            "idle_time": self.idle_time,
            "is_available": self.is_available(),
            "assigned_passenger_ids": self.get_assigned_passenger_ids(),
            "total_passengers_served": self.total_passengers_served,
            "total_distance_traveled": self.total_distance_traveled
        }
    
    def __repr__(self) -> str:
        """Return a concise string representation of the minibus."""
        next_info = ""
        if self.next_station_id:
            next_info = f", next={self.next_station_id}"
            if self.next_arrival_time:
                next_info += f"@{self.next_arrival_time:.0f}s"
        
        return (
            f"Minibus(id={self.minibus_id}, at={self.current_location_id}, "
            f"status={self.status}, occupancy={self.get_occupancy()}/{self.capacity}"
            f"{next_info})"
        )