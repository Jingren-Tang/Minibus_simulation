#!/usr/bin/env python3
"""
Test Data Generator for SimulationEngine

This script generates synthetic test data including:
- Station information (stations.json)
- Bus schedules (bus_schedule.csv)
- Travel time matrix (travel_time_matrix.npy)
- Matrix metadata (matrix_metadata.json)

Usage:
    python tools/generate_test_data.py
"""

import json
import csv
import os
from pathlib import Path
import numpy as np
from datetime import datetime, timedelta


def create_data_directory():
    """Create the mockdata directory if it doesn't exist."""
    data_dir = Path("mockdata")
    data_dir.mkdir(exist_ok=True)
    print(f"✓ Mock data directory ready: {data_dir.absolute()}")
    return data_dir


def generate_stations(data_dir):
    """
    Generate station information.
    
    Creates 5 test stations (A, B, C, D, E) with fictional coordinates
    around Zurich area.
    
    Note: Station format must match TransitNetwork.load_stations() expectations:
    - location: [lat, lon] array
    - index: integer index for travel time matrix
    """
    stations = {
        "stations": [
            {
                "station_id": "A",
                "name": "Station A",
                "location": [47.3769, 8.5417],
                "index": 0
            },
            {
                "station_id": "B",
                "name": "Station B",
                "location": [47.3800, 8.5450],
                "index": 1
            },
            {
                "station_id": "C",
                "name": "Station C",
                "location": [47.3830, 8.5480],
                "index": 2
            },
            {
                "station_id": "D",
                "name": "Station D",
                "location": [47.3860, 8.5510],
                "index": 3
            },
            {
                "station_id": "E",
                "name": "Station E",
                "location": [47.3890, 8.5540],
                "index": 4
            }
        ]
    }
    
    filepath = data_dir / "stations.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stations, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Generated {len(stations['stations'])} stations: {filepath}")
    return stations


def generate_bus_schedule(data_dir):
    """
    Generate bus schedule CSV.
    
    Creates 2 bus routes:
    - BUS_1: A -> B -> C -> D (5 minutes between stops)
    - BUS_2: E -> D -> C -> B (7 minutes between stops)
    """
    schedule = []
    
    # BUS_1: A -> B -> C -> D (starts at 08:00:00)
    route_1_stops = ['A', 'B', 'C', 'D']
    start_time_1 = datetime.strptime('08:00:00', '%H:%M:%S')
    interval_1 = timedelta(minutes=5)
    
    for seq, station_id in enumerate(route_1_stops):
        arrival_time = start_time_1 + (interval_1 * seq)
        schedule.append({
            'bus_id': 'BUS_1',
            'route_name': 'Route1',
            'stop_sequence': seq,
            'station_id': station_id,
            'arrival_time': arrival_time.strftime('%H:%M:%S')
        })
    
    # BUS_2: E -> D -> C -> B (starts at 08:10:00)
    route_2_stops = ['E', 'D', 'C', 'B']
    start_time_2 = datetime.strptime('08:10:00', '%H:%M:%S')
    interval_2 = timedelta(minutes=7)
    
    for seq, station_id in enumerate(route_2_stops):
        arrival_time = start_time_2 + (interval_2 * seq)
        schedule.append({
            'bus_id': 'BUS_2',
            'route_name': 'Route2',
            'stop_sequence': seq,
            'station_id': station_id,
            'arrival_time': arrival_time.strftime('%H:%M:%S')
        })
    
    # Write to CSV
    filepath = data_dir / "bus_schedule.csv"
    fieldnames = ['bus_id', 'route_name', 'stop_sequence', 'station_id', 'arrival_time']
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(schedule)
    
    print(f"✓ Generated bus schedule with {len(schedule)} stops: {filepath}")
    return schedule


def generate_travel_time_matrix(data_dir, num_stations=5):
    """
    Generate a simplified travel time matrix.
    
    Creates a 5x5x72 matrix (5 stations, 5 stations, 72 time slots).
    Time slots represent 10-minute intervals over 12 hours (06:00-18:00).
    Travel times are based on distance estimates with some time-of-day variation.
    
    Args:
        data_dir: Path to data directory
        num_stations: Number of stations (default 5)
    
    Returns:
        numpy array of shape (num_stations, num_stations, 72)
    """
    num_time_slots = 72  # 12 hours * 6 (10-minute intervals)
    
    # Initialize matrix
    matrix = np.zeros((num_stations, num_stations, num_time_slots), dtype=np.float32)
    
    # Base travel time between adjacent stations (in seconds)
    base_time = 300  # 5 minutes = 300 seconds
    
    for i in range(num_stations):
        for j in range(num_stations):
            if i == j:
                # Same station: 0 travel time
                matrix[i, j, :] = 0
            else:
                # Distance-based travel time (cumulative for non-adjacent stations)
                distance = abs(j - i)
                base_travel_time = distance * base_time
                
                # Add time-varying component for each time slot
                for t in range(num_time_slots):
                    # Calculate hour of day (starting from 6:00 AM)
                    hour = 6 + (t // 6)  # Convert time slot to hour
                    
                    # Add peak hour effect (rush hours have 20% increase)
                    peak_factor = 1.0
                    if 7 <= hour <= 9 or 17 <= hour <= 19:  # Morning and evening rush
                        peak_factor = 1.2
                    elif 12 <= hour <= 14:  # Lunch time, slight increase
                        peak_factor = 1.1
                    
                    # Calculate final travel time with peak factor
                    travel_time = base_travel_time * peak_factor
                    matrix[i, j, t] = travel_time
    
    # Save matrix
    filepath = data_dir / "travel_time_matrix.npy"
    np.save(filepath, matrix)
    
    print(f"✓ Generated travel time matrix {matrix.shape}: {filepath}")
    print(f"  - Time slots: {num_time_slots} (10-minute intervals, 06:00-18:00)")
    print(f"  - Sample travel times A->B at different hours:")
    print(f"    06:00 (slot 0): {matrix[0, 1, 0]:.0f}s")
    print(f"    08:00 (slot 12): {matrix[0, 1, 12]:.0f}s (rush hour)")
    print(f"    12:00 (slot 36): {matrix[0, 1, 36]:.0f}s (lunch)")
    print(f"    15:00 (slot 54): {matrix[0, 1, 54]:.0f}s (off-peak)")
    
    return matrix


def generate_matrix_metadata(data_dir):
    """
    Generate metadata for the travel time matrix.
    
    This metadata format matches the requirements of TravelTimeManager.
    CRITICAL: Must include 'station_mapping' field and time slot information!
    """
    metadata = {
        "station_ids": ["A", "B", "C", "D", "E"],
        "station_mapping": {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
            "E": 4
        },
        "matrix_shape": [5, 5, 72],
        "time_slot_duration_minutes": 10,
        "num_time_slots": 72,
        "start_time": "06:00:00",
        "end_time": "18:00:00",
        "description": "Travel time matrix for test simulation with time-varying travel times",
        "units": "seconds",
        "created_date": datetime.now().strftime("%Y-%m-%d"),
        "note": "Matrix includes peak hour effects (7-9 AM, 5-7 PM) with 20% increase"
    }
    
    filepath = data_dir / "matrix_metadata.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Generated matrix metadata: {filepath}")
    print(f"  - station_mapping: {metadata['station_mapping']}")
    print(f"  - Time slots: {metadata['num_time_slots']} x {metadata['time_slot_duration_minutes']} min")
    return metadata


def verify_generated_files(data_dir):
    """
    Verify that all expected files were generated successfully.
    
    Args:
        data_dir: Path to data directory
    
    Returns:
        bool: True if all files exist and are valid
    """
    required_files = [
        "stations.json",
        "bus_schedule.csv",
        "travel_time_matrix.npy",
        "matrix_metadata.json"
    ]
    
    print("\n=== Verification ===")
    all_valid = True
    
    for filename in required_files:
        filepath = data_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"✓ {filename}: {size:,} bytes")
            
            # Additional validation for metadata
            if filename == "matrix_metadata.json":
                with open(filepath, 'r') as f:
                    metadata = json.load(f)
                    if "station_mapping" in metadata:
                        print(f"  ✓ station_mapping field present")
                    else:
                        print(f"  ✗ station_mapping field MISSING!")
                        all_valid = False
            
            # Additional validation for matrix
            if filename == "travel_time_matrix.npy":
                matrix = np.load(filepath)
                print(f"  ✓ Matrix shape: {matrix.shape}")
                if matrix.shape != (5, 5, 72):
                    print(f"  ✗ Expected shape (5, 5, 72), got {matrix.shape}")
                    all_valid = False
        else:
            print(f"✗ {filename}: MISSING")
            all_valid = False
    
    return all_valid


def print_summary(data_dir):
    """Print a summary of the generated test data."""
    print("\n=== Summary ===")
    print("Generated test data files:")
    print(f"  Location: {data_dir.absolute()}")
    print("\nFiles:")
    print("  1. stations.json        - 5 test stations (A, B, C, D, E)")
    print("  2. bus_schedule.csv     - 2 bus routes with schedules")
    print("  3. travel_time_matrix.npy - 5x5x72 travel time matrix (seconds)")
    print("  4. matrix_metadata.json - Matrix metadata with station_mapping")
    print("\nStations:")
    print("  A, B, C, D, E (arranged in sequence)")
    print("\nRoutes:")
    print("  - BUS_1 (Route1): A → B → C → D (5 min intervals, starts 08:00)")
    print("  - BUS_2 (Route2): E → D → C → B (7 min intervals, starts 08:10)")
    print("\nTravel Times:")
    print("  - Adjacent stations: 300-360 seconds (5-6 minutes, time-varying)")
    print("  - Peak hours (7-9 AM, 5-7 PM): 20% increase")
    print("  - Time slots: 72 slots of 10 minutes (06:00-18:00)")
    print("\nUsage:")
    print("  python simulation/test_engine.py")


def main():
    """Main entry point for the test data generator."""
    print("=== Test Data Generator for SimulationEngine ===\n")
    
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Create data directory
    data_dir = create_data_directory()
    
    print("\n=== Generating Files ===")
    # Generate all data files
    generate_stations(data_dir)
    generate_bus_schedule(data_dir)
    generate_travel_time_matrix(data_dir)
    generate_matrix_metadata(data_dir)
    
    # Verify files
    if verify_generated_files(data_dir):
        print("\n✓ All files generated successfully!")
    else:
        print("\n✗ Some files are missing or invalid!")
        return 1
    
    # Print summary
    print_summary(data_dir)
    
    return 0


if __name__ == "__main__":
    exit(main())