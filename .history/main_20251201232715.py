"""
Traffic Simulation System - Main Entry Point

This module serves as the main entry point for the traffic simulation system.
It handles configuration loading, engine initialization, and simulation execution.
"""

import sys
import logging
import argparse
from datetime import datetime, timedelta
import time
import os

from simulation.engine import SimulationEngine
import config


def setup_logging(log_level=None, log_file=None):
    """
    Configure the logging system with both file and console handlers.
    
    Args:
        log_level: Override log level from config
        log_file: Override log file path from config
    """
    level = log_level or config.LOG_LEVEL
    file_path = log_file or config.LOG_FILE
    
    # Create formatters
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    try:
        file_handler = logging.FileHandler(file_path, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Failed to create log file handler: {e}")


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Traffic Simulation System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file (optional, defaults to config.py)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for simulation results (overrides config)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (overrides config)'
    )
    
    parser.add_argument(
        '--start-time',
        type=str,
        help='Simulation start time in format HH:MM:SS (overrides config)'
    )
    
    parser.add_argument(
        '--end-time',
        type=str,
        help='Simulation end time in format HH:MM:SS (overrides config)'
    )
    
    parser.add_argument(
        '--date',
        type=str,
        help='Simulation date in format YYYY-MM-DD (overrides config)'
    )
    
    return parser.parse_args()


def apply_config_overrides(sim_config):
    """
    Apply configuration overrides to the config module.
    This directly modifies the config module's attributes.
    
    Args:
        sim_config: Dictionary containing configuration overrides
    """
    logger = logging.getLogger(__name__)
    
    if 'output_dir' in sim_config:
        config.OUTPUT_DIR = sim_config['output_dir']
        logger.info(f"Override: OUTPUT_DIR = {sim_config['output_dir']}")
        
    if 'start_time' in sim_config:
        config.SIMULATION_START_TIME = sim_config['start_time']
        logger.info(f"Override: SIMULATION_START_TIME = {sim_config['start_time']}")
        
    if 'end_time' in sim_config:
        config.SIMULATION_END_TIME = sim_config['end_time']
        logger.info(f"Override: SIMULATION_END_TIME = {sim_config['end_time']}")
    
    if 'date' in sim_config:
        config.SIMULATION_DATE = sim_config['date']
        logger.info(f"Override: SIMULATION_DATE = {sim_config['date']}")


def validate_config(sim_config):
    """
    Validate the simulation configuration.
    
    Args:
        sim_config: Configuration dictionary
        
    Returns:
        bool: True if valid, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Check required fields from config module
    required_fields = ['SIMULATION_START_TIME', 'SIMULATION_END_TIME', 'SIMULATION_DATE']
    for field in required_fields:
        if not hasattr(config, field):
            logger.error(f"Missing required configuration field: {field}")
            return False
    
    # Validate time range
    start_time_str = sim_config.get('start_time', config.SIMULATION_START_TIME)
    end_time_str = sim_config.get('end_time', config.SIMULATION_END_TIME)
    date_str = sim_config.get('date', config.SIMULATION_DATE)
    
    try:
        # Parse times
        start_time = datetime.strptime(f"{date_str} {start_time_str}", '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(f"{date_str} {end_time_str}", '%Y-%m-%d %H:%M:%S')
        
        if start_time >= end_time:
            logger.error("Start time must be before end time")
            return False
    except ValueError as e:
        logger.error(f"Invalid time format: {e}")
        return False
    
    # Run config module validation
    if not config.validate_config():
        logger.error("Configuration validation failed")
        return False
    
    return True


def print_welcome():
    """Print welcome banner."""
    print("=" * 60)
    print("    Traffic Simulation System")
    print("=" * 60)
    print()


def print_config_summary(sim_config):
    """
    Print configuration summary.
    
    Args:
        sim_config: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    
    start_time = sim_config.get('start_time', config.SIMULATION_START_TIME)
    end_time = sim_config.get('end_time', config.SIMULATION_END_TIME)
    date = sim_config.get('date', config.SIMULATION_DATE)
    
    logger.info("Configuration Summary:")
    logger.info(f"  Simulation Date: {date}")
    logger.info(f"  Start Time: {start_time}")
    logger.info(f"  End Time: {end_time}")
    logger.info(f"  Number of Buses: {config.NUM_BUSES}")
    logger.info(f"  Bus Capacity: {config.BUS_CAPACITY}")
    logger.info(f"  Number of Minibuses: {config.NUM_MINIBUSES}")
    logger.info(f"  Minibus Capacity: {config.MINIBUS_CAPACITY}")
    logger.info(f"  Optimization Interval: {config.OPTIMIZATION_INTERVAL}s")
    logger.info(f"  Output Directory: {sim_config.get('output_dir', config.OUTPUT_DIR)}")
    logger.info(f"  Log Level: {logging.getLevelName(logger.getEffectiveLevel())}")
    print()


def main():
    """
    Main entry point for the traffic simulation system.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    # Record start time
    real_start_time = time.time()
    
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Setup logging
        log_level = getattr(logging, args.log_level) if args.log_level else None
        setup_logging(log_level=log_level)
        
        logger = logging.getLogger(__name__)
        
        # Print welcome message
        print_welcome()
        
        # Build configuration from config.py and command line arguments
        sim_config = {}
        
        if args.output_dir:
            sim_config['output_dir'] = args.output_dir
            
        if args.start_time:
            # Validate time format HH:MM:SS
            try:
                datetime.strptime(args.start_time, '%H:%M:%S')
                sim_config['start_time'] = args.start_time
            except ValueError:
                logger.error(f"Invalid start time format: {args.start_time} (expected HH:MM:SS)")
                return 1
                
        if args.end_time:
            # Validate time format HH:MM:SS
            try:
                datetime.strptime(args.end_time, '%H:%M:%S')
                sim_config['end_time'] = args.end_time
            except ValueError:
                logger.error(f"Invalid end time format: {args.end_time} (expected HH:MM:SS)")
                return 1
        
        if args.date:
            # Validate date format YYYY-MM-DD
            try:
                datetime.strptime(args.date, '%Y-%m-%d')
                sim_config['date'] = args.date
            except ValueError:
                logger.error(f"Invalid date format: {args.date} (expected YYYY-MM-DD)")
                return 1
        
        # Validate configuration
        if not validate_config(sim_config):
            logger.error("Configuration validation failed")
            return 1
        
        # Apply configuration overrides to config module
        if sim_config:
            logger.info("Applying configuration overrides...")
            apply_config_overrides(sim_config)
        
        # Print configuration summary
        print_config_summary(sim_config)
        
        # Log simulation start
        logger.info("=" * 60)
        logger.info("Starting traffic simulation...")
        logger.info(f"Real start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # Create and initialize simulation engine
        logger.info("Initializing simulation engine...")
        engine = SimulationEngine()
        
        # Initialize the engine
        engine.initialize()
        logger.info("Simulation engine initialized successfully")
        
        # Run the simulation
        logger.info("Running simulation...")
        engine.run()
        
        # Calculate and log execution time
        real_end_time = time.time()
        total_time = real_end_time - real_start_time
        
        logger.info("=" * 60)
        logger.info("Simulation completed successfully!")
        logger.info(f"Real end time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
        logger.info("=" * 60)
        
        print()
        print("=" * 60)
        print(f"✓ Simulation completed successfully!")
        print(f"  Total execution time: {total_time:.2f} seconds")
        print("=" * 60)
        
        return 0
        
    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.warning("\nSimulation interrupted by user")
        print("\n⚠ Simulation interrupted by user")
        return 1
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Fatal error during simulation: {e}")
        print(f"\n✗ Fatal error: {e}")
        print("  Check log file for details")
        return 1
        
    finally:
        # Log final message
        try:
            logger = logging.getLogger(__name__)
            logger.info("Simulation system shutdown")
        except:
            pass


if __name__ == "__main__":
    sys.exit(main())