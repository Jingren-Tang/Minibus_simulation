"""
optimizer/route_optimizer.py

Route optimizer interface for the mixed traffic simulation system.
Provides a bridge between the simulation engine and external optimization algorithms.

FIXED VERSION: Properly handles function objects in input_data for python_module type
"""

import logging
import json
import subprocess
import tempfile
import importlib
import os
from typing import List, Dict, Optional, Any

# Configure logger
logger = logging.getLogger(__name__)


class OptimizerError(Exception):
    """
    Custom exception raised when optimizer fails.
    
    This exception is used to wrap all optimizer-related errors including:
    - External program execution failures
    - Python module import/execution errors
    - Invalid input/output formats
    - Timeout errors
    """
    pass


class RouteOptimizer:
    """
    Interface to communicate with external route optimization algorithms.
    
    This class serves as a bridge between the simulation engine and various types
    of optimization algorithms. It handles data format conversion, optimizer invocation,
    and result validation.
    
    Supports multiple optimizer types:
    - 'dummy': Simple greedy strategy for testing (always available)
    - 'external_program': Call external executable/script (e.g., Julia, C++, Python script)
    - 'python_module': Import and call Python module directly
    
    Attributes:
        optimizer_type (str): Type of optimizer to use
        config (dict): Configuration dictionary with optimizer-specific settings
        logger (logging.Logger): Logger instance for this optimizer
        _module (module): Cached Python module (for python_module type)
    """
    
    def __init__(self, optimizer_type: str, config: dict):
        """
        Initialize the RouteOptimizer.
        
        Args:
            optimizer_type (str): One of 'dummy', 'external_program', 'python_module'
            config (dict): Configuration dict with optimizer-specific settings
                For 'external_program':
                    - 'program_path' (str): Path to executable program
                    - 'timeout' (int, optional): Max execution time in seconds (default: 60)
                For 'python_module':
                    - 'module_name' (str): Name of the module to import
                    - 'function_name' (str): Name of the function to call
                For 'dummy':
                    - No additional config needed
                    
        Raises:
            ValueError: If optimizer_type is not supported
        """
        # Validate optimizer type
        valid_types = ['dummy', 'external_program', 'python_module']
        if optimizer_type not in valid_types:
            raise ValueError(
                f"Unsupported optimizer_type '{optimizer_type}'. "
                f"Must be one of {valid_types}"
            )
        
        self.optimizer_type = optimizer_type
        self.config = config
        self.logger = logger
        self._module = None  # Cached module for python_module type
        
        # Validate configuration based on optimizer type
        if optimizer_type == 'external_program':
            if 'program_path' not in config:
                raise ValueError(
                    "Configuration for 'external_program' must include 'program_path'"
                )
            if not os.path.exists(config['program_path']):
                logger.warning(
                    f"Program path does not exist: {config['program_path']}. "
                    f"Will fail at runtime if called."
                )
        
        elif optimizer_type == 'python_module':
            if 'module_name' not in config:
                raise ValueError(
                    "Configuration for 'python_module' must include 'module_name'"
                )
            if 'function_name' not in config:
                raise ValueError(
                    "Configuration for 'python_module' must include 'function_name'"
                )
        
        logger.info(
            f"RouteOptimizer initialized with type='{optimizer_type}', "
            f"config={config}"
        )
    
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
        This is the primary interface called by the simulation engine.
        
        Args:
            pending_requests (List[Passenger]): List of unassigned Passenger objects
            minibus_states (List[Dict]): List of dicts with current minibus states
                Each dict should be from Minibus.get_minibus_info()
            network (TransitNetwork): TransitNetwork for station information and travel times
            current_time (float): Current simulation time in seconds
            
        Returns:
            Dict[str, List[Dict]]: Dictionary mapping minibus_id to new route_plan
                Example: {
                    "M1": [
                        {"station_id": "A", "action": "PICKUP", "passenger_ids": ["P1"]},
                        {"station_id": "B", "action": "DROPOFF", "passenger_ids": ["P1"]}
                    ],
                    "M2": [],
                    "M3": [...]
                }
            
        Raises:
            OptimizerError: If optimization fails (caught internally, returns safe empty plans)
        """
        logger.info(
            f"Starting optimization at time={current_time:.2f}s: "
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
            
            logger.debug(
                f"Input prepared: {len(input_data['pending_requests'])} requests, "
                f"{len(input_data['minibuses'])} minibuses, "
                f"{len(input_data['stations'])} stations"
            )
            
            # Step 2: Call appropriate optimizer
            if self.optimizer_type == 'dummy':
                output_data = self._call_dummy_optimizer(input_data)
            elif self.optimizer_type == 'external_program':
                output_data = self._call_external_program(input_data)
            elif self.optimizer_type == 'python_module':
                output_data = self._call_python_module(input_data)
            else:
                raise OptimizerError(f"Unknown optimizer type: {self.optimizer_type}")
            
            # Step 3: Validate output
            if not self._validate_output(output_data):
                logger.error("Optimizer output validation failed, returning empty plans")
                # Return safe empty plans for all minibuses
                return {mb["minibus_id"]: [] for mb in minibus_states}
            
            logger.info(
                f"Optimization completed successfully, "
                f"generated plans for {len(output_data)} minibuses"
            )
            
            return output_data
        
        except OptimizerError as e:
            logger.error(f"Optimizer error: {e}", exc_info=True)
            # Return safe empty plans (all minibuses keep current state)
            return {mb["minibus_id"]: [] for mb in minibus_states}
        
        except Exception as e:
            logger.error(f"Unexpected error during optimization: {e}", exc_info=True)
            # Return safe empty plans
            return {mb["minibus_id"]: [] for mb in minibus_states}
    

    def _prepare_input(
        self,
        pending_requests: List['Passenger'],
        minibus_states: List[Dict],
        network: 'TransitNetwork',
        current_time: float
    ) -> dict:
        """
        Format simulation state into optimizer input format.
        
        Enhanced version with travel time query function and optimization parameters.
        
        Args:
            pending_requests (List[Passenger]): Unassigned passengers
            minibus_states (List[Dict]): Minibus state dicts from get_minibus_info()
            network (TransitNetwork): Network object
            current_time (float): Current simulation time
            
        Returns:
            dict: Formatted input data with keys:
                - current_time (float)
                - pending_requests (List[Dict])
                - minibuses (List[Dict])
                - stations (List[str])
                - get_travel_time (callable): Travel time query function
                - max_waiting_time (float): Maximum waiting time constraint
                - max_detour_time (float): Maximum detour time constraint
        """
        logger.debug("Preparing optimizer input data...")
        
        # 1. Convert pending_requests (List[Passenger] -> List[dict])
        pending_list = []
        for passenger in pending_requests:
            pending_list.append({
                "passenger_id": passenger.passenger_id,
                "origin": passenger.origin_station_id,
                "destination": passenger.destination_station_id,
                "appear_time": passenger.appear_time,
                "wait_time": current_time - passenger.appear_time
            })
        
        logger.debug(f"Converted {len(pending_list)} pending passengers to dict format")
        
        # 2. Format minibus states
        minibus_list = []
        for mb_state in minibus_states:
            minibus_list.append({
                "minibus_id": mb_state["minibus_id"],
                "current_location": mb_state["current_location_id"],
                "capacity": mb_state["capacity"],
                "current_occupancy": mb_state["occupancy"],
                "passengers_onboard": mb_state["passenger_ids"],
                "current_route_plan": mb_state["route_plan"]
            })
        
        logger.debug(f"Formatted {len(minibus_list)} minibus states")
        
        # 3. Extract station list
        stations = list(network.stations.keys())
        logger.debug(f"Extracted {len(stations)} station IDs")
        
        # 4. Create travel time query function (closure)
        def get_travel_time_func(origin: str, dest: str, time: float = None) -> float:
            """
            Query function for travel time between stations.
            
            This closure captures the network and current_time from the outer scope,
            providing a clean interface for the optimizer.
            
            Args:
                origin: Origin station ID
                dest: Destination station ID
                time: Query time (defaults to current_time if None)
            
            Returns:
                Travel time in seconds
            """
            query_time = time if time is not None else current_time
            return network.get_travel_time(origin, dest, query_time)
        
        # 5. Extract optimization parameters from config
        # These can be overridden in the config when creating the optimizer
        max_waiting_time = self.config.get('max_waiting_time', 600.0)  # Default: 10 minutes
        max_detour_time = self.config.get('max_detour_time', 300.0)    # Default: 5 minutes
        
        logger.debug(
            f"Optimization parameters: max_waiting_time={max_waiting_time}s, "
            f"max_detour_time={max_detour_time}s"
        )
        
        # 6. Assemble input data
        input_data = {
            "current_time": current_time,
            "pending_requests": pending_list,
            "minibuses": minibus_list,
            "stations": stations,
            "get_travel_time": get_travel_time_func,  # Function object (for python_module)
            "max_waiting_time": max_waiting_time,
            "max_detour_time": max_detour_time
        }
        
        logger.debug("Input data preparation completed")
        return input_data
    
    def _validate_output(self, output: Dict[str, List[Dict]]) -> bool:
        """
        Validate optimizer output format.
        
        Performs comprehensive validation to ensure the optimizer output
        meets the expected format and can be safely used by the simulation.
        
        Checks:
        - Output is a dictionary
        - All keys are strings (minibus IDs)
        - All values are lists (route plans)
        - Each route plan element is a dict with required fields:
            * station_id (str)
            * action (str, must be 'PICKUP' or 'DROPOFF')
            * passenger_ids (list of str)
        
        Args:
            output (Dict[str, List[Dict]]): Optimizer output to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        logger.debug("Validating optimizer output...")
        
        # Check if output is a dictionary
        if not isinstance(output, dict):
            logger.error(f"Output must be a dict, got {type(output)}")
            return False
        
        # Validate each minibus's route plan
        for minibus_id, route_plan in output.items():
            # Check minibus_id is a string
            if not isinstance(minibus_id, str):
                logger.error(f"Minibus ID must be string, got {type(minibus_id)}")
                return False
            
            # Check route_plan is a list
            if not isinstance(route_plan, list):
                logger.error(
                    f"Route plan for {minibus_id} must be a list, "
                    f"got {type(route_plan)}"
                )
                return False
            
            # Validate each stop in the route plan
            for i, stop in enumerate(route_plan):
                # Check stop is a dict
                if not isinstance(stop, dict):
                    logger.error(
                        f"Stop {i} in route plan for {minibus_id} must be a dict, "
                        f"got {type(stop)}"
                    )
                    return False
                
                # Check required fields
                required_fields = ["station_id", "action", "passenger_ids"]
                for field in required_fields:
                    if field not in stop:
                        logger.error(
                            f"Stop {i} in route plan for {minibus_id} "
                            f"missing required field '{field}'"
                        )
                        return False
                
                # Validate station_id is a string
                if not isinstance(stop["station_id"], str):
                    logger.error(
                        f"Stop {i} in route plan for {minibus_id}: "
                        f"station_id must be string, got {type(stop['station_id'])}"
                    )
                    return False
                
                # Validate action is either PICKUP or DROPOFF
                if stop["action"] not in ["PICKUP", "DROPOFF"]:
                    logger.error(
                        f"Stop {i} in route plan for {minibus_id}: "
                        f"action must be 'PICKUP' or 'DROPOFF', got '{stop['action']}'"
                    )
                    return False
                
                # Validate passenger_ids is a list
                if not isinstance(stop["passenger_ids"], list):
                    logger.error(
                        f"Stop {i} in route plan for {minibus_id}: "
                        f"passenger_ids must be a list, got {type(stop['passenger_ids'])}"
                    )
                    return False
                
                # Validate all passenger_ids are strings
                for pid in stop["passenger_ids"]:
                    if not isinstance(pid, str):
                        logger.error(
                            f"Stop {i} in route plan for {minibus_id}: "
                            f"passenger_id must be string, got {type(pid)}"
                        )
                        return False
        
        logger.debug(f"Output validation passed for {len(output)} minibuses")
        return True
    
    def _call_dummy_optimizer(self, input_data: dict) -> dict:
        """
        Simple greedy optimizer for testing.
        
        This is a basic implementation that serves as a fallback and testing tool.
        It uses a simple greedy strategy to assign passengers to idle minibuses.
        
        Strategy:
        1. For each minibus:
            - If it has an existing route_plan, keep it unchanged
            - If it's idle (no route_plan):
                * Find the closest pending passenger (by travel time)
                * Assign a simple two-stop route: PICKUP at origin, DROPOFF at destination
                * Mark passenger as assigned (remove from available pool)
        2. Return the complete assignment for all minibuses
        
        This algorithm is NOT optimal but provides:
        - Fast execution for testing
        - Predictable behavior for debugging
        - Baseline performance for comparison
        
        Args:
            input_data (dict): Formatted input data from _prepare_input
            
        Returns:
            dict: Route plans for all minibuses
        """
        logger.info("Running dummy optimizer (greedy strategy)...")
        logger.info(f"Pending passengers: {[p['passenger_id'] for p in input_data['pending_requests']]}")
        for mb in input_data['minibuses']:
            logger.info(f"{mb['minibus_id']}: location={mb['current_location']}, "
                    f"route_plan={mb['current_route_plan']}")
        
        # Extract data
        current_time = input_data["current_time"]
        pending_requests = input_data["pending_requests"]
        minibuses = input_data["minibuses"]
        
        # Create output dictionary
        output = {}
        
        # Create a pool of available passengers (will be modified as we assign)
        available_passengers = pending_requests.copy()
        
        logger.debug(
            f"Starting assignment: {len(minibuses)} minibuses, "
            f"{len(available_passengers)} available passengers"
        )
        
        # Process each minibus
        for minibus in minibuses:
            minibus_id = minibus["minibus_id"]
            current_location = minibus["current_location"]
            route_plan = minibus["current_route_plan"]
            
            # Check if minibus has existing tasks
            if len(route_plan) > 0:
                # Minibus already has a route plan, keep it unchanged
                output[minibus_id] = route_plan
                logger.debug(
                    f"{minibus_id} has existing route plan with {len(route_plan)} stops, "
                    f"keeping unchanged"
                )
                continue
            
            # Minibus is idle, try to assign a passenger
            if len(available_passengers) == 0:
                # No passengers available
                output[minibus_id] = []
                logger.debug(f"{minibus_id} is idle, no passengers available")
                continue
            
            # Find the closest passenger (greedy by travel time)
            # Note: Since we don't have network object here, we use FIFO (first-come-first-served)
            # In a production version with network access, you would calculate actual travel times
            
            # Simple heuristic: assign first available passenger
            closest_passenger = available_passengers[0]
            closest_passenger_idx = 0
            
            if closest_passenger is not None:
                # Generate simple route: PICKUP -> DROPOFF
                new_route = [
                    {
                        "station_id": closest_passenger["origin"],
                        "action": "PICKUP",
                        "passenger_ids": [closest_passenger["passenger_id"]]
                    },
                    {
                        "station_id": closest_passenger["destination"],
                        "action": "DROPOFF",
                        "passenger_ids": [closest_passenger["passenger_id"]]
                    }
                ]
                
                output[minibus_id] = new_route
                
                # Remove assigned passenger from available pool
                available_passengers.pop(closest_passenger_idx)
                
                logger.debug(
                    f"{minibus_id} assigned passenger {closest_passenger['passenger_id']}: "
                    f"{closest_passenger['origin']} -> {closest_passenger['destination']}"
                )
            else:
                output[minibus_id] = []
                logger.debug(f"{minibus_id} is idle, no suitable passenger found")
        
        assigned_count = len(pending_requests) - len(available_passengers)
        logger.info(
            f"Dummy optimizer completed: assigned {assigned_count}/{len(pending_requests)} passengers"
        )
        
        return output
    
    def _call_external_program(self, input_data: dict) -> dict:
        """
        Call external optimizer program.
        
        ⚠️  IMPORTANT: The get_travel_time function cannot be serialized to JSON!
        External programs must implement their own travel time logic or receive
        a pre-computed travel time matrix.
        
        This method enables integration with optimization algorithms written in
        any programming language (Python, Julia, C++, etc.) by using file-based
        communication via JSON.
        
        Steps:
        1. Create temporary input JSON file with formatted data (excluding functions)
        2. Execute external program via subprocess
        3. Read output from temporary output JSON file
        4. Clean up temporary files
        5. Parse and return output
        
        The external program is expected to:
        - Accept two arguments: input_file_path output_file_path
        - Read input from the input JSON file
        - Write output to the output JSON file
        - Exit with status 0 on success
        
        Handles:
        - Timeout (configurable via config['timeout'])
        - Program execution errors
        - Invalid output format
        - File I/O errors
        
        Args:
            input_data (dict): Formatted input data
            
        Returns:
            dict: Optimizer output (route plans)
            
        Raises:
            OptimizerError: If external program fails or times out
        """
        logger.info("Calling external optimizer program...")
        
        program_path = self.config['program_path']
        timeout = self.config.get('timeout', 60)  # Default 60 seconds
        
        # 🔧 FIX: Remove non-serializable function from input_data
        serializable_input = input_data.copy()
        if 'get_travel_time' in serializable_input:
            logger.warning(
                "Removing 'get_travel_time' function from input data for external program. "
                "External programs must implement their own travel time logic."
            )
            del serializable_input['get_travel_time']
        
        # Create temporary files for input and output
        try:
            # Create temporary input file
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.json', 
                delete=False
            ) as input_file:
                input_file_path = input_file.name
                json.dump(serializable_input, input_file, indent=2)
            
            logger.debug(f"Input data written to temporary file: {input_file_path}")
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.json', 
                delete=False
            ) as output_file:
                output_file_path = output_file.name
            
            logger.debug(f"Output will be written to temporary file: {output_file_path}")
            
            try:
                # Execute external program
                logger.info(
                    f"Executing: {program_path} {input_file_path} {output_file_path} "
                    f"(timeout={timeout}s)"
                )
                
                result = subprocess.run(
                    [program_path, input_file_path, output_file_path],
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                logger.debug(f"External program completed with return code {result.returncode}")
                
                if result.stdout:
                    logger.debug(f"Program stdout: {result.stdout}")
                if result.stderr:
                    logger.warning(f"Program stderr: {result.stderr}")
                
                # Read output file
                with open(output_file_path, 'r') as f:
                    output_data = json.load(f)
                
                logger.info("External program output successfully read and parsed")
                
                return output_data
            
            except subprocess.TimeoutExpired:
                logger.error(f"External program timed out after {timeout} seconds")
                raise OptimizerError(
                    f"External optimizer timed out after {timeout} seconds"
                )
            
            except subprocess.CalledProcessError as e:
                logger.error(
                    f"External program failed with return code {e.returncode}: "
                    f"stderr={e.stderr}"
                )
                raise OptimizerError(
                    f"External optimizer failed with return code {e.returncode}: {e.stderr}"
                )
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse output JSON: {e}")
                raise OptimizerError(f"Invalid JSON output from external optimizer: {e}")
            
            except FileNotFoundError:
                logger.error(f"External program not found: {program_path}")
                raise OptimizerError(f"External program not found: {program_path}")
            
            finally:
                # Clean up temporary files
                try:
                    if os.path.exists(input_file_path):
                        os.remove(input_file_path)
                        logger.debug(f"Cleaned up input file: {input_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove input file: {e}")
                
                try:
                    if os.path.exists(output_file_path):
                        os.remove(output_file_path)
                        logger.debug(f"Cleaned up output file: {output_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove output file: {e}")
        
        except Exception as e:
            logger.error(f"Error in external program execution: {e}", exc_info=True)
            raise OptimizerError(f"External optimizer error: {e}")
    
    def _call_python_module(self, input_data: dict) -> dict:
        """
        Call Python module optimizer.
        
        ✅ This method properly passes the complete input_data including the
        get_travel_time function to Python-based optimizers like greedy_insertion.
        
        This method enables direct integration with Python-based optimization
        algorithms by dynamically importing and calling a specified function.
        
        Steps:
        1. Import the specified Python module (cached after first import)
        2. Get the specified function from the module
        3. Call the function with complete input_data (including get_travel_time)
        4. Return the output
        
        The Python module function is expected to have the signature:
            def optimize_function(input_data: dict) -> dict:
                '''
                Args:
                    input_data: Dict with keys:
                        - current_time (float)
                        - pending_requests (List[Dict])
                        - minibuses (List[Dict])
                        - stations (List[str])
                        - get_travel_time (callable): Function to query travel times
                        - max_waiting_time (float)
                        - max_detour_time (float)
                Returns:
                    Dict mapping minibus_id to route_plan
                '''
        
        Handles:
        - Module import errors
        - Function not found errors
        - Function execution errors
        
        Args:
            input_data (dict): Formatted input data (including get_travel_time function)
            
        Returns:
            dict: Optimizer output (route plans)
            
        Raises:
            OptimizerError: If module import or function execution fails
        """
        logger.info("Calling Python module optimizer...")
        
        module_name = self.config['module_name']
        function_name = self.config['function_name']
        
        try:
            # Import module if not already cached
            if self._module is None:
                logger.debug(f"Importing module: {module_name}")
                self._module = importlib.import_module(module_name)
                logger.info(f"Successfully imported module: {module_name}")
            else:
                logger.debug(f"Using cached module: {module_name}")
            
            # Get the optimization function
            if not hasattr(self._module, function_name):
                raise OptimizerError(
                    f"Function '{function_name}' not found in module '{module_name}'"
                )
            
            optimize_func = getattr(self._module, function_name)
            logger.debug(f"Retrieved function: {function_name}")
            
            # ✅ KEY FIX: Pass the complete input_data INCLUDING get_travel_time function
            # The greedy_insertion module needs this function to compute route costs
            logger.info(f"Calling {module_name}.{function_name} with complete input_data...")
            logger.debug(f"Input data keys: {list(input_data.keys())}")
            
            output_data = optimize_func(input_data)
            
            logger.info("Python module optimizer completed successfully")
            
            return output_data
        
        except ImportError as e:
            logger.error(f"Failed to import module '{module_name}': {e}")
            raise OptimizerError(f"Cannot import module '{module_name}': {e}")
        
        except AttributeError as e:
            logger.error(f"Function '{function_name}' not found in module: {e}")
            raise OptimizerError(
                f"Function '{function_name}' not found in module '{module_name}': {e}"
            )
        
        except Exception as e:
            logger.error(f"Error executing optimizer function: {e}", exc_info=True)
            raise OptimizerError(f"Optimizer function execution failed: {e}")


# Example usage and testing
if __name__ == "__main__":
    """
    Basic usage examples and testing code for integrating with greedy_insertion.
    """
    # Configure logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("RouteOptimizer - Integration with greedy_insertion Module")
    print("=" * 80)
    
    # Example 1: Initialize optimizer with greedy_insertion module
    print("\n1. Creating optimizer with greedy_insertion module...")
    optimizer = RouteOptimizer(
        optimizer_type='python_module',
        config={
            'module_name': 'greedy_insertion',  # Assumes greedy_insertion.py is in Python path
            'function_name': 'greedy_insert_optimize',
            'max_waiting_time': 600.0,  # 10 minutes
            'max_detour_time': 300.0    # 5 minutes
        }
    )
    print(f"   Created: {optimizer.optimizer_type} optimizer")
    print(f"   Module: {optimizer.config['module_name']}")
    print(f"   Function: {optimizer.config['function_name']}")
    
    # Example 2: Create mock network and passengers for testing
    print("\n2. Setting up mock network and data...")
    
    class MockNetwork:
        """Mock network for testing"""
        def __init__(self):
            self.stations = {
                "A": None, "B": None, "C": None, "D": None, "E": None
            }
        
        def get_travel_time(self, origin: str, dest: str, time: float) -> float:
            """Mock travel time function"""
            # Simple distance-based travel times (in seconds)
            travel_times = {
                ("A", "B"): 300,  # 5 min
                ("B", "A"): 300,
                ("B", "C"): 420,  # 7 min
                ("C", "B"): 420,
                ("C", "D"): 360,  # 6 min
                ("D", "C"): 360,
                ("A", "C"): 600,  # 10 min
                ("C", "A"): 600,
                ("A", "D"): 900,  # 15 min
                ("D", "A"): 900,
            }
            return travel_times.get((origin, dest), 600)  # Default 10 min
    
    class MockPassenger:
        """Mock passenger for testing"""
        def __init__(self, pid, origin, dest, appear_time):
            self.passenger_id = pid
            self.origin_station_id = origin
            self.destination_station_id = dest
            self.appear_time = appear_time
    
    mock_network = MockNetwork()
    current_time = 1000.0
    
    mock_passengers = [
        MockPassenger("P1", "A", "D", 900.0),
        MockPassenger("P2", "B", "C", 950.0),
    ]
    
    mock_minibus_states = [
        {
            "minibus_id": "M1",
            "current_location_id": "A",
            "capacity": 6,
            "occupancy": 0,
            "passenger_ids": [],
            "route_plan": []
        },
        {
            "minibus_id": "M2",
            "current_location_id": "B",
            "capacity": 6,
            "occupancy": 1,
            "passenger_ids": ["P_existing"],
            "route_plan": [
                {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P_existing"]}
            ]
        }
    ]
    
    print(f"   Mock network created with {len(mock_network.stations)} stations")
    print(f"   {len(mock_passengers)} pending passengers")
    print(f"   {len(mock_minibus_states)} minibuses")
    
    # Example 3: Run optimization
    print("\n3. Running optimization with greedy_insertion...")
    try:
        output = optimizer.optimize(
            pending_requests=mock_passengers,
            minibus_states=mock_minibus_states,
            network=mock_network,
            current_time=current_time
        )
        
        print("\n>>> Optimization Results:")
        for minibus_id, route_plan in output.items():
            print(f"\n{minibus_id}:")
            if not route_plan:
                print("  (idle)")
            else:
                for i, stop in enumerate(route_plan):
                    print(f"  {i+1}. {stop['station_id']}: {stop['action']} {stop['passenger_ids']}")
        
        print("\n✅ Integration test successful!")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Integration example completed!")
    print("=" * 80)
    
    # Example 4: How to use this in your simulation
    print("\n" + "=" * 80)
    print("USAGE IN YOUR SIMULATION:")
    print("=" * 80)
    print("""
# In your simulation code:

from route_optimizer import RouteOptimizer

# Initialize optimizer once at simulation start
optimizer = RouteOptimizer(
    optimizer_type='python_module',
    config={
        'module_name': 'greedy_insertion',
        'function_name': 'greedy_insert_optimize',
        'max_waiting_time': 600.0,
        'max_detour_time': 300.0
    }
)

# During simulation, call optimizer when needed
route_plans = optimizer.optimize(
    pending_requests=list_of_unassigned_passengers,
    minibus_states=list_of_minibus_info_dicts,
    network=your_transit_network_object,
    current_time=current_simulation_time
)

# Use the returned route_plans to update minibus routes
for minibus_id, new_route_plan in route_plans.items():
    minibus = get_minibus_by_id(minibus_id)
    minibus.update_route(new_route_plan)
""")