# Minibus Simulation System

A Python-based simulation system for on-demand minibus routing optimization in urban transit networks.

## Overview

This project simulates a dynamic transit network combining regular buses and on-demand minibuses. It uses real travel time data from Google Maps API and implements a greedy insertion optimization algorithm to assign passengers to minibuses and generate efficient routes in real-time.

## Key Features

- **Realistic Travel Times**: Uses pre-computed 3D travel time matrices obtained from Google Maps API
- **Demand Simulation**: Generates passenger requests using Poisson distribution with configurable peak hours
- **Route Optimization**: Greedy insertion algorithm for vehicle routing with time window and capacity constraints
- **Event-Driven Engine**: Discrete event simulation for accurate time-based passenger and vehicle interactions
- **Experiment Framework**: Automated batch experiment runner for comparing different configurations
- **Analytics Dashboard**: Comprehensive metrics collection including wait times, service rates, and vehicle occupancy

## Project Structure

```
simulation/
├── config.py                      # Global configuration settings
├── main.py                        # Main simulation entry point
├── run_experiments.py             # Batch experiment runner
│
├── network/                       # Network components
│   ├── station.py                 # Transit station definitions
│   ├── bus.py                     # Regular bus vehicle class
│   ├── minibus.py                 # On-demand minibus vehicle class
│   └── travel_time_manager.py     # Travel time matrix handler
│
├── optimizer/                     # Route optimization algorithms
│   └── greedy_insertion.py        # Greedy insertion vehicle routing optimizer
│
├── simulation/                    # Core simulation engine
│   ├── engine.py                  # Main discrete event simulation engine
│   └── event.py                   # Event definitions and handling
│
├── utils/                         # Utility functions
│   ├── google_maps_loader.py      # Google Maps API data loader
│   └── collect_travel_times.py    # Script to fetch & cache travel times
│
└── data/                          # Data storage
    ├── stations.json              # Station coordinates and metadata
    ├── travel_times/
    │   └── travel_time_matrix.npy # Precomputed 3D travel time matrix (from Google Maps)
    └── results/
        ├── logs/                  # Simulation logs
        ├── metrics.csv            # Aggregated performance metrics
        └── passenger_stats.csv    # Detailed passenger statistics
```

## Travel Times (Google Maps API)

Travel times are **pre-computed and cached** to avoid API rate limits:

- **Source**: Google Maps Distance Matrix API
- **Format**: 3D NumPy array (stations × stations × time_periods)
- **Time Periods**: Hourly intervals covering the full simulation day
- **Usage**: Loaded into `TravelTimeManager` for O(1) lookup during simulation

**Collecting Travel Times**:

```bash
python utils/collect_travel_times.py --config config.py
```

## Quick Start

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Prepare travel times** (if not cached):

   ```bash
   python utils/collect_travel_times.py
   ```

3. **Configure settings** in `config.py`:
   - `NUM_MINIBUSES`: Number of on-demand vehicles
   - `MINIBUS_CAPACITY`: Passenger capacity per vehicle
   - `OPTIMIZATION_INTERVAL`: Route optimization frequency (seconds)

4. **Run single simulation**:

   ```bash
   python main.py
   ```

5. **Run batch experiments**:
   ```bash
   python run_experiments.py --dry-run
   python run_experiments.py --resume
   ```

## Output & Results

Simulation results saved to `data/results/`:

- `metrics.csv` - Wait times, service rates, occupancy
- `passenger_stats.csv` - Per-passenger journey details
- `logs/` - Detailed event logs

## Technologies

- **Python 3.x**
- **NumPy**: Travel time matrix computations
- **Pandas**: Data analysis and output
- **Google Maps API**: Real-world distance and duration data
