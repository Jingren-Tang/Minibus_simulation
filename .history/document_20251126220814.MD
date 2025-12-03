# Transit Simulation System - Complete Development Guide

## Project Overview

This is a mixed transit simulation system featuring:

- **Fixed-route buses** with real schedule data
- **Flexible minibuses** that provide on-demand service
- **External route optimizer** for minibus route planning
- **Pre-computed travel time matrix** from Google Maps API

## System Architecture

```
transit_simulation/
│
├── main.py                          # Main entry point
├── config.py                        # Configuration parameters
├── requirements.txt                 # Python dependencies
│
├── network/                         # Transportation Network Layer
│   ├── __init__.py
│   ├── network.py                   # TransitNetwork class
│   ├── station.py                   # Station class
│   └── travel_time_manager.py      # Travel time matrix manager
│
├── vehicles/                        # Vehicle Management Layer
│   ├── __init__.py
│   ├── bus.py                      # Bus class
│   └── minibus.py                  # Minibus class
│
├── demand/                          # Demand Generation Layer
│   ├── __init__.py
│   ├── passenger.py                # Passenger class
│   └── demand_generator.py         # Demand generation logic
│
├── optimizer/                       # Optimization Decision Layer
│   ├── __init__.py
│   └── route_optimizer.py          # Interface to external optimizer
│
├── simulation/                      # Simulation Engine Layer
│   ├── __init__.py
│   ├── engine.py                   # SimulationEngine class
│   └── event.py                    # Event class
│
├── utils/                           # Utilities
│   ├── __init__.py
│   ├── google_maps_loader.py       # One-time Google Maps API call
│   └── statistics.py               # Statistics collection
│
└── data/                            # Data files
    ├── stations.json               # Station locations and info
    ├── bus_schedule.csv            # Bus timetable
    ├── travel_time_matrix.npy      # Pre-computed 3D travel time matrix
    └── results/                    # Simulation output folder
```

---

## Travel Time Matrix Design

### Matrix Structure

```python
# 3D numpy array: [station_i, station_j, time_slot]
# Dimensions:
#   - station_i: origin station index (0 to N-1)
#   - station_j: destination station index (0 to N-1)
#   - time_slot: time period index (0 to M-1)
#     where M = simulation_duration_minutes / 10

# Example: For 5 stations, 12-hour simulation (8:00-20:00):
# Shape: (5, 5, 72)
# travel_time_matrix[0, 3, 15] = travel time from station 0 to station 3
#                                  at time slot 15 (10:30-10:40)
```

### Time Slot Calculation

```python
# Given a simulation time (e.g., "08:35:00"):
# 1. Calculate minutes from simulation start: 35 minutes
# 2. Time slot index = 35 // 10 = 3
# 3. Look up: travel_time_matrix[origin_idx, dest_idx, 3]
```

### Benefits of This Design

- **No real-time API calls** during simulation (fast and cost-free)
- **Time-varying traffic** captured in 10-minute granularity
- **Simple lookup** using numpy indexing
- **Easy to extend** to different time granularities

---

## Core Components Specification

### 1. Event Class (`simulation/event.py`)

**Purpose:** Represents discrete events in the simulation

**Attributes:**

- `time` (float or datetime): When the event occurs
- `event_type` (str): Type of event (e.g., "BUS_ARRIVAL", "PASSENGER_APPEAR")
- `priority` (int): Priority for events at the same time (lower = higher priority)
- `data` (dict): Event-specific data

**Methods:**

- `__init__(time, event_type, data, priority=0)`
- `__lt__(other)`: Comparison for priority queue sorting
- `__repr__()`: String representation

**Event Types:**

- `"BUS_ARRIVAL"`: Bus arrives at a station
- `"MINIBUS_ARRIVAL"`: Minibus arrives at a station
- `"PASSENGER_APPEAR"`: New passenger request appears
- `"OPTIMIZE_CALL"`: Time to call the route optimizer
- `"SIMULATION_END"`: End of simulation

---

### 2. Station Class (`network/station.py`)

**Purpose:** Represents a transit station/stop

**Attributes:**

- `station_id` (str): Unique identifier (e.g., "A", "B", "C")
- `name` (str): Human-readable name
- `location` (tuple): (latitude, longitude)
- `index` (int): Index in the travel time matrix
- `waiting_passengers` (list): List of Passenger objects waiting here

**Methods:**

- `__init__(station_id, name, location, index)`
- `add_waiting_passenger(passenger)`: Add passenger to waiting list
- `remove_waiting_passenger(passenger)`: Remove passenger (when they board)
- `get_waiting_passengers()`: Return list of waiting passengers
- `__repr__()`: String representation

---

### 3. Travel Time Manager Class (`network/travel_time_manager.py`)

**Purpose:** Manages the 3D travel time matrix and provides time lookups

**Attributes:**

- `travel_time_matrix` (numpy array): 3D matrix [origin, dest, time_slot]
- `station_index_map` (dict): Maps station_id to matrix index
- `time_slot_duration` (int): Duration of each time slot in minutes (default: 10)
- `simulation_start_time` (datetime): Simulation start time

**Methods:**

- `__init__(matrix_file_path, station_mapping, start_time, slot_duration=10)`
- `load_matrix(file_path)`: Load pre-computed matrix from file
- `get_travel_time(origin_id, dest_id, current_time)`:
  - Convert current_time to time_slot index
  - Look up travel time from matrix
  - Return travel time in seconds
- `time_to_slot_index(current_time)`: Convert timestamp to slot index
- `save_matrix(file_path)`: Save matrix to file

---

### 4. Transit Network Class (`network/network.py`)

**Purpose:** Manages the overall transportation network

**Attributes:**

- `stations` (dict): {station_id: Station object}
- `travel_time_manager` (TravelTimeManager): Travel time lookup manager
- `station_list` (list): Ordered list of station IDs

**Methods:**

- `__init__(stations_data, travel_time_matrix_path, simulation_start_time)`
- `add_station(station)`: Add a station to the network
- `get_station(station_id)`: Retrieve a station by ID
- `get_travel_time(origin_id, dest_id, current_time)`:
  - Delegate to travel_time_manager
- `get_all_stations()`: Return list of all stations
- `load_from_file(file_path)`: Load network from JSON file

---

### 5. Passenger Class (`demand/passenger.py`)

**Purpose:** Represents a passenger demand/request

**Attributes:**

- `passenger_id` (str): Unique identifier
- `origin_station_id` (str): Starting station
- `destination_station_id` (str): Target station
- `appear_time` (float): When passenger appears in simulation
- `max_wait_time` (float): Maximum willing to wait (seconds)
- `status` (str): Current status
  - `"WAITING"`: Waiting at station
  - `"ASSIGNED"`: Assigned to a vehicle
  - `"ONBOARD"`: On vehicle
  - `"ARRIVED"`: Reached destination
  - `"ABANDONED"`: Left due to timeout
- `assigned_vehicle_id` (str): ID of assigned vehicle (if any)
- `pickup_time` (float): When passenger boarded (None if not yet)
- `arrival_time` (float): When passenger arrived at destination (None if not yet)

**Methods:**

- `__init__(passenger_id, origin, destination, appear_time, max_wait_time)`
- `assign_to_vehicle(vehicle_id, current_time)`: Mark as assigned
- `board_vehicle(current_time)`: Mark as onboard
- `arrive_at_destination(current_time)`: Mark as arrived
- `check_timeout(current_time)`: Check if wait time exceeded, mark as abandoned if so
- `get_wait_time(current_time)`: Calculate current wait time
- `get_travel_time()`: Calculate total travel time (if arrived)
- `__repr__()`: String representation

---

### 6. Bus Class (`vehicles/bus.py`)

**Purpose:** Represents a fixed-route bus with predetermined schedule

**Attributes:**

- `bus_id` (str): Unique identifier
- `route` (list): Ordered list of station IDs
- `schedule` (dict): {station_id: arrival_time} for each stop
- `capacity` (int): Maximum passenger capacity
- `current_route_index` (int): Current position in route
- `passengers` (list): List of Passenger objects onboard
- `next_station_id` (str): ID of next station
- `next_arrival_time` (float): When bus will arrive at next station

**Methods:**

- `__init__(bus_id, route, schedule, capacity)`
- `get_next_station()`: Return next station ID and arrival time
- `arrive_at_station(station, current_time)`:
  - Alight passengers whose destination is this station
  - Board waiting passengers (up to capacity)
  - Update current_route_index
  - Return lists of boarded and alighted passengers
- `can_board_passenger(passenger)`: Check if passenger's destination is on route
- `is_full()`: Check if bus is at capacity
- `get_occupancy()`: Return current passenger count
- `__repr__()`: String representation

---

### 7. Minibus Class (`vehicles/minibus.py`)

**Purpose:** Represents a flexible-route minibus with dynamic routing

**Attributes:**

- `minibus_id` (str): Unique identifier
- `capacity` (int): Maximum passenger capacity
- `current_location_id` (str): Current station ID
- `passengers` (list): List of Passenger objects onboard
- `route_plan` (list): Ordered list of planned stops
  - Each stop: {"station_id": str, "action": "PICKUP"/"DROPOFF", "passenger_ids": list}
- `status` (str): Current status
  - `"IDLE"`: No assigned tasks
  - `"EN_ROUTE"`: Traveling to next stop
  - `"SERVING"`: At station, picking up/dropping off passengers
- `next_station_id` (str): ID of next station (None if idle)
- `next_arrival_time` (float): When minibus will arrive at next station (None if idle)

**Methods:**

- `__init__(minibus_id, capacity, initial_location)`
- `update_route_plan(new_plan, network, current_time)`:
  - Replace current route_plan with new plan from optimizer
  - Calculate next_arrival_time using travel time matrix
- `arrive_at_station(station, current_time)`:
  - Execute current stop's actions (pickup/dropoff)
  - Remove completed stop from route_plan
  - Update next_station and next_arrival_time
  - Return lists of boarded and alighted passengers
- `is_available()`: Check if minibus can accept new assignments
- `is_full()`: Check if at capacity
- `get_occupancy()`: Return current passenger count
- `get_assigned_passenger_ids()`: Return IDs of all passengers in route_plan
- `__repr__()`: String representation

---

### 8. Route Optimizer Interface (`optimizer/route_optimizer.py`)

**Purpose:** Interface to communicate with external optimization algorithm

**Attributes:**

- `optimizer_type` (str): Type of optimizer ("external_program", "python_module", "api")
- `optimizer_config` (dict): Configuration for optimizer communication

**Methods:**

- `__init__(optimizer_type, config)`
- `optimize(pending_requests, minibus_states, network, current_time)`:
  - **Input:**
    - `pending_requests`: List of unassigned Passenger objects
    - `minibus_states`: List of dicts with minibus current state
      ```python
      {
          "minibus_id": str,
          "current_location": str,
          "passengers_onboard": [passenger_ids],
          "capacity": int,
          "current_occupancy": int,
          "current_route_plan": [...]
      }
      ```
    - `network`: TransitNetwork object for station info
    - `current_time`: Current simulation time
  - **Output:**
    - Dict mapping minibus_id to new route_plan
      ```python
      {
          "minibus_1": [
              {"station_id": "A", "action": "PICKUP", "passenger_ids": ["P1", "P2"]},
              {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["P1"]},
              {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P2"]}
          ],
          "minibus_2": [...]
      }
      ```
- `_call_external_program(input_data)`: For external optimizer
- `_call_python_module(input_data)`: For Python-based optimizer
- `_call_api(input_data)`: For API-based optimizer
- `prepare_input(...)`: Format data for optimizer
- `parse_output(optimizer_result)`: Parse optimizer response

---

### 9. Demand Generator Class (`demand/demand_generator.py`)

**Purpose:** Generates passenger requests during simulation

**Attributes:**

- `generation_mode` (str): "RANDOM", "POISSON", "FILE"
- `parameters` (dict): Generation parameters
- `historical_data` (list): Pre-loaded passenger data (if FILE mode)

**Methods:**

- `__init__(mode, parameters)`
- `generate_initial_events(simulation_start, simulation_end)`:
  - Generate all passenger appearance events for entire simulation
  - Return list of Event objects with type "PASSENGER_APPEAR"
- `generate_random_passenger(current_time)`: Create a random passenger
- `load_from_file(file_path)`: Load historical demand data

**Generation Modes:**

- **RANDOM**: Uniform random generation
  - Parameters: `rate` (passengers per minute), `station_list`
- **POISSON**: Poisson process generation
  - Parameters: `lambda_rate`, `peak_hours`, `station_list`
- **FILE**: Replay historical data
  - Parameters: `data_file_path`

---

### 10. Simulation Engine Class (`simulation/engine.py`)

**Purpose:** Core simulation engine that drives the entire simulation

**Attributes:**

- `current_time` (float): Current simulation time (seconds from start)
- `simulation_start_time` (datetime): Real start time
- `simulation_end_time` (datetime): Real end time
- `event_queue` (list): Priority queue of Event objects (using heapq)
- `network` (TransitNetwork): Transportation network
- `buses` (list): List of Bus objects
- `minibuses` (list): List of Minibus objects
- `all_passengers` (dict): {passenger_id: Passenger object} - all passengers
- `pending_requests` (list): Unassigned Passenger objects
- `optimizer` (RouteOptimizer): Route optimization interface
- `statistics` (Statistics): Statistics collector
- `optimization_interval` (float): How often to call optimizer (seconds)
- `last_optimization_time` (float): Last time optimizer was called

**Methods:**

- `__init__(config)`
- `initialize()`:
  - Load network
  - Create vehicles
  - Initialize demand generator
  - Schedule initial bus events (from timetable)
  - Schedule passenger appearance events
  - Schedule first optimization call
- `run()`:
  - Main simulation loop
  - Process events until queue is empty or end time reached
- `add_event(event)`: Add event to priority queue
- `process_event(event)`: Dispatch event to appropriate handler
- `handle_bus_arrival(event)`: Handle bus arrival at station
- `handle_minibus_arrival(event)`: Handle minibus arrival at station
- `handle_passenger_appear(event)`: Handle new passenger request
- `handle_optimization_call(event)`: Call optimizer and update minibus routes
- `check_passenger_timeouts()`: Check if any waiting passengers exceeded max wait time
- `finalize()`: Clean up and generate final statistics

**Event Handling Flow:**

```python
while event_queue is not empty and current_time < end_time:
    event = pop earliest event from queue
    current_time = event.time

    if event.type == "BUS_ARRIVAL":
        handle_bus_arrival(event)
        schedule next bus arrival

    elif event.type == "MINIBUS_ARRIVAL":
        handle_minibus_arrival(event)
        schedule next minibus arrival (if route_plan not empty)

    elif event.type == "PASSENGER_APPEAR":
        handle_passenger_appear(event)
        add to pending_requests

    elif event.type == "OPTIMIZE_CALL":
        handle_optimization_call(event)
        update all minibus route plans
        schedule next optimization call

    check_passenger_timeouts()
    update_statistics()
```

---

### 11. Statistics Collector Class (`utils/statistics.py`)

**Purpose:** Collect, analyze, and report simulation performance metrics

**Attributes:**

- `passenger_records` (list): Detailed records for each passenger
- `vehicle_logs` (dict): {vehicle_id: log_entries} for each vehicle
- `system_metrics` (dict): System-level aggregated metrics
- `time_series_data` (dict): Time-series metrics for plotting

**Methods:**

- `__init__()`
- `record_passenger_event(passenger, event_type, current_time)`: Log passenger event
- `record_vehicle_event(vehicle, event_type, current_time, details)`: Log vehicle event
- `calculate_metrics()`: Compute all statistics
  - Average wait time
  - Average travel time
  - Service rate (% of passengers served)
  - Abandonment rate
  - Vehicle utilization (average occupancy)
  - Empty distance ratio
- `generate_report()`: Create comprehensive simulation report
- `export_to_csv(output_dir)`: Export detailed data to CSV files
- `plot_metrics(output_dir)`: Generate visualization plots

**Metrics Tracked:**

- **Passenger Metrics:**
  - Wait time distribution
  - Travel time distribution
  - Service rate by time of day
- **Vehicle Metrics:**
  - Occupancy rate over time
  - Distance traveled
  - Number of passengers served
  - Idle time percentage
- **System Metrics:**
  - Total passengers served
  - Total passengers abandoned
  - System efficiency score

---

### 12. Google Maps Loader (`utils/google_maps_loader.py`)

**Purpose:** One-time loading and pre-computation of travel time matrix

**Methods:**

- `load_stations(stations_file)`: Load station locations
- `generate_time_slots(start_time, end_time, slot_duration=10)`:
  - Create list of time periods for the simulation
- `query_google_maps(origin_coords, dest_coords, departure_time)`:
  - Call Google Maps Distance Matrix API
  - Return travel time in seconds
- `build_travel_time_matrix(stations, time_slots, api_key)`:
  - For each time slot:
    - For each origin-destination pair:
      - Query Google Maps API
      - Store result in matrix
  - Return 3D numpy array
- `save_matrix(matrix, station_mapping, output_path)`:
  - Save matrix and metadata to file
- `main()`: Command-line script to generate matrix

**Usage:**

```bash
python utils/google_maps_loader.py \
  --stations data/stations.json \
  --start-time "08:00:00" \
  --end-time "20:00:00" \
  --slot-duration 10 \
  --api-key YOUR_API_KEY \
  --output data/travel_time_matrix.npy
```

---

## Configuration File (`config.py`)

```python
# Simulation time settings
SIMULATION_START_TIME = "08:00:00"  # HH:MM:SS
SIMULATION_END_TIME = "20:00:00"
SIMULATION_DATE = "2024-01-15"  # YYYY-MM-DD

# Network settings
STATIONS_FILE = "data/stations.json"
TRAVEL_TIME_MATRIX_FILE = "data/travel_time_matrix.npy"
TIME_SLOT_DURATION = 10  # minutes

# Vehicle settings
NUM_BUSES = 2
BUS_CAPACITY = 40
BUS_SCHEDULE_FILE = "data/bus_schedule.csv"

NUM_MINIBUSES = 3
MINIBUS_CAPACITY = 6
MINIBUS_INITIAL_LOCATIONS = ["A", "C", "E"]  # Starting positions

# Optimization settings
OPTIMIZER_TYPE = "external_program"  # or "python_module", "api"
OPTIMIZER_CONFIG = {
    "program_path": "./optimizer/solve.py",
    "input_file": "temp/optimizer_input.json",
    "output_file": "temp/optimizer_output.json"
}
OPTIMIZATION_INTERVAL = 120  # seconds (call optimizer every 2 minutes)

# Demand generation settings
DEMAND_MODE = "POISSON"  # or "RANDOM", "FILE"
DEMAND_PARAMETERS = {
    "lambda_rate": 0.5,  # passengers per minute on average
    "peak_hours": [(8, 9), (17, 18)],  # (start_hour, end_hour)
    "peak_multiplier": 2.0
}

# Passenger settings
PASSENGER_MAX_WAIT_TIME = 900  # seconds (15 minutes)

# Output settings
OUTPUT_DIR = "data/results/"
SAVE_DETAILED_LOGS = True
GENERATE_PLOTS = True

# Google Maps API (for initial matrix generation only)
GOOGLE_MAPS_API_KEY = "your_api_key_here"
```

---

## Data File Formats

### stations.json

```json
{
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
      "location": [47.38, 8.545],
      "index": 1
    }
  ]
}
```

### bus_schedule.csv

```csv
bus_id,route,stop_sequence,station_id,arrival_time
BUS_1,Route1,0,A,08:00:00
BUS_1,Route1,1,B,08:05:00
BUS_1,Route1,2,C,08:12:00
BUS_1,Route1,3,D,08:20:00
BUS_2,Route2,0,E,08:10:00
BUS_2,Route2,1,D,08:15:00
```

---

## Development Workflow

### Phase 1: Core Infrastructure

1. Implement Event class
2. Implement Station class
3. Implement TravelTimeManager class
4. Implement TransitNetwork class
5. Test: Load network and query travel times

### Phase 2: Vehicle Layer

1. Implement Passenger class
2. Implement Bus class
3. Implement Minibus class
4. Test: Create vehicles and simulate basic movements

### Phase 3: Simulation Engine

1. Implement SimulationEngine skeleton
2. Implement event queue management
3. Implement bus arrival handling
4. Test: Run simulation with buses only

### Phase 4: Minibus Integration

1. Implement RouteOptimizer interface
2. Create dummy optimizer for testing
3. Implement minibus arrival handling
4. Implement optimization call handling
5. Test: Run simulation with minibuses

### Phase 5: Demand Generation

1. Implement DemandGenerator class
2. Implement passenger appearance handling
3. Test: Full simulation with all components

### Phase 6: Statistics & Analysis

1. Implement Statistics class
2. Add metric calculations
3. Implement report generation
4. Add visualization

### Phase 7: Integration & Testing

1. Integrate real optimizer
2. Full system testing
3. Performance tuning
4. Documentation

---

## Standard Development Prompt Template

**Use this prompt template when implementing each component:**

```
I'm implementing the [COMPONENT_NAME] for a transit simulation system.

Context:
- This is part of a mixed transit simulation with fixed-route buses and flexible minibuses
- Travel times are pre-computed in a 3D matrix: [origin_station, dest_station, time_slot]
- Time slots are 10-minute intervals
- An external optimizer provides routes for minibuses

Component Specification:
[PASTE THE RELEVANT COMPONENT SPECIFICATION FROM ABOVE]

Requirements:
1. Follow the exact attributes and methods specified
2. Use type hints for all function parameters and returns
3. Include detailed docstrings (Google style)
4. Add inline comments for complex logic
5. Use descriptive variable names
6. Handle edge cases and add appropriate error checking
7. Make the code modular and easy to test

Additional Context for this Component:
[ADD ANY SPECIFIC REQUIREMENTS OR CLARIFICATIONS]

Please implement this component with complete, production-ready code.
```

---

## Component-Specific Prompts

### For Event Class:

```
Additional Context:
- Events must be sortable by time for use with heapq
- If two events have the same time, use priority field (lower value = higher priority)
- Priority examples: BUS_ARRIVAL=0, MINIBUS_ARRIVAL=1, PASSENGER_APPEAR=2, OPTIMIZE_CALL=3
- Include validation to ensure time is positive
```

### For TravelTimeManager:

```
Additional Context:
- Matrix file is saved as numpy .npy format
- Include error handling for out-of-bounds time_slot indices
- If time_slot exceeds matrix bounds, use the last time slot
- Include a method to validate matrix dimensions match number of stations
- Support both datetime and float (seconds from start) for current_time
```

### For Minibus Class:

```
Additional Context:
- route_plan can be empty (when minibus is idle)
- When executing a stop, process all passengers in that stop's passenger_ids list
- After completing a stop, automatically move to the next stop in route_plan
- If route_plan becomes empty after a stop, set status to "IDLE"
- Validate that pickup actions don't exceed remaining capacity
```

### For SimulationEngine:

```
Additional Context:
- Use heapq for event queue management
- current_time should be in seconds from simulation start for easier calculations
- After each event, check if any passengers have timed out
- Log every major event for debugging
- Include a dry_run parameter to test without actually running
- Add a max_events parameter to prevent infinite loops during testing
```

### For RouteOptimizer:

```
Additional Context:
- The optimizer is a black box - we only control input/output format
- For external_program mode, use subprocess to call the optimizer
- Include timeout handling (max 30 seconds for optimizer to respond)
- If optimizer fails, return empty route plans (let minibuses stay idle)
- Validate optimizer output format before applying to minibuses
```

### For Statistics Class:

```
Additional Context:
- Store raw data during simulation, compute metrics only at end
- Export functions should handle missing data gracefully
- Plots should include: wait time histogram, occupancy over time, service rate by hour
- Use pandas for data manipulation if available
- Include methods to export intermediate results (for long simulations)
```

---

## Testing Guidelines

### Unit Test Template:

```python
import unittest
from [module] import [ClassName]

class Test[ClassName](unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method"""
        pass

    def test_[functionality](self):
        """Test [specific functionality]"""
        # Arrange
        # Act
        # Assert
        pass

    def tearDown(self):
        """Clean up after each test method"""
        pass

if __name__ == '__main__':
    unittest.main()
```

### Integration Test Scenarios:

1. **Scenario: Single bus, no passengers**
   - Expected: Bus completes route on schedule
2. **Scenario: Single bus, multiple passengers**
   - Expected: Passengers board/alight correctly
3. **Scenario: Single minibus, one passenger**
   - Expected: Minibus picks up and drops off correctly
4. **Scenario: Multiple minibuses, competing for passengers**
   - Expected: Optimizer assigns passengers efficiently
5. **Scenario: Passenger timeout**
   - Expected: Passenger marked as abandoned after max_wait_time

---

## Common Patterns and Utilities

### Time Conversion Utilities:

```python
def time_str_to_seconds(time_str, start_time):
    """Convert HH:MM:SS string to seconds from start_time"""
    pass

def seconds_to_time_str(seconds, start_time):
    """Convert seconds from start_time to HH:MM:SS string"""
    pass

def get_time_slot_index(current_seconds, slot_duration_minutes):
    """Convert seconds to time slot index"""
    return current_seconds // (slot_duration_minutes * 60)
```

### Logging Setup:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simulation.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

---

## Next Steps

1. **Set up project structure**: Create all folders and empty files
2. **Implement Google Maps loader**: Generate travel time matrix (one-time task)
3. **Start with Phase 1**: Core infrastructure components
4. **Test incrementally**: Don't move to next phase until current phase works
5. **Use the standard prompt template**: For each component implementation

---
