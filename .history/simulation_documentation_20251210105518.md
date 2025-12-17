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
   - Load travel time matrix (npy format)

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

```

## 5. Event Types

### BUS_ARRIVAL - Bus Arrival

```
1. Get bus and station objects
2. Call bus.arrive_at_station()
   - Alight passengers who reached destination
   - Board waiting passengers (first-come-first-serve, capacity limited)

3. Remove boarded passengers from pending_requests
4. If more stops remain, add next BUS_ARRIVAL event
```

### MINIBUS_ARRIVAL - Minibus Arrival

```
1. Get minibus and station objects
2. Call minibus.arrive_at_station()
   - PICKUP: only board assigned passengers
   - DROPOFF: alight passengers who reached destination
3. Remove boarded passengers from pending_requests
4. If route plan has more stops, add next MINIBUS_ARRIVAL event
   Otherwise mark minibus as IDLE
```

### PASSENGER_APPEAR - Passenger Appearance

```
1. Create Passenger object
2. Add to pending_requests (unassigned pool)
3. Add to origin station's waiting_passengers list
4. Set status to WAITING
```

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
       if minibus already executing same route:
           skip update (avoid duplicate events)
       else:
           update minibus.route_plan

4. Update passenger assignments
   - Mark assigned passengers with assigned_vehicle_id
   - Remove assigned passengers from pending_requests

5. Schedule next optimizer call
   Add OPTIMIZE_CALL event at current_time + optimization_interval
```

## 6. Passenger Generation

### Method 1: OD Matrix (od_matrix)

The total number of passengerin each 10 mins follows Poisson distribution, but they appear randomly during the 10 minutes.

```python
_generate_passengers_from_od_matrix():
    for each time_slot in OD matrix:
        Get demand matrix for this time period (origin, destination, demand)

        for each OD pair:
            # Poisson sampling:
            n_passengers = Poisson(lambda=demand)

            for i in range(n_passengers):

                appear_time = random_uniform(slot_start, slot_end)

                Create Passenger object
                Add to all_passengers
                Add PASSENGER_APPEAR event
```

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


```

## Current Implementation Status

The simulation system has been developed and validated through two versions: a test version and a full-scale version.

### Test Version

- **Duration**: 1 hour
- **Fleet composition**: 3 minibuses and 7 buses
- **Passenger generation**: 7 test passengers
- **Optimizer**: Dummy optimizer (immediate dispatch strategy - assigns available minibuses to pending requests as soon as possible)

### Full-Scale Version (Bus-Only)

The full-scale version uses real-world data:

- **Data source**: Real bus schedule data from July 25, 2024
- **Simulation period**: 15:00 - 21:00 (6 hours)
- **Passenger demand**: Generated from real OD matrix using Poisson sampling
- **Fleet**: Bus-only system (minibuses not yet integrated)

**Validation results**: The bus-only system successfully transported all passengers to their destinations during the first four hours of simulation. Only passengers generated in the final few seconds could not be served, which is expected behavior as they appeared too close to the simulation end time.

### Next Steps

The development roadmap consists of two key phases:

**Phase 1: Minibus Integration in real data**

- Integrate minibuses into the full-scale version alongside the real bus schedules
- Implement travel time matrix retrieval via Google Maps API for minibus routing
- Test the mixed traffic coordination mechanism with realistic data

**Phase 2: Advanced Optimization**

- Replace the dummy optimizer with Lynn's optimization algorithm
- Integrate the sophisticated route planning logic through the `OPTIMIZE_CALL` event handler
- Evaluate system performance with intelligent minibus dispatch strategies
