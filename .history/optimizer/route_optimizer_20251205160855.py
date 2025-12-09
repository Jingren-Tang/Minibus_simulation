"""
optimizer/route_optimizer.py

Route optimizer interface for the mixed traffic simulation system.
Provides a bridge between the simulation engine and external optimization algorithms.
"""

import logging
import json
import subprocess
import tempfile
import importlib
import os
from typing import Dict, List, Optional, Any
from pathlib import Path


# Configure logger
logger = logging.getLogger(__name__)


class OptimizerError(Exception):
    """Raised when optimizer fails to execute or produces invalid output."""
    pass


class RouteOptimizer:
    """
    Interface to communicate with external route optimization algorithms.
    
    Supports multiple optimizer types:
    - 'dummy': Simple greedy strategy for testing
    - 'external_program': Call external executable/script
    - 'python_module': Import and call Python module
    
    Attributes:
        optimizer_type (str): Type of optimizer to use
        config (dict): Configuration for the optimizer
        logger (logging.Logger): Logger instance
        _module: Cached Python module (for 'python_module' type)
        _function: Cached function reference (for 'python_module' type)
    """
    
    def __init__(self, optimizer_type: str, config: dict):
        """
        Initialize the RouteOptimizer.
        
        Args:
            optimizer_type: One of 'dummy', 'external_program', 'python_module'
            config: Configuration dict with optimizer-specific settings
                For 'external_program':
                    - 'program_path': Path to executable
                    - 'timeout': Max execution time (seconds), default 30
                For 'python_module':
                    - 'module_name': Module to import
                    - 'function_name': Function to call
                For 'dummy':
                    - No additional config needed
                    
        Raises:
            ValueError: If optimizer_type is not supported
        """
        # Validate optimizer type
        valid_types = ['dummy', 'external_program', 'python_module']
        if optimizer_type not in valid_types:
            raise ValueError(
                f"Unsupported optimizer_type: {optimizer_type}. "
                f"Must be one of {valid_types}"
            )
        
        self.optimizer_type = optimizer_type
        self.config = config
        
        # For python_module type, cache the module and function
        self._module = None
        self._function = None
        
        logger.info(f"RouteOptimizer initialized with type: {optimizer_type}")
        logger.debug(f"Configuration: {config}")
        
        # Validate configuration based on optimizer type
        self._validate_config()
    
    def _validate_config(self) -> None:
        """
        Validate configuration based on optimizer type.
        
        Raises:
            ValueError: If required configuration is missing
        """
        if self.optimizer_type == 'external_program':
            if 'program_path' not in self.config:
                raise ValueError("'program_path' is required for external_program optimizer")
            
            program_path = self.config['program_path']
            if not os.path.exists(program_path):
                logger.warning(f"Program path does not exist: {program_path}")
            
            # Set default timeout if not provided
            if 'timeout' not in self.config:
                self.config['timeout'] = 30
                logger.info(f"Using default timeout: {self.config['timeout']}s")
        
        elif self.optimizer_type == 'python_module':
            if 'module_name' not in self.config:
                raise ValueError("'module_name' is required for python_module optimizer")
            if 'function_name' not in self.config:
                raise ValueError("'function_name' is required for python_module optimizer")
        
        # 'dummy' type requires no additional configuration
    
    def optimize(
        self,
        pending_requests: List['Passenger'],
        minibus_states: List[Dict],
        network: 'TransitNetwork',
        current_time: float
    ) -> Dict[str, List[Dict]]:
        """
        Main optimization method.
        
        Takes current simulation state and returns new route plans for all minibuses.
        
        Args:
            pending_requests: List of unassigned Passenger objects
            minibus_states: List of dicts with current minibus states
            network: TransitNetwork for station information
            current_time: Current simulation time
            
        Returns:
            Dict mapping minibus_id to new route_plan
            Example: {"M1": [...], "M2": [...], "M3": []}
            Each route plan is a list of stops:
                {"station_id": "A", "action": "PICKUP", "passenger_ids": ["P1", "P2"]}
            
        Raises:
            OptimizerError: If optimization fails
        """
        logger.info(
            f"Starting optimization at time {current_time:.1f}s: "
            f"{len(pending_requests)} pending requests, "
            f"{len(minibus_states)} minibuses"
        )
        
        try:
            # Step 1: Prepare input data
            input_data = self._prepare_input(
                pending_requests=pending_requests,
                minibus_states=minibus_states,
                network=network,
                current_time=current_time
            )
            
            logger.debug(f"Input data prepared: {len(input_data['pending_requests'])} requests")
            
            # Step 2: Call appropriate optimizer
            if self.optimizer_type == 'dummy':
                output = self._call_dummy_optimizer(input_data)
            elif self.optimizer_type == 'external_program':
                output = self._call_external_program(input_data)
            elif self.optimizer_type == 'python_module':
                output = self._call_python_module(input_data)
            else:
                raise OptimizerError(f"Unknown optimizer type: {self.optimizer_type}")
            
            # Step 3: Validate output
            if not self._validate_output(output):
                logger.error("Optimizer output validation failed")
                raise OptimizerError("Invalid optimizer output format")
            
            logger.info(f"Optimization completed successfully")
            return output
        
        except OptimizerError:
            # Re-raise OptimizerError
            raise
        
        except Exception as e:
            logger.error(f"Optimization failed: {e}", exc_info=True)
            
            # Return empty plans for all minibuses (keep current state)
            logger.warning("Returning empty plans due to optimization failure")
            return {mb['minibus_id']: [] for mb in minibus_states}
    
    def _prepare_input(
        self,
        pending_requests: List['Passenger'],
        minibus_states: List[Dict],
        network: 'TransitNetwork',
        current_time: float
    ) -> dict:
        """
        Format simulation state into optimizer input format.
        
        Converts Passenger objects and Minibus states into JSON-serializable dict.
        
        Args:
            pending_requests: List of Passenger objects
            minibus_states: List of minibus state dicts
            network: TransitNetwork instance
            current_time: Current simulation time
            
        Returns:
            Dict in the format expected by optimizers:
            {
                "current_time": float,
                "pending_requests": [...],
                "minibuses": [...],
                "stations": [...]
            }
        """
        # Convert pending requests (Passenger objects to dicts)
        pending_requests_data = []
        for passenger in pending_requests:
            pending_requests_data.append({
                "passenger_id": passenger.passenger_id,
                "origin": passenger.origin_station_id,
                "destination": passenger.destination_station_id,
                "appear_time": passenger.appear_time,
                "wait_time": current_time - passenger.appear_time
            })
        
        # Get all station IDs from network
        stations = list(network.stations.keys())
        
        # Construct input data
        input_data = {
            "current_time": current_time,
            "pending_requests": pending_requests_data,
            "minibuses": minibus_states,  # Already in dict format
            "stations": stations
        }
        
        logger.debug(
            f"Prepared input: {len(pending_requests_data)} requests, "
            f"{len(minibus_states)} minibuses, "
            f"{len(stations)} stations"
        )
        
        return input_data
    
    def _validate_output(self, output: Dict[str, List[Dict]]) -> bool:
        """
        Validate optimizer output format.
        
        Checks:
        - Output is a dict
        - All minibus IDs map to lists
        - Each route plan is a list
        - Each stop has required fields: station_id, action, passenger_ids
        - action is either 'PICKUP' or 'DROPOFF'
        - passenger_ids is a list
        
        Args:
            output: Optimizer output to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(output, dict):
            logger.error(f"Output is not a dict: {type(output)}")
            return False
        
        # Check each minibus's route plan
        for minibus_id, route_plan in output.items():
            if not isinstance(route_plan, list):
                logger.error(
                    f"Route plan for {minibus_id} is not a list: {type(route_plan)}"
                )
                return False
            
            # Validate each stop in the route plan
            for stop_idx, stop in enumerate(route_plan):
                if not isinstance(stop, dict):
                    logger.error(
                        f"Stop {stop_idx} for {minibus_id} is not a dict: {type(stop)}"
                    )
                    return False
                
                # Check required fields
                required_fields = ['station_id', 'action', 'passenger_ids']
                for field in required_fields:
                    if field not in stop:
                        logger.error(
                            f"Stop {stop_idx} for {minibus_id} missing field: {field}"
                        )
                        return False
                
                # Validate action
                if stop['action'] not in ['PICKUP', 'DROPOFF']:
                    logger.error(
                        f"Invalid action '{stop['action']}' in stop {stop_idx} "
                        f"for {minibus_id}. Must be 'PICKUP' or 'DROPOFF'"
                    )
                    return False
                
                # Validate passenger_ids
                if not isinstance(stop['passenger_ids'], list):
                    logger.error(
                        f"passenger_ids in stop {stop_idx} for {minibus_id} "
                        f"is not a list: {type(stop['passenger_ids'])}"
                    )
                    return False
        
        logger.debug("Output validation passed")
        return True
    
    def _call_dummy_optimizer(self, input_data: dict) -> dict:
        """
        Simple greedy optimizer for testing.
        
        Strategy:
        1. For each idle minibus (empty route plan), assign closest pending request
        2. Minibuses with existing tasks continue their current plan
        3. Very simple, not optimal, but works for testing
        
        Args:
            input_data: Input data dict with current state
            
        Returns:
            Dict mapping minibus_id to route_plan
        """
        logger.info("Running dummy optimizer (greedy strategy)")
        
        pending_requests = input_data['pending_requests']
        minibuses = input_data['minibuses']
        
        # Initialize output with existing plans
        output = {}
        for mb in minibuses:
            output[mb['minibus_id']] = mb.get('current_route_plan', [])
        
        # Track which passengers have been assigned
        assigned_passengers = set()
        
        # Simple greedy assignment: assign first available request to first idle minibus
        for mb in minibuses:
            mb_id = mb['minibus_id']
            
            # Check if minibus is idle (no current route plan or empty plan)
            current_plan = mb.get('current_route_plan', [])
            if len(current_plan) > 0:
                # Minibus is busy, keep existing plan
                logger.debug(f"{mb_id} is busy with {len(current_plan)} stops")
                continue
            
            # Check if minibus has capacity
            current_occupancy = mb.get('current_occupancy', 0)
            capacity = mb.get('capacity', 6)
            available_capacity = capacity - current_occupancy
            
            if available_capacity <= 0:
                logger.debug(f"{mb_id} is full")
                continue
            
            # Find an unassigned passenger
            assigned = False
            for req in pending_requests:
                pax_id = req['passenger_id']
                
                if pax_id in assigned_passengers:
                    continue
                
                # Assign this passenger to this minibus
                route_plan = [
                    {
                        "station_id": req['origin'],
                        "action": "PICKUP",
                        "passenger_ids": [pax_id]
                    },
                    {
                        "station_id": req['destination'],
                        "action": "DROPOFF",
                        "passenger_ids": [pax_id]
                    }
                ]
                
                output[mb_id] = route_plan
                assigned_passengers.add(pax_id)
                assigned = True
                
                logger.debug(
                    f"Assigned passenger {pax_id} to {mb_id}: "
                    f"{req['origin']} -> {req['destination']}"
                )
                break
            
            if not assigned:
                logger.debug(f"{mb_id} remains idle (no available passengers)")
        
        logger.info(
            f"Dummy optimizer completed: assigned {len(assigned_passengers)} passengers"
        )
        
        return output
    
    def _call_external_program(self, input_data: dict) -> dict:
        """
        Call external optimizer program.
        
        Steps:
        1. Write input_data to temp JSON file
        2. Execute external program with subprocess
        3. Read output from another JSON file
        4. Clean up temp files
        5. Parse and return output
        
        Handles:
        - Timeout
        - Program errors
        - Invalid output format
        
        Args:
            input_data: Input data dict
            
        Returns:
            Dict mapping minibus_id to route_plan
            
        Raises:
            OptimizerError: If external program fails
        """
        logger.info("Calling external optimizer program")
        
        program_path = self.config['program_path']
        timeout = self.config.get('timeout', 30)
        
        # Create temporary files for input and output
        try:
            # Create temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                input_file = os.path.join(temp_dir, 'input.json')
                output_file = os.path.join(temp_dir, 'output.json')
                
                # Write input data to JSON file
                logger.debug(f"Writing input to {input_file}")
                with open(input_file, 'w') as f:
                    json.dump(input_data, f, indent=2)
                
                # Construct command
                # Assume external program takes input_file and output_file as arguments
                command = [program_path, input_file, output_file]
                
                logger.info(f"Executing: {' '.join(command)}")
                
                # Execute external program
                try:
                    result = subprocess.run(
                        command,
                        timeout=timeout,
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        logger.error(f"External program failed with return code {result.returncode}")
                        logger.error(f"STDOUT: {result.stdout}")
                        logger.error(f"STDERR: {result.stderr}")
                        raise OptimizerError(
                            f"External program failed with return code {result.returncode}"
                        )
                    
                    logger.debug(f"External program executed successfully")
                    if result.stdout:
                        logger.debug(f"STDOUT: {result.stdout}")
                
                except subprocess.TimeoutExpired:
                    logger.error(f"External program timed out after {timeout}s")
                    raise OptimizerError(f"External program timed out after {timeout}s")
                
                # Read output file
                if not os.path.exists(output_file):
                    logger.error(f"Output file not found: {output_file}")
                    raise OptimizerError("External program did not produce output file")
                
                logger.debug(f"Reading output from {output_file}")
                with open(output_file, 'r') as f:
                    output_data = json.load(f)
                
                logger.info("External optimizer completed successfully")
                return output_data
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse output JSON: {e}")
            raise OptimizerError(f"Invalid JSON output from external program: {e}")
        
        except Exception as e:
            logger.error(f"Error calling external program: {e}", exc_info=True)
            raise OptimizerError(f"External program error: {e}")
    
    def _call_python_module(self, input_data: dict) -> dict:
        """
        Call Python module optimizer.
        
        Steps:
        1. Import module if not already imported (cached)
        2. Get function reference if not already cached
        3. Call specified function with input_data
        4. Return output
        
        Handles:
        - Import errors
        - Function errors
        - Invalid output
        
        Args:
            input_data: Input data dict
            
        Returns:
            Dict mapping minibus_id to route_plan
            
        Raises:
            OptimizerError: If module import or function call fails
        """
        logger.info("Calling Python module optimizer")
        
        module_name = self.config['module_name']
        function_name = self.config['function_name']
        
        try:
            # Import module (cache it)
            if self._module is None:
                logger.info(f"Importing module: {module_name}")
                self._module = importlib.import_module(module_name)
                logger.info(f"Module {module_name} imported successfully")
            
            # Get function reference (cache it)
            if self._function is None:
                logger.info(f"Getting function: {function_name}")
                if not hasattr(self._module, function_name):
                    raise OptimizerError(
                        f"Function '{function_name}' not found in module '{module_name}'"
                    )
                self._function = getattr(self._module, function_name)
                logger.info(f"Function {function_name} retrieved successfully")
            
            # Call the function
            logger.info(f"Calling {module_name}.{function_name}")
            output_data = self._function(input_data)
            
            logger.info("Python module optimizer completed successfully")
            return output_data
        
        except ImportError as e:
            logger.error(f"Failed to import module '{module_name}': {e}")
            raise OptimizerError(f"Module import error: {e}")
        
        except Exception as e:
            logger.error(f"Error calling Python module: {e}", exc_info=True)
            raise OptimizerError(f"Python module error: {e}")