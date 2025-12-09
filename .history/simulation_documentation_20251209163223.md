# Mixed Traffic Simulation System Documentation

## 1. System Overview

This is a public transit simulation system that models the mixed operation of fixed-route buses and dynamic-route minibuses. The system uses Discrete Event Simulation (DES) to process vehicle arrivals, passenger boarding/alighting, and other events in chronological order.

## 2. Simulation Principles

### Discrete Event Simulation (DES)

Time doesn't flow continuously but advances in jumps:

```
Event1(t=0) → Event2(t=10) → Event3(t=15) → ...
```

The system maintains a time-ordered event queue. Each iteration pops the earliest event, updates system state, and may generate new events to add to the queue. All state changes occur only at event timestamps, with no computation between events.

### Event-Driven Architecture

```
while event_queue not empty:
    event = pop earliest event
    current_time = event.time
    process event
    check passenger timeouts
```

## 3. System Components

```
SimulationEngine
├── Time Management: current_time, simulation start/end times
├── Event Queue: priority queue (min-heap)
├── Transit Network: stations + travel time matrix
├── Vehicles
│   ├── buses: bus dictionary
│   └── minibuses: minibus dictionary
├── Passengers
│   ├── all_passengers: all passenger records
│   └── pending_requests: unassigned passengers
├── route_optimizer: route optimizer (for minibuses)
└── statistics: statistics collector
```

## 4. Simulation Workflow

### Initialization (initialize)

```
1. Load transit network
   - Read stations CSV
   - Load travel time matrix (npz format)

2. Create vehicles
   - Load bus schedules from CSV
   - Create minibus fleet from config

3. Generate passengers
   - OD matrix method: Poisson sampling
   - Test method: hardcoded passengers

4. Populate event queue
   - Add initial vehicle arrival events
   - Add passenger appearance events
   - Add optimizer call events (if minibus enabled)
   - Add simulation end event
```

### Main Loop (run)

```python
while event_queue:
    event = heappop(event_queue)
    current_time = event.time
    
    if event.type == BUS_ARRIVAL:
        handle_bus_arrival()
    elif event.type == MINIBUS_ARRIVAL:
        handle_minibus_arrival()
    elif event.type == PASSENGER_APPEAR:
        handle_passenger_appear()
    elif event.type == OPTIMIZE_CALL:
        handle_optimize_call()
    
    check_passenger_timeouts()
```

### Finalization (finalize)

Statistical analysis, report generation, visualization, and CSV data export.

## 5. Event Types

### BUS_ARRIVAL - Bus Arrival

```
1. Get bus and station objects
2. Call bus.arrive_at_station()
   - Alight passengers who reached destination
   - Board waiting passengers (first-come-first-serve, capacity limited)
3. Record statistics (arrival, boarding count, alighting count, occupancy)
4. Remove boarded passengers from pending_requests
5. If more stops remain, add next BUS_ARRIVAL event
```

### MINIBUS_ARRIVAL - Minibus Arrival

```
1. Get minibus and station objects
2. Call minibus.arrive_at_station()
   - Execute planned action (PICKUP or DROPOFF)
   - PICKUP: only board assigned passengers
   - DROPOFF: alight passengers who reached destination
3. Record statistics
4. Remove boarded passengers from pending_requests
5. If route plan has more stops, add next MINIBUS_ARRIVAL event
   Otherwise mark minibus as IDLE
```

**Key Difference**: Buses use first-come-first-serve, minibuses only pick up assigned passengers.

### PASSENGER_APPEAR - Passenger Appearance

```
1. Create or retrieve Passenger object
2. Add to pending_requests (unassigned pool)
3. Add to origin station's waiting_passengers list
4. Set status to WAITING
```

After entering the system, passengers may be picked up directly by buses or assigned to minibuses by the optimizer.

### OPTIMIZE_CALL - Optimizer Call

This is the core event for the minibus system, triggered periodically (e.g., every 30 seconds).

```
1. Collect system state
   - pending_requests: all unassigned passengers
   - minibus_states: all minibus locations, occupancy, current routes

2. Call route_optimizer.optimize()
   Input: pending_requests, minibus_states, network, current_time
   Output: {minibus_id: route_plan}
   
   route_plan format:
   [
       {"station_id": "A", "action": "PICKUP", "passenger_ids": ["P1", "P2"]},
       {"station_id": "B", "action": "DROPOFF", "passenger_ids": ["P1"]},
       {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["P2"]}
   ]

3. Apply route plans
   for minibus_id, route_plan in new_plans:
       # Check if route actually changed
       if minibus already executing same route:
           skip update (avoid duplicate events)
       else:
           update minibus.route_plan
           add next MINIBUS_ARRIVAL event

4. Update passenger assignments
   - Mark assigned passengers with assigned_vehicle_id
   - Remove assigned passengers from pending_requests

5. Schedule next optimizer call
   Add OPTIMIZE_CALL event at current_time + optimization_interval
```

**Duplicate Prevention Mechanism**: If a minibus is already executing the same route, skip the update to avoid generating redundant events.

### SIMULATION_END - Simulation End

When reaching the configured end time, record final statistics, clear event queue, and trigger finalize().

## 6. Passenger Generation

### Method 1: OD Matrix (od_matrix)

For production use, generates large-scale realistic demand.

```python
_generate_passengers_from_od_matrix():
    for each time_slot in OD matrix:
        Get demand matrix for this time period (origin, destination, demand)
        
        for each OD pair:
            # Poisson sampling: sample passenger count based on demand
            n_passengers = Poisson(lambda=demand)
            
            for i in range(n_passengers):
                # Randomly assign appearance time within slot
                appear_time = random_uniform(slot_start, slot_end)
                
                Create Passenger object
                Add to all_passengers
                Add PASSENGER_APPEAR event
```

**Features**:
- Supports real demand data
- Can simulate peak/off-peak periods
- Generates thousands of passengers
- Uses Poisson distribution to model random arrivals

### Method 2: Test Data (test)

For debugging, generates a small number of hardcoded passengers.

```python
_generate_hardcoded_test_passengers():
    test_passengers = [
        {"id": "P1", "origin": "A", "dest": "C", "appear_time": 0.0},
        {"id": "P2", "origin": "A", "dest": "D", "appear_time": 0.0},
        {"id": "P3", "origin": "B", "dest": "D", "appear_time": 150.0},
        ...
    ]
    
    for pax_data in test_passengers:
        Create Passenger object
        Add to all_passengers
        Add PASSENGER_APPEAR event
```

**Features**:
- Deterministic and reproducible
- Small quantity (5-10 passengers)
- Convenient for debugging and verification
