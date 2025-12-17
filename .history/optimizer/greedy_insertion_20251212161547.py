"""
optimizer/greedy_insertion.py

Greedy insertion algorithm for dynamic vehicle routing.
Inserts pending passenger requests into existing vehicle routes by finding
the minimum-cost insertion position that satisfies capacity constraints.
"""

import logging
import copy
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """
    Main optimization function for greedy insertion algorithm.
    
    This function implements a simple greedy strategy:
    1. For each pending request, try to insert it into all vehicles
    2. Find the insertion position with minimum cost increase
    3. Apply the best assignment and move to next request
    
    Simplified version (v1):
    - Assumes vehicles are at stations (ignores in-transit state)
    - Only checks capacity constraint
    - Uses cumulative time calculation
    
    Args:
        input_data (dict): Input data with keys:
            - current_time (float): Current simulation time
            - pending_requests (List[Dict]): Unassigned passengers
            - minibuses (List[Dict]): Vehicle states
            - stations (List[str]): All station IDs
            - get_travel_time (callable): Function to query travel time
            - max_waiting_time (float): Maximum waiting time in seconds
            - max_detour_time (float): Maximum detour time in seconds
    
    Returns:
        Dict[str, List[Dict]]: Route plans for all vehicles
            Format: {
                "M1": [
                    {"station_id": "A", "action": "PICKUP", "passenger_ids": ["P1"]},
                    {"station_id": "B", "action": "DROPOFF", "passenger_ids": ["P1"]}
                ],
                "M2": []
            }
    """
    logger.info("Starting greedy insertion optimization")
    logger.info(f"Pending requests: {len(input_data['pending_requests'])}")
    logger.info(f"Active vehicles: {len(input_data['minibuses'])}")
    
    # Extract input data
    current_time = input_data["current_time"]
    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    get_travel_time = input_data["get_travel_time"]
    
    # Convert minibuses to internal format (mutable working copies)
    vehicles = _convert_to_vehicle_objects(minibuses)
    
    # Track assigned passengers
    assigned_passengers = set()
    
    # Process each pending request
    for request in pending_requests:
        passenger_id = request["passenger_id"]
        origin = request["origin"]
        destination = request["destination"]
        
        logger.debug(f"Processing request {passenger_id}: {origin} → {destination}")
        
        # Find best insertion across all vehicles
        best_vehicle = None
        best_route = None
        best_cost = float('inf')
        
        for vehicle in vehicles:
            # Try to insert this request into this vehicle
            candidate_route, cost = _try_insert_request(
                vehicle=vehicle,
                request=request,
                input_data=input_data
            )
            
            if candidate_route is not None and cost < best_cost:
                best_vehicle = vehicle
                best_route = candidate_route
                best_cost = cost
        
        # Apply best insertion
        if best_vehicle is not None:
            best_vehicle["route"] = best_route
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
    
    logger.info(
        f"Optimization complete: assigned {len(assigned_passengers)}/"
        f"{len(pending_requests)} passengers"
    )
    
    return output


def _convert_to_vehicle_objects(minibuses: List[Dict]) -> List[Dict]:
    """
    Convert minibus states to internal working format.
    
    Args:
        minibuses: List of minibus state dicts
    
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
            "route": current_route,  # Simple list of station IDs
            "tracker": tracker  # Pickup/dropoff tracking
        }
        
        vehicles.append(vehicle)
    
    return vehicles


def _try_insert_request(
    vehicle: Dict,
    request: Dict,
    input_data: Dict
) -> Tuple[Optional[List[str]], float]:
    """
    Try to insert a request into a vehicle's route.
    
    Enumerates all valid insertion positions and returns the one with
    minimum cost increase, or None if no feasible insertion exists.
    
    Args:
        vehicle: Vehicle object with current route and state
        request: Passenger request to insert
        input_data: Global input data (for travel time queries, etc.)
    
    Returns:
        Tuple of (best_route, cost) where:
        - best_route is the modified route (None if infeasible)
        - cost is the incremental cost (inf if infeasible)
    """
    origin = request["origin"]
    destination = request["destination"]
    current_route = vehicle["route"]
    
    best_route = None
    min_cost = float('inf')
    
    # Enumerate insertion positions
    # Origin can be inserted at position 0 to len(route)
    # Destination must be after origin
    
    for i in range(len(current_route) + 1):
        # Insert origin at position i
        for j in range(i + 1, len(current_route) + 2):
            # Insert destination at position j (note: j is relative to route after inserting origin)
            
            # Build candidate route
            candidate = current_route.copy()
            candidate.insert(i, origin)
            candidate.insert(j, destination)  # j is already adjusted for the insertion at i
            
            # Check feasibility (only capacity for v1)
            if not _check_capacity_feasible(vehicle, request, candidate):
                continue
            
            # Calculate cost
            cost = _compute_route_cost(candidate, input_data)
            
            if cost < min_cost:
                min_cost = cost
                best_route = candidate
    
    return best_route, min_cost


def _check_capacity_feasible(
    vehicle: Dict,
    new_request: Dict,
    candidate_route: List[str]
) -> bool:
    """
    Check if candidate route satisfies capacity constraint.
    
    Simulates the route and tracks occupancy at each station.
    
    Args:
        vehicle: Vehicle object
        new_request: New passenger request being inserted
        candidate_route: Proposed route with new request inserted
    
    Returns:
        True if capacity constraint is satisfied, False otherwise
    """
    capacity = vehicle["capacity"]
    tracker = vehicle["tracker"]
    
    # Start with current occupancy
    occupancy = vehicle["current_occupancy"]
    
    origin = new_request["origin"]
    destination = new_request["destination"]
    
    # Simulate the route
    for station in candidate_route:
        # Existing passengers getting on
        if station in tracker:
            occupancy += len(tracker[station]["pickup"])
        
        # New passenger getting on
        if station == origin:
            occupancy += 1
        
        # Check capacity
        if occupancy > capacity:
            return False
        
        # Existing passengers getting off
        if station in tracker:
            occupancy -= len(tracker[station]["dropoff"])
        
        # New passenger getting off
        if station == destination:
            occupancy -= 1
    
    return True


def _compute_route_cost(route: List[str], input_data: Dict) -> float:
    """
    Compute total travel time for a route using cumulative time calculation.
    
    This is the CORRECT way to handle time-dependent travel times:
    - Start from current_time
    - For each segment, query travel time using the arrival time at origin
    - Accumulate time as we progress through the route
    
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
    arrival_time = current_time  # Start from current time
    
    # Cumulative calculation
    for i in range(len(route) - 1):
        origin_station = route[i]
        dest_station = route[i + 1]
        
        # Query travel time using current arrival time (not fixed current_time!)
        travel_time = get_travel_time(origin_station, dest_station, arrival_time)
        
        # Accumulate
        total_time += travel_time
        arrival_time += travel_time  # Update arrival time for next segment
    
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
        
        # Convert route to route_plan format
        for station in route:
            # Check if there are pickups at this station
            if station in tracker and tracker[station]["pickup"]:
                route_plan.append({
                    "station_id": station,
                    "action": "PICKUP",
                    "passenger_ids": tracker[station]["pickup"]
                })
            
            # Check if there are dropoffs at this station
            if station in tracker and tracker[station]["dropoff"]:
                route_plan.append({
                    "station_id": station,
                    "action": "DROPOFF",
                    "passenger_ids": tracker[station]["dropoff"]
                })
        
        output[minibus_id] = route_plan
    
    return output


# Example and testing
if __name__ == "__main__":
    """
    Test the greedy insertion algorithm with mock data.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Mock travel time function (simple constant time)
    def mock_get_travel_time(origin, dest, time):
        # Simple mock: each segment takes 5 minutes
        return 300.0
    
    # Mock input data
    mock_input = {
        "current_time": 28800.0,  # 8:00 AM
        "pending_requests": [
            {
                "passenger_id": "P1",
                "origin": "A",
                "destination": "C",
                "appear_time": 28700.0,
                "wait_time": 100.0
            },
            {
                "passenger_id": "P2",
                "origin": "B",
                "destination": "D",
                "appear_time": 28750.0,
                "wait_time": 50.0
            }
        ],
        "minibuses": [
            {
                "minibus_id": "M1",
                "current_location": "A",
                "capacity": 6,
                "current_occupancy": 0,
                "passengers_onboard": [],
                "current_route_plan": []
            },
            {
                "minibus_id": "M2",
                "current_location": "E",
                "capacity": 6,
                "current_occupancy": 1,
                "passengers_onboard": ["P3"],
                "current_route_plan": [
                    {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["P3"]}
                ]
            }
        ],
        "stations": ["A", "B", "C", "D", "E", "F"],
        "get_travel_time": mock_get_travel_time,
        "max_waiting_time": 600.0,
        "max_detour_time": 300.0
    }
    
    print("=" * 80)
    print("Testing Greedy Insertion Algorithm")
    print("=" * 80)
    
    # Run optimization
    output = greedy_insert_optimize(mock_input)
    
    # Print results
    print("\nOptimization Results:")
    print("-" * 80)
    for minibus_id, route_plan in output.items():
        print(f"\n{minibus_id}:")
        if not route_plan:
            print("  (idle)")
        else:
            for stop in route_plan:
                action = stop["action"]
                station = stop["station_id"]
                passengers = stop["passenger_ids"]
                print(f"  → {station}: {action} {passengers}")
    
    print("\n" + "=" * 80)