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
    """修复版：正确显示载客量变化"""
    print(f"\n{minibus_id}:", end="")
    if capacity:
        print(f" (capacity: {capacity}, initial: {initial_occupancy})", end="")
    print()
    
    if not route_plan:
        print("  → (idle)")
        return
    
    occupancy = initial_occupancy
    
    for i, stop in enumerate(route_plan):
        station = stop['station_id']
        action = stop['action']
        passengers = stop['passenger_ids']
        
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
    """验证路线计划是否违反容量约束"""
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
    is_valid = True
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


def test_9_near_capacity_stress():
    print_test_header(9, "Near-Capacity Stress Test (Multiple vehicles at 80-90% capacity)")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 9000.0
    
    # 20个新乘客等待分配
    passengers = [
        MockPassenger(f"P_new_{i}", 
                     ["A", "B", "C", "D", "E", "F"][i % 6],
                     ["B", "C", "D", "E", "F", "A"][(i + 2) % 6],
                     current_time - (200 - i*10))
        for i in range(20)
    ]
    
    # 8辆车，每辆都接近满载
    minibuses = []
    for i in range(8):
        capacity = 6
        occupancy = 4 + (i % 2)  # 4或5个已有乘客
        existing_passengers = [f"P_exist_{i}_{j}" for j in range(occupancy)]
        
        # 创建复杂的现有路线
        route_plan = []
        stations = ["A", "B", "C", "D", "E", "F"]
        for j in range(occupancy):
            dropoff_station = stations[(i + j + 2) % 6]
            route_plan.append({
                "station_id": dropoff_station,
                "action": "DROPOFF",
                "passenger_ids": [existing_passengers[j]]
            })
        
        minibuses.append({
            "minibus_id": f"M{i+1}",
            "current_location_id": stations[i % 6],
            "capacity": capacity,
            "occupancy": occupancy,
            "passenger_ids": existing_passengers,
            "route_plan": route_plan
        })
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 800.0,
            'max_detour_time': 400.0
        }
    )
    
    print(f"\nScenario: 20 new passengers, 8 vehicles (each at 4-5 occupancy, capacity=6)")
    print("Expected: Should handle capacity constraints correctly without crashes")
    
    import time
    start_time = time.time()
    
    try:
        result = optimizer.optimize(passengers, minibuses, network, current_time)
        execution_time = time.time() - start_time
        
        print("\nResults:")
        assigned = count_assigned_passengers(result)
        
        all_valid = True
        for mb_id, route in result.items():
            mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
            if route:
                print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
                
                is_valid = validate_route_plan(route, mb_info['capacity'], mb_info['occupancy'])
                if not is_valid:
                    print(f"  ⚠️  CAPACITY VIOLATION DETECTED!")
                    all_valid = False
        
        print(f"\n✓ Assigned: {len(assigned)}/20 passengers")
        print(f"✓ All capacity constraints valid: {all_valid}")
        print(f"✓ Execution time: {execution_time:.3f}s")
        
        return all_valid and len(assigned) > 0
        
    except Exception as e:
        print(f"\n✗ CRASH DETECTED: {e}")
        logger.error(f"Test 9 crashed: {e}", exc_info=True)
        return False


def test_10_massive_scale():
    print_test_header(10, "Massive Scale Test (50 passengers, 15 vehicles)")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 10000.0
    
    # 50个新乘客
    passengers = [
        MockPassenger(f"P{i}", 
                     ["A", "B", "C", "D", "E", "F"][i % 6],
                     ["B", "C", "D", "E", "F", "A"][(i + 3) % 6],
                     current_time - (500 - i*10))
        for i in range(50)
    ]
    
    # 15辆车，各种状态
    minibuses = []
    stations = ["A", "B", "C", "D", "E", "F"]
    for i in range(15):
        if i < 5:
            # 空车
            occupancy = 0
            existing_passengers = []
            route_plan = []
        elif i < 10:
            # 半满
            occupancy = 3
            existing_passengers = [f"P_exist_{i}_{j}" for j in range(occupancy)]
            route_plan = [
                {"station_id": stations[(i+j) % 6], "action": "DROPOFF", "passenger_ids": [existing_passengers[j]]}
                for j in range(occupancy)
            ]
        else:
            # 接近满载
            occupancy = 5
            existing_passengers = [f"P_exist_{i}_{j}" for j in range(occupancy)]
            route_plan = [
                {"station_id": stations[(i+j) % 6], "action": "DROPOFF", "passenger_ids": [existing_passengers[j]]}
                for j in range(occupancy)
            ]
        
        minibuses.append({
            "minibus_id": f"M{i+1}",
            "current_location_id": stations[i % 6],
            "capacity": 6,
            "occupancy": occupancy,
            "passenger_ids": existing_passengers,
            "route_plan": route_plan
        })
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 900.0,
            'max_detour_time': 450.0
        }
    )
    
    print("\nScenario: 50 passengers, 15 vehicles (mixed occupancy)")
    print("Expected: Should handle large scale without crashes")
    
    import time
    start_time = time.time()
    
    try:
        result = optimizer.optimize(passengers, minibuses, network, current_time)
        execution_time = time.time() - start_time
        
        print("\nResults Summary:")
        assigned = count_assigned_passengers(result)
        
        all_valid = True
        vehicles_with_assignments = 0
        for mb_id, route in result.items():
            mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
            if route:
                vehicles_with_assignments += 1
                is_valid = validate_route_plan(route, mb_info['capacity'], mb_info['occupancy'])
                if not is_valid:
                    print(f"  ⚠️  {mb_id}: CAPACITY VIOLATION!")
                    print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
                    all_valid = False
        
        print(f"\n✓ Assigned: {len(assigned)}/50 passengers ({len(assigned)/50*100:.1f}%)")
        print(f"✓ Vehicles used: {vehicles_with_assignments}/15")
        print(f"✓ All capacity constraints valid: {all_valid}")
        print(f"✓ Execution time: {execution_time:.3f}s")
        
        return all_valid and len(assigned) >= 20
        
    except Exception as e:
        print(f"\n✗ CRASH DETECTED: {e}")
        logger.error(f"Test 10 crashed: {e}", exc_info=True)
        return False


def test_11_full_vehicles_with_queue():
    print_test_header(11, "Full Vehicles with Long Passenger Queue")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 11000.0
    
    # 30个等待的乘客
    passengers = [
        MockPassenger(f"P{i}", 
                     ["A", "B", "C"][i % 3],
                     ["D", "E", "F"][i % 3],
                     current_time - (300 - i*10))
        for i in range(30)
    ]
    
    # 10辆车，全部满载
    minibuses = []
    for i in range(10):
        capacity = 6
        occupancy = 6  # 全满
        existing_passengers = [f"P_full_{i}_{j}" for j in range(occupancy)]
        
        stations = ["A", "B", "C", "D", "E", "F"]
        route_plan = []
        # 前3个在前面的站下车
        for j in range(3):
            route_plan.append({
                "station_id": stations[j % 6],
                "action": "DROPOFF",
                "passenger_ids": [existing_passengers[j]]
            })
        # 后3个在后面的站下车
        for j in range(3, 6):
            route_plan.append({
                "station_id": stations[(j + 2) % 6],
                "action": "DROPOFF",
                "passenger_ids": [existing_passengers[j]]
            })
        
        minibuses.append({
            "minibus_id": f"M{i+1}",
            "current_location_id": stations[i % 6],
            "capacity": capacity,
            "occupancy": occupancy,
            "passenger_ids": existing_passengers,
            "route_plan": route_plan
        })
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 1000.0,
            'max_detour_time': 500.0
        }
    )
    
    print("\nScenario: 30 passengers waiting, 10 vehicles ALL FULL (occupancy=6/6)")
    print("Expected: Should insert passengers after dropoffs without crashes")
    
    import time
    start_time = time.time()
    
    try:
        result = optimizer.optimize(passengers, minibuses, network, current_time)
        execution_time = time.time() - start_time
        
        print("\nResults:")
        assigned = count_assigned_passengers(result)
        
        all_valid = True
        max_occupancy_seen = 0
        
        for mb_id, route in result.items():
            mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
            if route:
                print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
                
                is_valid = validate_route_plan(route, mb_info['capacity'], mb_info['occupancy'])
                if not is_valid:
                    print(f"  ⚠️  CAPACITY VIOLATION!")
                    all_valid = False
                
                # 检查最大载客量
                temp_occupancy = mb_info['occupancy']
                for stop in route:
                    if stop['action'] == 'DROPOFF':
                        temp_occupancy -= len(stop['passenger_ids'])
                    elif stop['action'] == 'PICKUP':
                        temp_occupancy += len(stop['passenger_ids'])
                    max_occupancy_seen = max(max_occupancy_seen, temp_occupancy)
        
        print(f"\n✓ Assigned: {len(assigned)}/30 passengers")
        print(f"✓ Max occupancy seen: {max_occupancy_seen}")
        print(f"✓ All capacity constraints valid: {all_valid}")
        print(f"✓ Execution time: {execution_time:.3f}s")
        
        return all_valid
        
    except Exception as e:
        print(f"\n✗ CRASH DETECTED: {e}")
        logger.error(f"Test 11 crashed: {e}", exc_info=True)
        return False


def test_12_complex_interleaved_routes():
    print_test_header(12, "Complex Interleaved Pickup/Dropoff Scenarios")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 12000.0
    
    # 15个新乘客，各种起终点组合
    passengers = [
        MockPassenger("P1", "A", "F", current_time - 100),
        MockPassenger("P2", "A", "E", current_time - 95),
        MockPassenger("P3", "B", "F", current_time - 90),
        MockPassenger("P4", "B", "D", current_time - 85),
        MockPassenger("P5", "C", "F", current_time - 80),
        MockPassenger("P6", "C", "E", current_time - 75),
        MockPassenger("P7", "D", "A", current_time - 70),
        MockPassenger("P8", "D", "B", current_time - 65),
        MockPassenger("P9", "E", "A", current_time - 60),
        MockPassenger("P10", "E", "C", current_time - 55),
        MockPassenger("P11", "A", "D", current_time - 50),
        MockPassenger("P12", "B", "E", current_time - 45),
        MockPassenger("P13", "C", "A", current_time - 40),
        MockPassenger("P14", "D", "F", current_time - 35),
        MockPassenger("P15", "E", "B", current_time - 30),
    ]
    
    # 5辆车，每辆有复杂的现有路线
    minibuses = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 6,
            "occupancy": 4,
            "passenger_ids": ["E1", "E2", "E3", "E4"],
            "route_plan": [
                {"station_id": "B", "action": "DROPOFF", "passenger_ids": ["E1"]},
                {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["E2"]},
                {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["E3"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["E4"]},
            ]
        },
        {
            "minibus_id": "M2",
            "current_location_id": "B",
            "capacity": 6,
            "occupancy": 5,
            "passenger_ids": ["E5", "E6", "E7", "E8", "E9"],
            "route_plan": [
                {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["E5", "E6"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["E7"]},
                {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["E8", "E9"]},
            ]
        },
        {
            "minibus_id": "M3",
            "current_location_id": "C",
            "capacity": 6,
            "occupancy": 3,
            "passenger_ids": ["E10", "E11", "E12"],
            "route_plan": [
                {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["E10"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["E11"]},
                {"station_id": "A", "action": "DROPOFF", "passenger_ids": ["E12"]},
            ]
        },
        {
            "minibus_id": "M4",
            "current_location_id": "D",
            "capacity": 8,
            "occupancy": 6,
            "passenger_ids": ["E13", "E14", "E15", "E16", "E17", "E18"],
            "route_plan": [
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["E13"]},
                {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["E14", "E15"]},
                {"station_id": "A", "action": "DROPOFF", "passenger_ids": ["E16"]},
                {"station_id": "B", "action": "DROPOFF", "passenger_ids": ["E17", "E18"]},
            ]
        },
        {
            "minibus_id": "M5",
            "current_location_id": "E",
            "capacity": 6,
            "occupancy": 2,
            "passenger_ids": ["E19", "E20"],
            "route_plan": [
                {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["E19"]},
                {"station_id": "A", "action": "DROPOFF", "passenger_ids": ["E20"]},
            ]
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
    
    print("\nScenario: 15 passengers, 5 vehicles with complex existing routes")
    print("Expected: Should handle complex insertion without violating capacity")
    
    import time
    start_time = time.time()
    
    try:
        result = optimizer.optimize(passengers, minibuses, network, current_time)
        execution_time = time.time() - start_time
        
        print("\nResults:")
        assigned = count_assigned_passengers(result)
        
        all_valid = True
        for mb_id, route in result.items():
            mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
            if route:
                print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
                
                is_valid = validate_route_plan(route, mb_info['capacity'], mb_info['occupancy'])
                if not is_valid:
                    print(f"  ⚠️  CAPACITY VIOLATION!")
                    all_valid = False
        
        print(f"\n✓ Assigned: {len(assigned)}/15 passengers")
        print(f"✓ All capacity constraints valid: {all_valid}")
        print(f"✓ Execution time: {execution_time:.3f}s")
        
        return all_valid and len(assigned) >= 5
        
    except Exception as e:
        print(f"\n✗ CRASH DETECTED: {e}")
        logger.error(f"Test 12 crashed: {e}", exc_info=True)
        return False


def test_13_extreme_capacity_edge_cases():
    print_test_header(13, "Extreme Capacity Edge Cases")
    
    from route_optimizer import RouteOptimizer
    
    network = MockNetwork()
    current_time = 13000.0
    
    # 25个乘客
    passengers = [
        MockPassenger(f"P{i}", 
                     ["A", "B", "C", "D", "E"][i % 5],
                     ["C", "D", "E", "F", "A"][(i + 2) % 5],
                     current_time - (250 - i*10))
        for i in range(25)
    ]
    
    # 特殊车辆配置：混合容量和极限状态
    minibuses = [
        # 小容量车，满载
        {
            "minibus_id": "M_small_1",
            "current_location_id": "A",
            "capacity": 4,
            "occupancy": 4,
            "passenger_ids": ["S1", "S2", "S3", "S4"],
            "route_plan": [
                {"station_id": "B", "action": "DROPOFF", "passenger_ids": ["S1"]},
                {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["S2", "S3", "S4"]},
            ]
        },
        # 小容量车，只有1个空位
        {
            "minibus_id": "M_small_2",
            "current_location_id": "B",
            "capacity": 4,
            "occupancy": 3,
            "passenger_ids": ["S5", "S6", "S7"],
            "route_plan": [
                {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["S5"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["S6", "S7"]},
            ]
        },
        # 标准容量车，接近满载
        {
            "minibus_id": "M_normal_1",
            "current_location_id": "C",
            "capacity": 6,
            "occupancy": 5,
            "passenger_ids": ["N1", "N2", "N3", "N4", "N5"],
            "route_plan": [
                {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["N1"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["N2"]},
                {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["N3", "N4", "N5"]},
            ]
        },
        # 标准容量车，空载
        {
            "minibus_id": "M_normal_2",
            "current_location_id": "D",
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        },
        # 大容量车，半满
        {
            "minibus_id": "M_large_1",
            "current_location_id": "E",
            "capacity": 10,
            "occupancy": 5,
            "passenger_ids": ["L1", "L2", "L3", "L4", "L5"],
            "route_plan": [
                {"station_id": "F", "action": "DROPOFF", "passenger_ids": ["L1", "L2"]},
                {"station_id": "A", "action": "DROPOFF", "passenger_ids": ["L3"]},
                {"station_id": "B", "action": "DROPOFF", "passenger_ids": ["L4", "L5"]},
            ]
        },
        # 大容量车，接近满载
        {
            "minibus_id": "M_large_2",
            "current_location_id": "F",
            "capacity": 10,
            "occupancy": 8,
            "passenger_ids": [f"L{i}" for i in range(6, 14)],
            "route_plan": [
                {"station_id": "A", "action": "DROPOFF", "passenger_ids": ["L6", "L7"]},
                {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["L8", "L9", "L10"]},
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["L11", "L12", "L13"]},
            ]
        },
    ]
    
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 1000.0,
            'max_detour_time': 500.0
        }
    )
    
    print("\nScenario: 25 passengers, 6 vehicles with varying capacities (4, 6, 10)")
    print("Expected: Should respect different capacity limits without errors")
    
    import time
    start_time = time.time()
    
    try:
        result = optimizer.optimize(passengers, minibuses, network, current_time)
        execution_time = time.time() - start_time
        
        print("\nResults:")
        assigned = count_assigned_passengers(result)
        
        all_valid = True
        capacity_summary = {}
        
        for mb_id, route in result.items():
            mb_info = next(mb for mb in minibuses if mb['minibus_id'] == mb_id)
            capacity_key = mb_info['capacity']
            
            if capacity_key not in capacity_summary:
                capacity_summary[capacity_key] = {'vehicles': 0, 'assigned': 0}
            capacity_summary[capacity_key]['vehicles'] += 1
            
            if route:
                print_route_plan(mb_id, route, mb_info['capacity'], mb_info['occupancy'])
                
                is_valid = validate_route_plan(route, mb_info['capacity'], mb_info['occupancy'])
                if not is_valid:
                    print(f"  ⚠️  CAPACITY VIOLATION!")
                    all_valid = False
                
                # 统计这辆车分配了多少新乘客
                new_assigned = 0
                for stop in route:
                    if stop['action'] == 'PICKUP':
                        new_assigned += len(stop['passenger_ids'])
                capacity_summary[capacity_key]['assigned'] += new_assigned
        
        print(f"\n✓ Assigned: {len(assigned)}/25 passengers")
        print("\nCapacity breakdown:")
        for cap, stats in sorted(capacity_summary.items()):
            print(f"  Capacity {cap}: {stats['vehicles']} vehicles, {stats['assigned']} new passengers assigned")
        print(f"\n✓ All capacity constraints valid: {all_valid}")
        print(f"✓ Execution time: {execution_time:.3f}s")
        
        return all_valid and len(assigned) >= 10
        
    except Exception as e:
        print(f"\n✗ CRASH DETECTED: {e}")
        logger.error(f"Test 13 crashed: {e}", exc_info=True)
        return False


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
        ("Stress Test (Basic)", test_8_stress_test),
        ("Near-Capacity Stress", test_9_near_capacity_stress),
        ("Massive Scale", test_10_massive_scale),
        ("Full Vehicles Queue", test_11_full_vehicles_with_queue),
        ("Complex Interleaving", test_12_complex_interleaved_routes),
        ("Extreme Edge Cases", test_13_extreme_capacity_edge_cases),
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