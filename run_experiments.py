"""
run_experiments.py

Automated experiment runner for the traffic simulation system.
Runs multiple experiments with different minibus configurations and
collects results for comparative analysis.

Usage:
    python run_experiments.py              # Run all experiments
    python run_experiments.py --resume     # Resume from last checkpoint
    python run_experiments.py --dry-run    # Preview experiments without running
"""

import os
import sys
import re
import json
import time
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ExperimentRunner:
    """
    Automated experiment runner for minibus ratio experiments.
    
    Manages the execution of multiple simulation experiments with different
    minibus configurations, collects results, and generates summary reports.
    """
    
    def __init__(self, output_base_dir: str = "Minibus_ratio_results"):
        """
        Initialize the experiment runner.
        
        Args:
            output_base_dir: Base directory for all experiment results
        """
        self.output_base_dir = Path(output_base_dir)
        self.config_backup_path = self.output_base_dir / "config_backup.py"
        self.summary_file = self.output_base_dir / "experiment_summary.csv"
        self.progress_file = self.output_base_dir / "experiment_log.json"
        
        # NEW: Minibus occupancy summary file
        self.minibus_occupancy_summary_file = self.output_base_dir / "minibus_occupancy_summary.csv"
        
        # # Experiment parameters
        self.num_minibuses_values = [1, 2, 3, 5]
        self.minibus_capacity_values = [6, 8]
        self.minibus_ratio_values = [0.01, 0.03, 0.05, 0.07, 0.09]
        self.optimization_interval_values = [30, 60, 120, 240, 300]

        # self.num_minibuses_values = [ 5]
        # self.minibus_capacity_values = [ 8]
        # self.minibus_ratio_values = [0.01, 0.03, 0.05]
        # self.optimization_interval_values = [30, 60, 120, 300]

        # Execution settings
        self.timeout_seconds = 3000
        self.stop_on_failure = True
        
        # Progress tracking
        self.completed_experiments = set()
        self.failed_experiments = []
        
        logger.info(f"Experiment runner initialized")
        logger.info(f"Output directory: {self.output_base_dir}")
        logger.info(f"Total experiments to run: {self.get_total_experiments()}")
    
    def get_total_experiments(self) -> int:
        """Calculate total number of experiments."""
        return (len(self.num_minibuses_values) * 
                len(self.minibus_capacity_values) * 
                len(self.minibus_ratio_values) *
                len(self.optimization_interval_values))
    
    def generate_experiment_configs(self) -> List[Dict]:
        """Generate all experiment configurations."""
        experiments = []
        exp_id = 1
        
        for num_minibuses in self.num_minibuses_values:
            for capacity in self.minibus_capacity_values:
                for ratio in self.minibus_ratio_values:
                    for optimization_interval in self.optimization_interval_values:
                        exp_config = {
                            'exp_id': exp_id,
                            'num_minibuses': num_minibuses,
                            'minibus_capacity': capacity,
                            'minibus_ratio': ratio,
                            'optimization_interval': optimization_interval,
                            'exp_name': f"exp_{exp_id:03d}_n{num_minibuses}_c{capacity}_r{ratio}_opt{optimization_interval}",
                            'output_dir': str(self.output_base_dir / f"exp_{exp_id:03d}_n{num_minibuses}_c{capacity}_r{ratio}_opt{optimization_interval}")
                        }
                        experiments.append(exp_config)
                        exp_id += 1
        
        return experiments
    
    def setup_directories(self) -> None:
        """Create necessary directories."""
        logger.info("Setting up directories...")
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.config_backup_path.exists():
            if Path("config.py").exists():
                shutil.copy2("config.py", self.config_backup_path)
                logger.info(f"Backed up original config.py to {self.config_backup_path}")
            else:
                logger.error("config.py not found! Cannot create backup.")
                raise FileNotFoundError("config.py not found")
        
        logger.info("Directory setup complete")
    
    def load_progress(self) -> None:
        """Load progress from checkpoint file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    progress_data = json.load(f)
                self.completed_experiments = set(progress_data.get('completed', []))
                self.failed_experiments = progress_data.get('failed', [])
                logger.info(f"Loaded progress: {len(self.completed_experiments)} completed, "
                          f"{len(self.failed_experiments)} failed")
            except Exception as e:
                logger.warning(f"Failed to load progress file: {e}")
                self.completed_experiments = set()
                self.failed_experiments = []
        else:
            logger.info("No previous progress found, starting fresh")
    
    def save_progress(self) -> None:
        """Save current progress to checkpoint file."""
        try:
            progress_data = {
                'completed': list(self.completed_experiments),
                'failed': self.failed_experiments,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            logger.debug("Progress saved")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
            
    def modify_config(self, exp_config: Dict) -> None:
        """Modify config.py with experiment parameters."""
        logger.info(f"Modifying config.py for experiment {exp_config['exp_id']}...")
        
        try:
            with open("config.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            num_minibuses = exp_config["num_minibuses"]
            
            content = re.sub(r'NUM_MINIBUSES\s*=\s*\d+', f'NUM_MINIBUSES = {num_minibuses}', content)
            content = re.sub(r'MINIBUS_CAPACITY\s*=\s*\d+', f'MINIBUS_CAPACITY = {exp_config["minibus_capacity"]}', content)
            content = re.sub(r'MINIBUS_PASSENGER_RATIO\s*=\s*[\d.]+', f'MINIBUS_PASSENGER_RATIO = {exp_config["minibus_ratio"]}', content)
            content = re.sub(r'OPTIMIZATION_INTERVAL\s*=\s*\d+', f'OPTIMIZATION_INTERVAL = {exp_config["optimization_interval"]}', content)
            
            output_dir_escaped = exp_config["output_dir"].replace("\\", "/")
            content = re.sub(r'OUTPUT_DIR\s*=\s*["\'].*?["\']', f'OUTPUT_DIR = "{output_dir_escaped}"', content)
            content = re.sub(r'PASSENGER_ALLOCATION_STRATEGY\s*=\s*["\'].*?["\']', 'PASSENGER_ALLOCATION_STRATEGY = "fixed"', content)
            content = re.sub(r'ENABLE_MINIBUS\s*=\s*\w+', 'ENABLE_MINIBUS = True', content)
            
            match = re.search(r'MINIBUS_INITIAL_LOCATIONS\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if match:
                locations_str = match.group(1).strip()
                if locations_str:
                    first_loc = locations_str.split(',')[0].strip().strip('"\'')
                    new_locations = ', '.join([f'"{first_loc}"'] * num_minibuses)
                else:
                    new_locations = '"random"' if num_minibuses == 0 else ', '.join(['"8592374"'] * num_minibuses)
            else:
                new_locations = ', '.join(['"8592374"'] * num_minibuses)
            
            content = re.sub(r'MINIBUS_INITIAL_LOCATIONS\s*=\s*\[.*?\]', 
                           f'MINIBUS_INITIAL_LOCATIONS = [{new_locations}]', content, flags=re.DOTALL)
            
            with open("config.py", 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Config modified: n={num_minibuses}, c={exp_config['minibus_capacity']}, "
                       f"r={exp_config['minibus_ratio']}, opt={exp_config['optimization_interval']}s")
        
        except Exception as e:
            logger.error(f"Failed to modify config.py: {e}")
            raise
    
    def restore_config(self) -> None:
        """Restore original config.py from backup."""
        try:
            if self.config_backup_path.exists():
                shutil.copy2(self.config_backup_path, "config.py")
                logger.info("Restored original config.py")
            else:
                logger.warning("No config backup found to restore")
        except Exception as e:
            logger.error(f"Failed to restore config: {e}")
    
    def run_simulation(self, exp_config: Dict) -> Tuple[bool, Optional[str], float]:
        """Run a single simulation experiment."""
        logger.info("=" * 70)
        logger.info(f"Running Experiment {exp_config['exp_id']}/{self.get_total_experiments()}: {exp_config['exp_name']}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        try:
            result = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True, timeout=self.timeout_seconds)
            runtime = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"✓ Experiment {exp_config['exp_id']} completed successfully in {runtime:.1f}s")
                return True, None, runtime
            else:
                error_msg = f"Non-zero exit code: {result.returncode}"
                logger.error(f"✗ Experiment {exp_config['exp_id']} failed: {error_msg}")
                logger.error(f"STDERR: {result.stderr[:500]}")
                return False, error_msg, runtime
        
        except subprocess.TimeoutExpired:
            runtime = time.time() - start_time
            error_msg = f"Timeout after {self.timeout_seconds}s"
            logger.error(f"✗ Experiment {exp_config['exp_id']} failed: {error_msg}")
            return False, error_msg, runtime
        
        except Exception as e:
            runtime = time.time() - start_time
            error_msg = str(e)
            logger.error(f"✗ Experiment {exp_config['exp_id']} failed: {error_msg}")
            return False, error_msg, runtime
    
    def extract_metrics_from_csv(self, result_dir: str) -> Dict:
        """Extract performance metrics from CSV output files."""
        logger.info(f"Extracting metrics from {result_dir}...")
        
        try:
            metrics = {}
            passengers_file = Path(result_dir) / "passengers.csv"
            if not passengers_file.exists():
                logger.error(f"passengers.csv not found in {result_dir}")
                return None
            
            passengers_df = pd.read_csv(passengers_file)
            
            total = len(passengers_df)
            arrived = len(passengers_df[passengers_df['status'] == 'ARRIVED'])
            abandoned = len(passengers_df[passengers_df['status'] == 'ABANDONED'])
            
            metrics['total_passengers'] = total
            metrics['service_rate'] = (arrived / total * 100) if total > 0 else 0.0
            metrics['abandoned_count'] = abandoned
            
            valid_wait_times = passengers_df['wait_time'].dropna()
            if len(valid_wait_times) > 0:
                metrics['avg_wait_time'] = float(valid_wait_times.mean())
                metrics['total_wait_time'] = float(valid_wait_times.sum())
                metrics['total_wait_time_hours'] = float(valid_wait_times.sum() / 3600)
            else:
                metrics['avg_wait_time'] = 0.0
                metrics['total_wait_time'] = 0.0
                metrics['total_wait_time_hours'] = 0.0
            
            valid_travel_times = passengers_df['travel_time'].dropna()
            if len(valid_travel_times) > 0:
                metrics['avg_travel_time'] = float(valid_travel_times.mean())
                metrics['total_travel_time'] = float(valid_travel_times.sum())
                metrics['total_travel_time_hours'] = float(valid_travel_times.sum() / 3600)
            else:
                metrics['avg_travel_time'] = 0.0
                metrics['total_travel_time'] = 0.0
                metrics['total_travel_time_hours'] = 0.0
            
            passengers_df['total_time'] = passengers_df['wait_time'].fillna(0) + passengers_df['travel_time'].fillna(0)
            valid_total_times = passengers_df['total_time'][passengers_df['total_time'] > 0]
            
            if len(valid_total_times) > 0:
                metrics['avg_total_time'] = float(valid_total_times.mean())
                metrics['total_total_time'] = float(valid_total_times.sum())
                metrics['total_total_time_hours'] = float(valid_total_times.sum() / 3600)
            else:
                metrics['avg_total_time'] = 0.0
                metrics['total_total_time'] = 0.0
                metrics['total_total_time_hours'] = 0.0
            
            # Infer vehicle_type
            if 'vehicle_type' not in passengers_df.columns and 'assigned_vehicle' in passengers_df.columns:
                def infer_vehicle_type(assigned_vehicle):
                    if pd.isna(assigned_vehicle) or assigned_vehicle == '':
                        return 'Bus'
                    return 'Minibus'
                passengers_df['vehicle_type'] = passengers_df['assigned_vehicle'].apply(infer_vehicle_type)
            
            if 'vehicle_type' in passengers_df.columns:
                bus_passengers = passengers_df[passengers_df['vehicle_type'] == 'Bus']
                if len(bus_passengers) > 0:
                    bus_total_times = bus_passengers['total_time'][bus_passengers['total_time'] > 0]
                    metrics['bus_avg_total_time'] = float(bus_total_times.mean()) if len(bus_total_times) > 0 else 0.0
                    metrics['bus_total_total_time'] = float(bus_total_times.sum()) if len(bus_total_times) > 0 else 0.0
                    metrics['bus_total_total_time_hours'] = float(bus_total_times.sum() / 3600) if len(bus_total_times) > 0 else 0.0
                    metrics['bus_passenger_count'] = len(bus_passengers)
                else:
                    metrics['bus_avg_total_time'] = 0.0
                    metrics['bus_total_total_time'] = 0.0
                    metrics['bus_total_total_time_hours'] = 0.0
                    metrics['bus_passenger_count'] = 0
                
                minibus_passengers = passengers_df[passengers_df['vehicle_type'] == 'Minibus']
                if len(minibus_passengers) > 0:
                    minibus_total_times = minibus_passengers['total_time'][minibus_passengers['total_time'] > 0]
                    metrics['minibus_avg_total_time'] = float(minibus_total_times.mean()) if len(minibus_total_times) > 0 else 0.0
                    metrics['minibus_total_total_time'] = float(minibus_total_times.sum()) if len(minibus_total_times) > 0 else 0.0
                    metrics['minibus_total_total_time_hours'] = float(minibus_total_times.sum() / 3600) if len(minibus_total_times) > 0 else 0.0
                    metrics['minibus_passenger_count'] = len(minibus_passengers)
                else:
                    metrics['minibus_avg_total_time'] = 0.0
                    metrics['minibus_total_total_time'] = 0.0
                    metrics['minibus_total_total_time_hours'] = 0.0
                    metrics['minibus_passenger_count'] = 0
            else:
                metrics['bus_avg_total_time'] = 0.0
                metrics['bus_total_total_time'] = 0.0
                metrics['bus_total_total_time_hours'] = 0.0
                metrics['bus_passenger_count'] = 0
                metrics['minibus_avg_total_time'] = 0.0
                metrics['minibus_total_total_time'] = 0.0
                metrics['minibus_total_total_time_hours'] = 0.0
                metrics['minibus_passenger_count'] = 0
            
            vehicles_file = Path(result_dir) / "vehicles.csv"
            if vehicles_file.exists():
                vehicles_df = pd.read_csv(vehicles_file)
                metrics['total_passengers_served'] = int(vehicles_df['total_passengers'].sum())
                metrics['avg_vehicle_occupancy'] = float(vehicles_df['avg_occupancy'].mean())
                
                bus_df = vehicles_df[vehicles_df['type'] == 'Bus']
                minibus_df = vehicles_df[vehicles_df['type'] == 'Minibus']
                
                metrics['bus_avg_occupancy'] = float(bus_df['avg_occupancy'].mean()) if len(bus_df) > 0 else 0.0
                metrics['minibus_avg_occupancy'] = float(minibus_df['avg_occupancy'].mean()) if len(minibus_df) > 0 else 0.0
            else:
                metrics['total_passengers_served'] = 0
                metrics['avg_vehicle_occupancy'] = 0.0
                metrics['bus_avg_occupancy'] = 0.0
                metrics['minibus_avg_occupancy'] = 0.0
            
            logger.info(f"Metrics extracted: service_rate={metrics['service_rate']:.1f}%")
            return metrics
        
        except Exception as e:
            logger.error(f"Error extracting metrics: {e}", exc_info=True)
            return None
    
    def extract_minibus_occupancy_data(self, result_dir: str) -> Dict:
        """
        Extract minibus occupancy over time data from experiment results.
        
        This data is saved to the summary file for later plotting and comparison.
        """
        logger.info(f"Extracting minibus occupancy data from {result_dir}...")
        
        try:
            occupancy_data = {}
            
            # First try minibus_occupancy_timeseries.csv
            timeseries_file = Path(result_dir) / "minibus_occupancy_timeseries.csv"
            if timeseries_file.exists():
                logger.info(f"Found minibus_occupancy_timeseries.csv")
                ts_df = pd.read_csv(timeseries_file)
                
                if len(ts_df) > 0:
                    occupancy_data['minibus_occ_data_points'] = len(ts_df)
                    occupancy_data['minibus_occ_mean'] = float(ts_df['occupancy'].mean())
                    occupancy_data['minibus_occ_max'] = int(ts_df['occupancy'].max())
                    occupancy_data['minibus_occ_min'] = int(ts_df['occupancy'].min())
                    occupancy_data['minibus_occ_std'] = float(ts_df['occupancy'].std())
                    
                    unique_vehicles = ts_df['vehicle_id'].nunique()
                    occupancy_data['minibus_count'] = unique_vehicles
                    
                    occupancy_data['minibus_occ_time_start'] = float(ts_df['time'].min())
                    occupancy_data['minibus_occ_time_end'] = float(ts_df['time'].max())
                    occupancy_data['minibus_occ_duration'] = occupancy_data['minibus_occ_time_end'] - occupancy_data['minibus_occ_time_start']
                    
                    if 'avg_occupancy' in ts_df.columns:
                        occupancy_data['minibus_occ_time_weighted_avg'] = float(ts_df['avg_occupancy'].mean())
                    
                    # Store time series as JSON for plotting
                    time_series_summary = ts_df.groupby('time').agg({
                        'occupancy': 'sum',
                        'avg_occupancy': 'first'
                    }).reset_index()
                    occupancy_data['minibus_occ_timeseries_json'] = json.dumps(
                        time_series_summary[['time', 'occupancy']].values.tolist()
                    )
                    
                    logger.info(f"Extracted minibus occupancy: mean={occupancy_data['minibus_occ_mean']:.2f}")
                    return occupancy_data
            
            # Fallback: vehicle_states.csv
            states_file = Path(result_dir) / "vehicle_states.csv"
            if states_file.exists():
                logger.info(f"Falling back to vehicle_states.csv")
                states_df = pd.read_csv(states_file)
                
                minibus_states = states_df[states_df['vehicle_id'].str.contains('MINIBUS', case=False, na=False)]
                
                if len(minibus_states) > 0:
                    occupancy_data['minibus_occ_data_points'] = len(minibus_states)
                    
                    if 'occupancy' in minibus_states.columns:
                        valid_occupancy = minibus_states['occupancy'].dropna()
                        if len(valid_occupancy) > 0:
                            occupancy_data['minibus_occ_mean'] = float(valid_occupancy.mean())
                            occupancy_data['minibus_occ_max'] = int(valid_occupancy.max())
                            occupancy_data['minibus_occ_min'] = int(valid_occupancy.min())
                            occupancy_data['minibus_occ_std'] = float(valid_occupancy.std())
                    
                    occupancy_data['minibus_count'] = minibus_states['vehicle_id'].nunique()
                    
                    if 'time' in minibus_states.columns:
                        valid_times = minibus_states['time'].dropna()
                        if len(valid_times) > 0:
                            occupancy_data['minibus_occ_time_start'] = float(valid_times.min())
                            occupancy_data['minibus_occ_time_end'] = float(valid_times.max())
                            occupancy_data['minibus_occ_duration'] = occupancy_data['minibus_occ_time_end'] - occupancy_data['minibus_occ_time_start']
                    
                    if 'time' in minibus_states.columns and 'occupancy' in minibus_states.columns:
                        time_series = minibus_states.groupby('time')['occupancy'].sum().reset_index()
                        occupancy_data['minibus_occ_timeseries_json'] = json.dumps(time_series.values.tolist())
                    
                    logger.info(f"Extracted minibus occupancy from vehicle_states")
                    return occupancy_data
            
            logger.warning(f"No minibus occupancy data found in {result_dir}")
            return {
                'minibus_occ_data_points': 0,
                'minibus_occ_mean': 0.0,
                'minibus_occ_max': 0,
                'minibus_occ_min': 0,
                'minibus_occ_std': 0.0,
                'minibus_count': 0,
                'minibus_occ_timeseries_json': '[]'
            }
        
        except Exception as e:
            logger.error(f"Error extracting minibus occupancy data: {e}", exc_info=True)
            return {
                'minibus_occ_data_points': 0,
                'minibus_occ_mean': 0.0,
                'minibus_occ_max': 0,
                'minibus_occ_min': 0,
                'minibus_occ_std': 0.0,
                'minibus_count': 0,
                'minibus_occ_timeseries_json': '[]'
            }
    
    def run_all_experiments(self, resume: bool = False) -> None:
        """Run all experiments in sequence."""
        self.setup_directories()
        
        if resume:
            self.load_progress()
        
        experiments = self.generate_experiment_configs()
        
        logger.info("=" * 70)
        logger.info(f"STARTING EXPERIMENT BATCH")
        logger.info(f"Total experiments: {len(experiments)}")
        logger.info(f"Already completed: {len(self.completed_experiments)}")
        logger.info(f"Remaining: {len(experiments) - len(self.completed_experiments)}")
        logger.info("=" * 70)
        
        all_results = []
        all_minibus_occupancy_results = []
        
        for exp_config in experiments:
            exp_name = exp_config['exp_name']
            
            if resume and exp_name in self.completed_experiments:
                logger.info(f"Skipping experiment {exp_config['exp_id']} (already completed)")
                
                existing_metrics = self.extract_metrics_from_csv(exp_config['output_dir'])
                if existing_metrics:
                    result = {
                        'exp_id': exp_config['exp_id'],
                        'exp_name': exp_name,
                        'num_minibuses': exp_config['num_minibuses'],
                        'minibus_capacity': exp_config['minibus_capacity'],
                        'minibus_ratio': exp_config['minibus_ratio'],
                        'optimization_interval': exp_config['optimization_interval'],
                        'status': 'SUCCESS',
                        'error_message': None,
                        'runtime_seconds': 0.0,
                        **existing_metrics
                    }
                    all_results.append(result)
                    
                    minibus_occ_data = self.extract_minibus_occupancy_data(exp_config['output_dir'])
                    minibus_occ_result = {
                        'exp_id': exp_config['exp_id'],
                        'exp_name': exp_name,
                        'num_minibuses': exp_config['num_minibuses'],
                        'minibus_capacity': exp_config['minibus_capacity'],
                        'minibus_ratio': exp_config['minibus_ratio'],
                        'optimization_interval': exp_config['optimization_interval'],
                        **minibus_occ_data
                    }
                    all_minibus_occupancy_results.append(minibus_occ_result)
                
                continue
            
            try:
                self.modify_config(exp_config)
            except Exception as e:
                logger.error(f"Failed to modify config for experiment {exp_config['exp_id']}: {e}")
                if self.stop_on_failure:
                    logger.error("Stopping due to failure (stop_on_failure=True)")
                    break
                continue
            
            success, error_msg, runtime = self.run_simulation(exp_config)
            
            if success:
                metrics = self.extract_metrics_from_csv(exp_config['output_dir'])
                
                if metrics:
                    result = {
                        'exp_id': exp_config['exp_id'],
                        'exp_name': exp_name,
                        'num_minibuses': exp_config['num_minibuses'],
                        'minibus_capacity': exp_config['minibus_capacity'],
                        'minibus_ratio': exp_config['minibus_ratio'],
                        'optimization_interval': exp_config['optimization_interval'],
                        'status': 'SUCCESS',
                        'error_message': None,
                        'runtime_seconds': runtime,
                        **metrics
                    }
                    
                    self.completed_experiments.add(exp_name)
                    
                    minibus_occ_data = self.extract_minibus_occupancy_data(exp_config['output_dir'])
                    minibus_occ_result = {
                        'exp_id': exp_config['exp_id'],
                        'exp_name': exp_name,
                        'num_minibuses': exp_config['num_minibuses'],
                        'minibus_capacity': exp_config['minibus_capacity'],
                        'minibus_ratio': exp_config['minibus_ratio'],
                        'optimization_interval': exp_config['optimization_interval'],
                        **minibus_occ_data
                    }
                    all_minibus_occupancy_results.append(minibus_occ_result)
                else:
                    logger.error(f"Failed to extract metrics for experiment {exp_config['exp_id']}")
                    result = {
                        'exp_id': exp_config['exp_id'],
                        'exp_name': exp_name,
                        'num_minibuses': exp_config['num_minibuses'],
                        'minibus_capacity': exp_config['minibus_capacity'],
                        'minibus_ratio': exp_config['minibus_ratio'],
                        'optimization_interval': exp_config['optimization_interval'],
                        'status': 'FAILED',
                        'error_message': 'Failed to extract metrics',
                        'runtime_seconds': runtime
                    }
                    self.failed_experiments.append(exp_name)
            else:
                result = {
                    'exp_id': exp_config['exp_id'],
                    'exp_name': exp_name,
                    'num_minibuses': exp_config['num_minibuses'],
                    'minibus_capacity': exp_config['minibus_capacity'],
                    'minibus_ratio': exp_config['minibus_ratio'],
                    'optimization_interval': exp_config['optimization_interval'],
                    'status': 'FAILED',
                    'error_message': error_msg,
                    'runtime_seconds': runtime
                }
                self.failed_experiments.append(exp_name)
            
            all_results.append(result)
            self.save_progress()
            
            if not success and self.stop_on_failure:
                logger.error("=" * 70)
                logger.error("STOPPING: Experiment failed and stop_on_failure=True")
                logger.error("=" * 70)
                break
        
        self.restore_config()
        
        if all_results:
            self.save_summary(all_results)
        
        if all_minibus_occupancy_results:
            self.save_minibus_occupancy_summary(all_minibus_occupancy_results)
        
        self.print_final_summary(all_results)
    
    def save_summary(self, results: List[Dict]) -> None:
        """Save experiment summary to CSV."""
        logger.info(f"Saving experiment summary to {self.summary_file}...")
        
        try:
            df = pd.DataFrame(results)
            
            column_order = [
                'exp_id', 'exp_name', 'status', 
                'num_minibuses', 'minibus_capacity', 'minibus_ratio', 'optimization_interval',
                'total_passengers', 'service_rate', 'abandoned_count',
                'avg_wait_time', 'total_wait_time', 'total_wait_time_hours',
                'avg_travel_time', 'total_travel_time', 'total_travel_time_hours',
                'avg_total_time', 'total_total_time', 'total_total_time_hours',
                'bus_passenger_count', 'bus_avg_total_time', 'bus_total_total_time', 'bus_total_total_time_hours',
                'minibus_passenger_count', 'minibus_avg_total_time', 'minibus_total_total_time', 'minibus_total_total_time_hours',
                'total_passengers_served',
                'avg_vehicle_occupancy', 'bus_avg_occupancy', 'minibus_avg_occupancy',
                'runtime_seconds', 'error_message'
            ]
            
            existing_columns = [col for col in column_order if col in df.columns]
            df = df[existing_columns]
            df.to_csv(self.summary_file, index=False, float_format='%.4f')
            
            logger.info(f"✓ Summary saved: {len(results)} experiments")
            logger.info(f"  Location: {self.summary_file}")
        
        except Exception as e:
            logger.error(f"Failed to save summary: {e}", exc_info=True)
    
    def save_minibus_occupancy_summary(self, results: List[Dict]) -> None:
        """
        Save minibus occupancy summary to a dedicated CSV file.
        
        This file contains minibus occupancy statistics and time series data 
        for each experiment, allowing you to compare and plot across experiments.
        """
        logger.info(f"Saving minibus occupancy summary to {self.minibus_occupancy_summary_file}...")
        
        try:
            df = pd.DataFrame(results)
            
            column_order = [
                'exp_id', 'exp_name',
                'num_minibuses', 'minibus_capacity', 'minibus_ratio', 'optimization_interval',
                'minibus_count',
                'minibus_occ_data_points',
                'minibus_occ_mean', 'minibus_occ_max', 'minibus_occ_min', 'minibus_occ_std',
                'minibus_occ_time_start', 'minibus_occ_time_end', 'minibus_occ_duration',
                'minibus_occ_time_weighted_avg',
                'minibus_occ_timeseries_json'
            ]
            
            existing_columns = [col for col in column_order if col in df.columns]
            df = df[existing_columns]
            df.to_csv(self.minibus_occupancy_summary_file, index=False, float_format='%.4f')
            
            logger.info(f"✓ Minibus occupancy summary saved: {len(results)} experiments")
            logger.info(f"  Location: {self.minibus_occupancy_summary_file}")
            
            if 'minibus_occ_mean' in df.columns:
                valid_data = df[df['minibus_occ_data_points'] > 0]
                if len(valid_data) > 0:
                    logger.info(f"  Overall minibus occupancy statistics:")
                    logger.info(f"    Mean across experiments: {valid_data['minibus_occ_mean'].mean():.2f}")
                    logger.info(f"    Max across experiments: {valid_data['minibus_occ_max'].max()}")
                    logger.info(f"    Experiments with data: {len(valid_data)}/{len(df)}")
        
        except Exception as e:
            logger.error(f"Failed to save minibus occupancy summary: {e}", exc_info=True)
    
    def print_final_summary(self, results: List[Dict]) -> None:
        """Print final summary of all experiments."""
        logger.info("=" * 70)
        logger.info("EXPERIMENT BATCH COMPLETED")
        logger.info("=" * 70)
        
        total = len(results)
        successful = sum(1 for r in results if r.get('status') == 'SUCCESS')
        failed = total - successful
        
        logger.info(f"Total experiments: {total}")
        logger.info(f"Successful: {successful} ({100*successful/total if total > 0 else 0:.1f}%)")
        logger.info(f"Failed: {failed} ({100*failed/total if total > 0 else 0:.1f}%)")
        
        if successful > 0:
            successful_results = [r for r in results if r.get('status') == 'SUCCESS']
            
            avg_service_rate = sum(r.get('service_rate', 0) for r in successful_results) / successful
            avg_wait_time = sum(r.get('avg_wait_time', 0) for r in successful_results) / successful
            avg_total_time = sum(r.get('avg_total_time', 0) for r in successful_results) / successful
            total_runtime = sum(r.get('runtime_seconds', 0) for r in successful_results)
            
            logger.info("")
            logger.info("Aggregate Statistics (successful experiments):")
            logger.info(f"  Average service rate: {avg_service_rate:.2f}%")
            logger.info(f"  Average wait time: {avg_wait_time:.1f}s ({avg_wait_time/60:.1f} min)")
            logger.info(f"  Average total time: {avg_total_time:.1f}s ({avg_total_time/60:.1f} min)")
            logger.info(f"  Total runtime: {total_runtime:.1f}s ({total_runtime/60:.1f} min)")
        
        logger.info("")
        logger.info(f"Results saved to: {self.summary_file}")
        logger.info(f"Minibus occupancy summary saved to: {self.minibus_occupancy_summary_file}")
        logger.info("=" * 70)
    
    def dry_run(self) -> None:
        """Preview all experiments without running them."""
        experiments = self.generate_experiment_configs()
        
        print("=" * 70)
        print(f"DRY RUN: Preview of {len(experiments)} experiments")
        print("=" * 70)
        print()
        
        for exp_config in experiments:
            print(f"Experiment {exp_config['exp_id']:3d}: {exp_config['exp_name']}")
            print(f"  Minibuses: {exp_config['num_minibuses']}, "
                  f"Capacity: {exp_config['minibus_capacity']}, "
                  f"Ratio: {exp_config['minibus_ratio']}, "
                  f"Optimization Interval: {exp_config['optimization_interval']}s")
            print(f"  Output: {exp_config['output_dir']}")
            print()
        
        print("=" * 70)
        print(f"Total: {len(experiments)} experiments")
        print("=" * 70)


def main():
    """Main entry point for the experiment runner."""
    parser = argparse.ArgumentParser(
        description='Run automated experiments for minibus ratio analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--resume', action='store_true',
                       help='Resume from last checkpoint (skip completed experiments)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview experiments without running them')
    parser.add_argument('--output-dir', type=str, default='batch_results/Minibus_ratio_results',
                       help='Base directory for experiment results (default: Minibus_ratio_results)')
    
    args = parser.parse_args()
    
    runner = ExperimentRunner(output_base_dir=args.output_dir)
    
    if args.dry_run:
        runner.dry_run()
    else:
        try:
            runner.run_all_experiments(resume=args.resume)
        except KeyboardInterrupt:
            logger.warning("\n⚠ Interrupted by user")
            logger.info("Progress has been saved. Use --resume to continue.")
            runner.restore_config()
            return 1
        except Exception as e:
            logger.error(f"\n✗ Fatal error: {e}", exc_info=True)
            runner.restore_config()
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())