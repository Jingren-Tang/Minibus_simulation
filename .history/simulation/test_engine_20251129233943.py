"""
test_engine.py

Test script for the SimulationEngine to verify basic functionality.
Tests bus arrivals, passenger boarding, and event processing.

Prerequisites:
    Run 'python tools/generate_test_data.py' first to create test data.
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


def check_test_data_exists():
    """
    Check if all required test data files exist.
    
    Returns:
        bool: True if all files exist, False otherwise
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    required_files = [
        os.path.join(project_root, "mockdata/stations.json"),
        os.path.join(project_root, "mockdata/travel_time_matrix.npy"),
        os.path.join(project_root, "mockdata/matrix_metadata.json"),
        os.path.join(project_root, "mockdata/bus_schedule.csv")
    ]
    
    missing_files = []
    for filepath in required_files:
        if not os.path.exists(filepath):
            missing_files.append(filepath)
    
    if missing_files:
        logger.error("=" * 80)
        logger.error("MISSING TEST DATA FILES")
        logger.error("=" * 80)
        logger.error("The following required files are missing:")
        for filepath in missing_files:
            logger.error(f"  ✗ {filepath}")
        logger.error("\nPlease run the following command first:")
        logger.error("  python tools/generate_test_data.py")
        logger.error("=" * 80)
        return False
    
    logger.info("✓ All required test data files found")
    return True


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
        
        # Data files (relative to project root)
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
                f"capacity {bus.capacity}"
            )
        
        # Print passenger details
        if engine.all_passengers:
            logger.info("\nTest Passengers:")
            for pax_id, pax in engine.all_passengers.items():
                logger.info(
                    f"  {pax_id}: {pax.origin_station_id} -> {pax.destination_station_id}, "
                    f"appears at {pax.appear_time}s"
                )
        else:
            logger.info("\nNo test passengers (will be added during simulation)")
        
        # Print first few events
        logger.info("\nFirst 10 Events in Queue:")
        sorted_events = sorted(engine.event_queue[:min(10, len(engine.event_queue))])
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
        if engine.all_passengers:
            logger.info("\nPassenger States:")
            for pax_id, pax in engine.all_passengers.items():
                wait_time = (pax.pickup_time - pax.appear_time) if pax.pickup_time else None
                travel_time = (pax.arrival_time - pax.pickup_time) if (pax.arrival_time and pax.pickup_time) else None
                logger.info(
                    f"  {pax_id}: Status={pax.status}, "
                    f"Wait time={wait_time if wait_time else 'N/A'}s, "
                    f"Travel time={travel_time if travel_time else 'N/A'}s"
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
        if total_pax > 0:
            arrived_pax = sum(1 for p in engine.all_passengers.values() if p.status == "ARRIVED")
            success_rate = (arrived_pax / total_pax * 100)
        else:
            arrived_pax = 0
            success_rate = 0
        
        logger.info("\n" + "=" * 80)
        logger.info("TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total passengers: {total_pax}")
        logger.info(f"Successfully arrived: {arrived_pax}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info("=" * 80)
        
        if total_pax == 0:
            logger.info("✓ TEST PASSED: Simulation ran without errors (no passengers to transport)")
        elif success_rate > 0:
            logger.info("✓ TEST PASSED: At least some passengers were successfully transported")
        else:
            logger.warning("⚠ TEST WARNING: No passengers successfully transported")
        
        return engine
    
    except FileNotFoundError as e:
        logger.error(f"✗ TEST FAILED: Required data file not found: {e}")
        logger.error("\nPlease run the following command first:")
        logger.error("  python tools/generate_test_data.py")
        raise
    
    except Exception as e:
        logger.error(f"✗ TEST FAILED with exception: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Check if test data exists before running
    if not check_test_data_exists():
        logger.error("\n" + "=" * 80)
        logger.error("TESTS ABORTED - Missing test data")
        logger.error("=" * 80)
        exit(1)
    
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