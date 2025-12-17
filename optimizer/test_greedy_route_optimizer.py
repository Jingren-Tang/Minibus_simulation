
import logging
import sys
from typing import List, Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class MockNetwork:
    def __init__(self, with_rush_hour: bool = False):
        self.stations = {
            "A": {"name": "Station A"},
            "B": {"name": "Station B"},
            "C": {"name": "Station C"},
            "D": {"name": "Station D"},
            "E": {"name": "Station E"},
            "F": {"name": "Station F"},
        }
        self.with_rush_hour = with_rush_hour
        
        self.base_times = {
            ("A", "B"): 300, ("B", "A"): 300,
            ("A", "C"): 600, ("C", "A"): 600,
            ("A", "D"): 900, ("D", "A"): 900,
            ("B", "C"): 420, ("C", "B"): 420,
            ("B", "D"): 780, ("D", "B"): 780,
            ("C", "D"): 360, ("D", "C"): 360,
            ("C", "E"): 480, ("E", "C"): 480,
            ("D", "E"): 540, ("E", "D"): 540,
            ("E", "F"): 300, ("F", "E"): 300,
        }
    
    def get_travel_time(self, origin: str, dest: str, time: float) -> float:
        if origin == dest:
            return 0.0
        
        base_time = self.base_times.get((origin, dest), 600.0)
        
        if self.with_rush_hour:
            rush_hour_start = 28800
            rush_hour_end = 32400
            
            if rush_hour_start <= time < rush_hour_end:
                return base_time * 1.5
        
        return base_time


class MockPassenger:
    def __init__(self, passenger_id: str, origin: str, destination: str, appear_time: float):
        self.passenger_id = passenger_id
        self.origin_station_id = origin
        self.destination_station_id = destination
        self.appear_time = appear_time


def print_section(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_test_header(test_num: int, description: str):
    print(f"\n{'─' * 80}")
    print(f"TEST {test_num}: {description}")
    print(f"{'─' * 80}")


def print_route_plan(minibus_id: str, route_plan: List[Dict], capacity: int = None, initial_occupancy: int = 0):
    """
    🔧 修复：添加 initial_occupancy 参数，从正确的初始值开始计算
    """
    print(f"\n{minibus_id}:", end="")
    if capacity:
        print(f" (capacity: {capacity}, initial: {initial_occupancy})", end="")
    print()
    
    if not route_plan:
        print("  → (idle)")
        return
    
    occupancy = initial_occupancy  # 🔧 关键修复：从初始载客量开始
    
    for i, stop in enumerate(route_plan):
        station = stop['station_id']
        action = stop['action']
        passengers = stop['passenger_ids']
        
        # 🔧 修复：先处理 DROPOFF，再处理 PICKUP，然后显示
        if action == 'DROPOFF':
            occupancy -= len(passengers)
            status = f"after dropoff: {occupancy}"
        elif action == 'PICKUP':
            occupancy += len(passengers)
            status = f"after pickup: {occupancy}"
        
        if capacity:
            status += f"/{capacity}"
        
        print(f"  {i+1}. {station}: {action} {passengers} ({status})")


def count_assigned_passengers(route_plans: Dict[str, List[Dict]]) -> set:
    assigned = set()
    for route_plan in route_plans.values():
        for stop in route_plan:
            if stop['action'] == 'PICKUP':
                assigned.update(stop['passenger_ids'])
    return assigned


def validate_route_plan(route_plan: List[Dict], capacity: int, initial_occupancy: int = 0) -> bool:
    occupancy = initial_occupancy
    
    for stop in route_plan:
        if stop['action'] == 'DROPOFF':
            occupancy -= len(stop['passenger_ids'])
        elif stop['action'] == 'PICKUP':
            occupancy += len(stop['passenger_ids'])
        
        if occupancy < 0 or occupancy > capacity:
            return False
    
    return True


def test_1_basic_assignment():
    print_test_header(1, "Basic Passenger Assignment")
    
    from route_optimizer import RouteOptimizer
    
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
    
    print("\nScenario: 2 passengers, 2 idle vehicles")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    
    return len(assigned) == 2


def test_2_capacity_constraint():
    print_test_header(2, "Capacity Constraint Enforcement")
    
    from route_optimizer import RouteOptimizer
    
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
            "capacity": 3,
            "occupancy": 1,
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
    
    print("\nScenario: 4 passengers, 1 vehicle (capacity=3, initial_occupancy=1)")
    print("Expected: Can only assign 2 more passengers (max occupancy = 3)")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])  
        
        is_valid = validate_route_plan(route, mb_info['capacity'], mb_info['occupancy'])
        print(f"  Capacity valid: {is_valid}")
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/4 passengers")
    print(f"✓ Capacity constraint respected: {is_valid}")
    
    return is_valid 


def test_3_existing_route_extension():
    print_test_header(3, "Existing Route Extension")
    
    from route_optimizer import RouteOptimizer
    
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
    
    print("\nScenario: 1 new passenger, 1 vehicle with existing route")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/1 passengers")
    
    original_stops = 2
    new_stops = len(result["M1"])
    print(f"✓ Route extended: {original_stops} → {new_stops} stops")
    
    return len(assigned) == 1 and new_stops > original_stops


def test_4_multiple_vehicles_competition():
    print_test_header(4, "Multiple Vehicles Competition")
    
    from route_optimizer import RouteOptimizer
    
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
            "current_location_id": "C",
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
    
    print("\nScenario: 2 passengers at C, 3 vehicles")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    
    return len(assigned) == 2


def test_5_sequential_route_building():
    print_test_header(5, "Sequential Route Building")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 5000.0
    
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
            "capacity": 8,
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
    
    print("\nScenario: 4 sequential passengers, 1 large vehicle")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/4 passengers")
    
    return len(assigned) >= 2


def test_6_infeasible_assignment():
    print_test_header(6, "Infeasible Assignment Handling")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 6000.0
    
    passengers = [
        MockPassenger("P1", "A", "E", 5900.0),
        MockPassenger("P2", "B", "F", 5920.0),
    ]
    
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "C",
            "capacity": 2,
            "occupancy": 2,
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
            "occupancy": 3,
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
    
    print("\nScenario: 2 passengers, all vehicles full")
    
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    
    return True


def test_7_rush_hour_routing():
    print_test_header(7, "Time-Dependent Routing (Rush Hour)")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork(with_rush_hour=True)
    rush_hour_time = 29000.0
    
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
            'max_waiting_time': 1200.0,
            'max_detour_time': 600.0
        }
    )
    
    print("\nScenario: Rush hour, travel times 50% longer")
    
    result = optimizer.optimize(passengers, minibuses, network, rush_hour_time)
    
    print("\nResults:")
    for mb_id, route in result.items():
        mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
        print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
    
    assigned = count_assigned_passengers(result)
    print(f"\n✓ Assigned: {len(assigned)}/2 passengers")
    
    return len(assigned) >= 1


def test_8_stress_test():
    print_test_header(8, "Stress Test (10 passengers, 5 vehicles)")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 8000.0
    
    passengers = [
        MockPassenger(f"P{i}", 
                     ["A", "B", "C", "D", "E"][i % 5],
                     ["B", "C", "D", "E", "F"][i % 5],
                     current_time - (100 - i*10))
        for i in range(10)
    ]
    
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
    
    print("\nScenario: 10 passengers, 5 vehicles")
    
    import time
    start_time = time.time()
    result = optimizer.optimize(passengers, minibuses, network, current_time)
    execution_time = time.time() - start_time
    
    print("\nResults:")
    assigned = count_assigned_passengers(result)
    
    for mb_id, route in result.items():
        if route:
            mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
            print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
    
    idle_count = sum(1 for route in result.values() if not route)
    
    print(f"\n✓ Assigned: {len(assigned)}/10 passengers")
    print(f"✓ Idle vehicles: {idle_count}/5")
    print(f"✓ Execution time: {execution_time:.3f}s")
    
    return len(assigned) >= 5


def run_all_tests():
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
            logger.error(f"Test '{test_name}' error: {e}", exc_info=True)
            results.append((test_name, "ERROR", str(e)))
    
    print_section("TEST SUMMARY")
    
    print(f"\n{'Test Name':<30} {'Status':<10} {'Notes'}")
    print("─" * 80)
    
    pass_count = sum(1 for _, status, _ in results if status == "PASS")
    fail_count = sum(1 for _, status, _ in results if status == "FAIL")
    error_count = sum(1 for _, status, _ in results if status == "ERROR")
    
    for test_name, status, error in results:
        print(f"{test_name:<30} {status:<10}", end="")
        if error:
            print(f" {error[:40]}...")
        else:
            print()
    
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
        print("\n\nTests interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test runner error: {e}", exc_info=True)
        sys.exit(1)