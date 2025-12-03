"""
Passenger module for mixed traffic simulation system.

This module implements the Passenger class representing individual travel demand
in a simulation containing both fixed-route buses and flexible-route minibuses.

State Machine:
    WAITING --> ASSIGNED --> ONBOARD --> ARRIVED
         |
         └-----> ABANDONED
         
    Valid transitions:
    - WAITING -> ASSIGNED (when vehicle assigned)
    - WAITING -> ABANDONED (when timeout)
    - WAITING -> ONBOARD (direct boarding without assignment)
    - ASSIGNED -> ONBOARD (when boarding)
    - ASSIGNED -> ABANDONED (when timeout before boarding)
    - ONBOARD -> ARRIVED (when reaching destination)
"""

import logging
from typing import Optional, Dict, Any

# Configure logger
logger = logging.getLogger(__name__)


class Passenger:
    """
    Represents a passenger with travel demand in the simulation.
    
    Tracks passenger lifecycle from appearance through waiting, boarding,
    and arrival or abandonment. Maintains timing information for statistical
    analysis.
    
    Attributes:
        passenger_id: Unique identifier for the passenger
        origin_station_id: ID of the origin station
        destination_station_id: ID of the destination station
        appear_time: Time when passenger appears at station (simulation seconds)
        max_wait_time: Maximum willing to wait (seconds), e.g., 900s = 15min
        status: Current status (one of the status constants)
        assigned_vehicle_id: ID of assigned vehicle (if any)
        pickup_time: Time when passenger boarded (if boarded)
        arrival_time: Time when passenger arrived at destination (if arrived)
    """
    
    # Status constants
    WAITING = "WAITING"        # Waiting at station
    ASSIGNED = "ASSIGNED"      # Assigned to vehicle but not yet boarded
    ONBOARD = "ONBOARD"        # On board the vehicle
    ARRIVED = "ARRIVED"        # Arrived at destination
    ABANDONED = "ABANDONED"    # Gave up waiting (timeout)
    
    def __init__(
        self,
        passenger_id: str,
        origin: str,
        destination: str,
        appear_time: float,
        max_wait_time: float
    ) -> None:
        """
        Initialize a new passenger.
        
        Args:
            passenger_id: Unique identifier for the passenger
            origin: Origin station ID
            destination: Destination station ID
            appear_time: Time when passenger appears (simulation seconds)
            max_wait_time: Maximum willing to wait (seconds)
            
        Raises:
            ValueError: If origin equals destination, appear_time < 0,
                       or max_wait_time <= 0
        """
        # Validation
        if origin == destination:
            raise ValueError(
                f"Origin and destination cannot be the same: {origin}"
            )
        if appear_time < 0:
            raise ValueError(
                f"Appear time must be non-negative, got: {appear_time}"
            )
        if max_wait_time <= 0:
            raise ValueError(
                f"Max wait time must be positive, got: {max_wait_time}"
            )
        
        # Basic attributes
        self.passenger_id = passenger_id
        self.origin_station_id = origin
        self.destination_station_id = destination
        self.appear_time = appear_time
        self.max_wait_time = max_wait_time
        
        # State tracking
        self.status = self.WAITING
        self.assigned_vehicle_id: Optional[str] = None
        self.pickup_time: Optional[float] = None
        self.arrival_time: Optional[float] = None
        
        logger.info(
            f"Passenger {passenger_id} created: {origin} -> {destination}, "
            f"appear_time={appear_time:.1f}s, max_wait={max_wait_time:.1f}s"
        )
    
    def assign_to_vehicle(self, vehicle_id: str, current_time: float) -> None:
        """
        Assign passenger to a vehicle.
        
        Args:
            vehicle_id: ID of the vehicle to assign
            current_time: Current simulation time
            
        Raises:
            ValueError: If current status is not WAITING or if current_time
                       is before appear_time
        """
        if self.status != self.WAITING:
            raise ValueError(
                f"Cannot assign passenger {self.passenger_id}: "
                f"invalid status {self.status}, must be {self.WAITING}"
            )
        
        if current_time < self.appear_time:
            raise ValueError(
                f"Current time {current_time:.1f} is before appear time "
                f"{self.appear_time:.1f}"
            )
        
        self.status = self.ASSIGNED
        self.assigned_vehicle_id = vehicle_id
        
        logger.info(
            f"Passenger {self.passenger_id} assigned to vehicle {vehicle_id} "
            f"at time {current_time:.1f}s"
        )
    
    def board_vehicle(self, current_time: float) -> None:
        """
        Passenger boards the vehicle.
        
        Args:
            current_time: Current simulation time
            
        Raises:
            ValueError: If current status is not ASSIGNED or WAITING,
                       or if current_time is invalid
        """
        if self.status not in (self.ASSIGNED, self.WAITING):
            raise ValueError(
                f"Cannot board passenger {self.passenger_id}: "
                f"invalid status {self.status}, must be {self.ASSIGNED} "
                f"or {self.WAITING}"
            )
        
        if current_time < self.appear_time:
            raise ValueError(
                f"Current time {current_time:.1f} is before appear time "
                f"{self.appear_time:.1f}"
            )
        
        self.status = self.ONBOARD
        self.pickup_time = current_time
        
        logger.info(
            f"Passenger {self.passenger_id} boarded vehicle "
            f"{self.assigned_vehicle_id or 'unknown'} at time {current_time:.1f}s, "
            f"wait_time={current_time - self.appear_time:.1f}s"
        )
    
    def arrive_at_destination(self, current_time: float) -> None:
        """
        Passenger arrives at destination.
        
        Args:
            current_time: Current simulation time
            
        Raises:
            ValueError: If current status is not ONBOARD or if current_time
                       is before pickup_time
        """
        if self.status != self.ONBOARD:
            raise ValueError(
                f"Cannot complete arrival for passenger {self.passenger_id}: "
                f"invalid status {self.status}, must be {self.ONBOARD}"
            )
        
        if self.pickup_time is None:
            raise ValueError(
                f"Passenger {self.passenger_id} has no pickup time recorded"
            )
        
        if current_time < self.pickup_time:
            raise ValueError(
                f"Current time {current_time:.1f} is before pickup time "
                f"{self.pickup_time:.1f}"
            )
        
        self.status = self.ARRIVED
        self.arrival_time = current_time
        
        travel_time = current_time - self.pickup_time
        total_time = current_time - self.appear_time
        
        logger.info(
            f"Passenger {self.passenger_id} arrived at destination "
            f"at time {current_time:.1f}s, travel_time={travel_time:.1f}s, "
            f"total_time={total_time:.1f}s"
        )
    
    def abandon(self, current_time: float) -> None:
        """
        Passenger abandons waiting (timeout).
        
        Args:
            current_time: Current simulation time
            
        Raises:
            ValueError: If current status is not WAITING or ASSIGNED
        """
        if self.status not in (self.WAITING, self.ASSIGNED):
            raise ValueError(
                f"Cannot abandon passenger {self.passenger_id}: "
                f"invalid status {self.status}, must be {self.WAITING} "
                f"or {self.ASSIGNED}"
            )
        
        if current_time < self.appear_time:
            raise ValueError(
                f"Current time {current_time:.1f} is before appear time "
                f"{self.appear_time:.1f}"
            )
        
        wait_time = current_time - self.appear_time
        self.status = self.ABANDONED
        
        logger.warning(
            f"Passenger {self.passenger_id} abandoned waiting at time "
            f"{current_time:.1f}s after waiting {wait_time:.1f}s "
            f"(max_wait={self.max_wait_time:.1f}s)"
        )
    
    def check_timeout(self, current_time: float) -> bool:
        """
        Check if passenger has exceeded maximum wait time.
        
        Does not change passenger state - caller must decide whether to
        call abandon().
        
        Args:
            current_time: Current simulation time
            
        Returns:
            True if passenger has waited longer than max_wait_time and is
            still waiting, False otherwise
        """
        if self.status != self.WAITING:
            return False
        
        wait_time = current_time - self.appear_time
        return wait_time > self.max_wait_time
    
    def get_wait_time(self, current_time: float) -> float:
        """
        Calculate waiting time (from appearance to boarding).
        
        Args:
            current_time: Current simulation time (used if not yet boarded)
            
        Returns:
            Wait time in seconds. If already boarded, returns actual wait time.
            If not yet boarded, returns time waited so far. If abandoned,
            returns wait time at abandonment.
        """
        if self.pickup_time is not None:
            # Already boarded - return actual wait time
            return self.pickup_time - self.appear_time
        else:
            # Not yet boarded - return current wait time
            return current_time - self.appear_time
    
    def get_travel_time(self) -> Optional[float]:
        """
        Calculate travel time (from boarding to arrival).
        
        Returns:
            Travel time in seconds if passenger has arrived, None otherwise
        """
        if self.pickup_time is None or self.arrival_time is None:
            return None
        
        return self.arrival_time - self.pickup_time
    
    def get_total_time(self) -> Optional[float]:
        """
        Calculate total time (from appearance to arrival).
        
        Returns:
            Total time in seconds if passenger has arrived, None otherwise
        """
        if self.arrival_time is None:
            return None
        
        return self.arrival_time - self.appear_time
    
    def is_waiting(self) -> bool:
        """
        Check if passenger is waiting.
        
        Returns:
            True if status is WAITING, False otherwise
        """
        return self.status == self.WAITING
    
    def is_onboard(self) -> bool:
        """
        Check if passenger is on board a vehicle.
        
        Returns:
            True if status is ONBOARD, False otherwise
        """
        return self.status == self.ONBOARD
    
    def is_completed(self) -> bool:
        """
        Check if passenger has completed their journey (arrived or abandoned).
        
        Returns:
            True if status is ARRIVED or ABANDONED, False otherwise
        """
        return self.status in (self.ARRIVED, self.ABANDONED)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert passenger to dictionary for statistics and serialization.
        
        Returns:
            Dictionary containing all passenger attributes and derived metrics
        """
        result = {
            'passenger_id': self.passenger_id,
            'origin_station_id': self.origin_station_id,
            'destination_station_id': self.destination_station_id,
            'appear_time': self.appear_time,
            'max_wait_time': self.max_wait_time,
            'status': self.status,
            'assigned_vehicle_id': self.assigned_vehicle_id,
            'pickup_time': self.pickup_time,
            'arrival_time': self.arrival_time,
        }
        
        # Add derived metrics
        if self.pickup_time is not None:
            result['actual_wait_time'] = self.pickup_time - self.appear_time
        
        travel_time = self.get_travel_time()
        if travel_time is not None:
            result['travel_time'] = travel_time
        
        total_time = self.get_total_time()
        if total_time is not None:
            result['total_time'] = total_time
        
        return result
    
    def __repr__(self) -> str:
        """
        Return readable string representation.
        
        Returns:
            String in format: Passenger(id=P1, A->B, status=ONBOARD)
        """
        return (
            f"Passenger(id={self.passenger_id}, "
            f"{self.origin_station_id}->{self.destination_station_id}, "
            f"status={self.status})"
        )