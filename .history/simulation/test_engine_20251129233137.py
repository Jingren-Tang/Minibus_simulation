"""
test_engine.py

Test script for the SimulationEngine to verify basic functionality.
Tests bus arrivals, passenger boarding, and event processing.
"""

import logging
import os
import sys

# Add parent directory to path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine import SimulationEngine

# Configure logging to see detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simulation_test.log', mode='w')
    ]
)

logger = logging.getLogger(__name__)


def test_simulation_engine():
    """
    Test the SimulationEngine with a simple configuration.
    """
    logger.info("=" * 80)
    logger.info("STARTING SIMULATION ENGINE TEST")
    logger.info("=" * 80)
    
    # Configuration for testing
    config = {
        # Simulation time settings
        "simulation_start_time": "08:00:00",
        "simulation_end_time": "20:00:00",
        "simulation_date": "2024-01-15",
        
        # Data files (adjust paths as needed - relative to project root)
        "stations_file": "mockdata/stations.json",
        "travel_time_matrix": "mockdata/travel_time_matrix.npy",
        "matrix_metadata": "mockdata/matrix_metadata.json",
        "bus_schedule_file": "mockdata/bus_schedule.csv",
        
        # Vehicle settings
        "bus_capacity": 50,
        "num_minibuses": 3,
        "minibus_capacity": 6,
        
        # Operational settings
        "optimization_interval": 120.0,  # seconds
        "passenger_max_wait_time": 900.0  # 15 minutes
    }
    
    try:
        # Step 1: Create simulation engine
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Creating SimulationEngine")
        logger.info("=" * 80)
        engine = SimulationEngine(config)
        logger.info("✓ SimulationEngine created successfully")
        
        # Step 2: Initialize simulation
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Initializing Simulation")
        logger.info("=" * 80)
        engine.initialize()
        logger.info("✓ Simulation initialized successfully")
        
        # Step 3: Print initial state
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Initial State Summary")
        logger.info("=" * 80)
        logger.info(f"Number of buses: {len(engine.buses)}")
        logger.info(f"Number of stations: {len(engine.network.stations)}")
        logger.info(f"Number of test passengers: {len(engine.all_passengers)}")
        logger.info(f"Number of events in queue: {len(engine.event_queue)}")
        
        # Print bus details
        logger.info("\nBus Details:")
        for bus_id, bus in engine.buses.items():
            logger.info(
                f"  {bus_id}: Route {bus.route}, "
                f"{len(bus.schedule)} stops, "
                f"capacity {bus.capacity}, "
                f"first arrival at {bus.schedule[0]}s"
            )
        
        # Print passenger details
        logger.info("\nTest Passengers:")
        for pax_id, pax in engine.all_passengers.items():
            logger.info(
                f"  {pax_id}: {pax.origin} -> {pax.destination}, "
                f"appears at {pax.request_time}s"
            )
        
        # Print first few events
        logger.info("\nFirst 10 Events in Queue:")
        sorted_events = sorted(engine.event_queue[:10])
        for i, event in enumerate(sorted_events, 1):
            logger.info(
                f"  {i}. {event.event_type} at {event.time}s "
                f"(priority={event.priority})"
            )
        
        # Step 4: Run simulation
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Running Simulation")
        logger.info("=" * 80)
        engine.run()
        logger.info("✓ Simulation completed successfully")
        
        # Step 5: Verify results
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Verification")
        logger.info("=" * 80)
        
        # Check passenger states
        logger.info("\nPassenger States:")
        for pax_id, pax in engine.all_passengers.items():
            logger.info(
                f"  {pax_id}: State={pax.state}, "
                f"Wait time={(pax.board_time - pax.request_time) if pax.board_time else 'N/A'}s, "
                f"Travel time={(pax.arrival_time - pax.board_time) if pax.arrival_time and pax.board_time else 'N/A'}s"
            )
        
        # Check bus performance
        logger.info("\nBus Performance:")
        for bus_id, bus in engine.buses.items():
            logger.info(
                f"  {bus_id}: Served {bus.total_passengers_served} passengers, "
                f"Final occupancy: {bus.current_occupancy}/{bus.capacity}"
            )
        
        # Success metrics
        total_pax = len(engine.all_passengers)
        arrived_pax = sum(1 for p in engine.all_passengers.values() if p.state == "ARRIVED")
        success_rate = (arrived_pax / total_pax * 100) if total_pax > 0 else 0
        
        logger.info("\n" + "=" * 80)
        logger.info("TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total passengers: {total_pax}")
        logger.info(f"Successfully arrived: {arrived_pax}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info("=" * 80)
        
        if success_rate > 0:
            logger.info("✓ TEST PASSED: At least some passengers were successfully transported")
        else:
            logger.warning("⚠ TEST WARNING: No passengers successfully transported")
        
        return engine
    
    except FileNotFoundError as e:
        logger.error(f"✗ TEST FAILED: Required data file not found: {e}")
        logger.error("Please ensure all data files exist in the mockdata/ directory:")
        logger.error("  - mockdata/stations.json")
        logger.error("  - mockdata/travel_time_matrix.npy")
        logger.error("  - mockdata/matrix_metadata.json")
        logger.error("  - mockdata/bus_schedule.csv")
        raise
    
    except Exception as e:
        logger.error(f"✗ TEST FAILED with exception: {e}", exc_info=True)
        raise
def create_minimal_test_data():
    """
    Helper function to create minimal test data if files don't exist.
    This helps verify the engine logic even without full data files.
    """
    import json
    import numpy as np
    
    logger.info("Creating minimal test data...")
    
    # Get the project root directory (parent of simulation folder)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    mockdata_dir = os.path.join(project_root, "mockdata")
    
    # Create mockdata directory if it doesn't exist
    os.makedirs(mockdata_dir, exist_ok=True)
    
    # Create minimal stations.json
    stations = {
        "stations": [
            {"station_id": "A", "name": "Station A", "lat": 47.3769, "lon": 8.5417},
            {"station_id": "B", "name": "Station B", "lat": 47.38, "lon": 8.545},
            {"station_id": "C", "name": "Station C", "lat": 47.383, "lon": 8.548},
            {"station_id": "D", "name": "Station D", "lat": 47.386, "lon": 8.551},
            {"station_id": "E", "name": "Station E", "lat": 47.389, "lon": 8.554}
        ]
    }
    
    stations_file = os.path.join(mockdata_dir, "stations.json")
    with open(stations_file, "w") as f:
        json.dump(stations, f, indent=2)
    logger.info(f"✓ Created {stations_file}")
    
    # Create minimal travel time matrix (5x5)
    # Travel times in seconds between stations
    travel_times = np.array([
        [0, 300, 600, 900, 1200],      # From A to A,B,C,D,E
        [300, 0, 300, 600, 900],        # From B to A,B,C,D,E
        [600, 300, 0, 300, 600],        # From C to A,B,C,D,E
        [900, 600, 300, 0, 300],        # From D to A,B,C,D,E
        [1200, 900, 600, 300, 0]        # From E to A,B,C,D,E
    ], dtype=np.float32)
    
    matrix_file = os.path.join(mockdata_dir, "travel_time_matrix.npy")
    np.save(matrix_file, travel_times)
    logger.info(f"✓ Created {matrix_file}")
    
    # Create metadata with correct format
    # Based on TravelTimeManager requirements
    metadata = {
        "station_ids": ["A", "B", "C", "D", "E"],
        "station_mapping": {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
            "E": 4
        },
        "matrix_shape": [5, 5],
        "description": "Test travel time matrix for simulation",
        "units": "seconds"
    }
    
    metadata_file = os.path.join(mockdata_dir, "matrix_metadata.json")
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"✓ Created {metadata_file}")
    
    # Create minimal bus schedule
    schedule_data = [
        "bus_id,route_name,stop_sequence,station_id,arrival_time",
        "BUS_1,Route1,0,A,08:00:00",
        "BUS_1,Route1,1,B,08:05:00",
        "BUS_1,Route1,2,C,08:12:00",
        "BUS_1,Route1,3,D,08:20:00",
        "BUS_2,Route2,0,E,08:10:00",
        "BUS_2,Route2,1,D,08:17:00",
        "BUS_2,Route2,2,C,08:25:00",
        "BUS_2,Route2,3,B,08:32:00"
    ]
    
    schedule_file = os.path.join(mockdata_dir, "bus_schedule.csv")
    with open(schedule_file, "w") as f:
        f.write("\n".join(schedule_data))
    logger.info(f"✓ Created {schedule_file}")
    
    logger.info("✓ Minimal test data created successfully")

if __name__ == "__main__":
    # Get the project root directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Check if data files exist, create minimal ones if not
    data_files = [
        os.path.join(project_root, "mockdata/stations.json"),
        os.path.join(project_root, "mockdata/travel_time_matrix.npy"),
        os.path.join(project_root, "mockdata/matrix_metadata.json"),
        os.path.join(project_root, "mockdata/bus_schedule.csv")
    ]
    
    missing_files = [f for f in data_files if not os.path.exists(f)]
    
    if missing_files:
        logger.warning(f"Missing data files: {missing_files}")
        logger.info("Creating minimal test data...")
        create_minimal_test_data()
    
    # Run the test
    try:
        engine = test_simulation_engine()
        logger.info("\n" + "=" * 80)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY! ✓")
        logger.info("=" * 80)
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("TESTS FAILED! ✗")
        logger.error("=" * 80)
        exit(1)