"""
Station module for the mixed traffic simulation system.

This module defines the Station class which represents transit stations where
passengers wait for vehicles (buses and minibuses).
"""

import logging
from threading import Lock
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from passenger import Passenger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Station:
    """
    Represents a station in the transportation network.
    
    A station is a node in the network where passengers wait for vehicles.
    Each station has a unique identifier, location, and maintains a queue
    of waiting passengers.
    
    Attributes:
        station_id (str): Unique identifier for the station (e.g., "A", "B").
        name (str): Human-readable name of the station.
        location (tuple): Immutable tuple of (latitude, longitude) coordinates.
        index (int): Index in the travel time matrix (0 to N-1).
        waiting_passengers (list): List of Passenger objects waiting at this station.
    """
    
    def __init__(self, station_id: str, name: str, location: tuple, index: int) -> None:
        """
        Initialize a new Station instance.
        
        Args:
            station_id (str): Unique identifier for the station.
            name (str): Human-readable name of the station.
            location (tuple): Tuple containing (latitude, longitude) as floats.
            index (int): Index position in the travel time matrix.
            
        Raises:
            ValueError: If location is not a tuple of two floats, or if index is negative.
            TypeError: If arguments are of incorrect type.
        """
        # Validate station_id
        if not isinstance(station_id, str) or not station_id:
            raise ValueError("station_id must be a non-empty string")
        
        # Validate name
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        
        # Validate location
        if not isinstance(location, tuple):
            raise TypeError("location must be a tuple")
        if len(location) != 2:
            raise ValueError("location must contain exactly 2 elements (latitude, longitude)")
        if not all(isinstance(coord, (int, float)) for coord in location):
            raise TypeError("location coordinates must be numeric (int or float)")
        
        # Validate index
        if not isinstance(index, int):
            raise TypeError("index must be an integer")
        if index < 0:
            raise ValueError("index must be non-negative (>= 0)")
        
        self.station_id = station_id
        self.name = name
        self.location = tuple(location)  # Ensure immutability
        self.index = index
        self.waiting_passengers: List['Passenger'] = []
        
        # Thread safety lock for waiting passengers list operations
        self._lock = Lock()
        
        logger.info(f"Station {self.station_id} initialized at location {self.location}")
    
    def add_waiting_passenger(self, passenger: 'Passenger') -> None:
        """
        Add a passenger to the waiting queue at this station.
        
        The passenger is added to the end of the queue (FIFO order).
        Duplicate passengers are not added - if the passenger is already
        waiting at this station, the operation is skipped.
        
        Args:
            passenger (Passenger): The passenger object to add to the waiting queue.
            
        Raises:
            ValueError: If passenger is None.
        """
        if passenger is None:
            raise ValueError("passenger cannot be None")
        
        with self._lock:
            # Check if passenger is already in the waiting list
            if passenger in self.waiting_passengers:
                logger.warning(
                    f"Passenger {passenger.passenger_id} is already waiting at {self.station_id}"
                )
                return
            
            self.waiting_passengers.append(passenger)
            logger.info(f"Passenger {passenger.passenger_id} is now waiting at {self.station_id}")
    
    def remove_waiting_passenger(self, passenger: 'Passenger') -> bool:
        """
        Remove a passenger from the waiting queue (typically when boarding a vehicle).
        
        Args:
            passenger (Passenger): The passenger object to remove from the queue.
            
        Returns:
            bool: True if the passenger was successfully removed, False if not found.
            
        Raises:
            ValueError: If passenger is None.
        """
        if passenger is None:
            raise ValueError("passenger cannot be None")
        
        with self._lock:
            if passenger in self.waiting_passengers:
                self.waiting_passengers.remove(passenger)
                logger.info(
                    f"Passenger {passenger.passenger_id} removed from waiting queue at {self.station_id}"
                )
                return True
            else:
                logger.warning(
                    f"Attempted to remove passenger {passenger.passenger_id} from {self.station_id}, "
                    f"but passenger was not in the waiting queue"
                )
                return False
    
    def get_waiting_passengers(self, destination_id: Optional[str] = None) -> List['Passenger']:
        """
        Get the list of passengers waiting at this station.
        
        Args:
            destination_id (str, optional): If provided, only return passengers
                whose destination matches this station ID. If None, return all
                waiting passengers.
                
        Returns:
            list: List of Passenger objects. Returns a copy to prevent external
                modification of the internal list.
        """
        with self._lock:
            if destination_id is None:
                # Return a copy of all waiting passengers
                return self.waiting_passengers.copy()
            else:
                # Filter passengers by destination
                filtered = [
                    p for p in self.waiting_passengers 
                    if p.destination_id == destination_id
                ]
                logger.debug(
                    f"Found {len(filtered)} passengers at {self.station_id} "
                    f"heading to {destination_id}"
                )
                return filtered
    
    def get_num_waiting(self) -> int:
        """
        Get the number of passengers currently waiting at this station.
        
        Returns:
            int: The count of waiting passengers.
        """
        with self._lock:
            return len(self.waiting_passengers)
    
    def clear_waiting_passengers(self) -> List['Passenger']:
        """
        Clear all passengers from the waiting queue.
        
        This method is primarily used for testing or simulation reset purposes.
        
        Returns:
            list: The list of passengers that were cleared from the queue.
        """
        with self._lock:
            cleared_passengers = self.waiting_passengers.copy()
            self.waiting_passengers.clear()
            logger.info(
                f"Cleared {len(cleared_passengers)} passengers from {self.station_id}"
            )
            return cleared_passengers
    
    def get_longest_waiting_passenger(self) -> Optional['Passenger']:
        """
        Get the passenger who has been waiting the longest (first in queue).
        
        This follows FIFO order - the first passenger added is the longest waiting.
        
        Returns:
            Passenger: The passenger object at the front of the queue, or None
                if no passengers are waiting.
        """
        with self._lock:
            if self.waiting_passengers:
                return self.waiting_passengers[0]
            return None
    
    def __repr__(self) -> str:
        """
        Return a string representation of the Station.
        
        Returns:
            str: String in format "Station(id=A, name=Central Station, waiting=3)"
        """
        num_waiting = self.get_num_waiting()
        return f"Station(id={self.station_id}, name={self.name}, waiting={num_waiting})"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Station to a dictionary representation.
        
        This method is useful for serialization (e.g., JSON export, database storage).
        Note that waiting passengers are represented by their IDs only to avoid
        circular references and deep nesting.
        
        Returns:
            dict: Dictionary containing station information with keys:
                - station_id: Station identifier
                - name: Station name
                - location: Tuple of (latitude, longitude)
                - index: Matrix index
                - num_waiting: Number of waiting passengers
                - waiting_passenger_ids: List of passenger IDs currently waiting
        """
        with self._lock:
            return {
                'station_id': self.station_id,
                'name': self.name,
                'location': self.location,
                'index': self.index,
                'num_waiting': len(self.waiting_passengers),
                'waiting_passenger_ids': [p.passenger_id for p in self.waiting_passengers]
            }
    
    def __eq__(self, other: object) -> bool:
        """
        Check equality based on station_id.
        
        Two stations are considered equal if they have the same station_id.
        
        Args:
            other (object): Another object to compare with.
            
        Returns:
            bool: True if both stations have the same station_id, False otherwise.
        """
        if not isinstance(other, Station):
            return NotImplemented
        return self.station_id == other.station_id
    
    def __hash__(self) -> int:
        """
        Return hash based on station_id.
        
        This allows Station objects to be used in sets and as dictionary keys.
        
        Returns:
            int: Hash value based on station_id.
        """
        return hash(self.station_id)