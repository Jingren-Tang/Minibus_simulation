"""
Minibus module for flexible route transit simulation.

This module implements the Minibus class, which represents a demand-responsive
minibus vehicle with dynamic routing capabilities.
"""

import logging
from typing import List, Dict, Optional, Any

# Import dependencies from other modules
from demand.passenger import Passenger
from network.station import Station
from network.network import TransitNetwork

# Configure logging
logger = logging.getLogger(__name__)


class Minibus:
    """
    Represents a minibus with flexible routing in a transit simulation system.
    
    The minibus follows a dynamic route_plan that is updated by an external
    optimizer. It can pick up and drop off passengers at various stations
    according to the plan.
    
    Attributes:
        minibus_id (str): Unique identifier for the minibus (e.g., "MINIBUS_1")
        capacity (int): Maximum passenger capacity (typically 6-8)
        current_location_id (str): Current station ID where the minibus is located
        passengers (List[Passenger]): List of Passenger objects currently on board
        route_plan (List[Dict]): Ordered list of stations to visit with actions
        status (str): Current operational status (IDLE, EN_ROUTE, SERVING)
        next_station_id (Optional[str]): ID of the next station to visit
        next_arrival_time (Optional[float]): Expected arrival time at next station
        total_distance (float): Cumulative distance traveled
        idle_time (float): Cumulative idle time
        network (TransitNetwork): Reference to the transit network for travel time queries
        total_passengers_served (int): Total number of passengers served (for statistics)
        total_distance_traveled (float): Total distance traveled (for statistics)
        total_service_time (float): Total time spent in service (for statistics)
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
        """
        Initialize a new Minibus instance.
        
        Args:
            minibus_id (str): Unique identifier for the minibus
            capacity (int): Maximum passenger capacity
            initial_location (str): Initial station ID where minibus starts
            network (TransitNetwork): Transit network for travel time queries
            
        Raises:
            ValueError: If capacity is not positive
        """
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
        
        # Performance tracking attributes (for statistics)
        self.total_passengers_served = 0
        self.total_distance_traveled = 0.0
        self.total_service_time = 0.0
        
        logger.info(
            f"Initialized {self.minibus_id} with capacity={capacity} "
            f"at location={initial_location}"
        )
    
    def update_route_plan(
        self, 
        new_plan: List[Dict[str, Any]], 
        current_time: float
    ) -> None:
        """
        Update the minibus route plan with a new plan from the optimizer.
        
        This is a core method called by the external optimizer to assign new
        tasks to the minibus. It validates the plan, updates internal state,
        and calculates the next arrival time.
        
        Args:
            new_plan (List[Dict]): New route plan with station visits and actions.
                Each element should be: {
                    "station_id": str,
                    "action": "PICKUP" or "DROPOFF",
                    "passenger_ids": List[str]
                }
            current_time (float): Current simulation time
            
        Raises:
            ValueError: If the route plan format is invalid
        """
        # Validate the new plan format
        if not self.validate_route_plan(new_plan):
            raise ValueError(f"Invalid route plan format for {self.minibus_id}")
        
        # Replace the route plan
        self.route_plan = new_plan.copy()
        
        logger.info(
            f"{self.minibus_id} received new route plan with {len(new_plan)} stops"
        )
        
        # Update next station and status based on the plan
        if len(self.route_plan) > 0:
            # Get the first station in the plan
            self.next_station_id = self.route_plan[0]["station_id"]
            
            # Query travel time from current location to next station
            travel_time = self.network.get_travel_time(
                self.current_location_id,
                self.next_station_id,
                current_time
            )
            
            # Track distance traveled (estimate based on average speed)
            # Assuming average speed of 30 km/h
            distance = (travel_time / 3600) * 30  # Convert seconds to hours, multiply by speed
            self.total_distance_traveled += distance
            
            # Calculate arrival time
            self.next_arrival_time = current_time + travel_time
            self.status = self.EN_ROUTE
            
            logger.info(
                f"{self.minibus_id} en route to {self.next_station_id}, "
                f"ETA={self.next_arrival_time:.2f}s (travel_time={travel_time:.2f}s, "
                f"distance={distance:.2f}km)"
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
        
        This is a core method that handles the minibus arriving at a station,
        executing pickup/dropoff actions, and updating the route plan.
        
        Args:
            station (Station): The station object where the minibus arrived
            current_time (float): Current simulation time
            
        Returns:
            Dict containing:
                - "boarded": List of Passenger objects that boarded
                - "alighted": List of Passenger objects that alighted
                - "action_type": "PICKUP" or "DROPOFF"
                
        Raises:
            ValueError: If arrival station doesn't match expected next_station
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
            f"{self.minibus_id} arrived at {station.station_id} at time={current_time:.2f}s"
        )
        
        # Get the current station's plan (first element)
        if not self.route_plan:
            raise ValueError(f"{self.minibus_id} has empty route_plan at arrival")
        
        current_stop = self.route_plan[0]
        action_type = current_stop["action"]
        passenger_ids = current_stop["passenger_ids"]
        
        # Execute the action
        boarded = []
        alighted = []
        
        if action_type == self.PICKUP:
            boarded = self.execute_pickup(passenger_ids, station, current_time)
            logger.info(
                f"{self.minibus_id} picked up {len(boarded)} passengers at {station.station_id}"
            )
        elif action_type == self.DROPOFF:
            alighted = self.execute_dropoff(passenger_ids, current_time)
            logger.info(
                f"{self.minibus_id} dropped off {len(alighted)} passengers at {station.station_id}"
            )
        else:
            logger.error(f"Unknown action type: {action_type}")
        
        # Remove this stop from the route plan
        self.route_plan.pop(0)
        
        # Update next station and status
        if len(self.route_plan) > 0:
            # More stops remaining
            self.next_station_id = self.route_plan[0]["station_id"]
            
            # Query travel time to next station using stored network reference
            travel_time = self.network.get_travel_time(
                self.current_location_id,
                self.next_station_id,
                current_time
            )
            
            # Track distance traveled
            distance = (travel_time / 3600) * 30  # Assuming 30 km/h average speed
            self.total_distance_traveled += distance
            
            # Calculate next arrival time
            self.next_arrival_time = current_time + travel_time
            self.status = self.EN_ROUTE
            
            logger.info(
                f"{self.minibus_id} proceeding to next stop: {self.next_station_id}, "
                f"ETA={self.next_arrival_time:.2f}s (distance={distance:.2f}km)"
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
        Execute pickup operation for specified passengers.
        
        Args:
            passenger_ids (List[str]): IDs of passengers to pick up
            station (Station): Station where pickup occurs
            current_time (float): Current simulation time
            
        Returns:
            List of Passenger objects that successfully boarded
        """
        boarded_passengers = []
        
        for passenger_id in passenger_ids:
            # Check capacity
            if self.is_full():
                logger.warning(
                    f"{self.minibus_id} is full, cannot pick up {passenger_id}"
                )
                continue
            
            # Find passenger in station's waiting passengers
            passenger = None
            for p in station.waiting_passengers:
                if p.passenger_id == passenger_id:
                    passenger = p
                    break
            
            if passenger is None:
                logger.warning(
                    f"Passenger {passenger_id} not found at station {station.station_id}, "
                    f"may have been picked up by another vehicle"
                )
                continue
            
            # Assign vehicle to passenger if not already assigned
            if passenger.assigned_vehicle_id is None:
                passenger.assigned_vehicle_id = self.minibus_id
            
            # Board the passenger
            passenger.board_vehicle(current_time)
            self.passengers.append(passenger)
            station.waiting_passengers.remove(passenger)
            boarded_passengers.append(passenger)
            
            # Increment served counter
            self.total_passengers_served += 1
            
            logger.debug(
                f"Passenger {passenger_id} boarded {self.minibus_id} "
                f"at {station.station_id} (total served: {self.total_passengers_served})"
            )
        
        return boarded_passengers
    
    def execute_dropoff(
        self, 
        passenger_ids: List[str], 
        current_time: float
    ) -> List[Passenger]:
        """
        Execute dropoff operation for specified passengers.
        
        Args:
            passenger_ids (List[str]): IDs of passengers to drop off
            current_time (float): Current simulation time
            
        Returns:
            List of Passenger objects that successfully alighted
        """
        alighted_passengers = []
        
        for passenger_id in passenger_ids:
            # Find passenger on board
            passenger = None
            for p in self.passengers:
                if p.passenger_id == passenger_id:
                    passenger = p
                    break
            
            if passenger is None:
                logger.warning(
                    f"Passenger {passenger_id} not found on {self.minibus_id}, "
                    f"possible routing logic error"
                )
                continue
            
            # Alight the passenger
            passenger.arrive_at_destination(current_time)
            self.passengers.remove(passenger)
            alighted_passengers.append(passenger)
            
            logger.debug(
                f"Passenger {passenger_id} alighted from {self.minibus_id} "
                f"at {self.current_location_id}"
            )
        
        return alighted_passengers
    
    def is_available(self) -> bool:
        """
        Check if the minibus is available for new task assignment.
        
        Returns:
            bool: True if minibus is idle or has no route plan
        """
        return self.status == self.IDLE or len(self.route_plan) == 0
    
    def is_full(self) -> bool:
        """
        Check if the minibus is at full capacity.
        
        Returns:
            bool: True if current occupancy equals capacity
        """
        return len(self.passengers) >= self.capacity
    
    def get_occupancy(self) -> int:
        """
        Get the current number of passengers on board.
        
        Returns:
            int: Number of passengers currently on the minibus
        """
        return len(self.passengers)
    
    def get_remaining_capacity(self) -> int:
        """
        Get the remaining passenger capacity.
        
        Returns:
            int: Number of additional passengers that can board
        """
        return self.capacity - len(self.passengers)
    
    def get_assigned_passenger_ids(self) -> List[str]:
        """
        Get all passenger IDs assigned to this minibus in the route plan.
        
        This includes both passengers waiting to be picked up and passengers
        already on board waiting to be dropped off. Used to avoid duplicate
        assignments by the optimizer.
        
        Returns:
            List[str]: All passenger IDs in the current route plan
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
            plan (List[Dict]): Route plan to validate
            
        Returns:
            bool: True if plan is valid, False otherwise
        """
        if not isinstance(plan, list):
            logger.error("Route plan must be a list")
            return False
        
        for i, stop in enumerate(plan):
            if not isinstance(stop, dict):
                logger.error(f"Stop {i} is not a dictionary")
                return False
            
            # Check required fields
            if "station_id" not in stop:
                logger.error(f"Stop {i} missing 'station_id' field")
                return False
            
            if "action" not in stop:
                logger.error(f"Stop {i} missing 'action' field")
                return False
            
            if "passenger_ids" not in stop:
                logger.error(f"Stop {i} missing 'passenger_ids' field")
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
        """
        Get the current task being executed.
        
        Returns:
            Dict or None: The first stop in route_plan if exists, else None
        """
        if len(self.route_plan) > 0:
            return self.route_plan[0].copy()
        return None
    
    def get_minibus_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the minibus current state.
        
        This method is useful for optimizer input and logging/debugging.
        
        Returns:
            Dict containing all relevant minibus state information
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
    
    def visualize_route_plan(self) -> str:
        """
        Create a human-readable visualization of the route plan.
        
        Useful for debugging and logging.
        
        Returns:
            str: Formatted string showing the route plan
        """
        if not self.route_plan:
            return f"{self.minibus_id}: No route plan (IDLE)"
        
        route_str = f"{self.minibus_id} Route Plan:\n"
        route_str += f"  Current: {self.current_location_id} ({self.status})\n"
        
        for i, stop in enumerate(self.route_plan):
            arrow = "→" if i == 0 else " →"
            route_str += (
                f"  {arrow} {stop['station_id']}: "
                f"{stop['action']} {len(stop['passenger_ids'])} pax "
                f"[{', '.join(stop['passenger_ids'][:3])}"
                f"{'...' if len(stop['passenger_ids']) > 3 else ''}]\n"
            )
        
        return route_str
    
    def __repr__(self) -> str:
        """
        Return a concise string representation of the minibus.
        
        Returns:
            str: String in format "Minibus(id=M1, at=C, status=EN_ROUTE, 
                 occupancy=3/6, next=D@800s)"
        """
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