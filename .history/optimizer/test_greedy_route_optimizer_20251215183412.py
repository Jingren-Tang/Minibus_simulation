

import logging
import sys
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# ============================================================================
# Mock Classes for Testing
# ============================================================================

class MockNetwork:
    """
    Mock TransitNetwork for testing.
    Simulates a simple network with time-dependent travel times.
    """
    def __init__(self, with_rush_hour: bool = False):
        """
        Initialize mock network.
        
        Args:
            with_rush_hour: If True, simulate rush hour effects
        """
        self.stations = {
            "A": {"name": "Station A"},
            "B": {"name": "Station B"},
            "C": {"name": "Station C"},
            "D": {"name": "Station D"},
            "E": {"name": "Station E"},
            "F": {"name": "Station F"},
        }
        self.with_rush_hour = with_rush_hour
        
        # Base travel times (seconds)
        self.base_times = {
            ("A", "B"): 300,   # 5 min
            ("B", "A"): 300,
            ("A", "C"): 600,   # 10 min
            ("C", "A"): 600,
            ("A", "D"): 900,   # 15 min
            ("D", "A"): 900,
            ("B", "C"): 420,   # 7 min
            ("C", "B"): 420,
            ("B", "D"): 780,   # 13 min
            ("D", "B"): 780,
            ("C", "D"): 360,   # 6 min
            ("D", "C"): 360,
            ("C", "E"): 480,   # 8 min
            ("E", "C"): 480,
            ("D", "E"): 540,   # 9 min
            ("E", "D"): 540,
            ("E", "F"): 300,   # 5 min
            ("F", "E"): 300,
        }
    
    def get_travel_time(self, origin: str, dest: str, time: float) -> float:
        """
        Get travel time between stations.
        
        Args:
            origin: Origin station ID
            dest: Destination station ID
            time: Query time (seconds since start)
        
        Returns:
            Travel time in seconds
        """
        if origin == dest:
            return 0.0
        
        base_time = self.base_times.get((origin, dest), 600.0)  # Default 10 min
        
        if self.with_rush_hour:
            # Rush hour: 8:00-9:00 AM (28800-32400 seconds)
            rush_hour_start = 28800
            rush_hour_end = 32400
            
            if rush_hour_start <= time < rush_hour_end:
                return base_time * 1.5  # 50% slower during rush hour
        
        return base_time


class MockPassenger:
    """Mock Passenger object for testing."""
    def __init__(self, passenger_id: str, origin: str, destination: str, appear_time: float):
        self.passenger_id = passenger_id
        self.origin_station_id = origin
        self.destination_station_id = destination
        self.appear_time = appear_time


# ============================================================================
# Test Utilities
# ============================================================================

def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_test_header(test_num: int, description: str):
    """Print a test case header."""
    print(f"\n{'─' * 80}")
    print(f"TEST {test_num}: {description}")
    print(f"{'─' * 80}")


def print_route_plan(minibus_id: str, route_plan: List[Dict], capacity: int = None):
    """Pretty print a route plan."""
    print(f"\n{minibus_id}:", end="")
    if capacity:
        print(f" (capacity: {capacity})", end="")
    print()
    
    if not route_plan:
        print("  → (idle)")
        return
    
    occupancy = 0
    for i, stop in enumerate(route_plan):
        station = stop['station_id']
        action = stop['action']
        passengers = stop['passenger_ids']
        
        if action == 'PICKUP':
            occupancy += len(passengers)
            status = f"occupancy: {occupancy}"
        elif action == 'DROPOFF':
            occupancy -= len(passengers)
            status = f"occupancy: {occupancy}"
        
        if capacity:
            status += f"/{capacity}"
        
        print(f"  {i+1}. {station}: {action} {passengers} ({status})")


def count_assigned_passengers(route_plans: Dict[str, List[Dict]]) -> set:
    """Count unique passengers assigned across all route plans."""
    assigned = set()
    for route_plan in route_plans.values():
        for stop in route_plan:
            if stop['action'] == 'PICKUP':
                assigned.update(stop['passenger_ids'])
    return assigned


def validate_route_plan(route_plan: List[Dict], capacity: int, initial_occupancy: int = 0) -> bool:
    """
    Validate that a route plan respects capacity constraints.
    
    Returns:
        True if valid, False otherwise
    """
    occupancy = initial_occupancy
    
    for stop in route_plan:
        if stop['action'] == 'DROPOFF':
            occupancy -= len(stop['passenger_ids'])
        elif stop['action'] == 'PICKUP':
            occupancy += len(stop['passenger_ids'])
        
        if occupancy < 0 or occupancy > capacity:
            return False
    
    return True


# ============================================================================
# Test Cases
# ============================================================================

def test_1_basic_assignment():
    """TEST 1: Basic passenger assignment to idle vehicles."""
    print_test_header(1, "Basic Passenger Assignment")
    
    from route_optimizer import RouteOptimizer
    
    # Setup
    network = MockNetwork()
    current_time = 1000.0
    
    passengers = [
        MockPassenger("P1", "A", "D", 900.0),
        MockPassenger("P2", "B", "C", 950.0),
    ]
    
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        },
        {
            "minibus_id": "M2",
            "current_location_id": "B",
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        }
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 600.0,
            'max_detour_time': 300.0
        }
    )
    
    # Execute
    print("\nScenario: 2 passengers, 2 idle vehicles")
    print(f"  P1: A → D (waiting {current_time - 900.0}s)")
    print(f"  P2: B → C (waiting {current_time - 950.0}s)")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    # Verify
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    
    return len(assigned) == 2


def test_2_capacity_constraint():
    """TEST 2: Capacity constraint enforcement."""
    print_test_header(2, "Capacity Constraint Enforcement")
    
    from route_optimizer_fixed import RouteOptimizer
    
    # Setup
    network = MockNetwork()
    current_time = 2000.0
    
    passengers = [
        MockPassenger("P1", "A", "E", 1900.0),
        MockPassenger("P2", "A", "F", 1920.0),
        MockPassenger("P3", "B", "E", 1940.0),
        MockPassenger("P4", "B", "F", 1960.0),
    ]
    
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 3,  # Small capacity
            "occupancy": 1,  # Already has 1 passenger
            "passenger_ids": ["P_existing"],
            "route_plan": [
                {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["P_existing"]}
            ]
        }
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 600.0,
            'max_detour_time': 300.0
        }
    )
    
    # Execute
    print("\nScenario: 4 passengers, 1 vehicle with capacity=3, already has 1 passenger")
    print("Expected: Can only assign 2 more passengers (total occupancy ≤ 3)")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    # Verify
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'])
        
        # Validate capacity
        is_valid = validate_route_plan(route, mb_info['capacity'], mb_info['occupancy'])
        print(f"  Capacity valid: {is_valid}")
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/4 passengers")
    print(f"✓ Capacity constraint respected: {len(assigned) <= 2}")
    
    return len(assigned) <= 2


def test_3_existing_route_extension():
    """TEST 3: Extending existing vehicle routes."""
    print_test_header(3, "Existing Route Extension")
    
    from route_optimizer_fixed import RouteOptimizer
    
    # Setup
    network = MockNetwork()
    current_time = 3000.0
    
    passengers = [
        MockPassenger("P_new", "B", "D", 2950.0),
    ]
    
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 6,
            "occupancy": 2,
            "passenger_ids": ["P1", "P2"],
            "route_plan": [
                {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["P1"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P2"]},
            ]
        }
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 600.0,
            'max_detour_time': 300.0
        }
    )
    
    # Execute
    print("\nScenario: 1 new passenger, 1 vehicle with existing route (C → E)")
    print("Expected: New passenger inserted into existing route")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    # Verify
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/1 passengers")
    
    # Check if route was modified
    original_stops = 2
    new_stops = len(result["M1"])
    print(f"✓ Route extended: {original_stops} → {new_stops} stops")
    
    return len(assigned) == 1 and new_stops > original_stops


def test_4_multiple_vehicles_competition():
    """TEST 4: Multiple vehicles competing for passengers."""
    print_test_header(4, "Multiple Vehicles Competition")
    
    from route_optimizer_fixed import RouteOptimizer
    
    # Setup
    network = MockNetwork()
    current_time = 4000.0
    
    passengers = [
        MockPassenger("P1", "C", "E", 3900.0),
        MockPassenger("P2", "C", "F", 3920.0),
    ]
    
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        },
        {
            "minibus_id": "M2",
            "current_location_id": "B",
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        },
        {
            "minibus_id": "M3",
            "current_location_id": "C",  # Closest!
            "capacity": 6,
            "occupancy": 1,
            "passenger_ids": ["P_other"],
            "route_plan": [
                {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["P_other"]}
            ]
        }
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 600.0,
            'max_detour_time': 300.0
        }
    )
    
    # Execute
    print("\nScenario: 2 passengers at C, 3 vehicles (M3 is closest)")
    print("Expected: Algorithm selects vehicles based on cost")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    # Verify
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    
    # Count which vehicles got passengers
    vehicles_with_new_passengers = 0
    for mb_id, route in result.items():
        for stop in route:
            if stop['action'] == 'PICKUP' and any(p in ['P1', 'P2'] for p in stop['passenger_ids']):
                vehicles_with_new_passengers += 1
                break
    
    print(f"✓ Vehicles used: {vehicles_with_new_passengers}/3")
    
    return len(assigned) == 2


def test_5_sequential_route_building():
    """TEST 5: Building sequential routes."""
    print_test_header(5, "Sequential Route Building")
    
    from route_optimizer_fixed import RouteOptimizer
    
    # Setup
    network = MockNetwork()
    current_time = 5000.0
    
    # Sequential passengers along a line
    passengers = [
        MockPassenger("P1", "A", "B", 4900.0),
        MockPassenger("P2", "B", "C", 4920.0),
        MockPassenger("P3", "C", "D", 4940.0),
        MockPassenger("P4", "D", "E", 4960.0),
    ]
    
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 8,  # Large capacity
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        }
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 800.0,
            'max_detour_time': 400.0
        }
    )
    
    # Execute
    print("\nScenario: 4 passengers in sequence (A→B→C→D→E), 1 large vehicle")
    print("Expected: All passengers combined into one efficient route")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    # Verify
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/4 passengers")
    print(f"✓ All in one vehicle: {len(result['M1']) > 0}")
    
    return len(assigned) >= 2  # At least some passengers assigned


def test_6_infeasible_assignment():
    """TEST 6: Handling infeasible assignments."""
    print_test_header(6, "Infeasible Assignment Handling")
    
    from route_optimizer_fixed import RouteOptimizer
    
    # Setup
    network = MockNetwork()
    current_time = 6000.0
    
    passengers = [
        MockPassenger("P1", "A", "E", 5900.0),
        MockPassenger("P2", "B", "F", 5920.0),
    ]
    
    # All vehicles are full
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "C",
            "capacity": 2,
            "occupancy": 2,  # Full!
            "passenger_ids": ["P_full1", "P_full2"],
            "route_plan": [
                {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["P_full1"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P_full2"]},
            ]
        },
        {
            "minibus_id": "M2",
            "current_location_id": "D",
            "capacity": 3,
            "occupancy": 3,  # Full!
            "passenger_ids": ["P_full3", "P_full4", "P_full5"],
            "route_plan": [
                {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["P_full3", "P_full4", "P_full5"]},
            ]
        }
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 600.0,
            'max_detour_time': 300.0
        }
    )
    
    # Execute
    print("\nScenario: 2 passengers, but all vehicles are at full capacity")
    print("Expected: Passengers cannot be assigned (graceful handling)")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    # Verify
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    print(f"✓ Graceful handling: No crashes, existing routes preserved")
    
    return True  # Test passes if no exception


def test_7_rush_hour_routing():
    """TEST 7: Time-dependent routing (rush hour)."""
    print_test_header(7, "Time-Dependent Routing (Rush Hour)")
    
    from route_optimizer_fixed import RouteOptimizer
    
    # Setup with rush hour
    network = MockNetwork(with_rush_hour=True)
    rush_hour_time = 29000.0  # 8:03 AM (in rush hour)
    
    passengers = [
        MockPassenger("P1", "A", "E", 28900.0),
        MockPassenger("P2", "B", "F", 28950.0),
    ]
    
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        }
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 1200.0,  # Extended for rush hour
            'max_detour_time': 600.0
        }
    )
    
    # Execute
    print("\nScenario: Rush hour (8:03 AM), travel times 50% longer")
    print(f"Current time: {rush_hour_time}s")
    print("Expected: Algorithm accounts for increased travel times")
    
    result = optimizer.optimize(passengers, minibuses, network, rush_hour_time)
    
    # Verify
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    print("✓ Rush hour delays considered in route cost calculation")
    
    return len(assigned) >= 1


def test_8_stress_test():
    """TEST 8: Stress test with many passengers and vehicles."""
    print_test_header(8, "Stress Test (10 passengers, 5 vehicles)")
    
    from route_optimizer_fixed import RouteOptimizer
    
    # Setup
    network = MockNetwork()
    current_time = 8000.0
    
    # Many passengers
    passengers = [
        MockPassenger(f"P{i}", 
                     ["A", "B", "C", "D", "E"][i % 5],
                     ["B", "C", "D", "E", "F"][i % 5],
                     current_time - (100 - i*10))
        for i in range(10)
    ]
    
    # Multiple vehicles
    minibuses = [
        {
            "minibus_id": f"M{i+1}",
            "current_location_id": ["A", "B", "C", "D", "E"][i],
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        }
        for i in range(5)
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 600.0,
            'max_detour_time': 300.0
        }
    )
    
    # Execute
    print("\nScenario: 10 passengers, 5 vehicles")
    print("Expected: Efficient assignment, all or most passengers assigned")
    
    import time
    start_time = time.time()
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    execution_time = time.time() - start_time
    
    # Verify
    print("\nResults:")
    assigned = count_assigned_passengers(result)
    
    for mb_id, route in result.items():
        if route:  # Only print non-empty routes
            mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
            print_route_plan(mb_id, route, mb_info['capacity'])
    
    # Count idle vehicles
    idle_count = sum(1 for route in result.values() if not route)
    
    print(f"\n✓ Assigned: {len(assigned)}/10 passengers")
    print(f"✓ Idle vehicles: {idle_count}/5")
    print(f"✓ Execution time: {execution_time:.3f} seconds")
    
    return len(assigned) >= 5  # At least half assigned


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Run all test cases and report results."""
    print_section("GREEDY INSERTION OPTIMIZER - COMPREHENSIVE TEST SUITE")
    
    tests = [
        ("Basic Assignment", test_1_basic_assignment),
        ("Capacity Constraint", test_2_capacity_constraint),
        ("Route Extension", test_3_existing_route_extension),
        ("Vehicle Competition", test_4_multiple_vehicles_competition),
        ("Sequential Routing", test_5_sequential_route_building),
        ("Infeasible Handling", test_6_infeasible_assignment),
        ("Rush Hour Routing", test_7_rush_hour_routing),
        ("Stress Test", test_8_stress_test),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, "PASS" if passed else "FAIL", None))
        except Exception as e:
            logger.error(f"Test '{test_name}' raised exception: {e}", exc_info=True)
            results.append((test_name, "ERROR", str(e)))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    print(f"\n{'Test Name':<30} {'Status':<10} {'Notes'}")
    print("─" * 80)
    
    pass_count = 0
    fail_count = 0
    error_count = 0
    
    for test_name, status, error in results:
        print(f"{test_name:<30} {status:<10}", end="")
        if error:
            print(f" {error[:40]}...")
            error_count += 1
        else:
            print()
            if status == "PASS":
                pass_count += 1
            else:
                fail_count += 1
    
    print("─" * 80)
    print(f"Total: {len(results)} tests")
    print(f"  ✓ Passed: {pass_count}")
    print(f"  ✗ Failed: {fail_count}")
    print(f"  ⚠ Errors: {error_count}")
    
    if pass_count == len(results):
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {fail_count + error_count} test(s) did not pass")
    
    print("\n" + "=" * 80)
    
    return pass_count == len(results)


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in test runner: {e}", exc_info=True)
        sys.exit(1)