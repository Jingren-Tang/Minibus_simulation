"""
Test script for Minibus class - self-contained version.

This script creates all necessary objects from scratch for testing,
no external data files required.
"""

import logging
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import real classes
from vehicles.minibus import Minibus
from demand.passenger import Passenger
from network.station import Station

# Configure logging to see all messages
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detail
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


class SimpleNetwork:
    """
    Simplified network for testing purposes.
    
    Creates a simple 4-station network with fixed travel times.
    """
    
    def __init__(self):
        """Initialize a simple test network."""
        # Create 4 stations
        self.stations = {
            "A": Station("A", "Station Alpha", (40.7128, 74.0060), 0),
            "B": Station("B", "Station Beta", (40.7589, 73.9851), 1),
            "C": Station("C", "Station Charlie", (40.7614, 73.9776), 2),
            "D": Station("D", "Station Delta", (40.7489, 73.9680), 3),
        }
        self.station_list = list(self.stations.keys())
        self.num_stations = len(self.stations)
        
        # Simple travel time model: 5 minutes (300s) between adjacent stations
        self.base_travel_time = 300.0
        
        print(f"Created simple network with {self.num_stations} stations: {', '.join(self.station_list)}")
    
    def get_station(self, station_id: str) -> Station:
        """Get a station by ID."""
        return self.stations.get(station_id)
    
    def get_travel_time(
        self, 
        origin_id: str, 
        dest_id: str, 
        current_time: float
    ) -> float:
        """
        Get travel time between two stations.
        
        Simple model: 0 if same station, 300s otherwise.
        """
        if origin_id == dest_id:
            return 0.0
        return self.base_travel_time


def test_minibus():
    """Main test function for Minibus class."""
    
    print_section("SETUP: Create Simple Network")
    
    # Create simple network
    network = SimpleNetwork()
    
    # Test 1: Initialize Minibus
    print_section("TEST 1: Initialize Minibus")
    
    minibus = Minibus(
        minibus_id="M1",
        capacity=6,
        initial_location="A",
        network=network
    )
    
    print(f"Created minibus: {minibus}")
    print(f"  Status: {minibus.status}")
    print(f"  Is available: {minibus.is_available()}")
    print(f"  Occupancy: {minibus.get_occupancy()}/{minibus.capacity}")
    assert minibus.status == Minibus.IDLE, "Minibus should start as IDLE"
    assert minibus.is_available(), "Minibus should be available initially"
    
    # Test 2: Create passengers
    print_section("TEST 2: Create Passengers and Add to Stations")
    
    current_time = 100.0
    
    # Create passengers
    p1 = Passenger(
        passenger_id="P1",
        origin="B",
        destination="C",
        appear_time=current_time,
        max_wait_time=900.0
    )
    
    p2 = Passenger(
        passenger_id="P2",
        origin="B",
        destination="D",
        appear_time=current_time,
        max_wait_time=900.0
    )
    
    p3 = Passenger(
        passenger_id="P3",
        origin="C",
        destination="D",
        appear_time=current_time + 50,
        max_wait_time=900.0
    )
    
    print(f"Created 3 passengers:")
    print(f"  P1: B -> C")
    print(f"  P2: B -> D")
    print(f"  P3: C -> D")
    
    # Get stations
    station_a = network.get_station("A")
    station_b = network.get_station("B")
    station_c = network.get_station("C")
    station_d = network.get_station("D")
    
    # Add passengers to stations
    station_b.add_waiting_passenger(p1)
    station_b.add_waiting_passenger(p2)
    station_c.add_waiting_passenger(p3)
    
    print(f"\nStation status:")
    print(f"  Station B: {len(station_b.waiting_passengers)} waiting")
    print(f"  Station C: {len(station_c.waiting_passengers)} waiting")
    
    # Test 3: Update route plan
    print_section("TEST 3: Update Route Plan")
    
    # Assign vehicle to passengers (optimizer would do this)
    p1.assigned_vehicle_id = "M1"
    p2.assigned_vehicle_id = "M1"
    p3.assigned_vehicle_id = "M1"
    
    # Route: A -> B (pickup P1, P2) -> C (pickup P3) -> C (dropoff P1) -> D (dropoff P2, P3)
    # Note: Station C appears twice - once for pickup, once for dropoff
    route_plan = [
        {"station_id": "B", "action": "PICKUP", "passenger_ids": ["P1", "P2"]},
        {"station_id": "C", "action": "PICKUP", "passenger_ids": ["P3"]},
        {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["P1"]},
        {"station_id": "D", "action": "DROPOFF", "passenger_ids": ["P2", "P3"]}
    ]
    
    minibus.update_route_plan(route_plan, current_time)
    
    print(f"Route plan updated:")
    print(f"  Status: {minibus.status}")
    print(f"  Next station: {minibus.next_station_id}")
    print(f"  ETA: {minibus.next_arrival_time:.1f}s")
    print(f"  Travel time: {minibus.next_arrival_time - current_time:.1f}s")
    print(f"\n{minibus.visualize_route_plan()}")
    
    assert minibus.status == Minibus.EN_ROUTE, "Should be EN_ROUTE after route plan update"
    assert minibus.next_station_id == "B", "Next station should be B"
    
    # Test 4: Arrive at station B (pickup)
    print_section("TEST 4: Arrive at Station B - PICKUP P1 and P2")
    
    current_time = minibus.next_arrival_time
    print(f"Arriving at station B at time {current_time:.1f}s")
    
    result = minibus.arrive_at_station(station_b, current_time)
    
    print(f"\nResult:")
    print(f"  Action: {result['action_type']}")
    print(f"  Boarded: {len(result['boarded'])} passengers {[p.passenger_id for p in result['boarded']]}")
    print(f"  Alighted: {len(result['alighted'])} passengers")
    
    print(f"\nMinibus after pickup:")
    print(f"  Location: {minibus.current_location_id}")
    print(f"  Status: {minibus.status}")
    print(f"  Occupancy: {minibus.get_occupancy()}/{minibus.capacity}")
    print(f"  Passengers: {[p.passenger_id for p in minibus.passengers]}")
    print(f"  Next stop: {minibus.next_station_id}")
    
    print(f"\nStation B after pickup:")
    print(f"  Waiting passengers: {len(station_b.waiting_passengers)}")
    
    print(f"\nPassenger statuses:")
    print(f"  P1: {p1.status} (boarded at {p1.pickup_time:.1f}s)")
    print(f"  P2: {p2.status} (boarded at {p2.pickup_time:.1f}s)")
    
    assert len(result['boarded']) == 2, "Should board 2 passengers"
    assert minibus.get_occupancy() == 2, "Should have 2 passengers on board"
    assert len(station_b.waiting_passengers) == 0, "Station B should have no waiting passengers"
    assert p1.status == Passenger.ONBOARD, "P1 should be ONBOARD"
    assert p2.status == Passenger.ONBOARD, "P2 should be ONBOARD"
    
    # Test 5: Arrive at station C (pickup)
    print_section("TEST 5: Arrive at Station C - PICKUP P3")
    
    current_time = minibus.next_arrival_time
    print(f"Arriving at station C at time {current_time:.1f}s")
    
    result = minibus.arrive_at_station(station_c, current_time)
    
    print(f"\nResult:")
    print(f"  Action: {result['action_type']}")
    print(f"  Boarded: {len(result['boarded'])} passengers {[p.passenger_id for p in result['boarded']]}")
    
    print(f"\nMinibus after pickup:")
    print(f"  Occupancy: {minibus.get_occupancy()}/{minibus.capacity}")
    print(f"  Passengers: {[p.passenger_id for p in minibus.passengers]}")
    print(f"  Next stop: {minibus.next_station_id}")
    
    assert len(result['boarded']) == 1, "Should board 1 passenger"
    assert minibus.get_occupancy() == 3, "Should have 3 passengers on board"
    assert p3.status == Passenger.ONBOARD, "P3 should be ONBOARD"
    
    # Test 6: Arrive at station C again (dropoff P1)
    print_section("TEST 6: Arrive at Station C - DROPOFF P1")
    
    current_time = minibus.next_arrival_time
    print(f"At station C (already here), time {current_time:.1f}s")
    print("Note: This tests same station with different action (pickup then dropoff)")
    
    result = minibus.arrive_at_station(station_c, current_time)
    
    print(f"\nResult:")
    print(f"  Action: {result['action_type']}")
    print(f"  Alighted: {len(result['alighted'])} passengers {[p.passenger_id for p in result['alighted']]}")
    
    print(f"\nMinibus after dropoff:")
    print(f"  Occupancy: {minibus.get_occupancy()}/{minibus.capacity}")
    print(f"  Passengers: {[p.passenger_id for p in minibus.passengers]}")
    print(f"  Next stop: {minibus.next_station_id}")
    
    print(f"\nP1 journey completed:")
    print(f"  Status: {p1.status}")
    print(f"  Wait time: {p1.pickup_time - p1.appear_time:.1f}s")
    print(f"  Travel time: {p1.arrival_time - p1.pickup_time:.1f}s")
    print(f"  Total time: {p1.arrival_time - p1.appear_time:.1f}s")
    
    assert len(result['alighted']) == 1, "Should dropoff 1 passenger"
    assert minibus.get_occupancy() == 2, "Should have 2 passengers on board"
    assert p1.status == Passenger.ARRIVED, "P1 should have ARRIVED"
    
    # Test 7: Arrive at station D (final dropoff)
    print_section("TEST 7: Arrive at Station D - DROPOFF P2 and P3")
    
    current_time = minibus.next_arrival_time
    print(f"Arriving at station D at time {current_time:.1f}s")
    
    result = minibus.arrive_at_station(station_d, current_time)
    
    print(f"\nResult:")
    print(f"  Action: {result['action_type']}")
    print(f"  Alighted: {len(result['alighted'])} passengers {[p.passenger_id for p in result['alighted']]}")
    
    print(f"\nMinibus final status:")
    print(f"  Location: {minibus.current_location_id}")
    print(f"  Status: {minibus.status}")
    print(f"  Occupancy: {minibus.get_occupancy()}/{minibus.capacity}")
    print(f"  Next stop: {minibus.next_station_id}")
    print(f"  Is available: {minibus.is_available()}")
    print(f"  Route plan remaining: {len(minibus.route_plan)} stops")
    
    print(f"\nAll passengers journey summary:")
    for passenger in [p1, p2, p3]:
        wait = passenger.pickup_time - passenger.appear_time
        travel = passenger.arrival_time - passenger.pickup_time
        total = passenger.arrival_time - passenger.appear_time
        print(f"  {passenger.passenger_id}: Wait={wait:.1f}s, Travel={travel:.1f}s, Total={total:.1f}s")
    
    assert len(result['alighted']) == 2, "Should dropoff 2 passengers"
    assert minibus.get_occupancy() == 0, "Minibus should be empty"
    assert minibus.status == Minibus.IDLE, "Minibus should be IDLE after completing route"
    assert minibus.is_available(), "Minibus should be available"
    assert len(minibus.route_plan) == 0, "Route plan should be empty"
    
    # Test 8: Test helper methods
    print_section("TEST 8: Test Helper Methods")
    
    print(f"Is full: {minibus.is_full()}")
    print(f"Is available: {minibus.is_available()}")
    print(f"Remaining capacity: {minibus.get_remaining_capacity()}")
    print(f"Assigned passenger IDs: {minibus.get_assigned_passenger_ids()}")
    print(f"Current task: {minibus.get_current_task()}")
    
    assert not minibus.is_full(), "Empty minibus should not be full"
    assert minibus.get_remaining_capacity() == 6, "Should have full capacity available"
    
    # Test 9: Get minibus info
    print_section("TEST 9: Get Comprehensive Minibus Info")
    
    info = minibus.get_minibus_info()
    print("\nMinibus info dictionary:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Test 10: Test validation
    print_section("TEST 10: Test Route Plan Validation")
    
    valid_plan = [
        {"station_id": "A", "action": "PICKUP", "passenger_ids": ["P1"]}
    ]
    print(f"Valid plan: {minibus.validate_route_plan(valid_plan)}")
    assert minibus.validate_route_plan(valid_plan), "Valid plan should pass validation"
    
    invalid_plan1 = [
        {"station_id": "A", "action": "PICKUP"}  # Missing passenger_ids
    ]
    print(f"Invalid plan (missing field): {minibus.validate_route_plan(invalid_plan1)}")
    assert not minibus.validate_route_plan(invalid_plan1), "Should fail validation"
    
    invalid_plan2 = [
        {"station_id": "A", "action": "INVALID_ACTION", "passenger_ids": ["P1"]}
    ]
    print(f"Invalid plan (wrong action): {minibus.validate_route_plan(invalid_plan2)}")
    assert not minibus.validate_route_plan(invalid_plan2), "Should fail validation"
    
    # Test 11: Test error handling
    print_section("TEST 11: Test Error Handling")
    
    # Test capacity limit
    print("\n11.1: Test capacity limit")
    minibus2 = Minibus("M2", capacity=2, initial_location="B", network=network)
    
    p4 = Passenger("P4", "B", "C", 500.0, 900.0)
    p5 = Passenger("P5", "B", "C", 500.0, 900.0)
    p6 = Passenger("P6", "B", "C", 500.0, 900.0)
    
    p4.assigned_vehicle_id = "M2"
    p5.assigned_vehicle_id = "M2"
    p6.assigned_vehicle_id = "M2"
    
    station_b.add_waiting_passenger(p4)
    station_b.add_waiting_passenger(p5)
    station_b.add_waiting_passenger(p6)
    
    route_plan2 = [{"station_id": "B", "action": "PICKUP", "passenger_ids": ["P4", "P5", "P6"]}]
    minibus2.update_route_plan(route_plan2, 500.0)
    result = minibus2.arrive_at_station(station_b, 800.0)
    
    print(f"  Tried to pick up 3 passengers with capacity=2")
    print(f"  Actually boarded: {len(result['boarded'])} passengers")
    print(f"  Is full: {minibus2.is_full()}")
    print(f"  Passengers left at station: {len(station_b.waiting_passengers)}")
    
    assert len(result['boarded']) == 2, "Should only board 2 passengers (at capacity)"
    assert minibus2.is_full(), "Minibus should be full"
    
    # Test wrong station arrival
    print("\n11.2: Test wrong station arrival")
    minibus3 = Minibus("M3", capacity=4, initial_location="A", network=network)
    plan = [{"station_id": "B", "action": "PICKUP", "passenger_ids": []}]
    minibus3.update_route_plan(plan, 1000.0)
    
    try:
        # Try to arrive at C when expecting B
        minibus3.arrive_at_station(station_c, 1300.0)
        print("  ERROR: Should have raised ValueError!")
        assert False, "Should raise ValueError"
    except ValueError as e:
        print(f"  ✓ Correctly raised error: {e}")
    
    # Test passenger not found
    print("\n11.3: Test passenger not at station")
    minibus4 = Minibus("M4", capacity=4, initial_location="A", network=network)
    plan = [{"station_id": "B", "action": "PICKUP", "passenger_ids": ["P999"]}]  # Non-existent passenger
    minibus4.update_route_plan(plan, 1500.0)
    result = minibus4.arrive_at_station(station_b, 1800.0)
    
    print(f"  Tried to pick up non-existent passenger P999")
    print(f"  Boarded: {len(result['boarded'])} passengers (should be 0)")
    assert len(result['boarded']) == 0, "Should not board any passengers"
    
    print_section("✅ ALL TESTS PASSED!")
    print("\nSummary:")
    print("  ✓ Minibus initialization")
    print("  ✓ Route plan updates")
    print("  ✓ Pickup operations")
    print("  ✓ Dropoff operations")
    print("  ✓ Same station pickup + dropoff")
    print("  ✓ Status transitions")
    print("  ✓ Helper methods")
    print("  ✓ Input validation")
    print("  ✓ Error handling")
    print("\nMinibus class is working correctly! 🎉")


if __name__ == "__main__":
    test_minibus()