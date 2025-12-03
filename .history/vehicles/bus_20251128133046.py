"""
Bus module for the traffic simulation system.

This module implements a fixed-route bus that operates on a strict schedule.
Buses are "wooden" - they mechanically follow their predetermined routes and
timetables without any flexibility.
"""

import logging
from typing import List, Dict, Tuple, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)


class Bus:
    """
    Represents a fixed-route bus in the transportation network.
    
    The bus follows a predetermined route and schedule, picking up and dropping
    off passengers at designated stations. It operates mechanically without
    route changes or schedule adjustments.
    
    Attributes:
        bus_id (str): Unique identifier for the bus (e.g., "BUS_1")
        route (List[str]): Ordered list of station IDs representing the fixed route
        schedule (Dict[str, float]): Timetable mapping station_id to arrival_time in seconds
        capacity (int): Maximum passenger capacity
        current_route_index (int): Current position in the route (0 = first station)
        passengers (List[Passenger]): List of passengers currently on board
        next_station_id (Optional[str]): ID of the next station to visit
        next_arrival_time (Optional[float]): Scheduled arrival time at next station
        total_distance (float): Cumulative distance traveled (for statistics)
        total_passengers_served (int): Total number of passengers served
    """
    
    def __init__(
        self,
        bus_id: str,
        route: List[str],
        schedule: Dict[str, float],
        capacity: int
    ) -> None:
        """
        Initialize a new Bus instance.
        
        Args:
            bus_id: Unique identifier for the bus
            route: Ordered list of station IDs
            schedule: Dictionary mapping station IDs to arrival times (seconds)
            capacity: Maximum number of passengers
            
        Raises:
            ValueError: If route is empty, capacity <= 0, or schedule doesn't 
                       contain all stations in route
        """
        # Input validation
        if not route:
            raise ValueError("Route cannot be empty")
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0")
        if not all(station_id in schedule for station_id in route):
            raise ValueError("Schedule must contain all stations in route")
        
        self.bus_id = bus_id
        self.route = route
        self.schedule = schedule
        self.capacity = capacity
        
        # Current state
        self.current_route_index = 0
        self.passengers: List[Any] = []  # List of Passenger objects
        
        # Next station information
        self.next_station_id = route[0]
        self.next_arrival_time = schedule[route[0]]
        
        # Statistics
        self.total_distance = 0.0
        self.total_passengers_served = 0
        
        logger.info(
            f"Initialized {self.bus_id} with route {route}, "
            f"capacity {capacity}, first station {self.next_station_id} "
            f"at {self.next_arrival_time}s"
        )
    
    def get_next_station(self) -> Tuple[Optional[str], Optional[float]]:
        """
        Get information about the next station to visit.
        
        Returns:
            Tuple of (station_id, arrival_time). Returns (None, None) if at terminal.
        """
        if self.is_at_terminal():
            return None, None
        return self.next_station_id, self.next_arrival_time
    
    def arrive_at_station(
        self,
        station: Any,  # Station object
        current_time: float
    ) -> Dict[str, List[Any]]:
        """
        Handle arrival at a station - the core method for bus operations.
        
        This method processes passenger alighting and boarding in the correct order:
        1. Alight passengers whose destination is this station
        2. Board waiting passengers whose destination is on the route (up to capacity)
        3. Update bus position and next station information
        
        Args:
            station: Station object where the bus is arriving
            current_time: Current simulation time in seconds
            
        Returns:
            Dictionary containing:
                - "boarded": List of passengers who boarded
                - "alighted": List of passengers who alighted
                - "rejected": List of passengers who couldn't board (capacity/route issues)
        """
        station_id = station.station_id
        boarded = []
        alighted = []
        rejected = []
        
        logger.info(
            f"{self.bus_id} arriving at {station_id} at {current_time}s "
            f"(scheduled: {self.schedule.get(station_id, 'N/A')}s), "
            f"occupancy: {self.get_occupancy()}/{self.capacity}"
        )
        
        # Step 1: Alight passengers whose destination is this station
        passengers_to_alight = [
            p for p in self.passengers if p.destination_id == station_id
        ]
        
        for passenger in passengers_to_alight:
            if self.alight_passenger(passenger, current_time):
                alighted.append(passenger)
        
        logger.info(
            f"{self.bus_id}: {len(alighted)} passengers alighted at {station_id}"
        )
        
        # Step 2: Board waiting passengers (FIFO order, check destination and capacity)
        waiting_passengers = station.get_waiting_passengers()
        
        for passenger in waiting_passengers:
            # Check if we can board this passenger
            if not self.can_board_passenger(passenger):
                # Check specific reason for rejection
                if self.is_full():
                    rejected.append(passenger)
                    logger.debug(
                        f"{self.bus_id}: Rejected {passenger.passenger_id} "
                        f"(bus full)"
                    )
                elif not self.is_destination_on_route(passenger.destination_id):
                    rejected.append(passenger)
                    logger.debug(
                        f"{self.bus_id}: Rejected {passenger.passenger_id} "
                        f"(destination {passenger.destination_id} not on route)"
                    )
                continue
            
            # Attempt to board the passenger
            if self.board_passenger(passenger, current_time):
                boarded.append(passenger)
                station.remove_waiting_passenger(passenger)
                
                # Stop if bus is now full
                if self.is_full():
                    break
        
        logger.info(
            f"{self.bus_id}: {len(boarded)} passengers boarded at {station_id}, "
            f"{len(rejected)} rejected"
        )
        
        # Step 3: Update bus position and next station information
        self.current_route_index += 1
        
        if not self.is_at_terminal():
            self.next_station_id = self.route[self.current_route_index]
            self.next_arrival_time = self.schedule[self.next_station_id]
            logger.info(
                f"{self.bus_id}: Next station {self.next_station_id} "
                f"at {self.next_arrival_time}s"
            )
        else:
            self.next_station_id = None
            self.next_arrival_time = None
            logger.info(f"{self.bus_id}: Reached terminal station")
        
        # Update statistics
        self.total_passengers_served += len(boarded)
        
        return {
            "boarded": boarded,
            "alighted": alighted,
            "rejected": rejected
        }
    
    def can_board_passenger(self, passenger: Any) -> bool:
        """
        Check if a passenger can board the bus.
        
        A passenger can board if:
        1. The bus is not full
        2. The passenger's destination is on the route after the current station
        
        Args:
            passenger: Passenger object attempting to board
            
        Returns:
            True if passenger can board, False otherwise
        """
        if self.is_full():
            return False
        
        if not self.is_destination_on_route(passenger.destination_id):
            return False
        
        return True
    
    def is_full(self) -> bool:
        """
        Check if the bus is at maximum capacity.
        
        Returns:
            True if bus is full, False otherwise
        """
        return len(self.passengers) >= self.capacity
    
    def get_occupancy(self) -> int:
        """
        Get the current number of passengers on board.
        
        Returns:
            Number of passengers currently on the bus
        """
        return len(self.passengers)
    
    def get_remaining_capacity(self) -> int:
        """
        Get the number of available seats.
        
        Returns:
            Number of empty seats
        """
        return self.capacity - len(self.passengers)
    
    def is_destination_on_route(self, destination_id: str) -> bool:
        """
        Check if a destination is on the route after the current station.
        
        This method determines if a passenger waiting at the current station
        can reach their destination using this bus.
        
        Args:
            destination_id: Station ID of the desired destination
            
        Returns:
            True if destination is reachable, False otherwise
        """
        try:
            # Find the index of the destination in the route
            dest_index = self.route.index(destination_id)
            # Destination must be after current position
            return dest_index > self.current_route_index
        except ValueError:
            # Destination not in route
            return False
    
    def get_passengers_alighting_at(self, station_id: str) -> List[Any]:
        """
        Get list of passengers who will alight at a specific station.
        
        This is a query method that doesn't modify the passenger list.
        
        Args:
            station_id: ID of the station to check
            
        Returns:
            List of Passenger objects whose destination is the given station
        """
        return [
            p for p in self.passengers if p.destination_id == station_id
        ]
    
    def board_passenger(self, passenger: Any, current_time: float) -> bool:
        """
        Board a single passenger onto the bus.
        
        Args:
            passenger: Passenger object to board
            current_time: Current simulation time in seconds
            
        Returns:
            True if boarding successful, False otherwise
        """
        # Verify capacity
        if self.is_full():
            logger.warning(
                f"{self.bus_id}: Cannot board {passenger.passenger_id} - bus full"
            )
            return False
        
        # Board the passenger - FIXED: board_vehicle() only takes current_time
        passenger.board_vehicle(current_time)
        self.passengers.append(passenger)
        
        logger.debug(
            f"{self.bus_id}: Boarded {passenger.passenger_id} "
            f"(destination: {passenger.destination_station_id})"
        )
        
        return True
    
    def alight_passenger(self, passenger: Any, current_time: float) -> bool:
        """
        Alight a single passenger from the bus.
        
        Args:
            passenger: Passenger object to alight
            current_time: Current simulation time in seconds
            
        Returns:
            True if alighting successful, False otherwise
        """
        if passenger not in self.passengers:
            logger.warning(
                f"{self.bus_id}: Cannot alight {passenger.passenger_id} - "
                f"not on bus"
            )
            return False
        
        # Remove from bus
        self.passengers.remove(passenger)
        
        # Notify passenger of arrival
        passenger.arrive_at_destination(current_time)
        
        logger.debug(
            f"{self.bus_id}: Alighted {passenger.passenger_id} "
            f"at {passenger.destination_id}"
        )
        
        return True
    
    def is_at_terminal(self) -> bool:
        """
        Check if the bus has reached the terminal (end of route).
        
        Returns:
            True if at terminal, False otherwise
        """
        return self.current_route_index >= len(self.route)
    
    def should_be_removed(self) -> bool:
        """
        Check if this bus should be removed from the simulation.
        
        A bus should be removed when it has completed its route (reached terminal).
        The simulation manager should check this after each station arrival and
        remove buses that have completed their service.
        
        Returns:
            True if bus has completed its route and should be removed, False otherwise
        """
        if self.is_at_terminal():
            # Warn if there are still passengers on board
            if self.passengers:
                logger.warning(
                    f"{self.bus_id}: At terminal with {len(self.passengers)} "
                    f"passengers still on board. Passengers: "
                    f"{[p.passenger_id for p in self.passengers]}"
                )
            return True
        return False
    
    def get_bus_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the bus's current state.
        
        Returns:
            Dictionary containing bus status information including:
                - bus_id
                - current_position (station index)
                - occupancy
                - capacity
                - next_station_id
                - next_arrival_time
                - passenger_count
                - passengers (list of IDs)
                - at_terminal
                - total_passengers_served
                - route
                - total_distance
        """
        return {
            "bus_id": self.bus_id,
            "current_position": self.current_route_index,
            "occupancy": self.get_occupancy(),
            "capacity": self.capacity,
            "next_station_id": self.next_station_id,
            "next_arrival_time": self.next_arrival_time,
            "passenger_count": len(self.passengers),
            "passengers": [p.passenger_id for p in self.passengers],
            "at_terminal": self.is_at_terminal(),
            "total_passengers_served": self.total_passengers_served,
            "route": self.route,
            "total_distance": self.total_distance
        }
    
    def __repr__(self) -> str:
        """
        Return a human-readable string representation of the bus.
        
        Returns:
            String in format: Bus(id=BUS_1, at=B, occupancy=5/40, next=C@500s)
        """
        if self.is_at_terminal():
            current_pos = "TERMINAL"
            next_info = "END"
        else:
            # Current position is the last station we visited/are at
            if self.current_route_index > 0:
                current_pos = self.route[self.current_route_index - 1]
            else:
                current_pos = "START"
            next_info = f"{self.next_station_id}@{self.next_arrival_time}s"
        
        return (
            f"Bus(id={self.bus_id}, at={current_pos}, "
            f"occupancy={self.get_occupancy()}/{self.capacity}, "
            f"next={next_info})"
        )