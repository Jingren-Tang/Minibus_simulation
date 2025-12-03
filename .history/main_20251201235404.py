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


def build_config_dict(cmd_overrides):
    """
    Build configuration dictionary from config module and command line overrides.
    
    Args:
        cmd_overrides: Dictionary containing command line parameter overrides
        
    Returns:
        dict: Complete configuration dictionary
    """
    # Start with the configuration from config.py
    config_dict = config.get_config()
    
    # Apply command line overrides
    if 'output_dir' in cmd_overrides:
        config_dict['output_dir'] = cmd_overrides['output_dir']
        
    if 'start_time' in cmd_overrides:
        config_dict['simulation_start_time'] = cmd_overrides['start_time']
        
    if 'end_time' in cmd_overrides:
        config_dict['simulation_end_time'] = cmd_overrides['end_time']
    
    if 'date' in cmd_overrides:
        config_dict['simulation_date'] = cmd_overrides['date']
    
    return config_dict


def validate_config(config_dict):
    """
    Validate the simulation configuration.
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        bool: True if valid, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Check required fields
    required_fields = ['simulation_start_time', 'simulation_end_time', 'simulation_date']
    for field in required_fields:
        if field not in config_dict:
            logger.error(f"Missing required configuration field: {field}")
            return False
    
    # Validate time range
    start_time_str = config_dict['simulation_start_time']
    end_time_str = config_dict['simulation_end_time']
    date_str = config_dict['simulation_date']
    
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


def print_config_summary(config_dict):
    """
    Print configuration summary.
    
    Args:
        config_dict: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    
    logger.info("Configuration Summary:")
    logger.info(f"  Simulation Date: {config_dict['simulation_date']}")
    logger.info(f"  Start Time: {config_dict['simulation_start_time']}")
    logger.info(f"  End Time: {config_dict['simulation_end_time']}")
    logger.info(f"  Number of Buses: {config_dict['num_buses']}")
    logger.info(f"  Bus Capacity: {config_dict['bus_capacity']}")
    logger.info(f"  Number of Minibuses: {config_dict['num_minibuses']}")
    logger.info(f"  Minibus Capacity: {config_dict['minibus_capacity']}")
    logger.info(f"  Optimization Interval: {config_dict['optimization_interval']}s")
    logger.info(f"  Output Directory: {config_dict['output_dir']}")
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
        
        # Build command line overrides dictionary
        cmd_overrides = {}
        
        if args.output_dir:
            cmd_overrides['output_dir'] = args.output_dir
            
        if args.start_time:
            # Validate time format HH:MM:SS
            try:
                datetime.strptime(args.start_time, '%H:%M:%S')
                cmd_overrides['start_time'] = args.start_time
            except ValueError:
                logger.error(f"Invalid start time format: {args.start_time} (expected HH:MM:SS)")
                return 1
                
        if args.end_time:
            # Validate time format HH:MM:SS
            try:
                datetime.strptime(args.end_time, '%H:%M:%S')
                cmd_overrides['end_time'] = args.end_time
            except ValueError:
                logger.error(f"Invalid end time format: {args.end_time} (expected HH:MM:SS)")
                return 1
        
        if args.date:
            # Validate date format YYYY-MM-DD
            try:
                datetime.strptime(args.date, '%Y-%m-%d')
                cmd_overrides['date'] = args.date
            except ValueError:
                logger.error(f"Invalid date format: {args.date} (expected YYYY-MM-DD)")
                return 1
        
        # Build complete configuration dictionary
        logger.info("Building configuration...")
        config_dict = build_config_dict(cmd_overrides)
        
        # Log any overrides applied
        if cmd_overrides:
            logger.info("Applied configuration overrides:")
            for key, value in cmd_overrides.items():
                logger.info(f"  {key} = {value}")
        
        # Validate configuration
        if not validate_config(config_dict):
            logger.error("Configuration validation failed")
            return 1
        
        # Print configuration summary
        print_config_summary(config_dict)
        
        # Log simulation start
        logger.info("=" * 60)
        logger.info("Starting traffic simulation...")
        logger.info(f"Real start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # Create and initialize simulation engine
        # Pass the configuration dictionary to SimulationEngine
        logger.info("Initializing simulation engine...")
        engine = SimulationEngine(config_dict)
        
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