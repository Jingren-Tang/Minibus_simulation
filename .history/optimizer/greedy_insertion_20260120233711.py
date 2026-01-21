"""
optimizer/greedy_insertion.py (OPTIMIZED VERSION - MINIMAL CHANGES)

Greedy insertion algorithm with BEST-FIRST passenger selection and performance optimizations.

Key Improvements (INTERNAL ONLY):
1. Batch processing to limit computational cost
2. Priority-based passenger selection (waiting time + distance)
3. Iteration limits to prevent timeout
4. Merged duplicate helper functions

NO CHANGES NEEDED to other files - all optimizations are internal.
"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """
    Main entry point for greedy insertion optimization with BEST-FIRST selection.
    
    PERFORMANCE OPTIMIZATIONS (all internal):
    - Filter already assigned passengers (NEW!)
    - Batch processing: Only optimize top N passengers by priority
    - Max iterations: Prevent runaway computation
    - Smart duplicate detection
    
    Args:
        input_data: Contains current_time, pending_requests, minibuses, and network info
        
    Returns:
        Dictionary mapping minibus_id to updated route_plan
    """
    logger.info("Starting OPTIMIZED BEST-FIRST greedy insertion")
    
    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    current_time = input_data["current_time"]
    
    # If no new passengers, return existing routes unchanged
    if len(pending_requests) == 0:
        logger.info("No pending requests, returning existing routes")
        return {mb["minibus_id"]: mb["current_route_plan"] for mb in minibuses}
    
    # ========================================================================
    # NEW: Filter out passengers who are already assigned to a vehicle
    # ========================================================================
    unassigned_requests = []
    already_assigned_count = 0
    
    for request in pending_requests:
        # Check if this is a Passenger object with assigned_vehicle_id
        if hasattr(request, 'assigned_vehicle_id'):
            if request.assigned_vehicle_id is None:
                # Not assigned yet, include it
                unassigned_requests.append(request)
            else:
                # Already assigned to a vehicle, skip it
                already_assigned_count += 1
                logger.debug(
                    f"Skipping {request.passenger_id}: already assigned to {request.assigned_vehicle_id}"
                )
        else:
            # If it's a dict or doesn't have assigned_vehicle_id, include it
            unassigned_requests.append(request)
    
    if already_assigned_count > 0:
        logger.info(
            f"Filtered out {already_assigned_count} already-assigned passengers, "
            f"optimizing {len(unassigned_requests)} unassigned passengers"
        )
    
    # If all passengers are already assigned, return existing routes
    if len(unassigned_requests) == 0:
        logger.info("All passengers already assigned, returning existing routes")
        return {mb["minibus_id"]: mb["current_route_plan"] for mb in minibuses}
    
    logger.info(f"Processing {len(unassigned_requests)} unassigned passengers")
    
    # ========================================================================
    # OPTIMIZATION 1: Convert and prioritize passengers
    # ========================================================================
    
    # Convert unassigned_requests to uniform format and calculate priorities
    passenger_data = []
    
    for request in unassigned_requests:  # ← unassigned_requests
        # Handle both dict and Passenger object formats
        if isinstance(request, dict):
            passenger_id = request["passenger_id"]
            origin = request["origin"]
            destination = request["destination"]
            appear_time = request["appear_time"]
        else:
            # It's a Passenger object
            passenger_id = request.passenger_id
            origin = request.origin_station_id
            destination = request.destination_station_id
            appear_time = request.appear_time
        
        # Calculate priority (higher = more urgent)
        wait_time = current_time - appear_time
        
        # Estimate distance if possible
        try:
            get_travel_time = input_data.get("get_travel_time")
            if get_travel_time:
                estimated_distance = get_travel_time(origin, destination, current_time)
            else:
                estimated_distance = 600.0  # Default 10 minutes
        except:
            estimated_distance = 600.0
        
        # Priority formula: waiting time (more important) - distance (less important)
        # Long wait + short distance = high priority
        priority = wait_time * 2.0 - estimated_distance * 0.1
        
        passenger_data.append({
            "passenger_id": passenger_id,
            "origin": origin,
            "destination": destination,
            "appear_time": appear_time,
            "priority": priority
        })
    
    # Sort by priority (highest first)
    passenger_data.sort(reverse=True, key=lambda x: x["priority"])
    
    # ========================================================================
    # OPTIMIZATION 2: Batch processing
    # ========================================================================
    BATCH_SIZE = 15  # Process at most 30 passengers per call
    MAX_ITERATIONS = 50  # Safety limit
    
    batch_to_process = passenger_data[:BATCH_SIZE]
    
    if len(batch_to_process) < len(passenger_data):
        logger.info(
            f"Batch mode: Processing {len(batch_to_process)}/{len(passenger_data)} passengers "
            f"(priority: {batch_to_process[0]['priority']:.1f} to {batch_to_process[-1]['priority']:.1f})"
        )
    else:
        logger.info(f"Processing all {len(batch_to_process)} passengers")
    
    
    # ========================================================================
    # Convert to internal working format
    # ========================================================================
    vehicles = _initialize_vehicles(minibuses)
    assigned_passengers = set()
    remaining_indices = set(range(len(batch_to_process)))
    
    iteration = 0
    
    # ========================================================================
    # BEST-FIRST LOOP with iteration limit
    # ========================================================================
    while remaining_indices and iteration < MAX_ITERATIONS:
        iteration += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"Iteration {iteration}: {len(remaining_indices)} passengers remaining")
        
        best_passenger_idx = None
        best_vehicle = None
        best_route = None
        best_cost_increase = float('inf')
        best_passenger_id = None
        
        # Evaluate EVERY unassigned passenger in batch
        for idx in remaining_indices:
            passenger = batch_to_process[idx]
            passenger_id = passenger["passenger_id"]
            origin = passenger["origin"]
            destination = passenger["destination"]
            priority = passenger["priority"]
            
            # Try inserting this passenger into EVERY vehicle
            for vehicle in vehicles:
                # Get current route cost
                current_cost = _compute_route_cost(vehicle["route"], input_data)
                
                # Try insertion
                candidate_route, new_cost = _try_insert_passenger(
                    vehicle=vehicle,
                    passenger_id=passenger_id,
                    origin=origin,
                    destination=destination,
                    input_data=input_data
                )
                
                # If feasible, compute cost increase
                if candidate_route is not None:
                    cost_increase = new_cost - current_cost
                    
                    # Adjust cost by priority (prefer urgent passengers)
                    # Higher priority = lower adjusted cost
                    adjusted_cost = cost_increase - priority * 0.5
                    
                    logger.debug(
                        f"  {passenger_id} → {vehicle['id']}: "
                        f"cost_increase={cost_increase:.1f}, priority={priority:.1f}, "
                        f"adjusted={adjusted_cost:.1f}"
                    )
                    
                    # Track the best option across ALL (passenger, vehicle) pairs
                    if adjusted_cost < best_cost_increase:
                        best_passenger_idx = idx
                        best_vehicle = vehicle
                        best_route = candidate_route
                        best_cost_increase = adjusted_cost
                        best_passenger_id = passenger_id
        
        # If we found a feasible assignment, apply it
        if best_passenger_idx is not None:
            best_vehicle["route"] = best_route
            assigned_passengers.add(best_passenger_id)
            remaining_indices.remove(best_passenger_idx)
            
            logger.info(
                f"✓ Iteration {iteration}: Assigned {best_passenger_id} to {best_vehicle['id']}, "
                f"adjusted_cost={best_cost_increase:.1f}"
            )
        else:
            # No feasible assignment for any remaining passenger
            logger.warning(
                f"✗ Iteration {iteration}: No feasible assignment found for "
                f"{len(remaining_indices)} remaining passengers"
            )
            break
    
    # Check if we hit iteration limit
    if iteration >= MAX_ITERATIONS and len(remaining_indices) > 0:
        logger.warning(
            f"Stopped after {MAX_ITERATIONS} iterations with {len(remaining_indices)} "
            f"passengers still unassigned"
        )
    
    # Convert back to output format
    output = _generate_output(vehicles)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Optimization complete: {len(assigned_passengers)}/{len(batch_to_process)} assigned")
    
    # Log unassigned passengers
    if len(assigned_passengers) < len(batch_to_process):
        unassigned = [batch_to_process[idx]["passenger_id"] for idx in remaining_indices]
        logger.warning(f"Unassigned passengers: {unassigned}")
    
    return output


def _initialize_vehicles(minibuses: List[Dict]) -> List[Dict]:
    """
    Convert minibus data to internal vehicle representation.
    
    Internal format:
    {
        "id": minibus_id,
        "capacity": max capacity,
        "route": [
            {"station": "A", "pickup": ["P1"], "dropoff": ["P2"]},
            {"station": "B", "pickup": [], "dropoff": ["P1", "P3"]},
            ...
        ]
    }
    """
    vehicles = []
    
    for mb in minibuses:
        minibus_id = mb["minibus_id"]
        capacity = mb["capacity"]
        current_occupancy = len(mb["passengers_onboard"])
        
        # Build route from current_route_plan
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
    """
    Convert route_plan to internal route format.
    Merges consecutive stops at the same station.
    """
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
        
        # If we've moved to a new station, save the previous one
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
    
    # Don't forget the last station
    if current_station is not None:
        route.append({
            "station": current_station,
            "pickup": current_pickups,
            "dropoff": current_dropoffs
        })
    
    return route


def _try_insert_passenger(
    vehicle: Dict,
    passenger_id: str,
    origin: str,
    destination: str,
    input_data: Dict
) -> Tuple[Optional[List[Dict]], float]:
    """
    Try to insert a passenger into a vehicle's route.
    
    Strategy: ALWAYS insert both pickup and dropoff as NEW stops.
    Try all valid positions where pickup comes before dropoff.
    
    Returns:
        (best_route, cost) if feasible, else (None, inf)
    """
    current_route = vehicle["route"]
    capacity = vehicle["capacity"]
    initial_occupancy = vehicle["initial_occupancy"]
    
    best_route = None
    best_cost = float('inf')
    
    # Try all combinations of insertion positions
    # pickup_pos can be 0 to len(route)
    # dropoff_pos must be > pickup_pos
    for pickup_pos in range(len(current_route) + 1):
        for dropoff_pos in range(pickup_pos + 1, len(current_route) + 2):
            # Create candidate route
            candidate = current_route.copy()
            
            # Insert pickup first (at earlier position)
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
            
            # Check capacity feasibility
            if _is_capacity_feasible(candidate, capacity, initial_occupancy):
                # Compute cost
                cost = _compute_route_cost(candidate, input_data)
                
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate
    
    return best_route, best_cost


def _is_capacity_feasible(
    route: List[Dict],
    capacity: int,
    initial_occupancy: int
) -> bool:
    """
    Check if route respects capacity constraints.
    
    CRITICAL FIX: Merge stations BEFORE checking capacity!
    The actual execution will use merged stations, so we must check against that.
    
    Args:
        route: List of stops (may have duplicates)
        capacity: Maximum vehicle capacity
        initial_occupancy: Number of passengers already onboard
        
    Returns:
        True if route is feasible after merging, False otherwise
    """
    # ========================================================================
    # FIXED: Use single merge function (removed duplicate _merge_consecutive_stations_for_check)
    # ========================================================================
    merged_route = _merge_consecutive_stations(route)
    
    occupancy = initial_occupancy
    
    for i, stop in enumerate(merged_route):
        # CRITICAL ORDER: Dropoff BEFORE Pickup
        occupancy -= len(stop["dropoff"])
        occupancy += len(stop["pickup"])
        
        # Check constraints
        if occupancy < 0:
            logger.debug(f"  ✗ Negative occupancy {occupancy} at stop {i+1}")
            return False
        
        if occupancy > capacity:
            logger.debug(f"  ✗ Over capacity {occupancy}/{capacity} at stop {i+1}")
            return False
    
    return True


def _compute_route_cost(route: List[Dict], input_data: Dict) -> float:
    """
    Compute total travel time for a route.
    
    Uses cumulative time calculation to handle time-dependent travel times correctly.
    """
    if len(route) <= 1:
        return 0.0
    
    get_travel_time = input_data["get_travel_time"]
    current_time = input_data["current_time"]
    
    total_time = 0.0
    arrival_time = current_time
    
    for i in range(len(route) - 1):
        origin_station = route[i]["station"]
        dest_station = route[i + 1]["station"]
        
        # Get travel time at current arrival time
        travel_time = get_travel_time(origin_station, dest_station, arrival_time)
        
        total_time += travel_time
        arrival_time += travel_time
    
    return total_time


def _generate_output(vehicles: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Convert internal vehicle format back to output format.
    
    CRITICAL FIX: When merging creates a stop with both pickup and dropoff,
    we MUST output them in the correct order for capacity validation.
    
    The test validation code processes actions in OUTPUT ORDER, so we must ensure:
    1. DROPOFF actions come before PICKUP actions at the same station
    2. This matches the order we used in _is_capacity_feasible
    """
    output = {}
    
    for vehicle in vehicles:
        minibus_id = vehicle["id"]
        route = vehicle["route"]
        
        # Merge consecutive stops at same station
        merged_route = _merge_consecutive_stations(route)
        
        # Convert to output format with CORRECT ORDER
        route_plan = []
        for stop in merged_route:
            station = stop["station"]
            
            # CRITICAL: DROPOFF before PICKUP
            # This is the order we used in capacity checking!
            
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
    """
    Merge consecutive stops at the same station.
    
    ========================================================================
    FIXED: This is now the ONLY merge function (removed duplicate)
    Used by both _is_capacity_feasible and _generate_output
    ========================================================================
    
    CRITICAL FIX: When merging, maintain DROPOFF-before-PICKUP order within the station.
    
    Example:
        [{"station": "A", "pickup": ["P1"], "dropoff": []},
         {"station": "A", "pickup": [], "dropoff": ["P2"]}]
        
    Becomes:
        [{"station": "A", "pickup": ["P1"], "dropoff": ["P2"]}]
        
    But the OUTPUT format must show DROPOFF first:
        Output: [
            {"station": "A", "action": "DROPOFF", "passenger_ids": ["P2"]},
            {"station": "A", "action": "PICKUP", "passenger_ids": ["P1"]}
        ]
    """
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
            # Same station - merge
            current["pickup"].extend(stop["pickup"])
            current["dropoff"].extend(stop["dropoff"])
        else:
            # Different station - save current and start new
            if current["pickup"] or current["dropoff"]:
                merged.append(current)
            
            current = {
                "station": stop["station"],
                "pickup": stop["pickup"].copy(),
                "dropoff": stop["dropoff"].copy()
            }
    
    # Don't forget the last stop
    if current["pickup"] or current["dropoff"]:
        merged.append(current)
    
    return merged


# ============================================================================
# Test code (if run directly)
# ============================================================================

if __name__ == "__main__":
    import json
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("GREEDY INSERTION - OPTIMIZED BEST-FIRST TEST")
    print("=" * 80)
    
    def mock_travel_time(origin, dest, time):
        """Mock travel times: different distances"""
        distances = {
            ("A", "B"): 60.0,   # 1 min
            ("B", "A"): 60.0,
            ("A", "C"): 120.0,  # 2 min
            ("C", "A"): 120.0,
            ("A", "Z"): 1800.0, # 30 min (very far!)
            ("Z", "A"): 1800.0,
            ("B", "C"): 60.0,
            ("C", "B"): 60.0,
        }
        return distances.get((origin, dest), 300.0)
    
    # Test 1: Basic test with 3 passengers
    print("\n" + "=" * 80)
    print("TEST 1: 3 passengers (1 far, 2 close), 1 vehicle (capacity=2)")
    print("=" * 80)
    
    test_input_1 = {
        "current_time": 1000.0,
        "pending_requests": [
            {
                "passenger_id": "P1",
                "origin": "A",
                "destination": "Z",  # Very far!
                "appear_time": 900.0,
            },
            {
                "passenger_id": "P2",
                "origin": "A",
                "destination": "B",  # Close
                "appear_time": 950.0,
            },
            {
                "passenger_id": "P3",
                "origin": "A",
                "destination": "C",  # Close
                "appear_time": 980.0,
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M1",
                "current_location": "A",
                "capacity": 2,  # Only room for 2 passengers
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            }
        ],
        "get_travel_time": mock_travel_time,
    }
    
    print("Expected: Should choose P2 and P3 (close) over P1 (far)")
    result_1 = greedy_insert_optimize(test_input_1)
    
    print("\nRESULT:")
    for minibus_id, route_plan in result_1.items():
        print(f"\n{minibus_id}:")
        if not route_plan:
            print("  (idle)")
        else:
            for stop in route_plan:
                print(f"  {stop['station_id']}: {stop['action']} {stop['passenger_ids']}")
    
    # Test 2: Batch processing test
    print("\n" + "=" * 80)
    print("TEST 2: 50 passengers, 2 vehicles (testing batch mode)")
    print("=" * 80)
    
    # Generate 50 test passengers
    test_passengers = []
    for i in range(50):
        test_passengers.append({
            "passenger_id": f"P{i+1}",
            "origin": "A" if i % 2 == 0 else "B",
            "destination": "C" if i % 3 == 0 else "D",
            "appear_time": 900.0 + i * 10,  # Staggered appearance
        })
    
    test_input_2 = {
        "current_time": 2000.0,
        "pending_requests": test_passengers,
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
                "capacity": 4,
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            }
        ],
        "get_travel_time": mock_travel_time,
    }
    
    print(f"Generated {len(test_passengers)} passengers")
    print("Batch mode should limit to 30 passengers...")
    
    result_2 = greedy_insert_optimize(test_input_2)
    
    print("\nRESULT:")
    total_assigned = 0
    for minibus_id, route_plan in result_2.items():
        assigned_in_route = set()
        for stop in route_plan:
            if stop['action'] == 'PICKUP':
                assigned_in_route.update(stop['passenger_ids'])
        total_assigned += len(assigned_in_route)
        print(f"{minibus_id}: {len(route_plan)} stops, {len(assigned_in_route)} passengers")
    
    print(f"\nTotal assigned: {total_assigned}/{len(test_passengers)}")
    print(f"Batch mode limited processing as expected: {total_assigned <= 30}")
    
    print("\n" + "=" * 80)