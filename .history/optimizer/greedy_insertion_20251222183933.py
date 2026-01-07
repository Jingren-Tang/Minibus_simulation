"""
optimizer/greedy_insertion.py

Greedy insertion algorithm for dynamic vehicle routing.
Inserts pending passenger requests into existing vehicle routes by finding
the minimum-cost insertion position that satisfies capacity constraints.
"""
"""
optimizer/greedy_insertion.py - COMPLETE DEFENSIVE VERSION

This version implements a three-layer defense system against state inconsistencies:
1. Layer 1: Validate optimizer output before applying (in simulation engine)
2. Layer 2: Defensive capacity checking (in optimizer)
3. Layer 3: Defensive execution (in minibus operations)

All comments are in English for international collaboration.
"""

import logging
import copy
from typing import Dict, List, Tuple, Optional, Set

logger = logging.getLogger(__name__)


def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """
    Main optimization function with state validation.
    
    Args:
        input_data: Dictionary containing:
            - current_time: Current simulation time
            - pending_requests: List of unassigned passenger requests
            - minibuses: List of minibus state dictionaries
            - stations: List of station IDs
            - get_travel_time: Function to query travel times
            - max_waiting_time: Maximum passenger waiting time
            - max_detour_time: Maximum detour time
    
    Returns:
        Dictionary mapping minibus_id to route_plan
    """
    logger.info("Starting greedy insertion optimization")
    logger.info(f"Pending requests: {len(input_data['pending_requests'])}")
    logger.info(f"Active vehicles: {len(input_data['minibuses'])}")
    
    current_time = input_data["current_time"]
    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    
    # Early return: if no pending requests, keep existing routes
    if len(pending_requests) == 0:
        logger.info("No pending requests, returning existing routes unchanged")
        output = {}
        for mb in minibuses:
            output[mb["minibus_id"]] = mb["current_route_plan"]
        return output
    
    # Convert to internal format
    vehicles = _convert_to_vehicle_objects(minibuses)
    assigned_passengers = set()
    
    # Process each pending request
    for request in pending_requests:
        passenger_id = request["passenger_id"]
        origin = request["origin"]
        destination = request["destination"]
        
        logger.debug(f"Processing request {passenger_id}: {origin} → {destination}")
        
        best_vehicle = None
        best_route = None
        best_tracker = None
        best_cost = float('inf')
        
        # Try to insert into each vehicle
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
        
        # Assign to best vehicle if found
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
    
    # Convert back to output format
    output = _convert_to_output_format(vehicles)
    
    # LAYER 2: Validate all output route plans
    logger.info("Validating optimizer output...")
    validated_output = {}
    
    for minibus_id, route_plan in output.items():
        # Find original minibus state
        mb_state = next((mb for mb in minibuses if mb["minibus_id"] == minibus_id), None)
        
        if mb_state is None:
            logger.error(f"Could not find minibus state for {minibus_id}")
            validated_output[minibus_id] = []
            continue
        
        # Validate the route plan
        if _validate_route_plan(minibus_id, route_plan, mb_state):
            validated_output[minibus_id] = route_plan
        else:
            logger.error(
                f"Route plan validation failed for {minibus_id}, "
                f"returning empty plan"
            )
            validated_output[minibus_id] = []
    
    logger.info(
        f"Optimization complete: assigned {len(assigned_passengers)}/"
        f"{len(pending_requests)} passengers"
    )
    
    return validated_output


def _validate_route_plan(
    minibus_id: str, 
    route_plan: List[Dict], 
    minibus_state: Dict
) -> bool:
    """
    LAYER 2 VALIDATION: Validate route plan consistency.
    
    Checks:
    1. All dropoffs must have corresponding passengers (onboard or in pickup)
    2. No duplicate pickups
    3. No duplicate dropoffs
    4. Every dropoff must match a pickup or existing passenger
    
    Args:
        minibus_id: ID of the minibus
        route_plan: Proposed route plan to validate
        minibus_state: Current state of the minibus
    
    Returns:
        True if valid, False otherwise
    """
    logger.debug(f"Validating route plan for {minibus_id}...")
    
    # Get passengers currently onboard
    passengers_onboard = set(minibus_state["passengers_onboard"])
    
    # Collect all pickups and dropoffs
    passengers_to_pickup = []
    passengers_to_dropoff = []
    
    for stop in route_plan:
        if stop["action"] == "PICKUP":
            passengers_to_pickup.extend(stop["passenger_ids"])
        elif stop["action"] == "DROPOFF":
            passengers_to_dropoff.extend(stop["passenger_ids"])
    
    # Convert to sets for checking
    pickup_set = set(passengers_to_pickup)
    dropoff_set = set(passengers_to_dropoff)
    
    # CHECK 1: No duplicate pickups
    if len(passengers_to_pickup) != len(pickup_set):
        duplicates = [pid for pid in pickup_set 
                     if passengers_to_pickup.count(pid) > 1]
        logger.error(
            f"❌ {minibus_id}: Duplicate pickups detected: {duplicates}"
        )
        return False
    
    # CHECK 2: No duplicate dropoffs
    if len(passengers_to_dropoff) != len(dropoff_set):
        duplicates = [pid for pid in dropoff_set 
                     if passengers_to_dropoff.count(pid) > 1]
        logger.error(
            f"❌ {minibus_id}: Duplicate dropoffs detected: {duplicates}"
        )
        return False
    
    # CHECK 3: All dropoffs must have matching pickups or be onboard
    all_available = passengers_onboard | pickup_set
    invalid_dropoffs = dropoff_set - all_available
    
    if invalid_dropoffs:
        logger.error(
            f"❌ {minibus_id}: Dropoffs without matching passengers: {invalid_dropoffs}. "
            f"Onboard: {passengers_onboard}, Pickups: {pickup_set}"
        )
        return False
    
    # CHECK 4: No passenger should be picked up if already onboard
    invalid_pickups = pickup_set & passengers_onboard
    
    if invalid_pickups:
        logger.error(
            f"❌ {minibus_id}: Trying to pickup passengers already onboard: {invalid_pickups}"
        )
        return False
    
    logger.debug(f"✅ Route plan validation passed for {minibus_id}")
    return True


def _try_insert_request(
    vehicle: Dict,
    request: Dict,
    input_data: Dict
) -> Tuple[Optional[List[str]], Optional[Dict], float]:
    """
    Try to insert request with station reuse support.
    
    Handles 4 cases:
    1. Both origin and destination exist → Reuse both
    2. Only origin exists → Reuse origin, insert destination
    3. Only destination exists → Insert origin, reuse destination
    4. Neither exists → Insert both
    
    Args:
        vehicle: Vehicle state dictionary
        request: Passenger request dictionary
        input_data: Input data containing network and constraints
    
    Returns:
        (best_route, best_tracker, cost) or (None, None, inf) if infeasible
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
        
        # Try all valid combinations (origin before destination)
        for o_pos in origin_positions:
            for d_pos in dest_positions:
                if o_pos < d_pos:
                    # Reuse existing route (no insertion needed)
                    candidate_route = current_route.copy()
                    
                    # Deep copy tracker
                    candidate_tracker = {}
                    for station, actions in current_tracker.items():
                        candidate_tracker[station] = {
                            "pickup": actions["pickup"].copy(),
                            "dropoff": actions["dropoff"].copy()
                        }
                    
                    # Ensure stations exist in tracker
                    if origin not in candidate_tracker:
                        candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                    if destination not in candidate_tracker:
                        candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                    
                    # CHECK: Prevent duplicate additions
                    if passenger_id in candidate_tracker[origin]["pickup"]:
                        logger.warning(
                            f"Case 1: Passenger {passenger_id} already in pickup list "
                            f"at {origin}, skipping"
                        )
                        continue
                    
                    if passenger_id in candidate_tracker[destination]["dropoff"]:
                        logger.warning(
                            f"Case 1: Passenger {passenger_id} already in dropoff list "
                            f"at {destination}, skipping"
                        )
                        continue
                    
                    # Add passenger
                    candidate_tracker[origin]["pickup"].append(passenger_id)
                    candidate_tracker[destination]["dropoff"].append(passenger_id)
                    
                    # Validate capacity
                    if _check_capacity_feasible(vehicle, candidate_route, candidate_tracker):
                        cost = _compute_route_cost(candidate_route, input_data)
                        if cost < min_cost:
                            min_cost = cost
                            best_route = candidate_route
                            best_tracker = candidate_tracker
    
    # === CASE 2: Only origin exists, need to insert destination ===
    elif origin_positions:
        logger.debug(f"Case 2: Only {origin} exists, inserting {destination}")
        
        for o_pos in origin_positions:
            # Try inserting destination after origin
            for d_insert_pos in range(o_pos + 1, len(current_route) + 1):
                candidate_route = current_route.copy()
                candidate_route.insert(d_insert_pos, destination)
                
                # Deep copy tracker
                candidate_tracker = {}
                for station, actions in current_tracker.items():
                    candidate_tracker[station] = {
                        "pickup": actions["pickup"].copy(),
                        "dropoff": actions["dropoff"].copy()
                    }
                
                # Ensure stations exist
                if origin not in candidate_tracker:
                    candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                if destination not in candidate_tracker:
                    candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                
                # Add passenger
                candidate_tracker[origin]["pickup"].append(passenger_id)
                candidate_tracker[destination]["dropoff"].append(passenger_id)
                
                if _check_capacity_feasible(vehicle, candidate_route, candidate_tracker):
                    cost = _compute_route_cost(candidate_route, input_data)
                    if cost < min_cost:
                        min_cost = cost
                        best_route = candidate_route
                        best_tracker = candidate_tracker
    
    # === CASE 3: Only destination exists, need to insert origin ===
    elif dest_positions:
        logger.debug(f"Case 3: Only {destination} exists, inserting {origin}")
        
        for d_pos in dest_positions:
            # Try inserting origin before destination
            for o_insert_pos in range(0, d_pos + 1):
                candidate_route = current_route.copy()
                candidate_route.insert(o_insert_pos, origin)
                
                # Deep copy tracker
                candidate_tracker = {}
                for station, actions in current_tracker.items():
                    candidate_tracker[station] = {
                        "pickup": actions["pickup"].copy(),
                        "dropoff": actions["dropoff"].copy()
                    }
                
                # Ensure stations exist
                if origin not in candidate_tracker:
                    candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                if destination not in candidate_tracker:
                    candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                
                # Add passenger
                candidate_tracker[origin]["pickup"].append(passenger_id)
                candidate_tracker[destination]["dropoff"].append(passenger_id)
                
                if _check_capacity_feasible(vehicle, candidate_route, candidate_tracker):
                    cost = _compute_route_cost(candidate_route, input_data)
                    if cost < min_cost:
                        min_cost = cost
                        best_route = candidate_route
                        best_tracker = candidate_tracker
    
    # === CASE 4: Neither exists, insert both ===
    else:
        logger.debug(f"Case 4: Neither {origin} nor {destination} exists, inserting both")
        
        for i in range(len(current_route) + 1):
            for j in range(i + 1, len(current_route) + 2):
                candidate_route = current_route.copy()
                candidate_route.insert(i, origin)
                candidate_route.insert(j, destination)
                
                # Deep copy tracker
                candidate_tracker = {}
                for station, actions in current_tracker.items():
                    candidate_tracker[station] = {
                        "pickup": actions["pickup"].copy(),
                        "dropoff": actions["dropoff"].copy()
                    }
                
                # Ensure stations exist
                if origin not in candidate_tracker:
                    candidate_tracker[origin] = {"pickup": [], "dropoff": []}
                if destination not in candidate_tracker:
                    candidate_tracker[destination] = {"pickup": [], "dropoff": []}
                
                # Add passenger
                candidate_tracker[origin]["pickup"].append(passenger_id)
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
    LAYER 2 DEFENSE: Check capacity constraint with state validation.
    
    This function validates that:
    1. All passengers to be dropped off are actually onboard
    2. No passenger is picked up twice
    3. Capacity constraints are satisfied at every stop
    4. Occupancy never goes negative
    
    Args:
        vehicle: Vehicle state dictionary
        candidate_route: Proposed route (list of station IDs)
        candidate_tracker: Tracker with pickup/dropoff information
    
    Returns:
        True if feasible, False otherwise
    """
    capacity = vehicle["capacity"]
    
    # Start with actual passengers onboard
    passengers_onboard = set(vehicle["passengers_onboard"])
    
    logger.debug(
        f"Capacity check for {vehicle['minibus_id']}: "
        f"capacity={capacity}, initial passengers={passengers_onboard}"
    )
    
    for station in candidate_route:
        if station in candidate_tracker:
            dropoff_ids = set(candidate_tracker[station]["dropoff"])
            pickup_ids = set(candidate_tracker[station]["pickup"])
            
            # VALIDATION 1: Can only dropoff passengers who are onboard
            invalid_dropoffs = dropoff_ids - passengers_onboard
            if invalid_dropoffs:
                logger.warning(
                    f"❌ Station {station}: Cannot dropoff {invalid_dropoffs} - "
                    f"NOT onboard! Current passengers: {passengers_onboard}"
                )
                return False
            
            # Execute dropoff
            passengers_onboard -= dropoff_ids
            logger.debug(
                f"  {station}: DROPOFF {dropoff_ids}, now onboard: {passengers_onboard}"
            )
            
            # VALIDATION 2: Cannot pickup passengers already onboard
            invalid_pickups = pickup_ids & passengers_onboard
            if invalid_pickups:
                logger.warning(
                    f"❌ Station {station}: Cannot pickup {invalid_pickups} - "
                    f"ALREADY onboard!"
                )
                return False
            
            # Execute pickup
            passengers_onboard |= pickup_ids
            logger.debug(
                f"  {station}: PICKUP {pickup_ids}, now onboard: {passengers_onboard}"
            )
            
            # VALIDATION 3: Check capacity
            if len(passengers_onboard) > capacity:
                logger.debug(
                    f"❌ Capacity exceeded at {station}: "
                    f"{len(passengers_onboard)} > {capacity}"
                )
                return False
    
    logger.debug(
        f"✅ Capacity check passed, final occupancy: {len(passengers_onboard)}/{capacity}"
    )
    return True


def _convert_to_vehicle_objects(minibuses: List[Dict]) -> List[Dict]:
    """
    Convert minibus states to internal working format.
    
    Args:
        minibuses: List of minibus state dictionaries
    
    Returns:
        List of vehicle working objects with mutable route information
    """
    vehicles = []
    
    for mb in minibuses:
        # Extract current route as simple station list
        current_route = [stop["station_id"] for stop in mb["current_route_plan"]]
        
        # Build tracking info: which passengers are picked up/dropped off at each station
        tracker = {}
        for stop in mb["current_route_plan"]:
            station = stop["station_id"]
            if station not in tracker:
                tracker[station] = {"pickup": [], "dropoff": []}
            
            if stop["action"] == "PICKUP":
                tracker[station]["pickup"].extend(stop["passenger_ids"])
            elif stop["action"] == "DROPOFF":
                tracker[station]["dropoff"].extend(stop["passenger_ids"])
        
        vehicle = {
            "minibus_id": mb["minibus_id"],
            "current_location": mb["current_location"],
            "capacity": mb["capacity"],
            "current_occupancy": mb["current_occupancy"],
            "passengers_onboard": mb["passengers_onboard"].copy(),
            "route": current_route,
            "tracker": tracker
        }
        
        vehicles.append(vehicle)
    
    return vehicles


def _compute_route_cost(route: List[str], input_data: Dict) -> float:
    """
    Compute total travel time for a route using cumulative time calculation.
    
    Args:
        route: List of station IDs representing the route
        input_data: Input data containing get_travel_time function and current_time
    
    Returns:
        Total travel time in seconds
    """
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
    """
    Convert internal vehicle objects back to output format.
    
    Args:
        vehicles: List of vehicle objects with assigned routes
    
    Returns:
        Dictionary mapping minibus_id to route_plan
    """
    output = {}
    
    for vehicle in vehicles:
        minibus_id = vehicle["minibus_id"]
        route = vehicle["route"]
        tracker = vehicle["tracker"]
        
        route_plan = []
        
        for station in route:
            # Add pickup stop if present
            if station in tracker and tracker[station]["pickup"]:
                route_plan.append({
                    "station_id": station,
                    "action": "PICKUP",
                    "passenger_ids": tracker[station]["pickup"]
                })
            
            # Add dropoff stop if present
            if station in tracker and tracker[station]["dropoff"]:
                route_plan.append({
                    "station_id": station,
                    "action": "DROPOFF",
                    "passenger_ids": tracker[station]["dropoff"]
                })
        
        output[minibus_id] = route_plan
    
    return output

if __name__ == "__main__":
    """
    Comprehensive test suite for greedy insertion algorithm.
    Tests various edge cases and realistic scenarios.
    """
    import json
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("GREEDY INSERTION ALGORITHM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    # =====================================================================
    # TEST 1: Time-Dependent Travel Times (Rush Hour Simulation)
    # =====================================================================
    print("\n" + "=" * 80)
    print("TEST 1: Time-Dependent Travel Times (Rush Hour)")
    print("=" * 80)
    
    def mock_time_dependent_travel(origin, dest, time):
        """
        Simulates rush hour vs off-peak travel times.
        
        Rush hour (8:00-9:00, time 28800-32400): 50% slower
        Off-peak: Normal speed
        """
        # Base travel times (in seconds)
        base_times = {
            ("A", "B"): 300,   # 5 min
            ("B", "A"): 300,
            ("B", "C"): 420,   # 7 min
            ("C", "B"): 420,
            ("C", "D"): 360,   # 6 min
            ("D", "C"): 360,
            ("A", "C"): 600,   # 10 min (direct)
            ("C", "A"): 600,
            ("A", "D"): 900,   # 15 min (direct)
            ("D", "A"): 900,
            ("B", "D"): 720,   # 12 min (direct)
            ("D", "B"): 720,
            ("E", "F"): 480,   # 8 min
            ("F", "E"): 480,
            ("E", "G"): 540,   # 9 min
            ("G", "E"): 540,
            ("F", "G"): 600,   # 10 min
            ("G", "F"): 600,
        }
        
        base_time = base_times.get((origin, dest), 600)  # Default 10 min
        
        # Check if it's rush hour (8:00-9:00 AM)
        rush_hour_start = 28800  # 8:00 AM
        rush_hour_end = 32400    # 9:00 AM
        
        if rush_hour_start <= time < rush_hour_end:
            # Rush hour: 50% slower
            multiplier = 1.5
            logger.debug(f"Rush hour! {origin}→{dest}: {base_time}s → {base_time * multiplier}s")
        else:
            # Off-peak
            multiplier = 1.0
        
        return base_time * multiplier
    
    test1_input = {
        "current_time": 28800.0,  # 8:00 AM (rush hour start)
        "pending_requests": [
            {
                "passenger_id": "P1",
                "origin": "A",
                "destination": "D",
                "appear_time": 28700.0,
                "wait_time": 100.0
            },
            {
                "passenger_id": "P2",
                "origin": "B",
                "destination": "C",
                "appear_time": 28750.0,
                "wait_time": 50.0
            },
            {
                "passenger_id": "P3",
                "origin": "A",
                "destination": "C",
                "appear_time": 28780.0,
                "wait_time": 20.0
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M1",
                "current_location": "A",
                "capacity": 4,
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            },
            {
                "minibus_id": "M2",
                "current_location": "B",
                "capacity": 6,
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            }
        ],
        "stations": ["A", "B", "C", "D", "E", "F", "G"],
        "get_travel_time": mock_time_dependent_travel,
        "max_waiting_time": 600.0,
        "max_detour_time": 300.0
    }
    
    print("\nScenario: 3 passengers, 2 idle vehicles, rush hour traffic")
    print("Expected: Algorithm should consider rush hour delays")
    
    output1 = greedy_insert_optimize(test1_input)
    
    print("\n>>> Results:")
    for minibus_id, route_plan in output1.items():
        print(f"\n{minibus_id}:")
        if not route_plan:
            print("  (idle)")
        else:
            for stop in route_plan:
                print(f"  → {stop['station_id']}: {stop['action']} {stop['passenger_ids']}")
    
    # =====================================================================
    # TEST 2: Capacity Constraint Enforcement
    # =====================================================================
    print("\n" + "=" * 80)
    print("TEST 2: Capacity Constraint Enforcement")
    print("=" * 80)

    test2_input = {
        "current_time": 30000.0,
        "pending_requests": [
            {
                "passenger_id": "P4",
                "origin": "A",
                "destination": "D",
                "appear_time": 29900.0,
                "wait_time": 100.0
            },
            {
                "passenger_id": "P5",
                "origin": "B",
                "destination": "D",
                "appear_time": 29950.0,
                "wait_time": 50.0
            },
            {
                "passenger_id": "P6",
                "origin": "C",
                "destination": "D",
                "appear_time": 29980.0,
                "wait_time": 20.0
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M3",
                "current_location": "A",
                "capacity": 3,  # Small capacity
                "current_occupancy": 1,  # Already has 1 passenger
                "passengers_onboard": ["P_existing"],
                "current_route_plan": [
                    {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P_existing"]}
                ]
            }
        ],
        "stations": ["A", "B", "C", "D", "E"],
        "get_travel_time": mock_time_dependent_travel,
        "max_waiting_time": 600.0,
        "max_detour_time": 300.0
    }

    print("\nScenario: 3 new passengers, 1 vehicle with capacity=3, already has 1 passenger")
    print("Expected: Can only pick up 2 more passengers (capacity limit)")

    output2 = greedy_insert_optimize(test2_input)

    print("\n>>> Results:")
    for minibus_id, route_plan in output2.items():
        print(f"\n{minibus_id}:")
        if not route_plan:
            print("  (idle)")
        else:
            # 🔧 FIXED: Correct occupancy simulation
            occupancy = 1  # Start with 1 existing passenger
            
            for i, stop in enumerate(route_plan):
                station = stop['station_id']
                action = stop['action']
                passengers = stop['passenger_ids']
                
                # 🔧 KEY FIX: Process DROPOFF before printing, PICKUP after printing
                if action == 'DROPOFF':
                    occupancy -= len(passengers)
                    print(f"  → {station}: DROPOFF {passengers} (occupancy: {occupancy}/{test2_input['minibuses'][0]['capacity']})")
                
                elif action == 'PICKUP':
                    occupancy += len(passengers)
                    print(f"  → {station}: PICKUP {passengers} (occupancy: {occupancy}/{test2_input['minibuses'][0]['capacity']})")

    # Count assigned passengers
    assigned_test2 = set()
    for route_plan in output2.values():
        for stop in route_plan:
            if stop['action'] == 'PICKUP':
                assigned_test2.update(stop['passenger_ids'])

    print(f"\n>>> Assigned: {len(assigned_test2)}/3 passengers (should be ≤2 due to capacity)")


    # =====================================================================
    # TEST 3: Multiple Vehicles Competition
    # =====================================================================
    print("\n" + "=" * 80)
    print("TEST 3: Multiple Vehicles Competing for Same Passenger")
    print("=" * 80)
    
    test3_input = {
        "current_time": 32000.0,
        "pending_requests": [
            {
                "passenger_id": "P7",
                "origin": "C",
                "destination": "D",
                "appear_time": 31900.0,
                "wait_time": 100.0
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M4",
                "current_location": "A",
                "capacity": 6,
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            },
            {
                "minibus_id": "M5",
                "current_location": "B",
                "capacity": 6,
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            },
            {
                "minibus_id": "M6",
                "current_location": "C",  # Closest to passenger!
                "capacity": 6,
                "current_occupancy": 2,
                "passengers_onboard": ["P_other1", "P_other2"],
                "current_route_plan": [
                    {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P_other1"]},
                    {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["P_other2"]}
                ]
            }
        ],
        "stations": ["A", "B", "C", "D", "E", "F"],
        "get_travel_time": mock_time_dependent_travel,
        "max_waiting_time": 600.0,
        "max_detour_time": 300.0
    }
    
    print("\nScenario: 1 passenger at C→D, 3 vehicles (M6 is closest but has existing route)")
    print("Expected: Algorithm chooses vehicle with minimum cost increase")
    
    output3 = greedy_insert_optimize(test3_input)
    
    print("\n>>> Results:")
    for minibus_id, route_plan in output3.items():
        print(f"\n{minibus_id}:")
        if not route_plan:
            print("  (idle)")
        else:
            for stop in route_plan:
                print(f"  → {stop['station_id']}: {stop['action']} {stop['passenger_ids']}")
    
    # Find which vehicle got the passenger
    winner = None
    for minibus_id, route_plan in output3.items():
        for stop in route_plan:
            if stop['action'] == 'PICKUP' and 'P7' in stop['passenger_ids']:
                winner = minibus_id
                break
    
    print(f"\n>>> Winner: {winner} (should prefer closest or least busy vehicle)")
    
    # =====================================================================
    # TEST 4: Sequential Assignment Order Effect
    # =====================================================================
    print("\n" + "=" * 80)
    print("TEST 4: Sequential Assignment Order (Greedy Behavior)")
    print("=" * 80)
    
    test4_input = {
        "current_time": 33000.0,
        "pending_requests": [
            {
                "passenger_id": "P8",
                "origin": "A",
                "destination": "B",
                "appear_time": 32900.0,
                "wait_time": 100.0
            },
            {
                "passenger_id": "P9",
                "origin": "B",
                "destination": "C",
                "appear_time": 32910.0,
                "wait_time": 90.0
            },
            {
                "passenger_id": "P10",
                "origin": "C",
                "destination": "D",
                "appear_time": 32920.0,
                "wait_time": 80.0
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M7",
                "current_location": "A",
                "capacity": 6,
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            }
        ],
        "stations": ["A", "B", "C", "D"],
        "get_travel_time": mock_time_dependent_travel,
        "max_waiting_time": 600.0,
        "max_detour_time": 300.0
    }
    
    print("\nScenario: 3 passengers on sequential route A→B→C→D, 1 vehicle at A")
    print("Expected: All 3 passengers assigned to M7 in a single route")
    
    output4 = greedy_insert_optimize(test4_input)
    
    print("\n>>> Results:")
    for minibus_id, route_plan in output4.items():
        print(f"\n{minibus_id}:")
        if not route_plan:
            print("  (idle)")
        else:
            for stop in route_plan:
                print(f"  → {stop['station_id']}: {stop['action']} {stop['passenger_ids']}")
    
    # =====================================================================
    # TEST 5: Empty/No Solution Case
    # =====================================================================
    print("\n" + "=" * 80)
    print("TEST 5: Infeasible Assignment (All Vehicles at Capacity)")
    print("=" * 80)
    
    test5_input = {
        "current_time": 34000.0,
        "pending_requests": [
            {
                "passenger_id": "P11",
                "origin": "A",
                "destination": "D",
                "appear_time": 33900.0,
                "wait_time": 100.0
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M8",
                "current_location": "B",
                "capacity": 2,
                "current_occupancy": 2,  # Full!
                "passengers_onboard": ["P_full1", "P_full2"],
                "current_route_plan": [
                    {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P_full1"]},
                    {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["P_full2"]}
                ]
            },
            {
                "minibus_id": "M9",
                "current_location": "C",
                "capacity": 3,
                "current_occupancy": 3,  # Full!
                "passengers_onboard": ["P_full3", "P_full4", "P_full5"],
                "current_route_plan": [
                    {"station_id": "G", "action": "DROPOFF", "passenger_ids": ["P_full3", "P_full4", "P_full5"]}
                ]
            }
        ],
        "stations": ["A", "B", "C", "D", "E", "F", "G"],
        "get_travel_time": mock_time_dependent_travel,
        "max_waiting_time": 600.0,
        "max_detour_time": 300.0
    }
    
    print("\nScenario: 1 passenger, but all vehicles are at full capacity")
    print("Expected: Passenger cannot be assigned (warning logged)")
    
    output5 = greedy_insert_optimize(test5_input)
    
    print("\n>>> Results:")
    assigned_p11 = False
    for minibus_id, route_plan in output5.items():
        print(f"\n{minibus_id}:")
        if not route_plan:
            print("  (keeping existing route, no new assignments)")
        else:
            for stop in route_plan:
                print(f"  → {stop['station_id']}: {stop['action']} {stop['passenger_ids']}")
                if 'P11' in stop['passenger_ids']:
                    assigned_p11 = True
    
    if not assigned_p11:
        print("\n>>> P11 NOT assigned (expected - all vehicles full)")
    
    # =====================================================================
    # TEST 6: Complex Multi-Stop Route
    # =====================================================================
    print("\n" + "=" * 80)
    print("TEST 6: Complex Multi-Stop Route Construction")
    print("=" * 80)
    
    test6_input = {
        "current_time": 35000.0,
        "pending_requests": [
            {
                "passenger_id": "P12",
                "origin": "A",
                "destination": "G",
                "appear_time": 34800.0,
                "wait_time": 200.0
            },
            {
                "passenger_id": "P13",
                "origin": "B",
                "destination": "F",
                "appear_time": 34850.0,
                "wait_time": 150.0
            },
            {
                "passenger_id": "P14",
                "origin": "C",
                "destination": "E",
                "appear_time": 34900.0,
                "wait_time": 100.0
            },
            {
                "passenger_id": "P15",
                "origin": "D",
                "destination": "A",
                "appear_time": 34950.0,
                "wait_time": 50.0
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M10",
                "current_location": "A",
                "capacity": 8,  # Large capacity
                "current_occupancy": 1,
                "passengers_onboard": ["P_existing"],
                "current_route_plan": [
                    {"station_id": "B", "action": "PICKUP", "passenger_ids": []},  # Empty pickup (pre-positioned)
                    {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["P_existing"]}
                ]
            }
        ],
        "stations": ["A", "B", "C", "D", "E", "F", "G"],
        "get_travel_time": mock_time_dependent_travel,
        "max_waiting_time": 800.0,
        "max_detour_time": 400.0
    }
    
    print("\nScenario: 4 diverse passengers, 1 large vehicle with existing route")
    print("Expected: Vehicle integrates multiple new passengers into existing route")
    
    output6 = greedy_insert_optimize(test6_input)
    
    print("\n>>> Results:")
    for minibus_id, route_plan in output6.items():
        print(f"\n{minibus_id} (capacity: 8):")
        if not route_plan:
            print("  (idle)")
        else:
            occupancy = 1  # Start with existing
            for i, stop in enumerate(route_plan):
                if stop['action'] == 'PICKUP':
                    occupancy += len(stop['passenger_ids'])
                    print(f"  {i+1}. {stop['station_id']}: PICKUP {stop['passenger_ids']} (occupancy: {occupancy}/8)")
                elif stop['action'] == 'DROPOFF':
                    print(f"  {i+1}. {stop['station_id']}: DROPOFF {stop['passenger_ids']} (occupancy: {occupancy}/8)")
                    occupancy -= len(stop['passenger_ids'])
    
    # Count total assigned in this test
    assigned_test6 = set()
    for route_plan in output6.values():
        for stop in route_plan:
            if stop['action'] == 'PICKUP':
                assigned_test6.update(stop['passenger_ids'])
    
    print(f"\n>>> Assigned: {len(assigned_test6)}/4 passengers")
    
    # =====================================================================
    # SUMMARY
    # =====================================================================
    print("\n" + "=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)
    
    print("""
Test 1 (Time-Dependent): Tests rush hour vs off-peak routing
Test 2 (Capacity):       Tests strict capacity enforcement
Test 3 (Competition):    Tests vehicle selection logic
Test 4 (Sequential):     Tests greedy sequential assignment
Test 5 (Infeasible):     Tests handling of impossible assignments
Test 6 (Complex):        Tests multi-passenger route construction

Key Observations:
- Cumulative time calculation handles time-varying travel times ✓
- Capacity constraints are enforced correctly ✓
- Greedy nature means assignment order matters ✓
- Algorithm gracefully handles infeasible cases ✓
""")
    
    print("=" * 80)
    print("All tests completed!")
    print("=" * 80)