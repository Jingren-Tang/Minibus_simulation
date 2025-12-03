"""
Test script for TransitNetwork class.

This script creates mock data and tests all methods of the TransitNetwork class.
"""

import json
import os
import tempfile
import numpy as np
import logging

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_test_data():
    """Create temporary test data files."""
    temp_dir = tempfile.mkdtemp()
    
    # Create stations JSON
    stations_data = {
        "stations": [
            {
                "station_id": "A",
                "name": "Station Alpha",
                "location": [47.3769, 8.5417],  # Zurich coordinates
                "index": 0
            },
            {
                "station_id": "B",
                "name": "Station Beta",
                "location": [47.3667, 8.5500],
                "index": 1
            },
            {
                "station_id": "C",
                "name": "Station Gamma",
                "location": [47.3800, 8.5300],
                "index": 2
            },
            {
                "station_id": "D",
                "name": "Station Delta",
                "location": [47.3900, 8.5600],
                "index": 3
            },
            {
                "station_id": "E",
                "name": "Station Epsilon",
                "location": [47.3700, 8.5700],
                "index": 4
            }
        ]
    }
    
    stations_file = os.path.join(temp_dir, "stations.json")
    with open(stations_file, 'w') as f:
        json.dump(stations_data, f, indent=2)
    
    # Create travel time matrix (5x5)
    travel_time_matrix = np.array([
        [0, 120, 180, 240, 300],
        [120, 0, 150, 200, 250],
        [180, 150, 0, 160, 220],
        [240, 200, 160, 0, 180],
        [300, 250, 220, 180, 0]
    ], dtype=np.float32)
    
    matrix_file = os.path.join(temp_dir, "travel_time_matrix.npy")
    np.save(matrix_file, travel_time_matrix)
    
    # Create matrix metadata
    metadata = {
        "station_id_to_index": {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
            "E": 4
        },
        "has_time_dependent": False,
        "creation_time": "2025-01-01T00:00:00"
    }
    
    metadata_file = os.path.join(temp_dir, "matrix_metadata.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return temp_dir, stations_file, matrix_file, metadata_file


def test_transit_network():
    """Comprehensive test of TransitNetwork class."""
    
    print("=" * 70)
    print("TESTING TRANSIT NETWORK CLASS")
    print("=" * 70)
    
    # Create test data
    print("\n1. Creating test data...")
    temp_dir, stations_file, matrix_file, metadata_file = create_test_data()
    print(f"   ✓ Test data created in: {temp_dir}")
    
    # Import the actual TransitNetwork class
    # Note: Adjust the import path based on your project structure
    from network.network import TransitNetwork
    
    # Test 1: Initialize network
    print("\n2. Testing __init__ (network initialization)...")
    try:
        network = TransitNetwork(stations_file, matrix_file, metadata_file)
        print(f"   ✓ Network initialized: {network}")
        print(f"   ✓ Number of stations: {network.num_stations}")
    except Exception as e:
        print(f"   ✗ Initialization failed: {e}")
        return
    
    # Test 2: get_station
    print("\n3. Testing get_station()...")
    try:
        station_a = network.get_station("A")
        print(f"   ✓ Retrieved station A: {station_a.name}")
        print(f"   ✓ Location: {station_a.location}")
    except Exception as e:
        print(f"   ✗ get_station failed: {e}")
    
    # Test 3: get_station with invalid ID
    print("\n4. Testing get_station() with invalid ID...")
    try:
        network.get_station("Z")
        print("   ✗ Should have raised KeyError")
    except KeyError as e:
        print(f"   ✓ Correctly raised KeyError: {e}")
    
    # Test 4: __contains__
    print("\n5. Testing __contains__ (in operator)...")
    if "A" in network:
        print("   ✓ 'A' in network: True")
    else:
        print("   ✗ 'A' should be in network")
    
    if "Z" not in network:
        print("   ✓ 'Z' not in network: True")
    else:
        print("   ✗ 'Z' should not be in network")
    
    # Test 5: get_all_stations
    print("\n6. Testing get_all_stations()...")
    all_stations = network.get_all_stations()
    print(f"   ✓ Retrieved {len(all_stations)} stations")
    for station in all_stations[:3]:  # Print first 3
        print(f"      - {station.station_id}: {station.name}")
    
    # Test 6: get_station_ids
    print("\n7. Testing get_station_ids()...")
    station_ids = network.get_station_ids()
    print(f"   ✓ Station IDs: {station_ids}")
    
    # Test 7: get_travel_time
    print("\n8. Testing get_travel_time()...")
    try:
        travel_time = network.get_travel_time("A", "B", 2100.0)
        print(f"   ✓ Travel time from A to B: {travel_time} seconds")
        
        travel_time_2 = network.get_travel_time("C", "E", 3600.0)
        print(f"   ✓ Travel time from C to E: {travel_time_2} seconds")
    except Exception as e:
        print(f"   ✗ get_travel_time failed: {e}")
    
    # Test 8: get_travel_time with invalid stations
    print("\n9. Testing get_travel_time() with invalid station...")
    try:
        network.get_travel_time("A", "Z", 2100.0)
        print("   ✗ Should have raised KeyError")
    except KeyError as e:
        print(f"   ✓ Correctly raised KeyError")
    
    # Test 9: get_distance_estimate
    print("\n10. Testing get_distance_estimate()...")
    try:
        distance = network.get_distance_estimate("A", "B")
        print(f"   ✓ Estimated distance from A to B: {distance:.3f} km")
        
        distance_2 = network.get_distance_estimate("A", "E")
        print(f"   ✓ Estimated distance from A to E: {distance_2:.3f} km")
    except Exception as e:
        print(f"   ✗ get_distance_estimate failed: {e}")
    
    # Test 10: add_station
    print("\n11. Testing add_station()...")
    try:
        new_station = Station(
            station_id="F",
            name="Station Zeta",
            location=(47.3600, 8.5800),
            index=5
        )
        network.add_station(new_station)
        print(f"   ✓ Added new station: {new_station}")
        print(f"   ✓ New station count: {network.num_stations}")
    except Exception as e:
        print(f"   ✗ add_station failed: {e}")
    
    # Test 11: add_station with duplicate ID
    print("\n12. Testing add_station() with duplicate ID...")
    try:
        duplicate_station = Station(
            station_id="A",
            name="Duplicate Station",
            location=(47.0, 8.0),
            index=6
        )
        network.add_station(duplicate_station)
        print("   ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Correctly raised ValueError: {e}")
    
    # Test 12: validate_network
    print("\n13. Testing validate_network()...")
    is_valid = network.validate_network()
    if is_valid:
        print("   ✓ Network validation passed")
    else:
        print("   ✗ Network validation failed")
    
    # Test 13: get_network_info
    print("\n14. Testing get_network_info()...")
    info = network.get_network_info()
    print(f"   ✓ Network info retrieved:")
    print(f"      - Number of stations: {info['num_stations']}")
    print(f"      - Station IDs: {info['station_ids']}")
    print(f"      - Has time-dependent matrix: {info['matrix_info']['has_time_dependent']}")
    
    # Test 14: __repr__
    print("\n15. Testing __repr__()...")
    repr_str = repr(network)
    print(f"   ✓ Network representation: {repr_str}")
    
    # Summary
    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED!")
    print("=" * 70)
    print(f"\nFinal network state:")
    print(f"  - Total stations: {network.num_stations}")
    print(f"  - Station IDs: {network.get_station_ids()}")
    print(f"  - Network valid: {network.validate_network()}")
    
    # Clean up
    print(f"\n(Test data remains in: {temp_dir})")
    print("You can manually delete this directory when done.")


if __name__ == "__main__":
    test_transit_network()