"""
optimizer/greedy_insertion.py (FIXED VERSION v2)

CRITICAL FIX: 
1. No longer skips "assigned" passengers - re-optimizes ALL pending passengers
2. Prevents passengers from being lost when routes change
"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """
    Main entry point for greedy insertion optimization with BEST-FIRST selection.
    
    ✅ FIXED: No longer skips "assigned" passengers - re-optimizes all pending passengers
    each time to ensure passengers are not lost when routes change.
    """
    logger.info("Starting OPTIMIZED BEST-FIRST greedy insertion")
    
    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    current_time = input_data["current_time"]
    
    if len(pending_requests) == 0:
        logger.info("No pending requests, returning existing routes")
        return {mb["minibus_id"]: mb["current_route_plan"] for mb in minibuses}
    
    # =========================================================================
    # ✅ CRITICAL FIX: Process ALL pending passengers, not just "unassigned" ones
    # 
    # The previous logic skipped passengers with assigned_vehicle_id != None,
    # but this caused passengers to be permanently lost when:
    # 1. Passenger assigned to MINIBUS_1 in iteration N
    # 2. MINIBUS_1's route changes in iteration N+1 (due to new passengers)
    # 3. Passenger is skipped (already assigned) but not in any route!
    # 
    # The correct approach: re-optimize all pending passengers every time.
    # The optimizer should always produce a complete, consistent route plan.
    # =========================================================================
    
    logger.info(f"Processing ALL {len(pending_requests)} pending passengers (re-optimizing)")
    
    # Convert and prioritize ALL passengers
    passenger_data = []
    
    for request in pending_requests:
        if isinstance(request, dict):
            passenger_id = request["passenger_id"]
            origin = request["origin"]
            destination = request["destination"]
            appear_time = request["appear_time"]
        else:
            passenger_id = request.passenger_id
            origin = request.origin_station_id
            destination = request.destination_station_id
            appear_time = request.appear_time
        
        wait_time = current_time - appear_time
        
        try:
            get_travel_time = input_data.get("get_travel_time")
            if get_travel_time:
                estimated_distance = get_travel_time(origin, destination, current_time)
            else:
                estimated_distance = 600.0
        except:
            estimated_distance = 600.0
        
        # Priority: longer wait time = higher priority
        priority = wait_time * 5.0 - estimated_distance * 0.1
        
        passenger_data.append({
            "passenger_id": passenger_id,
            "origin": origin,
            "destination": destination,
            "appear_time": appear_time,
            "priority": priority
        })
    
    # Sort by priority (highest first)
    passenger_data.sort(reverse=True, key=lambda x: x["priority"])
    
    # Batch processing parameters
    BATCH_SIZE = 50
    MAX_ITERATIONS = 100
    
    batch_to_process = passenger_data[:BATCH_SIZE]
    
    if len(batch_to_process) < len(passenger_data):
        logger.info(
            f"Batch mode: Processing {len(batch_to_process)}/{len(passenger_data)} passengers"
        )
    else:
        logger.info(f"Processing all {len(batch_to_process)} passengers")
    
    # =========================================================================
    # ✅ IMPORTANT: Initialize vehicles with EMPTY routes
    # 
    # We rebuild all routes from scratch to ensure consistency.
    # This prevents the "lost passenger" problem where a passenger is
    # assigned but then removed when routes are recalculated.
    # =========================================================================
    vehicles = _initialize_vehicles_fresh(minibuses)
    
    assigned_passengers = set()
    remaining_indices = set(range(len(batch_to_process)))
    
    iteration = 0
    
    # BEST-FIRST LOOP
    while remaining_indices and iteration < MAX_ITERATIONS:
        iteration += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"Iteration {iteration}: {len(remaining_indices)} passengers remaining")
        
        best_passenger_idx = None
        best_vehicle = None
        best_route = None
        best_cost_increase = float('inf')
        best_passenger_id = None
        
        for idx in remaining_indices:
            passenger = batch_to_process[idx]
            passenger_id = passenger["passenger_id"]
            origin = passenger["origin"]
            destination = passenger["destination"]
            priority = passenger["priority"]
            
            for vehicle in vehicles:
                current_cost = _compute_route_cost(vehicle["route"], input_data)
                
                # Try to insert this passenger into this vehicle's route
                candidate_route, new_cost = _try_insert_passenger_smart(
                    vehicle=vehicle,
                    passenger_id=passenger_id,
                    origin=origin,
                    destination=destination,
                    input_data=input_data
                )
                
                if candidate_route is not None:
                    cost_increase = new_cost - current_cost
                    adjusted_cost = cost_increase - priority * 0.5
                    
                    logger.debug(
                        f"  {passenger_id} → {vehicle['id']}: "
                        f"cost_increase={cost_increase:.1f}, priority={priority:.1f}, "
                        f"adjusted={adjusted_cost:.1f}"
                    )
                    
                    if adjusted_cost < best_cost_increase:
                        best_passenger_idx = idx
                        best_vehicle = vehicle
                        best_route = candidate_route
                        best_cost_increase = adjusted_cost
                        best_passenger_id = passenger_id
        
        if best_passenger_idx is not None:
            best_vehicle["route"] = best_route
            assigned_passengers.add(best_passenger_id)
            remaining_indices.remove(best_passenger_idx)
            
            logger.info(
                f"✓ Iteration {iteration}: Assigned {best_passenger_id} to {best_vehicle['id']}, "
                f"adjusted_cost={best_cost_increase:.1f}"
            )
        else:
            logger.warning(
                f"✗ Iteration {iteration}: No feasible assignment found for "
                f"{len(remaining_indices)} remaining passengers"
            )
            break
    
    if iteration >= MAX_ITERATIONS and len(remaining_indices) > 0:
        logger.warning(
            f"Stopped after {MAX_ITERATIONS} iterations with {len(remaining_indices)} "
            f"passengers still unassigned"
        )
    
    # Generate output
    output = _generate_output(vehicles)
    
    # Log summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Optimization complete: {len(assigned_passengers)}/{len(batch_to_process)} assigned")
    
    if len(assigned_passengers) < len(batch_to_process):
        unassigned = [batch_to_process[idx]["passenger_id"] for idx in remaining_indices]
        logger.warning(f"Unassigned passengers: {unassigned}")
    
    # ✅ Log which passengers are in each vehicle's plan
    for minibus_id, plan in output.items():
        pickup_passengers = []
        for stop in plan:
            if stop["action"] == "PICKUP":
                pickup_passengers.extend(stop["passenger_ids"])
        if pickup_passengers:
            logger.info(f"  {minibus_id} will pickup: {pickup_passengers}")
    
    return output


def _initialize_vehicles_fresh(minibuses: List[Dict]) -> List[Dict]:
    """
    Initialize vehicles with consideration for passengers already onboard.
    
    ✅ FIXED: Start with empty routes but preserve onboard passenger dropoffs.
    """
    vehicles = []
    
    for mb in minibuses:
        minibus_id = mb["minibus_id"]
        capacity = mb["capacity"]
        current_occupancy = len(mb["passengers_onboard"])
        passengers_onboard = mb["passengers_onboard"]
        current_location = mb["current_location"]
        
        # Build initial route: only dropoffs for passengers already onboard
        route = []
        
        # Check existing route for dropoff destinations of onboard passengers
        existing_plan = mb["current_route_plan"]
        dropoff_destinations = {}
        
        for stop in existing_plan:
            if stop["action"] == "DROPOFF":
                for pid in stop["passenger_ids"]:
                    if pid in passengers_onboard:
                        dest = stop["station_id"]
                        if dest not in dropoff_destinations:
                            dropoff_destinations[dest] = []
                        dropoff_destinations[dest].append(pid)
        
        # Create dropoff stops for onboard passengers
        for dest, pids in dropoff_destinations.items():
            route.append({
                "station": dest,
                "pickup": [],
                "dropoff": pids
            })
        
        vehicle = {
            "id": minibus_id,
            "capacity": capacity,
            "initial_occupancy": current_occupancy,
            "current_location": current_location,
            "route": route
        }
        
        vehicles.append(vehicle)
        
        logger.debug(
            f"Initialized {minibus_id}: capacity={capacity}, "
            f"occupancy={current_occupancy}, onboard={passengers_onboard}, "
            f"initial_dropoffs={len(route)}"
        )
    
    return vehicles


def _try_insert_passenger_smart(
    vehicle: Dict,
    passenger_id: str,
    origin: str,
    destination: str,
    input_data: Dict
) -> Tuple[Optional[List[Dict]], float]:
    """
    Try to insert a passenger into a vehicle's route using smart insertion.
    
    Strategy:
    1. Check if origin/destination already exist in route
    2. Try to reuse existing stations first (cheaper)
    3. Only insert new stations if necessary
    4. Ensure pickup comes before dropoff
    5. Validate capacity and time feasibility
    
    Returns:
        (best_route, cost) if feasible, else (None, inf)
    """
    current_route = vehicle["route"]
    capacity = vehicle["capacity"]
    initial_occupancy = vehicle["initial_occupancy"]
    
    best_route = None
    best_cost = float('inf')
    
    # Find existing positions of origin and destination in route
    origin_positions = []
    destination_positions = []
    
    for i, stop in enumerate(current_route):
        if stop["station"] == origin:
            origin_positions.append(i)
        if stop["station"] == destination:
            destination_positions.append(i)
    
    # ====================================================================
    # STRATEGY 1: Try reusing BOTH existing stations (cheapest)
    # ====================================================================
    for pickup_idx in origin_positions:
        for dropoff_idx in destination_positions:
            if dropoff_idx > pickup_idx:  # Must pickup before dropoff
                candidate = _deep_copy_route(current_route)
                
                # Add passenger to existing pickup station
                candidate[pickup_idx]["pickup"] = candidate[pickup_idx]["pickup"] + [passenger_id]
                
                # Add passenger to existing dropoff station
                candidate[dropoff_idx]["dropoff"] = candidate[dropoff_idx]["dropoff"] + [passenger_id]
                
                # Check feasibility
                if _is_capacity_feasible(candidate, capacity, initial_occupancy):
                    cost = _compute_route_cost(candidate, input_data)
                    if cost < best_cost:
                        best_cost = cost
                        best_route = candidate
                        logger.debug(
                            f"  Reused BOTH stations: pickup at {pickup_idx}, "
                            f"dropoff at {dropoff_idx}, cost={cost:.1f}"
                        )
    
    # ====================================================================
    # STRATEGY 2: Reuse origin, insert new destination
    # ====================================================================
    for pickup_idx in origin_positions:
        # Try inserting dropoff at all positions AFTER pickup
        for dropoff_pos in range(pickup_idx + 1, len(current_route) + 1):
            candidate = _deep_copy_route(current_route)
            
            # Reuse existing origin
            candidate[pickup_idx]["pickup"] = candidate[pickup_idx]["pickup"] + [passenger_id]
            
            # Insert new destination
            candidate.insert(dropoff_pos, {
                "station": destination,
                "pickup": [],
                "dropoff": [passenger_id]
            })
            
            if _is_capacity_feasible(candidate, capacity, initial_occupancy):
                cost = _compute_route_cost(candidate, input_data)
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate
                    logger.debug(
                        f"  Reused origin at {pickup_idx}, inserted dropoff at {dropoff_pos}, "
                        f"cost={cost:.1f}"
                    )
    
    # ====================================================================
    # STRATEGY 3: Insert new origin, reuse destination
    # ====================================================================
    for dropoff_idx in destination_positions:
        # Try inserting pickup at all positions BEFORE dropoff
        for pickup_pos in range(dropoff_idx + 1):
            candidate = _deep_copy_route(current_route)
            
            # Insert new origin
            candidate.insert(pickup_pos, {
                "station": origin,
                "pickup": [passenger_id],
                "dropoff": []
            })
            
            # Reuse existing destination (index shifts after insert)
            adjusted_dropoff_idx = dropoff_idx + 1
            candidate[adjusted_dropoff_idx]["dropoff"] = candidate[adjusted_dropoff_idx]["dropoff"] + [passenger_id]
            
            if _is_capacity_feasible(candidate, capacity, initial_occupancy):
                cost = _compute_route_cost(candidate, input_data)
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate
                    logger.debug(
                        f"  Inserted origin at {pickup_pos}, reused dropoff at {adjusted_dropoff_idx}, "
                        f"cost={cost:.1f}"
                    )
    
    # ====================================================================
    # STRATEGY 4: Insert BOTH as new stations (most expensive)
    # ====================================================================
    for pickup_pos in range(len(current_route) + 1):
        for dropoff_pos in range(pickup_pos + 1, len(current_route) + 2):
            candidate = _deep_copy_route(current_route)
            
            # Insert pickup
            candidate.insert(pickup_pos, {
                "station": origin,
                "pickup": [passenger_id],
                "dropoff": []
            })
            
            # Insert dropoff (position shifts by 1 after pickup insertion)
            candidate.insert(dropoff_pos, {
                "station": destination,
                "pickup": [],
                "dropoff": [passenger_id]
            })
            
            if _is_capacity_feasible(candidate, capacity, initial_occupancy):
                cost = _compute_route_cost(candidate, input_data)
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate
                    logger.debug(
                        f"  Inserted BOTH stations: pickup at {pickup_pos}, "
                        f"dropoff at {dropoff_pos}, cost={cost:.1f}"
                    )
    
    return best_route, best_cost


def _deep_copy_route(route: List[Dict]) -> List[Dict]:
    """Create a deep copy of a route to avoid mutation issues."""
    return [
        {
            "station": stop["station"],
            "pickup": stop["pickup"].copy(),
            "dropoff": stop["dropoff"].copy()
        }
        for stop in route
    ]


def _is_capacity_feasible(
    route: List[Dict],
    capacity: int,
    initial_occupancy: int
) -> bool:
    """Check if route respects capacity constraints."""
    merged_route = _merge_consecutive_stations(route)
    
    occupancy = initial_occupancy
    
    for i, stop in enumerate(merged_route):
        # CRITICAL ORDER: Dropoff BEFORE Pickup at each station
        occupancy -= len(stop["dropoff"])
        occupancy += len(stop["pickup"])
        
        if occupancy < 0:
            logger.debug(f"  ✗ Negative occupancy {occupancy} at stop {i+1}")
            return False
        
        if occupancy > capacity:
            logger.debug(f"  ✗ Over capacity {occupancy}/{capacity} at stop {i+1}")
            return False
    
    return True


def _compute_route_cost(route: List[Dict], input_data: Dict) -> float:
    """Compute total travel time for a route."""
    if len(route) <= 1:
        return 0.0
    
    get_travel_time = input_data.get("get_travel_time")
    if get_travel_time is None:
        # Fallback: count number of stops as cost
        return float(len(route)) * 300.0
    
    current_time = input_data["current_time"]
    
    total_time = 0.0
    arrival_time = current_time
    
    for i in range(len(route) - 1):
        origin_station = route[i]["station"]
        dest_station = route[i + 1]["station"]
        
        try:
            travel_time = get_travel_time(origin_station, dest_station, arrival_time)
        except:
            travel_time = 300.0  # Default 5 minutes
        
        total_time += travel_time
        arrival_time += travel_time
    
    return total_time


def _generate_output(vehicles: List[Dict]) -> Dict[str, List[Dict]]:
    """Convert internal vehicle format back to output format."""
    output = {}
    
    for vehicle in vehicles:
        minibus_id = vehicle["id"]
        route = vehicle["route"]
        
        merged_route = _merge_consecutive_stations(route)
        
        route_plan = []
        for stop in merged_route:
            station = stop["station"]
            
            # CRITICAL: DROPOFF before PICKUP at each station
            if stop["dropoff"]:
                route_plan.append({
                    "station_id": station,
                    "action": "DROPOFF",
                    "passenger_ids": stop["dropoff"]
                })
            
            if stop["pickup"]:
                route_plan.append({
                    "station_id": station,
                    "action": "PICKUP",
                    "passenger_ids": stop["pickup"]
                })
        
        output[minibus_id] = route_plan
    
    return output


def _merge_consecutive_stations(route: List[Dict]) -> List[Dict]:
    """Merge consecutive stops at the same station."""
    if not route:
        return []
    
    merged = []
    current = {
        "station": route[0]["station"],
        "pickup": route[0]["pickup"].copy(),
        "dropoff": route[0]["dropoff"].copy()
    }
    
    for stop in route[1:]:
        if stop["station"] == current["station"]:
            current["pickup"].extend(stop["pickup"])
            current["dropoff"].extend(stop["dropoff"])
        else:
            if current["pickup"] or current["dropoff"]:
                merged.append(current)
            
            current = {
                "station": stop["station"],
                "pickup": stop["pickup"].copy(),
                "dropoff": stop["dropoff"].copy()
            }
    
    if current["pickup"] or current["dropoff"]:
        merged.append(current)
    
    return merged