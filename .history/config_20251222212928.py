"""
Configuration module for the mixed traffic simulation system.

This module contains all configurable parameters for the simulation,
including time settings, file paths, vehicle configurations, and optimization settings.
All parameters can be modified here without changing the core simulation code.


Config to change: SIMULATION_START_TIME, SIMULATION_END_TIME, STATIONS_FILE, TRAVEL_TIME_MATRIX_FILE,
MATRIX_METADATA_FILE, BUS_SCHEDULE_FILE(data or data)
ENABLE_MINIBUS, MINIBUS_INITIAL_LOCATIONS,
OPTIMIZER_TYPE
PASSENGER_GENERATION_METHOD: "test" or "od_matrix"

"""

import os
from typing import Dict, Any


# ============================================================================
# TIME SETTINGS
# ============================================================================

# Simulation start time in HH:MM:SS format
SIMULATION_START_TIME = "15:00:00"

# Simulation end time in HH:MM:SS format
SIMULATION_END_TIME = "16:00:00"

# Simulation date in YYYY-MM-DD format
SIMULATION_DATE = "2024-07-25"


# ============================================================================
# DATA FILE PATHS
# ============================================================================

# Path to the stations definition file (JSON format)
STATIONS_FILE = "data/stations.json"

# Path to the travel time matrix (NumPy binary format)
TRAVEL_TIME_MATRIX_FILE = "data/travel_time_matrix.npy"

# Path to the matrix metadata file (JSON format)
MATRIX_METADATA_FILE = "data/matrix_metadata.json"

# Path to the bus schedule file (CSV format)
BUS_SCHEDULE_FILE = "data/bus_schedule.csv"


# ============================================================================
# VEHICLE SETTINGS
# ============================================================================

# Number of buses in the system (loaded from CSV, this is for reference only)
NUM_BUSES = 20

# Maximum passenger capacity for each bus
BUS_CAPACITY = 80

ENABLE_MINIBUS = True

# Number of minibuses in the system
NUM_MINIBUSES = 1

# Maximum passenger capacity for each minibus
MINIBUS_CAPACITY = 6

# Initial station locations for minibuses (must match station IDs)
MINIBUS_INITIAL_LOCATIONS = ["8592374"]  # Can also be "random"


# ============================================================================
# OPTIMIZER SETTINGS (for Phase 4)
# ============================================================================

# Time interval (in seconds) between optimizer calls
OPTIMIZATION_INTERVAL = 300


OPTIMIZER_TYPE = 'dummmy'  # 'dummy' optimizer does nothing

# Configuration dictionary for the optimizer


OPTIMIZER_CONFIG = {
    'module_name': 'optimizer.greedy_insertion',  
    'function_name': 'greedy_insert_optimize',  
    'max_waiting_time': 600.0,  
    'max_detour_time': 300.0,   
}

# ============================================================================
# PASSENGER SETTINGS
# ============================================================================

# Maximum time (in seconds) a passenger will wait before abandoning the trip
# Default: 900 seconds = 15 minutes
PASSENGER_MAX_WAIT_TIME = 9000.0


# ============================================================================
# OUTPUT SETTINGS
# ============================================================================

# Directory where simulation results will be saved
OUTPUT_DIR = "data/results/"

# Name of the log file
LOG_FILE = "simulation.log"

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"

# Whether to save detailed logs (may impact performance)
SAVE_DETAILED_LOGS = True

# OD MATRIX SETTINGS
OD_MATRIX_FILE = "data/od_matrix.npy"
OD_METADATA_FILE = "data/od_metadata.json"

# Passenger generation method: "test", "od_matrix", "file"
PASSENGER_GENERATION_METHOD = "od_matrix"

# ============================================================================
# OTHER SETTINGS
# ============================================================================

# Random seed for reproducibility (set to None for non-deterministic behavior)
RANDOM_SEED = 42


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_config() -> Dict[str, Any]:
    """
    Package all configuration parameters into a dictionary.
    
    Returns:
        Dict[str, Any]: Dictionary containing all configuration parameters
    """
    config = {
        # Time settings
        "simulation_start_time": SIMULATION_START_TIME,
        "simulation_end_time": SIMULATION_END_TIME,
        "simulation_date": SIMULATION_DATE,
        
        # Data file paths
        "stations_file": STATIONS_FILE,
        "travel_time_matrix": TRAVEL_TIME_MATRIX_FILE,
        "matrix_metadata": MATRIX_METADATA_FILE,
        "bus_schedule_file": BUS_SCHEDULE_FILE,  # 改回 bus_schedule_file
        
        # Vehicle settings
        "num_buses": NUM_BUSES,
        "bus_capacity": BUS_CAPACITY,
        "enable_minibus": ENABLE_MINIBUS, 
        "num_minibuses": NUM_MINIBUSES,
        "minibus_capacity": MINIBUS_CAPACITY,
        "minibus_initial_locations": MINIBUS_INITIAL_LOCATIONS,
        
        # Optimizer settings

        "optimization_interval": OPTIMIZATION_INTERVAL,
        "optimizer_type": OPTIMIZER_TYPE,
        "optimizer_config": OPTIMIZER_CONFIG,
        
        # Passenger settings
        "passenger_max_wait_time": PASSENGER_MAX_WAIT_TIME,
        
        
        # Output settings
        "output_dir": OUTPUT_DIR,
        "log_file": LOG_FILE,
        "log_level": LOG_LEVEL,
        "save_detailed_logs": SAVE_DETAILED_LOGS,
        
        # OD matrix settings
        "od_matrix_file": OD_MATRIX_FILE,
        "od_metadata_file": OD_METADATA_FILE,
        "passenger_generation_method": PASSENGER_GENERATION_METHOD,
        
        # Other settings
        "random_seed": RANDOM_SEED
    }
    
    return config


def validate_config() -> bool:
    """
    Validate the configuration parameters.
    
    Checks:
    - Required data files exist
    - Output directory is writable
    - Parameter values are within valid ranges
    - Initial minibus locations match the number of minibuses
    
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    valid = True
    
    # Check if required data files exist
    required_files = [
        STATIONS_FILE,
        TRAVEL_TIME_MATRIX_FILE,
        MATRIX_METADATA_FILE,
        BUS_SCHEDULE_FILE
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"Warning: Required file not found: {file_path}")
            valid = False
    
    # Check if output directory exists, create if it doesn't
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            print(f"Created output directory: {OUTPUT_DIR}")
        except Exception as e:
            print(f"Error: Cannot create output directory {OUTPUT_DIR}: {e}")
            valid = False
    
    # Validate vehicle capacity values
    if BUS_CAPACITY <= 0:
        print("Error: BUS_CAPACITY must be positive")
        valid = False
    
    if MINIBUS_CAPACITY <= 0:
        print("Error: MINIBUS_CAPACITY must be positive")
        valid = False
    

    # Validate number of minibuses matches initial locations (only if it's a list)
    if isinstance(MINIBUS_INITIAL_LOCATIONS, list):
        if len(MINIBUS_INITIAL_LOCATIONS) != NUM_MINIBUSES:
            print(f"Warning: Number of initial minibus locations ({len(MINIBUS_INITIAL_LOCATIONS)}) "
                f"does not match NUM_MINIBUSES ({NUM_MINIBUSES})")
            valid = False
    elif MINIBUS_INITIAL_LOCATIONS != "random":
        print(f"Error: MINIBUS_INITIAL_LOCATIONS must be a list or 'random', "
            f"got {MINIBUS_INITIAL_LOCATIONS}")
        valid = False

    # Validate time format (basic check)
    time_fields = [SIMULATION_START_TIME, SIMULATION_END_TIME]
    for time_str in time_fields:
        parts = time_str.split(":")
        if len(parts) != 3:
            print(f"Error: Invalid time format: {time_str} (expected HH:MM:SS)")
            valid = False
    
    # Validate date format (basic check)
    date_parts = SIMULATION_DATE.split("-")
    if len(date_parts) != 3:
        print(f"Error: Invalid date format: {SIMULATION_DATE} (expected YYYY-MM-DD)")
        valid = False
    
    # Validate optimization interval
    if OPTIMIZATION_INTERVAL <= 0:
        print("Error: OPTIMIZATION_INTERVAL must be positive")
        valid = False
    
    # Validate passenger max wait time
    if PASSENGER_MAX_WAIT_TIME <= 0:
        print("Error: PASSENGER_MAX_WAIT_TIME must be positive")
        valid = False
    
    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if LOG_LEVEL not in valid_log_levels:
        print(f"Error: Invalid LOG_LEVEL: {LOG_LEVEL} (must be one of {valid_log_levels})")
        valid = False
    
    if valid:
        print("Configuration validation passed")
    else:
        print("Configuration validation failed")
    
    return valid


# ============================================================================
# MODULE TEST
# ============================================================================

if __name__ == "__main__":
    print("=== Configuration Module Test ===\n")
    
    print("Current Configuration:")
    config = get_config()
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    print("\n" + "="*50 + "\n")
    
    print("Validating configuration...")
    is_valid = validate_config()
    
    print(f"\nConfiguration is {'valid' if is_valid else 'invalid'}")