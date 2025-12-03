"""
Simple test for Event class
"""
import heapq
from event import Event


def test_basic_functionality():
    """Test basic Event functionality"""
    print("=" * 50)
    print("Test 1: Basic Event Creation")
    print("=" * 50)
    
    event1 = Event(100, Event.BUS_ARRIVAL, {"bus_id": "B1"})
    print(f"Created: {event1}")
    print(f"Time: {event1.time}")
    print(f"Type: {event1.event_type}")
    print(f"Priority: {event1.priority}")
    print(f"Data: {event1.data}")
    print()


def test_heapq_ordering():
    """Test heapq ordering with multiple events"""
    print("=" * 50)
    print("Test 2: Heapq Ordering")
    print("=" * 50)
    
    events = []
    
    # Add events in random order
    print("Adding events...")
    heapq.heappush(events, Event(100, Event.BUS_ARRIVAL, {"bus_id": "B1"}))
    print("  - Added: time=100, BUS_ARRIVAL")
    
    heapq.heappush(events, Event(100, Event.PASSENGER_APPEAR, {"passenger_id": "P1"}))
    print("  - Added: time=100, PASSENGER_APPEAR")
    
    heapq.heappush(events, Event(50, Event.MINIBUS_ARRIVAL, {"minibus_id": "M1"}))
    print("  - Added: time=50, MINIBUS_ARRIVAL")
    
    heapq.heappush(events, Event(200, Event.OPTIMIZE_CALL))
    print("  - Added: time=200, OPTIMIZE_CALL")
    
    heapq.heappush(events, Event(100, Event.MINIBUS_ARRIVAL, {"minibus_id": "M2"}))
    print("  - Added: time=100, MINIBUS_ARRIVAL")
    
    print("\nProcessing events in order:")
    while events:
        event = heapq.heappop(events)
        print(f"  -> {event}")
    print()


def test_same_time_priority():
    """Test priority ordering for same time"""
    print("=" * 50)
    print("Test 3: Same Time, Different Priorities")
    print("=" * 50)
    
    events = []
    
    # All events at time=100, different types (different priorities)
    heapq.heappush(events, Event(100, Event.OPTIMIZE_CALL))        # priority=3
    heapq.heappush(events, Event(100, Event.PASSENGER_APPEAR))     # priority=2
    heapq.heappush(events, Event(100, Event.BUS_ARRIVAL))          # priority=0
    heapq.heappush(events, Event(100, Event.MINIBUS_ARRIVAL))      # priority=1
    
    print("All events at time=100, processing by priority:")
    while events:
        event = heapq.heappop(events)
        print(f"  -> {event}")
    print()


def test_negative_time_error():
    """Test that negative time raises error"""
    print("=" * 50)
    print("Test 4: Negative Time Validation")
    print("=" * 50)
    
    try:
        event = Event(-10, Event.BUS_ARRIVAL)
        print("❌ ERROR: Should have raised ValueError!")
    except ValueError as e:
        print(f"✅ Correctly raised error: {e}")
    print()


def test_custom_priority():
    """Test custom priority override"""
    print("=" * 50)
    print("Test 5: Custom Priority")
    print("=" * 50)
    
    # Same type, but custom priority
    event1 = Event(100, Event.BUS_ARRIVAL, priority=10)
    event2 = Event(100, Event.BUS_ARRIVAL, priority=1)
    
    events = []
    heapq.heappush(events, event1)
    heapq.heappush(events, event2)
    
    print("Two BUS_ARRIVAL events with custom priorities:")
    first = heapq.heappop(events)
    print(f"  First:  {first} (priority={first.priority})")
    second = heapq.heappop(events)
    print(f"  Second: {second} (priority={second.priority})")
    print()

def test_equal_time_and_priority():
    print("=" * 50)
    print("Test: Equal Time AND Equal Priority")
    print("=" * 50)
    
    events = []
    
    # 三个完全相同时间和优先级的事件
    heapq.heappush(events, Event(100, Event.BUS_ARRIVAL, {"bus_id": "B1"}))
    heapq.heappush(events, Event(100, Event.BUS_ARRIVAL, {"bus_id": "B2"}))
    heapq.heappush(events, Event(100, Event.BUS_ARRIVAL, {"bus_id": "B3"}))
    
    print("Added 3 events: all time=100, priority=0")
    print("\nProcessing order (undefined, but works):")
    while events:
        event = heapq.heappop(events)
        print(f"  -> {event}, data={event.data}")
    
    print("\n✅ No errors! Order may vary but that's OK.")




if __name__ == "__main__":
    print("\n🚌 Testing Event Class 🚐\n")
    
    test_basic_functionality()
    test_heapq_ordering()
    test_same_time_priority()
    test_negative_time_error()
    test_custom_priority()
    test_equal_time_and_priority()
    
    print("=" * 50)
    print("✅ All tests completed!")
    print("=" * 50)