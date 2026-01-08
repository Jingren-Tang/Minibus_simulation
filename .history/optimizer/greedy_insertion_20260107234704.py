"""
optimizer/greedy_insertion.py (CLEAN REWRITE)

Greedy insertion algorithm for dynamic vehicle routing.
Uses a simple, robust approach that always inserts both pickup and dropoff as new stops.

Key Design Principles:
1. Always insert BOTH pickup and dropoff stations as NEW stops
2. Never reuse existing stations (avoids complex capacity tracking bugs)
3. ALWAYS enforce DROPOFF before PICKUP order when checking capacity
4. Clean and merge duplicate stations only in final output
"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """
    Main entry point for greedy insertion optimization.
    
    Args:
        input_data: Contains current_time, pending_requests, minibuses, and network info
        
    Returns:
        Dictionary mapping minibus_id to updated route_plan
    """
    logger.info("Starting greedy insertion optimization")
    logger.info(f"Pending requests: {len(input_data['pending_requests'])}")
    logger.info(f"Active vehicles: {len(input_data['minibuses'])}")
    
    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    
    # If no new passengers, return existing routes unchanged
    if len(pending_requests) == 0:
        logger.info("No pending requests, returning existing routes")
        return {mb["minibus_id"]: mb["current_route_plan"] for mb in minibuses}
    
    # Convert to internal working format
    vehicles = _initialize_vehicles(minibuses)
    assigned_passengers = set()
    
    # Try to assign each passenger greedily
    for request in pending_requests:
        passenger_id = request["passenger_id"]
        origin = request["origin"]
        destination = request["destination"]
        
        logger.debug(f"Processing {passenger_id}: {origin} → {destination}")
        
        best_vehicle = None
        best_route = None
        best_cost = float('inf')
        
        # Try inserting into each vehicle
        for vehicle in vehicles:
            candidate_route, cost = _try_insert_passenger(
                vehicle=vehicle,
                passenger_id=passenger_id,
                origin=origin,
                destination=destination,
                input_data=input_data
            )
            
            if candidate_route is not None and cost < best_cost:
                best_vehicle = vehicle
                best_route = candidate_route
                best_cost = cost
        
        # Assign to best vehicle
        if best_vehicle is not None:
            best_vehicle["route"] = best_route
            assigned_passengers.add(passenger_id)
            logger.debug(f"✓ Assigned {passenger_id} to {best_vehicle['id']}, cost={best_cost:.1f}")
        else:
            logger.warning(f"✗ Could not assign {passenger_id} to any vehicle")
    
    # Convert back to output format
    output = _generate_output(vehicles)
    
    logger.info(f"Optimization complete: {len(assigned_passengers)}/{len(pending_requests)} assigned")
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
    # CRITICAL: Merge first!
    merged_route = _merge_consecutive_stations_for_check(route)
    
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


def _merge_consecutive_stations_for_check(route: List[Dict]) -> List[Dict]:
    """
    Helper function to merge stations for capacity checking.
    Same logic as _merge_consecutive_stations.
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
    print("GREEDY INSERTION - SIMPLE TEST")
    print("=" * 80)
    
    def mock_travel_time(origin, dest, time):
        """Simple mock: 5 minutes between any stations"""
        return 300.0 if origin != dest else 0.0
    
    test_input = {
        "current_time": 1000.0,
        "pending_requests": [
            {
                "passenger_id": "P1",
                "origin": "A",
                "destination": "C",
                "appear_time": 900.0,
            },
            {
                "passenger_id": "P2",
                "origin": "B",
                "destination": "D",
                "appear_time": 950.0,
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
            }
        ],
        "get_travel_time": mock_travel_time,
    }
    
    print("\nTest: 2 passengers, 1 empty vehicle")
    result = greedy_insert_optimize(test_input)
    
    print("\nResult:")
    for minibus_id, route_plan in result.items():
        print(f"\n{minibus_id}:")
        for stop in route_plan:
            print(f"  {stop['station_id']}: {stop['action']} {stop['passenger_ids']}")
    
    print("\n" + "=" * 80)