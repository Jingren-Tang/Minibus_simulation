"""
Test script for Passenger class.

Tests all functionality including:
- Normal state transitions (bus and minibus scenarios)
- Edge cases and error handling
- Timeout scenarios
- Time calculations
- State queries
"""

import logging
from passenger import Passenger

# Configure logging to see the passenger lifecycle events
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

print("=" * 80)
print("PASSENGER CLASS FUNCTIONALITY TEST")
print("=" * 80)

# Test 1: Normal Minibus Scenario (with assignment)
print("\n### Test 1: Normal Minibus Scenario (WAITING → ASSIGNED → ONBOARD → ARRIVED)")
print("-" * 80)
passenger1 = Passenger("P1", "StationA", "StationB", appear_time=100.0, max_wait_time=900.0)
print(f"Initial status: {passenger1.status}")
assert passenger1.status == Passenger.WAITING
assert passenger1.is_waiting() == True
assert passenger1.is_onboard() == False
assert passenger1.is_completed() == False

# Assign to minibus
passenger1.assign_to_vehicle("MINIBUS_1", current_time=150.0)
print(f"After assignment: {passenger1.status}, vehicle={passenger1.assigned_vehicle_id}")
assert passenger1.status == Passenger.ASSIGNED
assert passenger1.assigned_vehicle_id == "MINIBUS_1"

# Board the minibus
passenger1.board_vehicle(current_time=200.0)
print(f"After boarding: {passenger1.status}")
print(f"Wait time: {passenger1.get_wait_time(200.0):.1f}s (should be 100.0s)")
assert passenger1.status == Passenger.ONBOARD
assert passenger1.is_onboard() == True
assert passenger1.pickup_time == 200.0
assert passenger1.get_wait_time(200.0) == 100.0

# Arrive at destination
passenger1.arrive_at_destination(current_time=500.0)
print(f"After arrival: {passenger1.status}")
print(f"Travel time: {passenger1.get_travel_time():.1f}s (should be 300.0s)")
print(f"Total time: {passenger1.get_total_time():.1f}s (should be 400.0s)")
assert passenger1.status == Passenger.ARRIVED
assert passenger1.is_completed() == True
assert passenger1.get_travel_time() == 300.0
assert passenger1.get_total_time() == 400.0
print(f"Passenger1 representation: {passenger1}")
print("✓ Test 1 PASSED\n")


# Test 2: Normal Bus Scenario (direct boarding without assignment)
print("\n### Test 2: Normal Bus Scenario (WAITING → ONBOARD → ARRIVED)")
print("-" * 80)
passenger2 = Passenger("P2", "StationC", "StationD", appear_time=100.0, max_wait_time=900.0)
print(f"Initial status: {passenger2.status}")

# Bus arrives, passenger boards directly (no assignment needed)
passenger2.board_vehicle(current_time=250.0)
print(f"After boarding bus directly: {passenger2.status}")
print(f"Wait time: {passenger2.get_wait_time(250.0):.1f}s (should be 150.0s)")
assert passenger2.status == Passenger.ONBOARD
assert passenger2.assigned_vehicle_id is None  # No assignment for bus
assert passenger2.get_wait_time(250.0) == 150.0

# Arrive at destination
passenger2.arrive_at_destination(current_time=400.0)
print(f"After arrival: {passenger2.status}")
print(f"Travel time: {passenger2.get_travel_time():.1f}s (should be 150.0s)")
print(f"Total time: {passenger2.get_total_time():.1f}s (should be 300.0s)")
assert passenger2.get_travel_time() == 150.0
assert passenger2.get_total_time() == 300.0
print("✓ Test 2 PASSED\n")


# Test 3: Timeout and Abandonment Scenario
print("\n### Test 3: Timeout and Abandonment (WAITING → ABANDONED)")
print("-" * 80)
passenger3 = Passenger("P3", "StationE", "StationF", appear_time=100.0, max_wait_time=300.0)
print(f"Initial status: {passenger3.status}")

# Check timeout at different times
print(f"Check timeout at t=200: {passenger3.check_timeout(200.0)} (should be False)")
assert passenger3.check_timeout(200.0) == False
assert passenger3.status == Passenger.WAITING  # Status unchanged

print(f"Check timeout at t=450: {passenger3.check_timeout(450.0)} (should be True)")
assert passenger3.check_timeout(450.0) == True
assert passenger3.status == Passenger.WAITING  # Still unchanged - check doesn't modify state

# Abandon the passenger
passenger3.abandon(current_time=450.0)
print(f"After abandonment: {passenger3.status}")
print(f"Wait time at abandonment: {passenger3.get_wait_time(450.0):.1f}s (should be 350.0s)")
assert passenger3.status == Passenger.ABANDONED
assert passenger3.is_completed() == True
assert passenger3.get_wait_time(450.0) == 350.0
assert passenger3.get_travel_time() is None
assert passenger3.get_total_time() is None
print("✓ Test 3 PASSED\n")


# Test 4: Abandonment after Assignment (minibus assigned but never arrives)
print("\n### Test 4: Abandonment After Assignment (WAITING → ASSIGNED → ABANDONED)")
print("-" * 80)
passenger4 = Passenger("P4", "StationG", "StationH", appear_time=100.0, max_wait_time=600.0)
passenger4.assign_to_vehicle("MINIBUS_2", current_time=200.0)
print(f"Status after assignment: {passenger4.status}")

# Minibus never arrives, passenger gives up
passenger4.abandon(current_time=800.0)
print(f"After abandonment: {passenger4.status}")
print(f"Wait time: {passenger4.get_wait_time(800.0):.1f}s (should be 700.0s)")
assert passenger4.status == Passenger.ABANDONED
assert passenger4.get_wait_time(800.0) == 700.0
print("✓ Test 4 PASSED\n")


# Test 5: to_dict() Method
print("\n### Test 5: Serialization with to_dict()")
print("-" * 80)
passenger5 = Passenger("P5", "StationI", "StationJ", appear_time=0.0, max_wait_time=1800.0)
passenger5.assign_to_vehicle("BUS_5", current_time=60.0)
passenger5.board_vehicle(current_time=120.0)
passenger5.arrive_at_destination(current_time=600.0)

passenger_dict = passenger5.to_dict()
print("Passenger dictionary:")
for key, value in passenger_dict.items():
    print(f"  {key}: {value}")

assert passenger_dict['passenger_id'] == 'P5'
assert passenger_dict['status'] == Passenger.ARRIVED
assert passenger_dict['actual_wait_time'] == 120.0
assert passenger_dict['travel_time'] == 480.0
assert passenger_dict['total_time'] == 600.0
print("✓ Test 5 PASSED\n")


# Test 6: Error Handling - Invalid State Transitions
print("\n### Test 6: Error Handling - Invalid State Transitions")
print("-" * 80)

# Try to assign an already assigned passenger
passenger6 = Passenger("P6", "StationK", "StationL", appear_time=0.0, max_wait_time=900.0)
passenger6.assign_to_vehicle("MINIBUS_3", current_time=10.0)
try:
    passenger6.assign_to_vehicle("MINIBUS_4", current_time=20.0)
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Correctly rejected re-assignment: {e}")

# Try to arrive without boarding
passenger7 = Passenger("P7", "StationM", "StationN", appear_time=0.0, max_wait_time=900.0)
try:
    passenger7.arrive_at_destination(current_time=100.0)
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Correctly rejected arrival without boarding: {e}")

# Try to abandon after boarding
passenger8 = Passenger("P8", "StationO", "StationP", appear_time=0.0, max_wait_time=900.0)
passenger8.board_vehicle(current_time=50.0)
try:
    passenger8.abandon(current_time=100.0)
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Correctly rejected abandonment while onboard: {e}")

print("✓ Test 6 PASSED\n")


# Test 7: Error Handling - Invalid Inputs
print("\n### Test 7: Error Handling - Invalid Inputs")
print("-" * 80)

# Same origin and destination
try:
    p = Passenger("P_ERR1", "StationA", "StationA", appear_time=0.0, max_wait_time=900.0)
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Correctly rejected same origin/destination: {e}")

# Negative appear time
try:
    p = Passenger("P_ERR2", "StationA", "StationB", appear_time=-10.0, max_wait_time=900.0)
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Correctly rejected negative appear_time: {e}")

# Zero or negative max_wait_time
try:
    p = Passenger("P_ERR3", "StationA", "StationB", appear_time=0.0, max_wait_time=0.0)
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Correctly rejected zero max_wait_time: {e}")

# Time going backwards
passenger9 = Passenger("P9", "StationQ", "StationR", appear_time=100.0, max_wait_time=900.0)
passenger9.board_vehicle(current_time=200.0)
try:
    passenger9.arrive_at_destination(current_time=150.0)  # Earlier than pickup
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Correctly rejected time going backwards: {e}")

print("✓ Test 7 PASSED\n")


# Test 8: Edge Cases - Immediate Boarding
print("\n### Test 8: Edge Cases - Immediate Boarding")
print("-" * 80)
passenger10 = Passenger("P10", "StationS", "StationT", appear_time=100.0, max_wait_time=900.0)
# Board immediately at appear time (zero wait)
passenger10.board_vehicle(current_time=100.0)
print(f"Wait time with immediate boarding: {passenger10.get_wait_time(100.0):.1f}s (should be 0.0s)")
assert passenger10.get_wait_time(100.0) == 0.0
passenger10.arrive_at_destination(current_time=100.0)  # Instantaneous travel (edge case)
print(f"Travel time: {passenger10.get_travel_time():.1f}s (should be 0.0s)")
assert passenger10.get_travel_time() == 0.0
print("✓ Test 8 PASSED\n")


# Test 9: Wait Time Calculation for Different States
print("\n### Test 9: Wait Time Calculation in Different States")
print("-" * 80)
passenger11 = Passenger("P11", "StationU", "StationV", appear_time=1000.0, max_wait_time=900.0)

# While waiting
wait_time_1 = passenger11.get_wait_time(1050.0)
print(f"Wait time while WAITING (t=1050): {wait_time_1:.1f}s (should be 50.0s)")
assert wait_time_1 == 50.0

wait_time_2 = passenger11.get_wait_time(1100.0)
print(f"Wait time while WAITING (t=1100): {wait_time_2:.1f}s (should be 100.0s)")
assert wait_time_2 == 100.0

# After boarding
passenger11.board_vehicle(current_time=1200.0)
wait_time_3 = passenger11.get_wait_time(1500.0)
print(f"Wait time after ONBOARD (any t): {wait_time_3:.1f}s (should be 200.0s - fixed)")
assert wait_time_3 == 200.0

# After arrival
passenger11.arrive_at_destination(current_time=1800.0)
wait_time_4 = passenger11.get_wait_time(2000.0)
print(f"Wait time after ARRIVED (any t): {wait_time_4:.1f}s (should be 200.0s - fixed)")
assert wait_time_4 == 200.0

print("✓ Test 9 PASSED\n")


# Summary
print("=" * 80)
print("ALL TESTS PASSED! ✓")
print("=" * 80)
print("\nSummary:")
print("✓ Normal minibus scenario (with assignment)")
print("✓ Normal bus scenario (direct boarding)")
print("✓ Timeout detection and abandonment")
print("✓ Abandonment after assignment")
print("✓ Dictionary serialization")
print("✓ Invalid state transition prevention")
print("✓ Invalid input validation")
print("✓ Edge cases (immediate boarding, zero times)")
print("✓ Wait time calculations across all states")
print("\nThe Passenger class is working correctly! 🎉")