"""
Test script for TravelTimeManager

This script creates sample data and thoroughly tests all methods of the TravelTimeManager class.
"""

import os
import json
import numpy as np
import sys

# Import the TravelTimeManager (assuming it's in the same directory or adjust path)
# If the file is in network/travel_time_manager.py, uncomment the next two lines:
# sys.path.append('..')
# from network.travel_time_manager import TravelTimeManager

# For now, assuming the file is in the same directory
from travel_time_manager import TravelTimeManager


def create_test_data():
    """Create realistic test data for the TravelTimeManager"""
    print("=" * 60)
    print("Creating Test Data")
    print("=" * 60)
    
    # Parameters
    n_stations = 5
    n_time_slots = 144  # 24 hours with 10-minute slots (600 seconds each)
    
    # Station IDs
    stations = ['StationA', 'StationB', 'StationC', 'StationD', 'StationE']
    
    # Create 3D matrix: (stations, stations, time_slots)
    # We'll create realistic travel times that vary by time of day
    travel_matrix = np.zeros((n_stations, n_stations, n_time_slots))
    
    # Base travel times between stations (in seconds)
    base_times = np.array([
        [0,   600,  900,  1200, 1500],  # From StationA
        [600, 0,    450,  750,  1050],  # From StationB
        [900, 450,  0,    600,  900],   # From StationC
        [1200, 750, 600,  0,    450],   # From StationD
        [1500, 1050, 900, 450,  0]      # From StationE
    ])
    
    # Add time-of-day variations (rush hour effects)
    for t in range(n_time_slots):
        # Convert slot to hour of day
        hour = (t * 10 / 60) % 24  # 10 minutes per slot
        
        # Rush hour multiplier (morning 7-9, evening 17-19)
        if (7 <= hour < 9) or (17 <= hour < 19):
            multiplier = 1.5  # 50% slower during rush hour
        elif (12 <= hour < 14):
            multiplier = 1.2  # 20% slower during lunch
        elif (0 <= hour < 6):
            multiplier = 0.8  # 20% faster at night
        else:
            multiplier = 1.0  # Normal speed
        
        # Apply multiplier and add some random variation
        travel_matrix[:, :, t] = base_times * multiplier + np.random.uniform(-30, 30, (n_stations, n_stations))
        
        # Ensure diagonal is always 0 (same station)
        np.fill_diagonal(travel_matrix[:, :, t], 0)
        
        # Ensure no negative values
        travel_matrix[:, :, t] = np.maximum(travel_matrix[:, :, t], 0)
    
    # Create station mapping
    station_mapping = {station: idx for idx, station in enumerate(stations)}
    
    # Create metadata
    metadata = {
        'station_mapping': station_mapping,
        'time_slot_duration': 600,  # 600 seconds = 10 minutes
        'start_time': 0.0,
        'end_time': 86400.0,  # 24 hours in seconds
        'date': '2024-01-15',
        'description': 'Realistic test data with rush hour patterns',
        'note': 'All time values are in SECONDS'
    }
    
    # Create data directory if it doesn't exist
    os.makedirs('test_data', exist_ok=True)
    
    # Save files
    matrix_path = 'test_data/test_travel_time_matrix.npy'
    metadata_path = 'test_data/test_metadata.json'
    
    np.save(matrix_path, travel_matrix)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Created matrix: {matrix_path}")
    print(f"   Shape: {travel_matrix.shape}")
    print(f"   Size: {os.path.getsize(matrix_path) / 1024:.2f} KB")
    print(f"✅ Created metadata: {metadata_path}")
    print(f"   Stations: {list(station_mapping.keys())}")
    print(f"   Time slots: {n_time_slots} (24 hours)")
    print()
    
    return matrix_path, metadata_path, stations


def test_initialization(matrix_path, metadata_path):
    """Test TravelTimeManager initialization"""
    print("=" * 60)
    print("Test 1: Initialization")
    print("=" * 60)
    
    try:
        manager = TravelTimeManager(matrix_path, metadata_path)
        print("✅ Manager initialized successfully")
        print(f"   {manager}")
        print()
        return manager
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return None


def test_basic_queries(manager, stations):
    """Test basic travel time queries"""
    print("=" * 60)
    print("Test 2: Basic Travel Time Queries")
    print("=" * 60)
    
    test_cases = [
        (stations[0], stations[1], 0.0, "Start of day"),
        (stations[0], stations[1], 3600.0, "1 hour in (slot 6)"),
        (stations[0], stations[1], 28800.0, "8:00 AM - rush hour"),
        (stations[0], stations[1], 64800.0, "18:00 PM - evening rush"),
        (stations[1], stations[3], 43200.0, "Noon"),
        (stations[4], stations[2], 7200.0, "2 hours in"),
    ]
    
    all_passed = True
    for origin, dest, time, description in test_cases:
        try:
            travel_time = manager.get_travel_time(origin, dest, time)
            slot = manager.time_to_slot_index(time)
            hour = time / 3600
            print(f"✅ {description}")
            print(f"   {origin} → {dest} at t={time:.0f}s ({hour:.1f}h)")
            print(f"   Travel time: {travel_time:.1f}s ({travel_time/60:.2f} min)")
            print(f"   Time slot: {slot}")
        except Exception as e:
            print(f"❌ Failed for {origin} → {dest}: {e}")
            all_passed = False
    
    print()
    return all_passed


def test_same_station(manager, stations):
    """Test same origin and destination"""
    print("=" * 60)
    print("Test 3: Same Station (Should Return 0)")
    print("=" * 60)
    
    all_passed = True
    for station in stations:
        try:
            travel_time = manager.get_travel_time(station, station, 5000.0)
            if travel_time == 0.0:
                print(f"✅ {station} → {station}: {travel_time}s")
            else:
                print(f"❌ {station} → {station}: Expected 0, got {travel_time}s")
                all_passed = False
        except Exception as e:
            print(f"❌ Failed for {station}: {e}")
            all_passed = False
    
    print()
    return all_passed


def test_time_slot_conversion(manager):
    """Test time to slot index conversion"""
    print("=" * 60)
    print("Test 4: Time Slot Conversion")
    print("=" * 60)
    
    test_cases = [
        (0.0, 0, "Start"),
        (600.0, 1, "10 minutes"),
        (3600.0, 6, "1 hour"),
        (7200.0, 12, "2 hours"),
        (43200.0, 72, "12 hours"),
        (86400.0, 143, "24 hours (last slot)"),
        (100000.0, 143, "Beyond end (should clip to last slot)"),
    ]
    
    all_passed = True
    for time, expected_slot, description in test_cases:
        try:
            slot = manager.time_to_slot_index(time)
            if slot == expected_slot:
                print(f"✅ {description}: t={time:.0f}s → slot {slot}")
            else:
                print(f"❌ {description}: Expected slot {expected_slot}, got {slot}")
                all_passed = False
        except Exception as e:
            print(f"❌ Failed for t={time}: {e}")
            all_passed = False
    
    print()
    return all_passed


def test_station_mapping(manager, stations):
    """Test station ID to index mapping"""
    print("=" * 60)
    print("Test 5: Station Mapping")
    print("=" * 60)
    
    all_passed = True
    
    # Test get_station_index
    for idx, station in enumerate(stations):
        try:
            result_idx = manager.get_station_index(station)
            if result_idx == idx:
                print(f"✅ get_station_index('{station}') = {result_idx}")
            else:
                print(f"❌ Expected {idx}, got {result_idx}")
                all_passed = False
        except Exception as e:
            print(f"❌ Failed for '{station}': {e}")
            all_passed = False
    
    print()
    
    # Test get_station_id
    for idx, expected_station in enumerate(stations):
        try:
            station = manager.get_station_id(idx)
            if station == expected_station:
                print(f"✅ get_station_id({idx}) = '{station}'")
            else:
                print(f"❌ Expected '{expected_station}', got '{station}'")
                all_passed = False
        except Exception as e:
            print(f"❌ Failed for index {idx}: {e}")
            all_passed = False
    
    print()
    return all_passed


def test_error_handling(manager):
    """Test error handling for invalid inputs"""
    print("=" * 60)
    print("Test 6: Error Handling")
    print("=" * 60)
    
    all_passed = True
    
    # Test 1: Invalid station ID
    try:
        manager.get_station_index('InvalidStation')
        print("❌ Should have raised ValueError for invalid station")
        all_passed = False
    except ValueError as e:
        print(f"✅ Correctly raised ValueError for invalid station")
        print(f"   Error message: {str(e)[:60]}...")
    
    # Test 2: Negative time
    try:
        manager.time_to_slot_index(-100.0)
        print("❌ Should have raised ValueError for negative time")
        all_passed = False
    except ValueError as e:
        print(f"✅ Correctly raised ValueError for negative time")
        print(f"   Error message: {str(e)}")
    
    # Test 3: Invalid station index
    try:
        manager.get_station_id(999)
        print("❌ Should have raised ValueError for invalid index")
        all_passed = False
    except ValueError as e:
        print(f"✅ Correctly raised ValueError for invalid index")
        print(f"   Error message: {str(e)[:60]}...")
    
    print()
    return all_passed


def test_matrix_validation(manager):
    """Test matrix validation"""
    print("=" * 60)
    print("Test 7: Matrix Validation")
    print("=" * 60)
    
    is_valid = manager.validate_matrix()
    if is_valid:
        print("✅ Matrix validation passed all checks")
    else:
        print("❌ Matrix validation found issues")
    
    print()
    return is_valid


def test_matrix_statistics(manager):
    """Test matrix statistics"""
    print("=" * 60)
    print("Test 8: Matrix Statistics")
    print("=" * 60)
    
    try:
        stats = manager.get_matrix_stats()
        print("✅ Successfully retrieved matrix statistics:")
        print(f"   Min travel time: {stats['min']:.1f}s ({stats['min']/60:.2f} min)")
        print(f"   Max travel time: {stats['max']:.1f}s ({stats['max']/60:.2f} min)")
        print(f"   Mean travel time: {stats['mean']:.1f}s ({stats['mean']/60:.2f} min)")
        print(f"   Median travel time: {stats['median']:.1f}s ({stats['median']/60:.2f} min)")
        print(f"   Std deviation: {stats['std']:.1f}s")
        print(f"   Temporal variance (mean): {stats['temporal_variance_mean']:.1f}")
        print(f"   Temporal variance (max): {stats['temporal_variance_max']:.1f}")
        print()
        return True
    except Exception as e:
        print(f"❌ Failed to get statistics: {e}")
        print()
        return False


def test_caching_performance(manager, stations):
    """Test caching performance"""
    print("=" * 60)
    print("Test 9: Caching Performance")
    print("=" * 60)
    
    import time
    
    origin = stations[0]
    dest = stations[1]
    query_time = 5000.0
    
    # First call (not cached)
    start = time.time()
    for _ in range(1000):
        _ = manager.get_travel_time(origin, dest, query_time)
    first_duration = time.time() - start
    
    # Second call (should be cached)
    start = time.time()
    for _ in range(1000):
        _ = manager.get_travel_time(origin, dest, query_time)
    second_duration = time.time() - start
    
    print(f"✅ 1000 queries (first run): {first_duration*1000:.2f}ms")
    print(f"✅ 1000 queries (cached): {second_duration*1000:.2f}ms")
    print(f"   Speedup: {first_duration/second_duration:.1f}x")
    
    # Check cache info
    cache_info = manager.get_travel_time.cache_info()
    print(f"\n   Cache stats:")
    print(f"   Hits: {cache_info.hits}")
    print(f"   Misses: {cache_info.misses}")
    print(f"   Hit rate: {cache_info.hits/(cache_info.hits+cache_info.misses)*100:.1f}%")
    
    print()
    return True


def test_rush_hour_patterns(manager, stations):
    """Test that rush hour patterns are reflected in the data"""
    print("=" * 60)
    print("Test 10: Rush Hour Patterns")
    print("=" * 60)
    
    origin = stations[0]
    dest = stations[1]
    
    # Compare travel times at different times of day
    times_of_day = [
        (10800.0, "3:00 AM (night)"),
        (28800.0, "8:00 AM (morning rush)"),
        (43200.0, "12:00 PM (lunch)"),
        (64800.0, "18:00 PM (evening rush)"),
        (72000.0, "20:00 PM (evening)"),
    ]
    
    print(f"Travel times from {origin} to {dest}:")
    travel_times = []
    for time, description in times_of_day:
        travel_time = manager.get_travel_time(origin, dest, time)
        travel_times.append(travel_time)
        print(f"   {description:25s}: {travel_time:.1f}s ({travel_time/60:.2f} min)")
    
    # Check that rush hour times are generally higher
    night_time = travel_times[0]
    morning_rush = travel_times[1]
    evening_rush = travel_times[3]
    
    print(f"\n   Night vs Morning Rush: {morning_rush/night_time:.2f}x")
    print(f"   Night vs Evening Rush: {evening_rush/night_time:.2f}x")
    
    if morning_rush > night_time and evening_rush > night_time:
        print("✅ Rush hour patterns detected (rush times > night times)")
    else:
        print("⚠️  Rush hour patterns may not be as expected")
    
    print()
    return True


def run_all_tests():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "TRAVEL TIME MANAGER TEST SUITE" + " " * 17 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Create test data
    matrix_path, metadata_path, stations = create_test_data()
    
    # Initialize manager
    manager = test_initialization(matrix_path, metadata_path)
    if not manager:
        print("❌ Cannot continue tests - initialization failed")
        return
    
    # Run all tests
    results = []
    results.append(("Basic Queries", test_basic_queries(manager, stations)))
    results.append(("Same Station", test_same_station(manager, stations)))
    results.append(("Time Slot Conversion", test_time_slot_conversion(manager)))
    results.append(("Station Mapping", test_station_mapping(manager, stations)))
    results.append(("Error Handling", test_error_handling(manager)))
    results.append(("Matrix Validation", test_matrix_validation(manager)))
    results.append(("Matrix Statistics", test_matrix_statistics(manager)))
    results.append(("Caching Performance", test_caching_performance(manager, stations)))
    results.append(("Rush Hour Patterns", test_rush_hour_patterns(manager, stations)))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed successfully! 🎉")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    print()


if __name__ == "__main__":
    run_all_tests()