"""
optimizer/greedy_insertion.py (FIXED VERSION)

CRITICAL FIX: Prevent unnecessary duplicate station visits by:
1. Reusing existing stations in route when possible
2. Only inserting new stations when necessary
3. Proper time-based feasibility checking


"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """
    Main entry point for greedy insertion optimization with BEST-FIRST selection.
    """
    logger.info("Starting OPTIMIZED BEST-FIRST greedy insertion")
    
    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    current_time = input_data["current_time"]
    
    if len(pending_requests) == 0:
        logger.info("No pending requests, returning existing routes")
        return {mb["minibus_id"]: mb["current_route_plan"] for mb in minibuses}
    
    # Filter out already assigned passengers
    unassigned_requests = []
    already_assigned_count = 0
    
    for request in pending_requests:
        if hasattr(request, 'assigned_vehicle_id'):
            if request.assigned_vehicle_id is None:
                unassigned_requests.append(request)
            else:
                already_assigned_count += 1
                logger.debug(
                    f"Skipping {request.passenger_id}: already assigned to {request.assigned_vehicle_id}"
                )
        else:
            unassigned_requests.append(request)
    
    if already_assigned_count > 0:
        logger.info(
            f"Filtered out {already_assigned_count} already-assigned passengers, "
            f"optimizing {len(unassigned_requests)} unassigned passengers"
        )
    
    if len(unassigned_requests) == 0:
        logger.info("All passengers already assigned, returning existing routes")
        return {mb["minibus_id"]: mb["current_route_plan"] for mb in minibuses}
    
    logger.info(f"Processing {len(unassigned_requests)} unassigned passengers")
    
    # Convert and prioritize passengers
    passenger_data = []
    
    for request in unassigned_requests:
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
        
        priority = wait_time * 2.0 - estimated_distance * 0.1
        
        passenger_data.append({
            "passenger_id": passenger_id,
            "origin": origin,
            "destination": destination,
            "appear_time": appear_time,
            "priority": priority
        })
    
    passenger_data.sort(reverse=True, key=lambda x: x["priority"])
    
    BATCH_SIZE = 20
    MAX_ITERATIONS = 25
    
    batch_to_process = passenger_data[:BATCH_SIZE]
    
    if len(batch_to_process) < len(passenger_data):
        logger.info(
            f"Batch mode: Processing {len(batch_to_process)}/{len(passenger_data)} passengers"
        )
    else:
        logger.info(f"Processing all {len(batch_to_process)} passengers")
    
    # Convert to internal working format
    vehicles = _initialize_vehicles(minibuses)
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
                
                # ✅ FIXED: Use new insertion method that reuses existing stations
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
    
    output = _generate_output(vehicles)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Optimization complete: {len(assigned_passengers)}/{len(batch_to_process)} assigned")
    
    if len(assigned_passengers) < len(batch_to_process):
        unassigned = [batch_to_process[idx]["passenger_id"] for idx in remaining_indices]
        logger.warning(f"Unassigned passengers: {unassigned}")
    
    return output


def _try_insert_passenger_smart(
    vehicle: Dict,
    passenger_id: str,
    origin: str,
    destination: str,
    input_data: Dict
) -> Tuple[Optional[List[Dict]], float]:
    """
    
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
                candidate = current_route.copy()
                
                # Add passenger to existing pickup station
                candidate[pickup_idx] = {
                    "station": origin,
                    "pickup": candidate[pickup_idx]["pickup"] + [passenger_id],
                    "dropoff": candidate[pickup_idx]["dropoff"].copy()
                }
                
                # Add passenger to existing dropoff station
                candidate[dropoff_idx] = {
                    "station": destination,
                    "pickup": candidate[dropoff_idx]["pickup"].copy(),
                    "dropoff": candidate[dropoff_idx]["dropoff"] + [passenger_id]
                }
                
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
            candidate = current_route.copy()
            
            # Reuse existing origin
            candidate[pickup_idx] = {
                "station": origin,
                "pickup": candidate[pickup_idx]["pickup"] + [passenger_id],
                "dropoff": candidate[pickup_idx]["dropoff"].copy()
            }
            
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
            candidate = current_route.copy()
            
            # Insert new origin
            candidate.insert(pickup_pos, {
                "station": origin,
                "pickup": [passenger_id],
                "dropoff": []
            })
            
            # Reuse existing destination (index shifts after insert)
            adjusted_dropoff_idx = dropoff_idx + 1 if dropoff_idx >= pickup_pos else dropoff_idx
            candidate[adjusted_dropoff_idx] = {
                "station": destination,
                "pickup": candidate[adjusted_dropoff_idx]["pickup"].copy(),
                "dropoff": candidate[adjusted_dropoff_idx]["dropoff"] + [passenger_id]
            }
            
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
            candidate = current_route.copy()
            
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


# ========================================================================
# Keep all other helper functions unchanged
# ========================================================================

def _initialize_vehicles(minibuses: List[Dict]) -> List[Dict]:
    """Convert minibus data to internal vehicle representation."""
    vehicles = []
    
    for mb in minibuses:
        minibus_id = mb["minibus_id"]
        capacity = mb["capacity"]
        current_occupancy = len(mb["passengers_onboard"])
        
        route = _build_route_from_plan(mb["current_route_plan"])
        
        vehicle = {
            "id": minibus_id,
            "capacity": capacity,
            "initial_occupancy": current_occupancy,
            "route": route
        }
        
        vehicles.append(vehicle)
        
        logger.debug(f"Initialized {minibus_id}: capacity={capacity}, occupancy={current_occupancy}, stops={len(route)}")
    
    return vehicles


def _build_route_from_plan(route_plan: List[Dict]) -> List[Dict]:
    """Convert route_plan to internal route format."""
    if not route_plan:
        return []
    
    route = []
    current_station = None
    current_pickups = []
    current_dropoffs = []
    
    for stop in route_plan:
        station = stop["station_id"]
        action = stop["action"]
        passengers = stop["passenger_ids"]
        
        if station != current_station and current_station is not None:
            route.append({
                "station": current_station,
                "pickup": current_pickups,
                "dropoff": current_dropoffs
            })
            current_pickups = []
            current_dropoffs = []
        
        current_station = station
        
        if action == "PICKUP":
            current_pickups.extend(passengers)
        elif action == "DROPOFF":
            current_dropoffs.extend(passengers)
    
    if current_station is not None:
        route.append({
            "station": current_station,
            "pickup": current_pickups,
            "dropoff": current_dropoffs
        })
    
    return route


def _is_capacity_feasible(
    route: List[Dict],
    capacity: int,
    initial_occupancy: int
) -> bool:
    """Check if route respects capacity constraints."""
    merged_route = _merge_consecutive_stations(route)
    
    occupancy = initial_occupancy
    
    for i, stop in enumerate(merged_route):
        # CRITICAL ORDER: Dropoff BEFORE Pickup
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
    
    get_travel_time = input_data["get_travel_time"]
    current_time = input_data["current_time"]
    
    total_time = 0.0
    arrival_time = current_time
    
    for i in range(len(route) - 1):
        origin_station = route[i]["station"]
        dest_station = route[i + 1]["station"]
        
        travel_time = get_travel_time(origin_station, dest_station, arrival_time)
        
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
            
            # CRITICAL: DROPOFF before PICKUP
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
