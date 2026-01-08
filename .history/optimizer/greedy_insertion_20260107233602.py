"""
optimizer/greedy_insertion.py (FIXED VERSION)

Greedy insertion algorithm for dynamic vehicle routing.
Inserts pending passenger requests into existing vehicle routes by finding
the minimum-cost insertion position that satisfies capacity constraints.

🔧 CRITICAL FIX: Properly handles initial occupancy in capacity checks
"""

import logging
import copy
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """Main optimization function"""
    logger.info("Starting greedy insertion optimization")
    logger.info(f"Pending requests: {len(input_data['pending_requests'])}")
    logger.info(f"Active vehicles: {len(input_data['minibuses'])}")
    
    current_time = input_data["current_time"]
    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    
    # Return existing routes if no new passengers
    if len(pending_requests) == 0:
        logger.info("No pending requests, returning existing routes unchanged")
        output = {}
        for mb in minibuses:
            output[mb["minibus_id"]] = mb["current_route_plan"]
        return output
    
    vehicles = _convert_to_vehicle_objects(minibuses)
    assigned_passengers = set()
    
    for request in pending_requests:
        passenger_id = request["passenger_id"]
        origin = request["origin"]
        destination = request["destination"]
        
        logger.debug(f"Processing request {passenger_id}: {origin} → {destination}")
        
        best_vehicle = None
        best_route = None
        best_tracker = None
        best_cost = float('inf')
        
        for vehicle in vehicles:
            candidate_route, candidate_tracker, cost = _try_insert_request(
                vehicle=vehicle,
                request=request,
                input_data=input_data
            )
            
            if candidate_route is not None and cost < best_cost:
                best_vehicle = vehicle
                best_route = candidate_route
                best_tracker = candidate_tracker
                best_cost = cost
        
        if best_vehicle is not None:
            best_vehicle["route"] = best_route
            best_vehicle["tracker"] = best_tracker
            assigned_passengers.add(passenger_id)
            logger.debug(
                f"Assigned {passenger_id} to {best_vehicle['minibus_id']}, "
                f"cost={best_cost:.2f}"
            )
        else:
            logger.warning(
                f"Could not assign passenger {passenger_id} to any vehicle"
            )
    
    # Clean routes before converting to output
    for vehicle in vehicles:
        _clean_route(vehicle)
    
    output = _convert_to_output_format(vehicles)

    logger.info(
        f"Optimization complete: assigned {len(assigned_passengers)}/"
        f"{len(pending_requests)} passengers"
    )
    return output


def _try_insert_request(
    vehicle: Dict,
    request: Dict,
    input_data: Dict
) -> Tuple[Optional[List[str]], Optional[Dict], float]:
    """
    Try to insert request with STATION REUSE support
    """
    origin = request["origin"]
    destination = request["destination"]
    passenger_id = request["passenger_id"]
    current_route = vehicle["route"]
    current_tracker = vehicle["tracker"]
    
    best_route = None
    best_tracker = None
    min_cost = float('inf')
    
    # Find existing positions of origin and destination
    origin_positions = [i for i, s in enumerate(current_route) if s == origin]
    dest_positions = [i for i, s in enumerate(current_route) if s == destination]
    
    # === CASE 1: Both stations already exist ===
    if origin_positions and dest_positions:
        logger.debug(f"Case 1: Both {origin} and {destination} exist in route")
        
        for o_pos in origin_positions:
            for d_pos in dest_positions:
                if o_pos < d_pos:
                    candidate_route = current_route.copy()
                    
                    candidate_tracker = {}
                    for station, actions in current_tracker.items():
                        candidate_tracker[station] = {
                            "pickup": actions["pickup"].copy(),
                            "dropoff": actions["dropoff"].copy()
                        }
                    
                    if origin not in candidate_tracker:
                        candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                    if destination not in candidate_tracker:
                        candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                    
                    candidate_tracker[origin]["pickup"].append(passenger_id)
                    candidate_tracker[destination]["dropoff"].append(passenger_id)
                    
                    if _check_capacity_feasible(vehicle, candidate_route, candidate_tracker):
                        cost = _compute_route_cost(candidate_route, input_data)
                        if cost < min_cost:
                            min_cost = cost
                            best_route = candidate_route
                            best_tracker = candidate_tracker
    
    # === CASE 2: Only origin exists ===
    elif origin_positions:
        logger.debug(f"Case 2: Only {origin} exists, inserting {destination}")
        
        for o_pos in origin_positions:
            for d_insert_pos in range(o_pos + 1, len(current_route) + 1):
                candidate_route = current_route.copy()
                candidate_route.insert(d_insert_pos, destination)
                
                candidate_tracker = {}
                for station, actions in current_tracker.items():
                    candidate_tracker[station] = {
                        "pickup": actions["pickup"].copy(),
                        "dropoff": actions["dropoff"].copy()
                    }
                
                if origin not in candidate_tracker:
                    candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                candidate_tracker[origin]["pickup"].append(passenger_id)
                
                if destination not in candidate_tracker:
                    candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                candidate_tracker[destination]["dropoff"].append(passenger_id)
                
                if _check_capacity_feasible(vehicle, candidate_route, candidate_tracker):
                    cost = _compute_route_cost(candidate_route, input_data)
                    if cost < min_cost:
                        min_cost = cost
                        best_route = candidate_route
                        best_tracker = candidate_tracker
    
    # === CASE 3: Only destination exists ===
    elif dest_positions:
        logger.debug(f"Case 3: Only {destination} exists, inserting {origin}")
        
        for d_pos in dest_positions:
            for o_insert_pos in range(0, d_pos + 1):
                candidate_route = current_route.copy()
                candidate_route.insert(o_insert_pos, origin)
                
                candidate_tracker = {}
                for station, actions in current_tracker.items():
                    candidate_tracker[station] = {
                        "pickup": actions["pickup"].copy(),
                        "dropoff": actions["dropoff"].copy()
                    }
                
                if origin not in candidate_tracker:
                    candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                candidate_tracker[origin]["pickup"].append(passenger_id)
                
                if destination not in candidate_tracker:
                    candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                candidate_tracker[destination]["dropoff"].append(passenger_id)
                
                if _check_capacity_feasible(vehicle, candidate_route, candidate_tracker):
                    cost = _compute_route_cost(candidate_route, input_data)
                    if cost < min_cost:
                        min_cost = cost
                        best_route = candidate_route
                        best_tracker = candidate_tracker
    
    # === CASE 4: Neither exists ===
    else:
        logger.debug(f"Case 4: Neither {origin} nor {destination} exists, inserting both")
        
        for i in range(len(current_route) + 1):
            for j in range(i + 1, len(current_route) + 2):
                candidate_route = current_route.copy()
                candidate_route.insert(i, origin)
                candidate_route.insert(j, destination)
                
                candidate_tracker = {}
                for station, actions in current_tracker.items():
                    candidate_tracker[station] = {
                        "pickup": actions["pickup"].copy(),
                        "dropoff": actions["dropoff"].copy()
                    }
                
                if origin not in candidate_tracker:
                    candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                candidate_tracker[origin]["pickup"].append(passenger_id)
                
                if destination not in candidate_tracker:
                    candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                candidate_tracker[destination]["dropoff"].append(passenger_id)
                
                if _check_capacity_feasible(vehicle, candidate_route, candidate_tracker):
                    cost = _compute_route_cost(candidate_route, input_data)
                    if cost < min_cost:
                        min_cost = cost
                        best_route = candidate_route
                        best_tracker = candidate_tracker
    
    return best_route, best_tracker, min_cost


def _check_capacity_feasible(
    vehicle: Dict,
    candidate_route: List[str],
    candidate_tracker: Dict
) -> bool:
    """
    🔧 CRITICAL FIX: Properly handle initial occupancy
    
    The key insight is that passengers_onboard are ALREADY counted in current_occupancy.
    When we simulate the route, we must:
    1. Start with current_occupancy (includes onboard passengers)
    2. Process dropoffs (reduces occupancy as passengers get off)
    3. Process pickups (increases occupancy as new passengers get on)
    
    The tracker should ONLY contain passengers that will be picked up or dropped off
    in the FUTURE route, not passengers already onboard at the start.
    """
    capacity = vehicle["capacity"]
    occupancy = vehicle["current_occupancy"]  # Includes onboard passengers
    
    logger.debug(f"Capacity check: Starting occupancy={occupancy}, capacity={capacity}")
    
    for i, station in enumerate(candidate_route):
        if station in candidate_tracker:
            # Get passengers getting off/on at this station
            dropoff_passengers = candidate_tracker[station]["dropoff"]
            pickup_passengers = candidate_tracker[station]["pickup"]
            
            # CRITICAL ORDER: DROPOFF before PICKUP
            occupancy -= len(dropoff_passengers)
            occupancy += len(pickup_passengers)
            
            logger.debug(
                f"  Stop {i+1} ({station}): "
                f"dropoff={len(dropoff_passengers)}, pickup={len(pickup_passengers)}, "
                f"occupancy={occupancy}"
            )
            
            # Check constraints
            if occupancy > capacity:
                logger.debug(f"  ❌ OVER capacity: {occupancy} > {capacity}")
                return False
            
            if occupancy < 0:
                logger.warning(
                    f"  ❌ NEGATIVE occupancy: {occupancy} at {station}. "
                    f"Dropoffs: {dropoff_passengers}, Pickups: {pickup_passengers}"
                )
                return False
    
    logger.debug(f"  ✓ Capacity check passed, final occupancy={occupancy}")
    return True


def _convert_to_vehicle_objects(minibuses: List[Dict]) -> List[Dict]:
    """
    Convert minibus states to internal working format.
    
    🔧 KEY FIX: Ensure tracker only contains FUTURE actions, not already-boarded passengers
    """
    vehicles = []
    
    for mb in minibuses:
        minibus_id = mb["minibus_id"]
        passengers_onboard = mb["passengers_onboard"]
        current_route_plan = mb["current_route_plan"]
        capacity = mb["capacity"]
        
        actual_occupancy = len(passengers_onboard)
        reported_occupancy = mb["current_occupancy"]
        
        if actual_occupancy != reported_occupancy:
            logger.warning(
                f"{minibus_id}: Occupancy mismatch! "
                f"Reported: {reported_occupancy}, Actual: {actual_occupancy}"
            )
        
        # Build route (deduplicate stations)
        current_route = []
        seen_stations = set()
        for stop in current_route_plan:
            station = stop["station_id"]
            if station not in seen_stations:
                current_route.append(station)
                seen_stations.add(station)
        
        # Build tracker - accumulate actions at same station
        tracker = {}
        for stop in current_route_plan:
            station = stop["station_id"]
            if station not in tracker:
                tracker[station] = {"pickup": [], "dropoff": []}
            
            if stop["action"] == "PICKUP":
                for pid in stop["passenger_ids"]:
                    if pid not in tracker[station]["pickup"]:
                        tracker[station]["pickup"].append(pid)
            elif stop["action"] == "DROPOFF":
                for pid in stop["passenger_ids"]:
                    if pid not in tracker[station]["dropoff"]:
                        tracker[station]["dropoff"].append(pid)
        
        # 🔧 DIAGNOSTIC: Validate the tracker
        onboard_set = set(passengers_onboard)
        all_pickups = set()
        all_dropoffs = set()
        
        for actions in tracker.values():
            all_pickups.update(actions["pickup"])
            all_dropoffs.update(actions["dropoff"])
        
        logger.info(f"=== {minibus_id} State ===")
        logger.info(f"  Capacity: {capacity}")
        logger.info(f"  Current occupancy: {actual_occupancy}")
        logger.info(f"  Passengers onboard: {passengers_onboard}")
        logger.info(f"  Route: {current_route}")
        logger.info(f"  Future pickups: {all_pickups}")
        logger.info(f"  Future dropoffs: {all_dropoffs}")
        
        # Check for conflicts
        conflict_pickup = all_pickups & onboard_set
        if conflict_pickup:
            logger.error(
                f"  ❌ CONFLICT: {conflict_pickup} are BOTH onboard AND scheduled for pickup!"
            )
        
        missing_dropoff = all_dropoffs - onboard_set - all_pickups
        if missing_dropoff:
            logger.error(
                f"  ❌ CONFLICT: {missing_dropoff} scheduled for dropoff but NOT onboard "
                f"and NOT scheduled for pickup!"
            )
        
        # Simulate route
        logger.info(f"  Simulating route:")
        test_occupancy = actual_occupancy
        
        for i, station in enumerate(current_route):
            if station in tracker:
                dropoff_count = len(tracker[station]["dropoff"])
                pickup_count = len(tracker[station]["pickup"])
                
                logger.info(
                    f"    Stop {i+1}/{len(current_route)} ({station}): "
                    f"occ={test_occupancy}, -dropoff={dropoff_count}, +pickup={pickup_count}"
                )
                
                test_occupancy -= dropoff_count
                test_occupancy += pickup_count
                
                if test_occupancy < 0:
                    logger.error(f"      ❌ NEGATIVE: {test_occupancy}")
                if test_occupancy > capacity:
                    logger.error(f"      ❌ OVER CAPACITY: {test_occupancy}/{capacity}")
                
                logger.info(f"      → After: {test_occupancy}")
        
        logger.info(f"  Final occupancy: {test_occupancy}")
        logger.info("=" * 60)
        
        # Create vehicle object
        vehicle = {
            "minibus_id": minibus_id,
            "current_location": mb["current_location"],
            "capacity": capacity,
            "current_occupancy": actual_occupancy,
            "passengers_onboard": passengers_onboard.copy(),
            "route": current_route,
            "tracker": tracker
        }
        
        vehicles.append(vehicle)
    
    return vehicles


def _compute_route_cost(route: List[str], input_data: Dict) -> float:
    """Compute total travel time with cumulative time calculation"""
    if len(route) <= 1:
        return 0.0
    
    get_travel_time = input_data["get_travel_time"]
    current_time = input_data["current_time"]
    
    total_time = 0.0
    arrival_time = current_time
    
    for i in range(len(route) - 1):
        origin_station = route[i]
        dest_station = route[i + 1]
        
        travel_time = get_travel_time(origin_station, dest_station, arrival_time)
        
        total_time += travel_time
        arrival_time += travel_time
    
    return total_time


def _convert_to_output_format(vehicles: List[Dict]) -> Dict[str, List[Dict]]:
    """Convert internal vehicle objects back to output format"""
    output = {}
    
    for vehicle in vehicles:
        minibus_id = vehicle["minibus_id"]
        route = vehicle["route"]
        tracker = vehicle["tracker"]
        
        route_plan = []
        
        for station in route:
            # Add pickups first, then dropoffs (order matters for output)
            if station in tracker and tracker[station]["pickup"]:
                route_plan.append({
                    "station_id": station,
                    "action": "PICKUP",
                    "passenger_ids": tracker[station]["pickup"]
                })
            
            if station in tracker and tracker[station]["dropoff"]:
                route_plan.append({
                    "station_id": station,
                    "action": "DROPOFF",
                    "passenger_ids": tracker[station]["dropoff"]
                })
        
        output[minibus_id] = route_plan
    
    return output


def _clean_route(vehicle: Dict) -> Dict:
    """Remove stations with no actions and duplicates"""
    route = vehicle["route"]
    tracker = vehicle["tracker"]
    
    cleaned_route = []
    seen_stations = set()
    
    for station in route:
        if station in seen_stations:
            logger.debug(f"Removing duplicate station {station}")
            continue
        
        has_action = (
            station in tracker and 
            (tracker[station]["pickup"] or tracker[station]["dropoff"])
        )
        
        if has_action:
            cleaned_route.append(station)
            seen_stations.add(station)
        else:
            logger.debug(f"Removing empty station {station}")
    
    vehicle["route"] = cleaned_route
    return vehicle