"""
Traffic Simulation System - Main Entry Point

This module serves as the main entry point for the traffic simulation system.
It handles configuration loading, engine initialization, and simulation execution.
"""

import sys
import logging
import argparse
from datetime import datetime
import time

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
        help='Simulation start time in format YYYY-MM-DD HH:MM:SS (overrides config)'
    )
    
    parser.add_argument(
        '--end-time',
        type=str,
        help='Simulation end time in format YYYY-MM-DD HH:MM:SS (overrides config)'
    )
    
    return parser.parse_args()


def validate_config(sim_config):
    """
    Validate the simulation configuration.
    
    Args:
        sim_config: Configuration dictionary
        
    Returns:
        bool: True if valid, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Check required fields
    required_fields = ['START_TIME', 'END_TIME', 'TIME_STEP']
    for field in required_fields:
        if not hasattr(config, field) and field not in sim_config:
            logger.error(f"Missing required configuration field: {field}")
            return False
    
    # Validate time range
    start_time = sim_config.get('start_time', getattr(config, 'START_TIME', None))
    end_time = sim_config.get('end_time', getattr(config, 'END_TIME', None))
    
    if start_time and end_time:
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            
        if start_time >= end_time:
            logger.error("Start time must be before end time")
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
    
    logger.info("Configuration Summary:")
    logger.info(f"  Start Time: {sim_config.get('start_time', config.START_TIME)}")
    logger.info(f"  End Time: {sim_config.get('end_time', config.END_TIME)}")
    logger.info(f"  Time Step: {getattr(config, 'TIME_STEP', 'N/A')}")
    logger.info(f"  Output Directory: {sim_config.get('output_dir', getattr(config, 'OUTPUT_DIR', 'N/A'))}")
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
            try:
                sim_config['start_time'] = datetime.strptime(args.start_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                logger.error(f"Invalid start time format: {args.start_time}")
                return 1
                
        if args.end_time:
            try:
                sim_config['end_time'] = datetime.strptime(args.end_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                logger.error(f"Invalid end time format: {args.end_time}")
                return 1
        
        # Validate configuration
        if not validate_config(sim_config):
            logger.error("Configuration validation failed")
            return 1
        
        # Print configuration summary
        print_config_summary(sim_config)
        
        # Log simulation start
        logger.info("=" * 60)
        logger.info("Starting traffic simulation...")
        logger.info(f"Real start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # Create and initialize simulation engine
        logger.info("Initializing simulation engine...")
        engine = SimulationEngine(config_override=sim_config)
        
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