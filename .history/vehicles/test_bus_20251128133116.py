"""
Unit tests for the Bus class.

This test module validates all functionality of the Bus class including:
- Initialization and validation
- Station arrival processing
- Passenger boarding and alighting
- Route completion and removal
"""

import sys
import os
import logging
from typing import List

# Add parent directory to path to import from sibling directories
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from demand.passenger import Passenger
from network.station import Station
from vehicles.bus import Bus

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_bus_initialization():
    """Test bus initialization with valid and invalid inputs."""
    print("\n" + "="*70)
    print("TEST 1: Bus Initialization")
    print("="*70)
    
    # Valid initialization
    route = ["A", "B", "C", "D"]
    schedule = {
        "A": 0.0,
        "B": 300.0,
        "C": 720.0,
        "D": 1200.0
    }
    
    bus = Bus("BUS_1", route, schedule, capacity=40)
    print(f"✓ Created bus: {bus}")
    print(f"  - Next station: {bus.next_station_id} at {bus.next_arrival_time}s")
    print(f"  - Capacity: {bus.capacity}")
    print(f"  - Occupancy: {bus.get_occupancy()}")
    
    # Test invalid inputs
    print("\nTesting invalid inputs:")
    
    # Empty route
    try:
        bad_bus = Bus("BUS_2", [], schedule, 40)
        print("✗ FAILED: Should reject empty route")
    except ValueError as e:
        print(f"✓ Correctly rejected empty route: {e}")
    
    # Invalid capacity
    try:
        bad_bus = Bus("BUS_3", route, schedule, 0)
        print("✗ FAILED: Should reject capacity <= 0")
    except ValueError as e:
        print(f"✓ Correctly rejected invalid capacity: {e}")
    
    # Incomplete schedule
    try:
        incomplete_schedule = {"A": 0.0, "B": 300.0}  # Missing C and D
        bad_bus = Bus("BUS_4", route, incomplete_schedule, 40)
        print("✗ FAILED: Should reject incomplete schedule")
    except ValueError as e:
        print(f"✓ Correctly rejected incomplete schedule: {e}")


def test_passenger_boarding_and_alighting():
    """Test passenger boarding and alighting operations."""
    print("\n" + "="*70)
    print("TEST 2: Passenger Boarding and Alighting")
    print("="*70)
    
    # Create bus
    route = ["A", "B", "C", "D"]
    schedule = {"A": 0.0, "B": 300.0, "C": 720.0, "D": 1200.0}
    bus = Bus("BUS_1", route, schedule, capacity=40)
    
    # Create station A with waiting passengers
    station_a = Station("A", "Station A", location=(22.3193, 114.1694), index=0)
    
    # Create passengers - they start in WAITING status automatically
    p1 = Passenger("P1", origin="A", destination="B", appear_time=0.0, max_wait_time=900.0)
    p2 = Passenger("P2", origin="A", destination="C", appear_time=0.0, max_wait_time=900.0)
    p3 = Passenger("P3", origin="A", destination="D", appear_time=0.0, max_wait_time=900.0)
    p4 = Passenger("P4", origin="A", destination="E", appear_time=0.0, max_wait_time=900.0)  # E not on route
    
    # Add passengers to station (they're already in WAITING status)
    for p in [p1, p2, p3, p4]:
        station_a.add_waiting_passenger(p)
    
    print(f"Station A has {len(station_a.get_waiting_passengers())} waiting passengers")
    print(f"Bus occupancy before boarding: {bus.get_occupancy()}/{bus.capacity}")
    
    # Bus arrives at station A
    result = bus.arrive_at_station(station_a, current_time=0.0)
    
    print(f"\nBoarding results:")
    print(f"  - Boarded: {len(result['boarded'])} passengers")
    for p in result['boarded']:
        print(f"    • {p.passenger_id} → {p.destination_station_id}")
    print(f"  - Rejected: {len(result['rejected'])} passengers")
    for p in result['rejected']:
        print(f"    • {p.passenger_id} → {p.destination_station_id} (not on route)")
    print(f"  - Alighted: {len(result['alighted'])} passengers")
    
    print(f"\nBus occupancy after boarding: {bus.get_occupancy()}/{bus.capacity}")
    print(f"Station A waiting passengers: {len(station_a.get_waiting_passengers())}")
    print(f"Bus next station: {bus.next_station_id} at {bus.next_arrival_time}s")
    
    # Move to station B
    print("\n" + "-"*70)
    station_b = Station("B", "Station B", location=(22.3200, 114.1700), index=1)
    result = bus.arrive_at_station(station_b, current_time=300.0)
    
    print(f"At station B:")
    print(f"  - Boarded: {len(result['boarded'])} passengers")
    print(f"  - Alighted: {len(result['alighted'])} passengers")
    for p in result['alighted']:
        print(f"    • {p.passenger_id} reached destination")
    print(f"  - Bus occupancy: {bus.get_occupancy()}/{bus.capacity}")
    print(f"  - Next station: {bus.next_station_id} at {bus.next_arrival_time}s")


def test_bus_capacity():
    """Test bus capacity limits."""
    print("\n" + "="*70)
    print("TEST 3: Bus Capacity Limits")
    print("="*70)
    
    # Create small capacity bus
    route = ["A", "B", "C"]
    schedule = {"A": 0.0, "B": 300.0, "C": 600.0}
    bus = Bus("BUS_SMALL", route, schedule, capacity=2)  # Only 2 seats
    
    # Create station with many passengers
    station_a = Station("A", "Station A", location=(22.3193, 114.1694), index=0)
    
    passengers = []
    for i in range(5):
        p = Passenger(f"P{i+1}", origin="A", destination="C", appear_time=0.0, max_wait_time=900.0)
        station_a.add_waiting_passenger(p)
        passengers.append(p)
    
    print(f"Created bus with capacity {bus.capacity}")
    print(f"Station has {len(station_a.get_waiting_passengers())} waiting passengers")
    
    # Bus arrives
    result = bus.arrive_at_station(station_a, current_time=0.0)
    
    print(f"\nBoarding results:")
    print(f"  - Boarded: {len(result['boarded'])} passengers (bus full!)")
    print(f"  - Rejected: {len(result['rejected'])} passengers (no space)")
    print(f"  - Bus is full: {bus.is_full()}")
    print(f"  - Remaining capacity: {bus.get_remaining_capacity()}")
    print(f"  - Still waiting at station: {len(station_a.get_waiting_passengers())}")


def test_destination_checking():
    """Test destination route checking."""
    print("\n" + "="*70)
    print("TEST 4: Destination Route Checking")
    print("="*70)
    
    route = ["A", "B", "C", "D"]
    schedule = {"A": 0.0, "B": 300.0, "C": 720.0, "D": 1200.0}
    bus = Bus("BUS_1", route, schedule, capacity=40)
    
    print(f"Bus route: {route}")
    print(f"Current position index: {bus.current_route_index}")
    
    # Test various destinations
    test_cases = [
        ("B", True, "Next station on route"),
        ("C", True, "Later station on route"),
        ("D", True, "Terminal station"),
        ("A", False, "Already passed"),
        ("E", False, "Not on route at all"),
    ]
    
    print("\nDestination checks:")
    for dest, expected, description in test_cases:
        result = bus.is_destination_on_route(dest)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {dest}: {result} - {description}")
    
    # Move bus forward and test again
    print("\nAfter moving to position 2 (station C):")
    bus.current_route_index = 2
    
    test_cases_after = [
        ("D", True, "Terminal still reachable"),
        ("C", False, "Current station"),
        ("B", False, "Already passed"),
        ("A", False, "Already passed"),
    ]
    
    for dest, expected, description in test_cases_after:
        result = bus.is_destination_on_route(dest)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {dest}: {result} - {description}")


def test_complete_journey():
    """Test a complete bus journey from start to terminal."""
    print("\n" + "="*70)
    print("TEST 5: Complete Bus Journey")
    print("="*70)
    
    # Create bus and stations
    route = ["A", "B", "C", "D"]
    schedule = {"A": 0.0, "B": 300.0, "C": 720.0, "D": 1200.0}
    bus = Bus("BUS_1", route, schedule, capacity=40)
    
    stations = {
        "A": Station("A", "Station A", location=(22.3193, 114.1694), index=0),
        "B": Station("B", "Station B", location=(22.3200, 114.1700), index=1),
        "C": Station("C", "Station C", location=(22.3210, 114.1710), index=2),
        "D": Station("D", "Station D", location=(22.3220, 114.1720), index=3),
    }
    
    # Add passengers at station A
    passengers_a = [
        Passenger("P1", origin="A", destination="B", appear_time=0.0, max_wait_time=900.0),
        Passenger("P2", origin="A", destination="C", appear_time=0.0, max_wait_time=900.0),
        Passenger("P3", origin="A", destination="D", appear_time=0.0, max_wait_time=900.0),
    ]
    for p in passengers_a:
        stations["A"].add_waiting_passenger(p)
    
    # Add passengers at station B (going to C and D)
    passengers_b = [
        Passenger("P4", origin="B", destination="C", appear_time=300.0, max_wait_time=900.0),
        Passenger("P5", origin="B", destination="D", appear_time=300.0, max_wait_time=900.0),
    ]
    for p in passengers_b:
        stations["B"].add_waiting_passenger(p)
    
    print(f"Starting journey: {bus}")
    print(f"Should be removed: {bus.should_be_removed()}")
    
    # Journey through all stations
    journey_times = [0.0, 300.0, 720.0, 1200.0]
    
    for i, (station_id, time) in enumerate(zip(route, journey_times)):
        print(f"\n--- Stop {i+1}: Station {station_id} at {time}s ---")
        
        station = stations[station_id]
        result = bus.arrive_at_station(station, time)
        
        print(f"Boarded: {len(result['boarded'])}, Alighted: {len(result['alighted'])}")
        print(f"Current occupancy: {bus.get_occupancy()}/{bus.capacity}")
        print(f"At terminal: {bus.is_at_terminal()}")
        print(f"Should be removed: {bus.should_be_removed()}")
        print(f"Bus state: {bus}")
        
        if not bus.is_at_terminal():
            print(f"Next: {bus.next_station_id} at {bus.next_arrival_time}s")
    
    print(f"\n{'='*70}")
    print("Journey Statistics:")
    info = bus.get_bus_info()
    print(f"  - Total passengers served: {info['total_passengers_served']}")
    print(f"  - Final occupancy: {info['occupancy']}/{info['capacity']}")
    print(f"  - At terminal: {info['at_terminal']}")
    print(f"  - Should remove from simulation: {bus.should_be_removed()}")


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "="*70)
    print("TEST 6: Edge Cases")
    print("="*70)
    
    route = ["A", "B", "C"]
    schedule = {"A": 0.0, "B": 300.0, "C": 600.0}
    bus = Bus("BUS_1", route, schedule, capacity=40)
    
    # Test 1: Board passenger when bus is full
    print("\nTest 1: Board when full")
    bus.passengers = [f"dummy_{i}" for i in range(40)]  # Fill bus manually
    p = Passenger("P_EXTRA", origin="A", destination="B", appear_time=0.0, max_wait_time=900.0)
    result = bus.board_passenger(p, 0.0)
    print(f"  Boarding when full: {result} (should be False)")
    bus.passengers.clear()
    
    # Test 2: Alight passenger not on bus
    print("\nTest 2: Alight passenger not on bus")
    p2 = Passenger("P_NOTHERE", origin="A", destination="B", appear_time=0.0, max_wait_time=900.0)
    result = bus.alight_passenger(p2, 0.0)
    print(f"  Alighting non-existent passenger: {result} (should be False)")
    
    # Test 3: Get next station when at terminal
    print("\nTest 3: Next station at terminal")
    bus.current_route_index = len(route)  # Move to terminal
    next_station, next_time = bus.get_next_station()
    print(f"  Next station at terminal: {next_station}, {next_time} (should be None, None)")
    
    # Test 4: Check passengers alighting at station
    print("\nTest 4: Get passengers alighting at station")
    bus.current_route_index = 0
    p3 = Passenger("P3", origin="A", destination="B", appear_time=0.0, max_wait_time=900.0)
    p4 = Passenger("P4", origin="A", destination="C", appear_time=0.0, max_wait_time=900.0)
    bus.passengers = [p3, p4]
    
    alighting_b = bus.get_passengers_alighting_at("B")
    alighting_c = bus.get_passengers_alighting_at("C")
    print(f"  Passengers for B: {len(alighting_b)} (should be 1)")
    print(f"  Passengers for C: {len(alighting_c)} (should be 1)")
    
    # Test 5: Bus info
    print("\nTest 5: Bus info dictionary")
    info = bus.get_bus_info()
    print(f"  Info keys: {list(info.keys())}")
    print(f"  Bus ID: {info['bus_id']}")
    print(f"  Route: {info['route']}")


def run_all_tests():
    """Run all test functions."""
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#" + " "*20 + "BUS CLASS TEST SUITE" + " "*28 + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    try:
        test_bus_initialization()
        test_passenger_boarding_and_alighting()
        test_bus_capacity()
        test_destination_checking()
        test_complete_journey()
        test_edge_cases()
        
        print("\n" + "#"*70)
        print("#" + " "*68 + "#")
        print("#" + " "*22 + "ALL TESTS COMPLETED" + " "*27 + "#")
        print("#" + " "*68 + "#")
        print("#"*70 + "\n")
        
    except Exception as e:
        print(f"\n{'!'*70}")
        print(f"TEST FAILED WITH ERROR: {e}")
        print(f"{'!'*70}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()