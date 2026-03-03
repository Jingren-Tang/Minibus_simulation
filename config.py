
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
from typing import Dict, Any, List, Optional


# ============================================================================
# TIME SETTINGS
# ============================================================================

# Simulation start time in HH:MM:SS format
SIMULATION_START_TIME = "15:00:00"

# Simulation end time in HH:MM:SS format
SIMULATION_END_TIME = "21:00:00"  # MODIFIED: Extended to 21:00 for full 6-hour simulation

# Simulation date in YYYY-MM-DD format
SIMULATION_DATE = "2024-07-25"

PASSENGER_GENERATION_TIME_WINDOW = ("15:00:00", "20:00:00")  # 15:00 to 20:30

SAMPLING_INTERVAL = 30.0  # New: Interval (in seconds) for periodic sampling events
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

ENABLE_MINIBUS = False

# Number of minibuses in the system
NUM_MINIBUSES = 3

# Maximum passenger capacity for each minibus
MINIBUS_CAPACITY = 8

# Initial station locations for minibuses (must match station IDs)
MINIBUS_INITIAL_LOCATIONS = ["8592374", "8592374", "8592374"]  # Can also be "random"


# ============================================================================
# OPTIMIZER SETTINGS (for Phase 4)
# ============================================================================

# Time interval (in seconds) between optimizer calls
OPTIMIZATION_INTERVAL = 60

# ['dummy', 'external_program', 'python_module']
OPTIMIZER_TYPE = 'python_module'  # 'dummy' optimizer does nothing

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
PASSENGER_MAX_WAIT_TIME = 1200.0



# ============================================================================
# NEW: PASSENGER SERVICE MODE ALLOCATION SETTINGS
# ============================================================================

# NEW: Choose allocation strategy: "fixed" or "schedule"
PASSENGER_ALLOCATION_STRATEGY = "fixed"  # "fixed" or "schedule"

# NEW: Fixed ratio mode - Used when PASSENGER_ALLOCATION_STRATEGY = "fixed"
# Ratio of passengers that will use minibus service (0.0 to 1.0)
# Example: 0.3 means 30% use minibus, 70% use bus
MINIBUS_PASSENGER_RATIO = 0.0

# NEW: Schedule-based mode - Used when PASSENGER_ALLOCATION_STRATEGY = "fixed"
# Define different minibus usage ratios for different time periods
# Each period is a dictionary with:
#   - start_time: Start time in HH:MM:SS format
#   - end_time: End time in HH:MM:SS format (exclusive)
#   - ratio: Minibus usage ratio for this period (0.0 to 1.0)
# 
# Example scenario:
#   15:00-17:00 (off-peak): 20% minibus, 80% bus
#   17:00-19:00 (peak): 50% minibus, 50% bus
#   19:00-21:00 (evening): 25% minibus, 75% bus
MINIBUS_PASSENGER_RATIO_SCHEDULE = [
    {"start_time": "15:00:00", "end_time": "17:00:00", "ratio": 0.2},
    {"start_time": "17:00:00", "end_time": "19:00:00", "ratio": 0.3},
    {"start_time": "19:00:00", "end_time": "21:00:00", "ratio": 0.2}
]

# IMPORTANT NOTES:
# 1. Time periods should not overlap
# 2. Time periods should cover the entire simulation duration
# 3. If a passenger appears outside defined periods, MINIBUS_PASSENGER_RATIO will be used as default
# 4. Ratios must be between 0.0 and 1.0
# 5. start_time is inclusive, end_time is exclusive


# ============================================================================
# OUTPUT SETTINGS
# ============================================================================

# Directory where simulation results will be saved
OUTPUT_DIR = "bus_simulation_results"

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
        "bus_schedule_file": BUS_SCHEDULE_FILE,
        "sampling_interval": SAMPLING_INTERVAL, 
        
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
        "passenger_generation_time_window": PASSENGER_GENERATION_TIME_WINDOW,
        # NEW: Passenger service mode allocation settings
        "passenger_allocation_strategy": PASSENGER_ALLOCATION_STRATEGY,
        "minibus_passenger_ratio": MINIBUS_PASSENGER_RATIO,
        "minibus_passenger_ratio_schedule": MINIBUS_PASSENGER_RATIO_SCHEDULE if PASSENGER_ALLOCATION_STRATEGY == "schedule" else None,
        
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
    - NEW: Passenger allocation schedule is valid
    
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
    
    # ========================================================================
    # NEW: Validate passenger allocation settings
    # ========================================================================
    
    # Validate allocation strategy
    valid_strategies = ["fixed", "schedule"]
    if PASSENGER_ALLOCATION_STRATEGY not in valid_strategies:
        print(f"Error: PASSENGER_ALLOCATION_STRATEGY must be one of {valid_strategies}, "
              f"got '{PASSENGER_ALLOCATION_STRATEGY}'")
        valid = False
    
    # Validate fixed ratio
    if not (0.0 <= MINIBUS_PASSENGER_RATIO <= 1.0):
        print(f"Error: MINIBUS_PASSENGER_RATIO must be between 0.0 and 1.0, "
              f"got {MINIBUS_PASSENGER_RATIO}")
        valid = False
    
    # Validate schedule (if using schedule mode)
    if PASSENGER_ALLOCATION_STRATEGY == "schedule":
        if not isinstance(MINIBUS_PASSENGER_RATIO_SCHEDULE, list):
            print(f"Error: MINIBUS_PASSENGER_RATIO_SCHEDULE must be a list, "
                  f"got {type(MINIBUS_PASSENGER_RATIO_SCHEDULE)}")
            valid = False
        elif len(MINIBUS_PASSENGER_RATIO_SCHEDULE) == 0:
            print("Warning: MINIBUS_PASSENGER_RATIO_SCHEDULE is empty, will use fixed ratio")
        else:
            # Validate each period in the schedule
            for i, period in enumerate(MINIBUS_PASSENGER_RATIO_SCHEDULE):
                # Check required fields
                if not isinstance(period, dict):
                    print(f"Error: Schedule period {i} must be a dictionary, got {type(period)}")
                    valid = False
                    continue
                
                required_fields = ["start_time", "end_time", "ratio"]
                for field in required_fields:
                    if field not in period:
                        print(f"Error: Schedule period {i} missing required field '{field}'")
                        valid = False
                
                # Validate time format
                if "start_time" in period:
                    parts = period["start_time"].split(":")
                    if len(parts) != 3:
                        print(f"Error: Schedule period {i} has invalid start_time format: "
                              f"{period['start_time']} (expected HH:MM:SS)")
                        valid = False
                
                if "end_time" in period:
                    parts = period["end_time"].split(":")
                    if len(parts) != 3:
                        print(f"Error: Schedule period {i} has invalid end_time format: "
                              f"{period['end_time']} (expected HH:MM:SS)")
                        valid = False
                
                # Validate ratio range
                if "ratio" in period:
                    ratio = period["ratio"]
                    if not isinstance(ratio, (int, float)):
                        print(f"Error: Schedule period {i} ratio must be numeric, got {type(ratio)}")
                        valid = False
                    elif not (0.0 <= ratio <= 1.0):
                        print(f"Error: Schedule period {i} ratio must be between 0.0 and 1.0, "
                              f"got {ratio}")
                        valid = False
            
            # Check for overlapping periods (simplified check)
            # Parse times to seconds for comparison
            def time_to_seconds(time_str: str) -> int:
                try:
                    parts = time_str.split(":")
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                except:
                    return -1
            
            periods_with_seconds = []
            for period in MINIBUS_PASSENGER_RATIO_SCHEDULE:
                if "start_time" in period and "end_time" in period:
                    start = time_to_seconds(period["start_time"])
                    end = time_to_seconds(period["end_time"])
                    if start >= 0 and end >= 0:
                        if start >= end:
                            print(f"Warning: Period {period['start_time']}-{period['end_time']} "
                                  f"has start_time >= end_time")
                            valid = False
                        periods_with_seconds.append((start, end, period))
            
            # Check for overlaps
            for i in range(len(periods_with_seconds)):
                for j in range(i + 1, len(periods_with_seconds)):
                    start1, end1, p1 = periods_with_seconds[i]
                    start2, end2, p2 = periods_with_seconds[j]
                    
                    # Check if periods overlap
                    if not (end1 <= start2 or end2 <= start1):
                        print(f"Warning: Schedule periods overlap: "
                              f"{p1['start_time']}-{p1['end_time']} and "
                              f"{p2['start_time']}-{p2['end_time']}")
                        # This is a warning, not an error - simulation will handle it
    
    if valid:
        print("Configuration validation passed")
    else:
        print("Configuration validation failed")
    
    return valid


# ============================================================================
# CONFIGURATION TEMPLATES (for easy switching)
# ============================================================================

def get_fixed_ratio_config() -> Dict[str, Any]:
    """
    Get configuration with fixed minibus ratio (simple mode).
    
    Returns:
        Configuration dictionary with fixed 30% minibus ratio
    """
    global PASSENGER_ALLOCATION_STRATEGY, MINIBUS_PASSENGER_RATIO
    PASSENGER_ALLOCATION_STRATEGY = "fixed"
    MINIBUS_PASSENGER_RATIO = 0.05
    return get_config()


def get_schedule_based_config() -> Dict[str, Any]:
    """
    Get configuration with time-based schedule (flexible mode).
    
    Returns:
        Configuration dictionary with schedule-based allocation
    """
    global PASSENGER_ALLOCATION_STRATEGY
    PASSENGER_ALLOCATION_STRATEGY = "fixed"
    return get_config()


def print_allocation_summary():
    """
    Print a summary of the passenger allocation configuration.
    """
    print("\n" + "=" * 70)
    print("PASSENGER SERVICE MODE ALLOCATION SUMMARY")
    print("=" * 70)
    
    if PASSENGER_ALLOCATION_STRATEGY == "fixed":
        print(f"Strategy: Fixed Ratio")
        print(f"  Minibus: {MINIBUS_PASSENGER_RATIO * 100:.1f}%")
        print(f"  Bus:     {(1 - MINIBUS_PASSENGER_RATIO) * 100:.1f}%")
    
    elif PASSENGER_ALLOCATION_STRATEGY == "schedule":
        print(f"Strategy: Time-based Schedule")
        print(f"\nSchedule:")
        for i, period in enumerate(MINIBUS_PASSENGER_RATIO_SCHEDULE, 1):
            start = period.get("start_time", "?")
            end = period.get("end_time", "?")
            ratio = period.get("ratio", 0)
            print(f"  Period {i}: {start} - {end}")
            print(f"    Minibus: {ratio * 100:.1f}%")
            print(f"    Bus:     {(1 - ratio) * 100:.1f}%")
        
        print(f"\nDefault (outside schedule): {MINIBUS_PASSENGER_RATIO * 100:.1f}% minibus")
    
    else:
        print(f"Strategy: Unknown ({PASSENGER_ALLOCATION_STRATEGY})")
    
    print("=" * 70 + "\n")


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