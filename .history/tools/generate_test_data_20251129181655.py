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
    """
    stations = {
        "stations": [
            {
                "station_id": "A",
                "name": "Station A",
                "location": [47.3769, 8.5417],  # Zurich HB area
                "index": 0
            },
            {
                "station_id": "B",
                "name": "Station B",
                "location": [47.3800, 8.5450],  # North of A
                "index": 1
            },
            {
                "station_id": "C",
                "name": "Station C",
                "location": [47.3830, 8.5480],  # North of B
                "index": 2
            },
            {
                "station_id": "D",
                "name": "Station D",
                "location": [47.3860, 8.5510],  # North of C
                "index": 3
            },
            {
                "station_id": "E",
                "name": "Station E",
                "location": [47.3890, 8.5540],  # North of D
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
    - BUS_2: E -> D -> C (7 minutes between stops)
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
    
    # BUS_2: E -> D -> C (starts at 08:10:00)
    route_2_stops = ['E', 'D', 'C']
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
    
    Creates a 5x5x72 matrix (5 stations, 72 time slots for 12 hours in 10-min intervals).
    Travel times are based on distance estimates with some random variation.
    
    Args:
        data_dir: Path to data directory
        num_stations: Number of stations (default 5)
    
    Returns:
        numpy array of shape (num_stations, num_stations, 72)
    """
    num_time_slots = 72  # 12 hours * 6 (10-minute intervals)
    
    # Initialize matrix
    matrix = np.zeros((num_stations, num_stations, num_time_slots))
    
    # Base travel times between adjacent stations (in minutes)
    base_time = 5
    
    for i in range(num_stations):
        for j in range(num_stations):
            if i == j:
                # Same station: 0 travel time
                matrix[i, j, :] = 0
            else:
                # Distance-based travel time (cumulative for non-adjacent stations)
                distance = abs(j - i)
                base_travel_time = distance * base_time
                
                # Add time-varying component with random variation
                for t in range(num_time_slots):
                    # Add peak hour effect (higher during rush hours)
                    hour = t // 6  # Convert time slot to hour
                    peak_factor = 1.0
                    if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
                        peak_factor = 1.3
                    
                    # Add random variation (±20%)
                    random_factor = np.random.uniform(0.8, 1.2)
                    
                    travel_time = base_travel_time * peak_factor * random_factor
                    matrix[i, j, t] = travel_time
    
    # Save matrix
    filepath = data_dir / "travel_time_matrix.npy"
    np.save(filepath, matrix)
    
    print(f"✓ Generated travel time matrix {matrix.shape}: {filepath}")
    print(f"  - Time slots: {num_time_slots} (10-minute intervals)")
    print(f"  - Sample travel times (A->D): {matrix[0, 3, :5].round(2)} minutes")
    
    return matrix


def generate_matrix_metadata(data_dir):
    """
    Generate metadata for the travel time matrix.
    
    Includes time slot duration and station ID mapping.
    """
    metadata = {
        "time_slot_duration_minutes": 10,
        "num_time_slots": 72,
        "start_time": "06:00:00",
        "end_time": "18:00:00",
        "station_id_to_index": {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
            "E": 4
        },
        "index_to_station_id": {
            "0": "A",
            "1": "B",
            "2": "C",
            "3": "D",
            "4": "E"
        }
    }
    
    filepath = data_dir / "matrix_metadata.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Generated matrix metadata: {filepath}")
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
    print("  3. travel_time_matrix.npy - 5x5x72 travel time matrix")
    print("  4. matrix_metadata.json - Matrix metadata")
    print("\nRoutes:")
    print("  - BUS_1 (Route1): A → B → C → D (5 min intervals)")
    print("  - BUS_2 (Route2): E → D → C (7 min intervals)")
    print("\nUsage:")
    print("  Load this data in your SimulationEngine for testing.")


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
        print("\n✗ Some files are missing!")
        return 1
    
    # Print summary
    print_summary(data_dir)
    
    return 0


if __name__ == "__main__":
    exit(main())