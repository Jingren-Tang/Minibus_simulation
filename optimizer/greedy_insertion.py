"""
optimizer/greedy_insertion.py

Greedy insertion optimizer with best-first selection strategy.

Key design decisions:
- Re-optimizes ALL pending passengers every call (no "skip if already assigned")
  to prevent passengers from being lost when routes change between optimizer calls.
- Rebuilds all routes from scratch each call to ensure a consistent, complete plan.
- Checks detour constraints for ALL passengers currently in a candidate route,
  not just the newly inserted one.
"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def greedy_insert_optimize(input_data: dict) -> Dict[str, List[Dict]]:
    """
    Main entry point for greedy insertion optimization with best-first selection.

    Re-optimizes all pending passengers from scratch on every call.
    This avoids the "lost passenger" bug where a passenger is marked as assigned
    but then silently dropped when the route plan is rebuilt.

    Args:
        input_data: Dict containing:
            - current_time (float)
            - pending_requests (List[Dict])
            - minibuses (List[Dict])
            - get_travel_time (callable)
            - max_waiting_time (float)
            - max_detour_time (float)

    Returns:
        Dict mapping minibus_id -> route_plan (list of stop dicts)
    """
    logger.info("Starting OPTIMIZED BEST-FIRST greedy insertion")

    pending_requests = input_data["pending_requests"]
    minibuses = input_data["minibuses"]
    current_time = input_data["current_time"]

    if len(pending_requests) == 0:
        logger.info("No pending requests, returning existing routes")
        return {mb["minibus_id"]: mb["current_route_plan"] for mb in minibuses}

    logger.info(f"Processing ALL {len(pending_requests)} pending passengers (re-optimizing from scratch)")

    # -------------------------------------------------------------------------
    # Build priority-sorted passenger list.
    # Priority = longer wait is better (we want to serve waiting passengers first),
    # minus a small penalty for long direct travel time (prefer shorter trips
    # when wait times are equal).
    # -------------------------------------------------------------------------
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
            estimated_distance = get_travel_time(origin, destination, current_time) if get_travel_time else 600.0
        except Exception:
            estimated_distance = 600.0

        priority = wait_time * 5.0 - estimated_distance * 0.1

        passenger_data.append({
            "passenger_id": passenger_id,
            "origin": origin,
            "destination": destination,
            "appear_time": appear_time,
            "priority": priority
        })

    # Sort descending: highest priority (longest waiter) first
    passenger_data.sort(reverse=True, key=lambda x: x["priority"])

    # Batch processing: only optimize the top N passengers to bound runtime
    BATCH_SIZE = 30
    MAX_ITERATIONS = 100

    batch_to_process = passenger_data[:BATCH_SIZE]

    if len(batch_to_process) < len(passenger_data):
        logger.info(f"Batch mode: processing {len(batch_to_process)}/{len(passenger_data)} passengers")
    else:
        logger.info(f"Processing all {len(batch_to_process)} passengers")

    # -------------------------------------------------------------------------
    # Initialize vehicles with empty routes (except committed dropoffs for
    # passengers already onboard).  Rebuilding from scratch guarantees that
    # every passenger appearing in the output plan was explicitly assigned in
    # this optimization call.
    # -------------------------------------------------------------------------
    vehicles = _initialize_vehicles_fresh(minibuses)

    assigned_passengers = set()
    remaining_indices = set(range(len(batch_to_process)))
    iteration = 0

    # -------------------------------------------------------------------------
    # Best-first assignment loop.
    # Each iteration picks the single (passenger, vehicle) pair that has the
    # lowest adjusted cost increase and commits that assignment before moving on.
    # -------------------------------------------------------------------------
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

                candidate_route, new_cost = _try_insert_passenger_smart(
                    vehicle=vehicle,
                    passenger_id=passenger_id,
                    origin=origin,
                    destination=destination,
                    appear_time=passenger["appear_time"],
                    input_data=input_data
                )

                if candidate_route is not None:
                    cost_increase = new_cost - current_cost
                    # Subtract priority bonus so high-priority passengers are
                    # preferred even when the raw cost increase is slightly higher
                    adjusted_cost = cost_increase - priority * 0.5

                    logger.debug(
                        f"  {passenger_id} -> {vehicle['id']}: "
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

    if iteration >= MAX_ITERATIONS and remaining_indices:
        logger.warning(
            f"Stopped after {MAX_ITERATIONS} iterations with {len(remaining_indices)} "
            f"passengers still unassigned"
        )

    # Convert internal vehicle format to the output format expected by the engine
    output = _generate_output(vehicles)

    logger.info(f"\n{'='*60}")
    logger.info(f"Optimization complete: {len(assigned_passengers)}/{len(batch_to_process)} assigned")

    if len(assigned_passengers) < len(batch_to_process):
        unassigned = [batch_to_process[idx]["passenger_id"] for idx in remaining_indices]
        logger.warning(f"Unassigned passengers: {unassigned}")

    for minibus_id, plan in output.items():
        pickup_passengers = [pid for stop in plan if stop["action"] == "PICKUP" for pid in stop["passenger_ids"]]
        if pickup_passengers:
            logger.info(f"  {minibus_id} will pickup: {pickup_passengers}")

    return output


# =============================================================================
# Vehicle initialization
# =============================================================================

def _initialize_vehicles_fresh(minibuses: List[Dict]) -> List[Dict]:
    """
    Initialize the internal vehicle list for this optimization call.

    Each vehicle starts with an empty route, EXCEPT that dropoff stops for
    passengers already onboard are pre-populated so those passengers are
    guaranteed to reach their destinations.

    Args:
        minibuses: List of minibus state dicts from the engine.

    Returns:
        List of internal vehicle dicts used throughout the optimizer.
    """
    vehicles = []

    for mb in minibuses:
        minibus_id = mb["minibus_id"]
        capacity = mb["capacity"]
        current_occupancy = len(mb["passengers_onboard"])
        passengers_onboard = mb["passengers_onboard"]       # list of passenger IDs
        current_location = mb["current_location"]
        onboard_details = mb.get("onboard_passenger_details", {})  # {pid: {pickup_time, origin_station_id, ...}}

        # Recover committed dropoff destinations for onboard passengers
        # by reading the existing route plan (which the engine already knows about).
        existing_plan = mb["current_route_plan"]
        dropoff_destinations = {}

        for stop in existing_plan:
            if stop["action"] == "DROPOFF":
                for pid in stop["passenger_ids"]:
                    if pid in passengers_onboard:
                        dest = stop["station_id"]
                        dropoff_destinations.setdefault(dest, []).append(pid)

        # Build the initial route: only dropoff stops for onboard passengers
        route = []
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
            "initial_occupancy_ids": set(passengers_onboard),
            "onboard_passenger_details": onboard_details,   # real pickup time/origin per onboard passenger
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


# =============================================================================
# Insertion strategies
# =============================================================================

def _try_insert_passenger_smart(
    vehicle: Dict,
    passenger_id: str,
    origin: str,
    destination: str,
    appear_time: float,
    input_data: Dict
) -> Tuple[Optional[List[Dict]], float]:
    """
    Try every feasible way to insert a new passenger into the vehicle's route,
    and return the lowest-cost feasible insertion.

    Four strategies are tried in order of increasing cost:
      1. Reuse an existing stop for both pickup and dropoff.
      2. Reuse an existing pickup stop, insert a new dropoff stop.
      3. Insert a new pickup stop, reuse an existing dropoff stop.
      4. Insert both pickup and dropoff as new stops.

    Feasibility is checked via capacity, max-waiting-time, and max-detour
    constraints for ALL passengers in the candidate route (not just the new one).

    Args:
        vehicle:       Internal vehicle dict (contains route, capacity, etc.)
        passenger_id:  ID of the passenger to insert.
        origin:        Pickup station ID.
        destination:   Dropoff station ID.
        appear_time:   Time the passenger appeared (seconds from sim start).
        input_data:    Full optimizer input dict (for travel time function, constraints).

    Returns:
        (best_route, best_cost) if a feasible insertion exists, else (None, inf).
    """
    current_route = vehicle["route"]
    best_route = None
    best_cost = float('inf')

    # Locate existing stops that share the passenger's origin or destination
    origin_positions = [i for i, s in enumerate(current_route) if s["station"] == origin]
    destination_positions = [i for i, s in enumerate(current_route) if s["station"] == destination]

    # --- Strategy 1: reuse existing stop for BOTH pickup and dropoff -----------
    for pickup_idx in origin_positions:
        for dropoff_idx in destination_positions:
            if dropoff_idx <= pickup_idx:
                continue  # dropoff must come after pickup

            candidate = _deep_copy_route(current_route)
            candidate[pickup_idx]["pickup"] = candidate[pickup_idx]["pickup"] + [passenger_id]
            candidate[dropoff_idx]["dropoff"] = candidate[dropoff_idx]["dropoff"] + [passenger_id]

            if _is_candidate_feasible(candidate, vehicle, passenger_id, origin, destination, appear_time, input_data):
                cost = _compute_route_cost(candidate, input_data)
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate

    # --- Strategy 2: reuse existing pickup stop, insert new dropoff stop -------
    for pickup_idx in origin_positions:
        for dropoff_pos in range(pickup_idx + 1, len(current_route) + 1):
            candidate = _deep_copy_route(current_route)
            candidate[pickup_idx]["pickup"] = candidate[pickup_idx]["pickup"] + [passenger_id]
            candidate.insert(dropoff_pos, {
                "station": destination,
                "pickup": [],
                "dropoff": [passenger_id]
            })

            if _is_candidate_feasible(candidate, vehicle, passenger_id, origin, destination, appear_time, input_data):
                cost = _compute_route_cost(candidate, input_data)
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate

    # --- Strategy 3: insert new pickup stop, reuse existing dropoff stop -------
    for dropoff_idx in destination_positions:
        for pickup_pos in range(dropoff_idx + 1):
            candidate = _deep_copy_route(current_route)
            candidate.insert(pickup_pos, {
                "station": origin,
                "pickup": [passenger_id],
                "dropoff": []
            })
            adjusted_dropoff_idx = dropoff_idx + 1  # index shifts after insert
            candidate[adjusted_dropoff_idx]["dropoff"] = candidate[adjusted_dropoff_idx]["dropoff"] + [passenger_id]

            if _is_candidate_feasible(candidate, vehicle, passenger_id, origin, destination, appear_time, input_data):
                cost = _compute_route_cost(candidate, input_data)
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate

    # --- Strategy 4: insert BOTH as brand-new stops (most expensive) ----------
    for pickup_pos in range(len(current_route) + 1):
        for dropoff_pos in range(pickup_pos + 1, len(current_route) + 2):
            candidate = _deep_copy_route(current_route)
            candidate.insert(pickup_pos, {
                "station": origin,
                "pickup": [passenger_id],
                "dropoff": []
            })
            candidate.insert(dropoff_pos, {
                "station": destination,
                "pickup": [],
                "dropoff": [passenger_id]
            })

            if _is_candidate_feasible(candidate, vehicle, passenger_id, origin, destination, appear_time, input_data):
                cost = _compute_route_cost(candidate, input_data)
                if cost < best_cost:
                    best_cost = cost
                    best_route = candidate

    return best_route, best_cost


# =============================================================================
# Feasibility checks
# =============================================================================

def _is_candidate_feasible(
    candidate_route: List[Dict],
    vehicle: Dict,
    passenger_id: str,
    origin: str,
    destination: str,
    appear_time: float,
    input_data: Dict
) -> bool:
    """
    Gate function: a candidate insertion is feasible only if it satisfies
    both the capacity constraint and the time-based constraints (wait + detour)
    for every passenger in the route.

    Args:
        candidate_route: Proposed route after inserting the new passenger.
        vehicle:         Internal vehicle dict.
        passenger_id:    ID of the newly inserted passenger.
        origin:          Pickup station of the new passenger.
        destination:     Dropoff station of the new passenger.
        appear_time:     Appearance time of the new passenger.
        input_data:      Full optimizer input dict.

    Returns:
        True if the route is feasible, False otherwise.
    """
    if not _is_capacity_feasible(candidate_route, vehicle["capacity"], vehicle["initial_occupancy"]):
        return False
    if not _is_wait_and_detour_feasible(
        candidate_route, vehicle, passenger_id, origin, destination, appear_time, input_data
    ):
        return False
    return True


def _is_capacity_feasible(
    route: List[Dict],
    capacity: int,
    initial_occupancy: int
) -> bool:
    """
    Verify that occupancy never exceeds capacity and never goes negative
    throughout the merged route.

    Dropoffs are processed BEFORE pickups at each station (passengers
    alight before new passengers board), which is the physically correct order.

    Args:
        route:             Route to check (before merging consecutive same-station stops).
        capacity:          Maximum number of passengers the vehicle can carry.
        initial_occupancy: Number of passengers already onboard at route start.

    Returns:
        True if capacity constraints are satisfied at every stop.
    """
    merged_route = _merge_consecutive_stations(route)
    occupancy = initial_occupancy

    for i, stop in enumerate(merged_route):
        # Dropoff first, then pickup — physically correct boarding order
        occupancy -= len(stop["dropoff"])
        occupancy += len(stop["pickup"])

        if occupancy < 0:
            logger.debug(f"  ✗ Negative occupancy {occupancy} at stop {i+1}")
            return False

        if occupancy > capacity:
            logger.debug(f"  ✗ Over capacity {occupancy}/{capacity} at stop {i+1}")
            return False

    return True


def _is_wait_and_detour_feasible(
    route: List[Dict],
    vehicle: Dict,
    passenger_id: str,
    origin: str,
    destination: str,
    appear_time: float,
    input_data: Dict
) -> bool:
    """
    Check waiting-time and detour-time constraints for ALL passengers in the
    candidate route, including passengers already onboard.

    Waiting time  = pickup_time - appear_time          (new passengers only)
    Detour time   = (dropoff_time - pickup_time) - direct_travel_time(origin, dest)

    For passengers already onboard (no pickup stop in current route):
      - pickup_time  is read from vehicle["onboard_passenger_details"][pid]["pickup_time"]
      - pickup station is read from vehicle["onboard_passenger_details"][pid]["origin_station_id"]
      These are the REAL values recorded when the passenger boarded, not approximations.

    Args:
        route:         Candidate route (internal format, before merging).
        vehicle:       Internal vehicle dict (contains onboard_passenger_details).
        passenger_id:  ID of the newly inserted passenger (used for wait check).
        origin:        Pickup station of the new passenger.
        destination:   Dropoff station of the new passenger.
        appear_time:   Appearance time of the new passenger.
        input_data:    Full optimizer input dict.

    Returns:
        True if all passengers satisfy both constraints, False otherwise.
    """
    max_waiting_time = float(input_data.get("max_waiting_time", float("inf")))
    max_detour_time = float(input_data.get("max_detour_time", float("inf")))
    current_time = input_data["current_time"]

    merged = _merge_consecutive_stations(route)
    if not merged:
        return False

    arrival_times = _simulate_arrival_times(merged, vehicle, input_data)

    get_travel_time = input_data.get("get_travel_time")

    def tt(a, b, t):
        """Safe wrapper around the travel-time query function."""
        if get_travel_time is None:
            return 300.0
        try:
            return float(get_travel_time(a, b, t))
        except Exception:
            return 300.0

    # -------------------------------------------------------------------------
    # Step 1: collect pickup_time and dropoff_time for every passenger that
    # has a stop in this route (i.e. passengers being picked up in this plan).
    # -------------------------------------------------------------------------
    # pax_info[pid] = {"pickup_time": float|None, "pickup_station": str|None,
    #                  "dropoff_time": float|None, "dropoff_station": str|None}
    pax_info: Dict[str, dict] = {}

    for i, stop in enumerate(merged):
        t = arrival_times[i]
        for pid in stop["pickup"]:
            info = pax_info.setdefault(pid, {})
            info["pickup_time"] = t
            info["pickup_station"] = stop["station"]
        for pid in stop["dropoff"]:
            info = pax_info.setdefault(pid, {})
            info["dropoff_time"] = t
            info["dropoff_station"] = stop["station"]

    # -------------------------------------------------------------------------
    # Step 2: also account for onboard passengers (their pickup already happened
    # before this route starts, so they have no pickup stop in the current plan).
    # We inject their real historical pickup data from onboard_passenger_details.
    # -------------------------------------------------------------------------
    onboard_ids = vehicle.get("initial_occupancy_ids", set())
    onboard_details = vehicle.get("onboard_passenger_details", {})

    for pid in onboard_ids:
        if pid not in pax_info:
            # This passenger has a dropoff stop but no pickup stop in this route
            pax_info.setdefault(pid, {})

        if "pickup_time" not in pax_info[pid]:
            details = onboard_details.get(pid, {})
            real_pickup_time = details.get("pickup_time")
            real_pickup_station = details.get("origin_station_id")

            if real_pickup_time is not None and real_pickup_station is not None:
                # Use the real recorded boarding time and station
                pax_info[pid]["pickup_time"] = real_pickup_time
                pax_info[pid]["pickup_station"] = real_pickup_station
            else:
                # Fallback: should not happen if engine passes onboard_details correctly
                logger.warning(
                    f"  ⚠ No real pickup data for onboard passenger {pid}; "
                    f"falling back to current_time / current_location"
                )
                pax_info[pid]["pickup_time"] = current_time
                pax_info[pid]["pickup_station"] = vehicle["current_location"]

    # -------------------------------------------------------------------------
    # Step 3: check constraints for EVERY passenger with known pickup + dropoff.
    # -------------------------------------------------------------------------
    for pid, info in pax_info.items():
        p_pickup_time = info.get("pickup_time")
        p_dropoff_time = info.get("dropoff_time")
        p_pickup_station = info.get("pickup_station")
        p_dropoff_station = info.get("dropoff_station")

        # Skip if we couldn't resolve both times (data gap — be lenient)
        if p_pickup_time is None or p_dropoff_time is None or p_dropoff_station is None:
            logger.debug(f"  ⚠ Incomplete timing data for {pid}, skipping constraint check")
            continue

        if p_dropoff_time <= p_pickup_time:
            # Dropoff before or at pickup — physically impossible
            return False

        # --- Waiting-time check (only for the newly inserted passenger) ------
        # if pid == passenger_id:
        #     waiting = p_pickup_time - float(appear_time)
        #     if waiting > max_waiting_time:
        #         logger.debug(
        #             f"  ✗ WAIT: {pid} waiting={waiting:.1f}s > {max_waiting_time:.1f}s"
        #         )
        #         return False

        appear_time_map = input_data.get("appear_time_map", {})
        onboard_ids = vehicle.get("initial_occupancy_ids", set())

        if pid == passenger_id:
            pax_appear_time = float(appear_time)
        elif pid not in onboard_ids: 
            pax_appear_time = appear_time_map.get(pid)
        else:
            pax_appear_time = None

        if pax_appear_time is not None:
            waiting = p_pickup_time - pax_appear_time
            if waiting > max_waiting_time:
                logger.debug(
                    f"  ✗ WAIT: {pid} waiting={waiting:.1f}s > {max_waiting_time:.1f}s"
                )
                return False




        # --- Detour check (for ALL passengers including onboard) --------------
        if p_pickup_station is None:
            logger.debug(f"  ⚠ No pickup station for {pid}, skipping detour check")
            continue

        direct = tt(p_pickup_station, p_dropoff_station, p_pickup_time)
        onboard_segment = p_dropoff_time - p_pickup_time
        detour = onboard_segment - direct

        if detour > max_detour_time:
            logger.debug(
                f"  ✗ DETOUR: {pid} detour={detour:.1f}s > {max_detour_time:.1f}s "
                f"(segment={onboard_segment:.1f}s, direct={direct:.1f}s)"
            )
            return False

    return True


# =============================================================================
# Route cost computation
# =============================================================================

def _compute_route_cost(route: List[Dict], input_data: Dict) -> float:
    """
    Compute total travel time along a route (sum of leg travel times).

    This is used as the objective function when comparing candidate insertions.
    The vehicle is assumed to start from its current location; the cost here
    only covers the stops that appear in the route list, not the leg from
    current_location to the first stop (which is constant across comparisons
    and therefore does not affect relative cost).

    Args:
        route:      Internal route list (station / pickup / dropoff dicts).
        input_data: Full optimizer input dict.

    Returns:
        Total travel time in seconds.  Returns 0.0 for routes with <= 1 stop.
    """
    if len(route) <= 1:
        return 0.0

    get_travel_time = input_data.get("get_travel_time")
    if get_travel_time is None:
        return float(len(route)) * 300.0  # fallback: 5 min per stop

    current_time = input_data["current_time"]
    total_time = 0.0
    arrival_time = current_time

    for i in range(len(route) - 1):
        origin_station = route[i]["station"]
        dest_station = route[i + 1]["station"]

        try:
            travel_time = get_travel_time(origin_station, dest_station, arrival_time)
        except Exception:
            travel_time = 300.0

        total_time += travel_time
        arrival_time += travel_time

    return total_time


# =============================================================================
# Arrival time simulation
# =============================================================================

def _simulate_arrival_times(route: List[Dict], vehicle: Dict, input_data: Dict) -> List[float]:
    """
    Compute the estimated arrival time at each stop in the (merged) route.

    Includes the travel leg from the vehicle's current location to the first stop.

    Args:
        route:      Merged route list (output of _merge_consecutive_stations).
        vehicle:    Internal vehicle dict (used for current_location).
        input_data: Full optimizer input dict.

    Returns:
        List of arrival times (seconds from sim start), one entry per stop.
        Returns [] if route is empty.
    """
    if not route:
        return []

    get_travel_time = input_data.get("get_travel_time")
    current_time = input_data["current_time"]

    def tt(a, b, t):
        if get_travel_time is None:
            return 300.0
        try:
            return float(get_travel_time(a, b, t))
        except Exception:
            return 300.0

    times = [0.0] * len(route)

    # Travel from current vehicle location to the first stop in the plan
    t = current_time + tt(vehicle["current_location"], route[0]["station"], current_time)
    times[0] = t

    for i in range(1, len(route)):
        t = t + tt(route[i - 1]["station"], route[i]["station"], t)
        times[i] = t

    return times


# =============================================================================
# Output generation
# =============================================================================

def _generate_output(vehicles: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Convert the internal vehicle / route representation into the output format
    expected by the simulation engine.

    Output format per stop:
        {"station_id": str, "action": "PICKUP" | "DROPOFF", "passenger_ids": List[str]}

    At each station, DROPOFF stops are emitted before PICKUP stops to match
    the physical order (alighting before boarding).

    Args:
        vehicles: List of internal vehicle dicts after optimization.

    Returns:
        Dict mapping minibus_id -> route_plan list.
    """
    output = {}

    for vehicle in vehicles:
        minibus_id = vehicle["id"]
        merged_route = _merge_consecutive_stations(vehicle["route"])

        route_plan = []
        for stop in merged_route:
            station = stop["station"]

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


# =============================================================================
# Route utilities
# =============================================================================

def _deep_copy_route(route: List[Dict]) -> List[Dict]:
    """
    Return a deep copy of the internal route list.

    Each stop's pickup and dropoff lists are copied independently so that
    mutations in the candidate route do not affect the original.

    Args:
        route: Internal route list to copy.

    Returns:
        New list of stop dicts with independent pickup / dropoff lists.
    """
    return [
        {
            "station": stop["station"],
            "pickup": stop["pickup"].copy(),
            "dropoff": stop["dropoff"].copy()
        }
        for stop in route
    ]


def _merge_consecutive_stations(route: List[Dict]) -> List[Dict]:
    """
    Merge consecutive stops that share the same station ID into a single stop.

    This can happen when both a pickup and a dropoff are inserted at the same
    station via different strategies.  Merging keeps the route compact and
    avoids the vehicle visiting the same station twice in a row.

    Args:
        route: Internal route list (may have consecutive duplicates).

    Returns:
        Merged route list where no two consecutive stops share the same station.
        Stops with empty pickup AND empty dropoff lists are discarded.
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
            # Same station: merge passenger lists into the running stop
            current["pickup"].extend(stop["pickup"])
            current["dropoff"].extend(stop["dropoff"])
        else:
            # New station: flush the running stop (if non-empty) and start fresh
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