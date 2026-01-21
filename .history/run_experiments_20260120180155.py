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
    
    def __init__(self, output_base_dir: str = "Minibus_ratio_results_5"):
        """
        Initialize the experiment runner.
        
        Args:
            output_base_dir: Base directory for all experiment results
        """
        self.output_base_dir = Path(output_base_dir)
        self.config_backup_path = self.output_base_dir / "config_backup.py"
        self.summary_file = self.output_base_dir / "experiment_summary.csv"
        self.progress_file = self.output_base_dir / "experiment_log.json"
        
        # Experiment parameters - UPDATED WITH OPTIMIZATION_INTERVAL
        self.num_minibuses_values = [2, 3]
        self.minibus_capacity_values = [6, 8]  # Changed from [6, 8]
        self.minibus_ratio_values =  [0.1,0.2,0.3]  # Changed from [0.1, 0.2, 0.3]
        self.optimization_interval_values = [30, 60, 120, 300, 450]  # Optimization interval in seconds (1min, 2min, 5min, 10min)
        
        # Execution settings
        self.timeout_seconds =  3000
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
        """
        Generate all experiment configurations.
        
        Returns:
            List of experiment configuration dictionaries
        """
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
        
        # Create base directory
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup original config if not already backed up
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
        """
        Modify config.py with experiment parameters.
        
        Args:
            exp_config: Experiment configuration dictionary
        """
        logger.info(f"Modifying config.py for experiment {exp_config['exp_id']}...")
        
        try:
            # Read original config
            with open("config.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            num_minibuses = exp_config["num_minibuses"]
            
            # Modify parameters using regex
            # NUM_MINIBUSES
            content = re.sub(
                r'NUM_MINIBUSES\s*=\s*\d+',
                f'NUM_MINIBUSES = {num_minibuses}',
                content
            )
            
            # MINIBUS_CAPACITY
            content = re.sub(
                r'MINIBUS_CAPACITY\s*=\s*\d+',
                f'MINIBUS_CAPACITY = {exp_config["minibus_capacity"]}',
                content
            )
            
            # MINIBUS_PASSENGER_RATIO
            content = re.sub(
                r'MINIBUS_PASSENGER_RATIO\s*=\s*[\d.]+',
                f'MINIBUS_PASSENGER_RATIO = {exp_config["minibus_ratio"]}',
                content
            )
            
            # OPTIMIZATION_INTERVAL (UPDATED)
            content = re.sub(
                r'OPTIMIZATION_INTERVAL\s*=\s*\d+',
                f'OPTIMIZATION_INTERVAL = {exp_config["optimization_interval"]}',
                content
            )
            
            # OUTPUT_DIR (escape backslashes for Windows)
            output_dir_escaped = exp_config["output_dir"].replace("\\", "/")
            content = re.sub(
                r'OUTPUT_DIR\s*=\s*["\'].*?["\']',
                f'OUTPUT_DIR = "{output_dir_escaped}"',
                content
            )
            
            # PASSENGER_ALLOCATION_STRATEGY (force to "fixed")
            content = re.sub(
                r'PASSENGER_ALLOCATION_STRATEGY\s*=\s*["\'].*?["\']',
                'PASSENGER_ALLOCATION_STRATEGY = "fixed"',
                content
            )
            
            # ENABLE_MINIBUS (ensure it's True)
            content = re.sub(
                r'ENABLE_MINIBUS\s*=\s*\w+',
                'ENABLE_MINIBUS = True',
                content
            )
            
            # ===================================================================
            # CRITICAL FIX: Update MINIBUS_INITIAL_LOCATIONS to match NUM_MINIBUSES
            # ===================================================================
            # Generate location list matching the number of minibuses
            # Use the first station ID from the original config or "random"
            
            # Try to extract existing initial location
            match = re.search(r'MINIBUS_INITIAL_LOCATIONS\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if match:
                # Extract first location if list format
                locations_str = match.group(1).strip()
                if locations_str:
                    # Get first location
                    first_loc = locations_str.split(',')[0].strip().strip('"\'')
                    # Create list with num_minibuses copies
                    new_locations = ', '.join([f'"{first_loc}"'] * num_minibuses)
                else:
                    # Default to "random"
                    new_locations = '"random"' if num_minibuses == 0 else ', '.join(['"8592374"'] * num_minibuses)
            else:
                # If not found, use default
                new_locations = ', '.join(['"8592374"'] * num_minibuses)
            
            # Replace MINIBUS_INITIAL_LOCATIONS
            content = re.sub(
                r'MINIBUS_INITIAL_LOCATIONS\s*=\s*\[.*?\]',
                f'MINIBUS_INITIAL_LOCATIONS = [{new_locations}]',
                content,
                flags=re.DOTALL
            )
            # ===================================================================
            
            # Write modified config
            with open("config.py", 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Config modified: n={num_minibuses}, "
                    f"c={exp_config['minibus_capacity']}, "
                    f"r={exp_config['minibus_ratio']}, "
                    f"opt={exp_config['optimization_interval']}s, "
                    f"locations=[{new_locations}]")
        
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
        """
        Run a single simulation experiment.
        
        Args:
            exp_config: Experiment configuration
        
        Returns:
            Tuple of (success, error_message, runtime_seconds)
        """
        logger.info("=" * 70)
        logger.info(f"Running Experiment {exp_config['exp_id']}/{self.get_total_experiments()}: "
                   f"{exp_config['exp_name']}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        try:
            # Run main.py as subprocess
            result = subprocess.run(
                [sys.executable, "main.py"],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            
            runtime = time.time() - start_time
            
            # Check return code
            if result.returncode == 0:
                logger.info(f"✓ Experiment {exp_config['exp_id']} completed successfully "
                          f"in {runtime:.1f}s")
                return True, None, runtime
            else:
                error_msg = f"Non-zero exit code: {result.returncode}"
                logger.error(f"✗ Experiment {exp_config['exp_id']} failed: {error_msg}")
                logger.error(f"STDERR: {result.stderr[:500]}")  # Log first 500 chars
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
        """
        Extract performance metrics from CSV output files.
        
        Args:
            result_dir: Directory containing simulation output CSVs
        
        Returns:
            Dictionary of extracted metrics
        """
        logger.info(f"Extracting metrics from {result_dir}...")
        
        try:
            metrics = {}
            
            # Load passengers.csv
            passengers_file = Path(result_dir) / "passengers.csv"
            if not passengers_file.exists():
                logger.error(f"passengers.csv not found in {result_dir}")
                return None
            
            passengers_df = pd.read_csv(passengers_file)
            
            # Basic passenger statistics
            total = len(passengers_df)
            arrived = len(passengers_df[passengers_df['status'] == 'ARRIVED'])
            abandoned = len(passengers_df[passengers_df['status'] == 'ABANDONED'])
            
            metrics['total_passengers'] = total
            metrics['service_rate'] = (arrived / total * 100) if total > 0 else 0.0
            metrics['abandoned_count'] = abandoned
            
            # ===================================================================
            # ENHANCED: Total wait time, travel time, and combined total time
            # ===================================================================
            
            # Wait time statistics (including all passengers)
            valid_wait_times = passengers_df['wait_time'].dropna()
            
            if len(valid_wait_times) > 0:
                metrics['avg_wait_time'] = float(valid_wait_times.mean())
                metrics['total_wait_time'] = float(valid_wait_times.sum())
                metrics['total_wait_time_hours'] = float(valid_wait_times.sum() / 3600)
            else:
                metrics['avg_wait_time'] = 0.0
                metrics['total_wait_time'] = 0.0
                metrics['total_wait_time_hours'] = 0.0
            
            # Travel time statistics (including all passengers)
            valid_travel_times = passengers_df['travel_time'].dropna()
            
            if len(valid_travel_times) > 0:
                metrics['avg_travel_time'] = float(valid_travel_times.mean())
                metrics['total_travel_time'] = float(valid_travel_times.sum())
                metrics['total_travel_time_hours'] = float(valid_travel_times.sum() / 3600)
            else:
                metrics['avg_travel_time'] = 0.0
                metrics['total_travel_time'] = 0.0
                metrics['total_travel_time_hours'] = 0.0
            
            # Total time = wait time + travel time for each passenger
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
            
            # ===================================================================
            
            # Load vehicles.csv
            vehicles_file = Path(result_dir) / "vehicles.csv"
            if vehicles_file.exists():
                vehicles_df = pd.read_csv(vehicles_file)
                
                metrics['total_passengers_served'] = int(vehicles_df['total_passengers'].sum())
                metrics['avg_vehicle_occupancy'] = float(vehicles_df['avg_occupancy'].mean())
                
                # Separate by vehicle type
                bus_df = vehicles_df[vehicles_df['type'] == 'Bus']
                minibus_df = vehicles_df[vehicles_df['type'] == 'Minibus']
                
                metrics['bus_avg_occupancy'] = float(bus_df['avg_occupancy'].mean()) if len(bus_df) > 0 else 0.0
                metrics['minibus_avg_occupancy'] = float(minibus_df['avg_occupancy'].mean()) if len(minibus_df) > 0 else 0.0
            else:
                logger.warning(f"vehicles.csv not found in {result_dir}")
                metrics['total_passengers_served'] = 0
                metrics['avg_vehicle_occupancy'] = 0.0
                metrics['bus_avg_occupancy'] = 0.0
                metrics['minibus_avg_occupancy'] = 0.0
            
            logger.info(f"Metrics extracted: service_rate={metrics['service_rate']:.1f}%, "
                       f"avg_wait={metrics['avg_wait_time']:.1f}s, "
                       f"total_wait={metrics['total_wait_time_hours']:.2f}h, "
                       f"total_travel={metrics['total_travel_time_hours']:.2f}h, "
                       f"total_time={metrics['total_total_time_hours']:.2f}h")
            
            return metrics
        
        except Exception as e:
            logger.error(f"Error extracting metrics: {e}", exc_info=True)
            return None
    
    def run_all_experiments(self, resume: bool = False) -> None:
        """
        Run all experiments in sequence.
        
        Args:
            resume: If True, skip already completed experiments
        """
        # Setup
        self.setup_directories()
        
        if resume:
            self.load_progress()
        
        # Generate experiment configurations
        experiments = self.generate_experiment_configs()
        
        logger.info("=" * 70)
        logger.info(f"STARTING EXPERIMENT BATCH")
        logger.info(f"Total experiments: {len(experiments)}")
        logger.info(f"Already completed: {len(self.completed_experiments)}")
        logger.info(f"Remaining: {len(experiments) - len(self.completed_experiments)}")
        logger.info("=" * 70)
        
        # Initialize results list
        all_results = []
        
        # Run experiments
        for exp_config in experiments:
            exp_name = exp_config['exp_name']
            
            # Skip if already completed
            if resume and exp_name in self.completed_experiments:
                logger.info(f"Skipping experiment {exp_config['exp_id']} (already completed)")
                
                # Try to load existing results
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
                
                continue
            
            # Modify config
            try:
                self.modify_config(exp_config)
            except Exception as e:
                logger.error(f"Failed to modify config for experiment {exp_config['exp_id']}: {e}")
                if self.stop_on_failure:
                    logger.error("Stopping due to failure (stop_on_failure=True)")
                    break
                continue
            
            # Run simulation
            success, error_msg, runtime = self.run_simulation(exp_config)
            
            # Extract metrics if successful
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
                    
                    # Mark as completed
                    self.completed_experiments.add(exp_name)
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
            
            # Save progress
            self.save_progress()
            
            # Stop on failure if configured
            if not success and self.stop_on_failure:
                logger.error("=" * 70)
                logger.error("STOPPING: Experiment failed and stop_on_failure=True")
                logger.error("=" * 70)
                break
        
        # Restore original config
        self.restore_config()
        
        # Save summary
        if all_results:
            self.save_summary(all_results)
        
        # Print final summary
        self.print_final_summary(all_results)
    
    def save_summary(self, results: List[Dict]) -> None:
        """
        Save experiment summary to CSV.
        
        Args:
            results: List of result dictionaries
        """
        logger.info(f"Saving experiment summary to {self.summary_file}...")
        
        try:
            df = pd.DataFrame(results)
            
            # Reorder columns for better readability - UPDATED with optimization_interval
            column_order = [
                'exp_id', 'exp_name', 'status', 
                'num_minibuses', 'minibus_capacity', 'minibus_ratio', 'optimization_interval',
                'total_passengers', 'service_rate', 'abandoned_count',
                'avg_wait_time', 'total_wait_time', 'total_wait_time_hours',
                'avg_travel_time', 'total_travel_time', 'total_travel_time_hours',
                'avg_total_time', 'total_total_time', 'total_total_time_hours',
                'total_passengers_served',
                'avg_vehicle_occupancy', 'bus_avg_occupancy', 'minibus_avg_occupancy',
                'runtime_seconds', 'error_message'
            ]
            
            # Only include columns that exist
            existing_columns = [col for col in column_order if col in df.columns]
            df = df[existing_columns]
            
            # Save to CSV
            df.to_csv(self.summary_file, index=False, float_format='%.4f')
            
            logger.info(f"✓ Summary saved: {len(results)} experiments")
            logger.info(f"  Location: {self.summary_file}")
        
        except Exception as e:
            logger.error(f"Failed to save summary: {e}", exc_info=True)
    
    def print_final_summary(self, results: List[Dict]) -> None:
        """
        Print final summary of all experiments.
        
        Args:
            results: List of result dictionaries
        """
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
            # Calculate aggregate statistics
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
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint (skip completed experiments)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview experiments without running them'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='Minibus_ratio_results',
        help='Base directory for experiment results (default: Minibus_ratio_results)'
    )
    
    args = parser.parse_args()
    
    # Create runner
    runner = ExperimentRunner(output_base_dir=args.output_dir)
    
    # Execute
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