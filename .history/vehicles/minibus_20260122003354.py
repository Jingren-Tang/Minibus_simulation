"""
Minibus module - FIXED VERSION

CRITICAL FIX: update_route_plan now correctly skips stops at current location
to prevent the "横跳" (zigzag) problem where minibus repeatedly visits same station.
"""

import logging
from typing import List, Dict, Optional, Any

from demand.passenger import Passenger
from network.station import Station
from network.network import TransitNetwork

logger = logging.getLogger(__name__)

# ============================================================================
# DEBUG LOGGING FUNCTIONS (unchanged)
# ============================================================================

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
    Minibus with flexible routing - FIXED VERSION.
    
    This version correctly handles route updates by skipping stops at the
    current location to prevent unnecessary duplicate station visits.
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
        
        if minibus_id == "MINIBUS_1":
            init_debug_log()
    
    def update_route_plan(
        self, 
        new_plan: List[Dict[str, Any]], 
        current_time: float
    ) -> None:
        """
        ✅ FIXED VERSION: Update route plan with smart current-location handling.
        
        Key improvements:
        1. Skips stops at current location (prevents A→A travel)
        2. Executes current-location actions immediately
        3. Only schedules travel to different stations
        
        Args:
            new_plan: New route plan from optimizer
            current_time: Current simulation time
        """
        # Validate the new plan format
        if not self.validate_route_plan(new_plan):
            raise ValueError(f"Invalid route plan format for {self.minibus_id}")
        
        # Replace the route plan
        self.route_plan = new_plan.copy()
        
        logger.info(
            f"{self.minibus_id} received new route plan with {len(new_plan)} stops"
        )
        
        # =====================================================================
        # ✅ CRITICAL FIX: Find first station DIFFERENT from current location
        # =====================================================================
        
        if len(self.route_plan) == 0:
            # Empty plan - become idle
            self.next_station_id = None
            self.next_arrival_time = None
            self.status = self.IDLE
            logger.info(f"{self.minibus_id} has empty route plan, now IDLE")
            return
        
        # Find the first stop that is NOT at current location
        next_stop_index = 0
        immediate_actions = []  # Collect actions at current location
        
        while (next_stop_index < len(self.route_plan) and 
               self.route_plan[next_stop_index]["station_id"] == self.current_location_id):
            
            # This stop is at current location - mark for immediate execution
            immediate_actions.append(self.route_plan[next_stop_index])
            logger.info(
                f"{self.minibus_id} will immediately execute: "
                f"{self.route_plan[next_stop_index]['action']} at {self.current_location_id}"
            )
            next_stop_index += 1
        
        # =====================================================================
        # Handle immediate actions at current location (if any)
        # =====================================================================
        if len(immediate_actions) > 0:
            logger.warning(
                f"{self.minibus_id} has {len(immediate_actions)} action(s) at current location "
                f"{self.current_location_id}. These should be handled by simulation engine "
                f"immediately or optimizer should not include them. Keeping in route_plan for now."
            )
            # Note: We keep these in route_plan because the simulation engine
            # (handle_minibus_arrival) expects to execute them via arrive_at_station
        
        # =====================================================================
        # Schedule travel to next different station
        # =====================================================================
        if next_stop_index >= len(self.route_plan):
            # All stops are at current location - will be handled by simulation
            # Set next station to the first stop (even though it's current location)
            # The simulation will execute it and then minibus will become idle
            self.next_station_id = self.route_plan[0]["station_id"]
            
            # For stops at current location, set arrival time to current time
            # This will trigger immediate execution
            self.next_arrival_time = current_time
            self.status = self.SERVING
            
            logger.info(
                f"{self.minibus_id} all stops at current location {self.current_location_id}, "
                f"will execute immediately"
            )
        else:
            # Found a stop at a different station - schedule travel
            self.next_station_id = self.route_plan[next_stop_index]["station_id"]
            
            # ✅ CRITICAL: Calculate travel time from current location to DIFFERENT station
            travel_time = self.network.get_travel_time(
                self.current_location_id,
                self.next_station_id,
                current_time
            )
            
            # Safety check: travel_time should be positive
            if travel_time <= 0:
                logger.error(
                    f"{self.minibus_id}: Invalid travel_time={travel_time}s "
                    f"from {self.current_location_id} to {self.next_station_id}. "
                    f"Using minimum 60s."
                )
                travel_time = 60.0  # Minimum 1 minute
            
            # Track distance
            distance = (travel_time / 3600) * 30  # 30 km/h average
            self.total_distance_traveled += distance
            
            # Calculate arrival time
            self.next_arrival_time = current_time + travel_time
            self.status = self.EN_ROUTE
            
            # DEBUG LOGGING
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
                f"{self.minibus_id} en route to {self.next_station_id} "
                f"(stop index {next_stop_index}), "
                f"ETA={self.next_arrival_time:.2f}s (travel_time={travel_time:.2f}s, "
                f"distance={distance:.2f}km)"
            )
    
    def arrive_at_station(
        self, 
        station: Station,
        current_time: float
    ) -> Dict[str, Any]:
        """
        Process arrival at a station and execute planned actions.
        
        ✅ ENHANCED: Better handling of current-location stops.
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
        
        # Get the current station's plan
        if not self.route_plan:
            raise ValueError(f"{self.minibus_id} has empty route_plan at arrival")
        
        # =====================================================================
        # ✅ ENHANCED: Execute ALL stops at current station (not just first one)
        # =====================================================================
        boarded_all = []
        alighted_all = []
        actions_executed = 0
        
        # Execute all consecutive stops at this station
        while (len(self.route_plan) > 0 and 
               self.route_plan[0]["station_id"] == station.station_id):
            
            current_stop = self.route_plan[0]
            action_type = current_stop["action"]
            passenger_ids = current_stop["passenger_ids"]
            
            # Execute the action
            if action_type == self.PICKUP:
                boarded = self.execute_pickup(passenger_ids, station, current_time)
                boarded_all.extend(boarded)
                logger.info(
                    f"{self.minibus_id} picked up {len(boarded)} passengers at {station.station_id}"
                )
            elif action_type == self.DROPOFF:
                alighted = self.execute_dropoff(passenger_ids, current_time)
                alighted_all.extend(alighted)
                logger.info(
                    f"{self.minibus_id} dropped off {len(alighted)} passengers at {station.station_id}"
                )
            
            # Remove this stop
            self.route_plan.pop(0)
            actions_executed += 1
        
        logger.info(
            f"{self.minibus_id} executed {actions_executed} action(s) at {station.station_id}"
        )
        
        # =====================================================================
        # ✅ CRITICAL FIX: Find next DIFFERENT station
        # =====================================================================
        if len(self.route_plan) > 0:
            # Find next station that is DIFFERENT from current location
            next_different_station = None
            next_different_index = 0
            
            for i, stop in enumerate(self.route_plan):
                if stop["station_id"] != self.current_location_id:
                    next_different_station = stop["station_id"]
                    next_different_index = i
                    break
            
            if next_different_station is None:
                # All remaining stops are at current location
                # This is unusual but possible - execute them immediately
                logger.warning(
                    f"{self.minibus_id} has {len(self.route_plan)} remaining stop(s) "
                    f"all at current location {self.current_location_id}. "
                    f"Will execute in next arrival event."
                )
                
                self.next_station_id = self.route_plan[0]["station_id"]
                self.next_arrival_time = current_time  # Immediate
                self.status = self.SERVING
            else:
                # Schedule travel to next different station
                self.next_station_id = next_different_station
                
                # Calculate travel time from current location
                travel_time = self.network.get_travel_time(
                    self.current_location_id,
                    self.next_station_id,
                    current_time
                )
                
                # Safety check
                if travel_time <= 0:
                    logger.error(
                        f"{self.minibus_id}: Invalid travel_time={travel_time}s "
                        f"from {self.current_location_id} to {self.next_station_id}. "
                        f"Using minimum 60s."
                    )
                    travel_time = 60.0
                
                # Track distance
                distance = (travel_time / 3600) * 30
                self.total_distance_traveled += distance
                
                # Calculate next arrival
                self.next_arrival_time = current_time + travel_time
                self.status = self.EN_ROUTE
                
                # DEBUG LOGGING
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
            "boarded": boarded_all,
            "alighted": alighted_all,
            "action_type": "MULTIPLE" if actions_executed > 1 else current_stop["action"]
        }
    
    # =========================================================================
    # All other methods remain unchanged
    # =========================================================================
    
    def execute_pickup(
        self, 
        passenger_ids: List[str], 
        station: Station,
        current_time: float
    ) -> List[Passenger]:
        """Execute pickup operation."""
        boarded_passengers = []
        
        for passenger_id in passenger_ids:
            if self.is_full():
                logger.warning(
                    f"{self.minibus_id} is full, cannot pick up {passenger_id}"
                )
                continue
            
            passenger = None
            for p in station.waiting_passengers:
                if p.passenger_id == passenger_id:
                    passenger = p
                    break
            
            if passenger is None:
                logger.warning(
                    f"Passenger {passenger_id} not found at station {station.station_id}"
                )
                continue
            
            if passenger.assigned_vehicle_id is None:
                passenger.assigned_vehicle_id = self.minibus_id
            
            passenger.board_vehicle(current_time)
            self.passengers.append(passenger)
            station.waiting_passengers.remove(passenger)
            boarded_passengers.append(passenger)
            self.total_passengers_served += 1
            
            logger.debug(
                f"Passenger {passenger_id} boarded {self.minibus_id}"
            )
        
        return boarded_passengers
    
    def execute_dropoff(
        self, 
        passenger_ids: List[str], 
        current_time: float
    ) -> List[Passenger]:
        """Execute dropoff operation."""
        alighted_passengers = []
        
        for passenger_id in passenger_ids:
            passenger = None
            for p in self.passengers:
                if p.passenger_id == passenger_id:
                    passenger = p
                    break
            
            if passenger is None:
                logger.warning(
                    f"Passenger {passenger_id} not found on {self.minibus_id}"
                )
                continue
            
            passenger.arrive_at_destination(current_time)
            self.passengers.remove(passenger)
            alighted_passengers.append(passenger)
            
            logger.debug(
                f"Passenger {passenger_id} alighted from {self.minibus_id}"
            )
        
        return alighted_passengers
    
    def is_available(self) -> bool:
        return self.status == self.IDLE or len(self.route_plan) == 0
    
    def is_full(self) -> bool:
        return len(self.passengers) >= self.capacity
    
    def get_occupancy(self) -> int:
        return len(self.passengers)
    
    def get_remaining_capacity(self) -> int:
        return self.capacity - len(self.passengers)
    
    def get_assigned_passenger_ids(self) -> List[str]:
        assigned_ids = set()
        for passenger in self.passengers:
            assigned_ids.add(passenger.passenger_id)
        for stop in self.route_plan:
            assigned_ids.update(stop["passenger_ids"])
        return list(assigned_ids)
    
    def validate_route_plan(self, plan: List[Dict[str, Any]]) -> bool:
        """Validate route plan format."""
        if not isinstance(plan, list):
            return False
        
        for i, stop in enumerate(plan):
            if not isinstance(stop, dict):
                return False
            
            if "station_id" not in stop or "action" not in stop or "passenger_ids" not in stop:
                return False
            
            if stop["action"] not in [self.PICKUP, self.DROPOFF]:
                return False
            
            if len(stop["passenger_ids"]) == 0:
                logger.warning(f"Stop {i} has empty passenger_ids")
                return False
            
            if not isinstance(stop["passenger_ids"], list):
                return False
        
        return True
    
    def get_current_task(self) -> Optional[Dict[str, Any]]:
        if len(self.route_plan) > 0:
            return self.route_plan[0].copy()
        return None
    
    def get_minibus_info(self) -> Dict[str, Any]:
        """Get comprehensive minibus state information."""
        if self.next_station_id is None:
            remaining_route_plan = []
        else:
            remaining_route_plan = []
            found_next_station = False
            
            for stop in self.route_plan:
                if stop["station_id"] == self.next_station_id:
                    found_next_station = True
                
                if found_next_station:
                    remaining_route_plan.append(stop)
            
            if not found_next_station:
                logger.warning(
                    f"{self.minibus_id}: next_station_id not found in route_plan"
                )
                remaining_route_plan = self.route_plan.copy()
        
        return {
            "minibus_id": self.minibus_id,
            "capacity": self.capacity,
            "occupancy": self.get_occupancy(),
            "remaining_capacity": self.get_remaining_capacity(),
            "current_location_id": self.current_location_id,
            "status": self.status,
            "passenger_ids": [p.passenger_id for p in self.passengers],
            "assigned_passenger_ids": self.get_assigned_passenger_ids(),
            "route_plan": remaining_route_plan,
            "next_station_id": self.next_station_id,
            "next_arrival_time": self.next_arrival_time,
            "total_distance": self.total_distance,
            "idle_time": self.idle_time,
            "total_passengers_served": self.total_passengers_served,
            "total_distance_traveled": self.total_distance_traveled,
            "is_available": self.is_available()
        }
    
    def visualize_route_plan(self) -> str:
        """Create human-readable route visualization."""
        if not self.route_plan:
            return f"{self.minibus_id}: No route plan (IDLE)"
        
        route_str = f"{self.minibus_id} Route Plan:\n"
        route_str += f"  Current: {self.current_location_id} ({self.status})\n"
        
        for i, stop in enumerate(self.route_plan):
            arrow = "→" if i == 0 else " →"
            route_str += (
                f"  {arrow} {stop['station_id']}: "
                f"{stop['action']} {len(stop['passenger_ids'])} pax\n"
            )
        
        return route_str
    
    def __repr__(self) -> str:
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