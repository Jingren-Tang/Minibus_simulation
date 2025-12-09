"""
test_route_optimizer.py

Simple unit tests for the RouteOptimizer class.
Tests basic functionality including initialization, dummy optimizer, and validation.
"""

import unittest
import logging
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import route_optimizer
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the RouteOptimizer class
# For testing purposes, we'll create a minimal version inline
# In production, you would import: from optimizer.route_optimizer import RouteOptimizer, OptimizerError


class TestRouteOptimizer(unittest.TestCase):
    """Test suite for RouteOptimizer class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Suppress logging during tests
        logging.disable(logging.CRITICAL)
        
        # Mock passenger class
        self.mock_passenger = Mock()
        self.mock_passenger.passenger_id = "P1"
        self.mock_passenger.origin_station_id = "A"
        self.mock_passenger.destination_station_id = "B"
        self.mock_passenger.appear_time = 100.0
        
        # Mock network
        self.mock_network = Mock()
        self.mock_network.stations = {"A": Mock(), "B": Mock(), "C": Mock()}
    
    def tearDown(self):
        """Clean up after each test method."""
        logging.disable(logging.NOTSET)
    
    def test_init_dummy_optimizer(self):
        """Test initialization with dummy optimizer."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(
            optimizer_type='dummy',
            config={}
        )
        
        self.assertEqual(optimizer.optimizer_type, 'dummy')
        self.assertEqual(optimizer.config, {})
        self.assertIsNone(optimizer._module)
    
    def test_init_invalid_type(self):
        """Test initialization with invalid optimizer type."""
        from route_optimizer import RouteOptimizer
        
        with self.assertRaises(ValueError) as context:
            RouteOptimizer(
                optimizer_type='invalid_type',
                config={}
            )
        
        self.assertIn("Unsupported optimizer_type", str(context.exception))
    
    def test_init_external_program_missing_path(self):
        """Test initialization of external_program without program_path."""
        from route_optimizer import RouteOptimizer
        
        with self.assertRaises(ValueError) as context:
            RouteOptimizer(
                optimizer_type='external_program',
                config={}
            )
        
        self.assertIn("program_path", str(context.exception))
    
    def test_init_python_module_missing_config(self):
        """Test initialization of python_module without required config."""
        from route_optimizer import RouteOptimizer
        
        with self.assertRaises(ValueError) as context:
            RouteOptimizer(
                optimizer_type='python_module',
                config={'module_name': 'test'}
            )
        
        self.assertIn("function_name", str(context.exception))
    
    def test_prepare_input(self):
        """Test input data preparation."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        # Create mock data
        pending_requests = [self.mock_passenger]
        minibus_states = [
            {
                "minibus_id": "M1",
                "current_location_id": "A",
                "capacity": 6,
                "occupancy": 0,
                "passenger_ids": [],
                "route_plan": []
            }
        ]
        
        # Prepare input
        input_data = optimizer._prepare_input(
            pending_requests=pending_requests,
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Verify structure
        self.assertIn("current_time", input_data)
        self.assertIn("pending_requests", input_data)
        self.assertIn("minibuses", input_data)
        self.assertIn("stations", input_data)
        
        # Verify values
        self.assertEqual(input_data["current_time"], 200.0)
        self.assertEqual(len(input_data["pending_requests"]), 1)
        self.assertEqual(len(input_data["minibuses"]), 1)
        self.assertEqual(input_data["pending_requests"][0]["passenger_id"], "P1")
    
    def test_validate_output_valid(self):
        """Test output validation with valid data."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        valid_output = {
            "M1": [
                {
                    "station_id": "A",
                    "action": "PICKUP",
                    "passenger_ids": ["P1"]
                },
                {
                    "station_id": "B",
                    "action": "DROPOFF",
                    "passenger_ids": ["P1"]
                }
            ],
            "M2": []
        }
        
        result = optimizer._validate_output(valid_output)
        self.assertTrue(result)
    
    def test_validate_output_invalid_action(self):
        """Test output validation with invalid action."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        invalid_output = {
            "M1": [
                {
                    "station_id": "A",
                    "action": "INVALID_ACTION",
                    "passenger_ids": ["P1"]
                }
            ]
        }
        
        result = optimizer._validate_output(invalid_output)
        self.assertFalse(result)
    
    def test_validate_output_missing_field(self):
        """Test output validation with missing required field."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        invalid_output = {
            "M1": [
                {
                    "station_id": "A",
                    "action": "PICKUP"
                    # Missing passenger_ids
                }
            ]
        }
        
        result = optimizer._validate_output(invalid_output)
        self.assertFalse(result)
    
    def test_validate_output_wrong_type(self):
        """Test output validation with wrong data type."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        # Output is not a dict
        result = optimizer._validate_output([])
        self.assertFalse(result)
    
    def test_call_dummy_optimizer_empty_input(self):
        """Test dummy optimizer with no passengers or minibuses."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        input_data = {
            "current_time": 0.0,
            "pending_requests": [],
            "minibuses": [],
            "stations": ["A", "B"]
        }
        
        output = optimizer._call_dummy_optimizer(input_data)
        self.assertEqual(output, {})
    
    def test_call_dummy_optimizer_basic_assignment(self):
        """Test dummy optimizer with basic passenger assignment."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        input_data = {
            "current_time": 200.0,
            "pending_requests": [
                {
                    "passenger_id": "P1",
                    "origin": "A",
                    "destination": "B",
                    "appear_time": 100.0,
                    "wait_time": 100.0
                }
            ],
            "minibuses": [
                {
                    "minibus_id": "M1",
                    "current_location": "A",
                    "capacity": 6,
                    "current_occupancy": 0,
                    "passengers_onboard": [],
                    "current_route_plan": []
                }
            ],
            "stations": ["A", "B", "C"]
        }
        
        output = optimizer._call_dummy_optimizer(input_data)
        
        # Verify output structure
        self.assertIn("M1", output)
        self.assertEqual(len(output["M1"]), 2)  # PICKUP and DROPOFF
        
        # Verify PICKUP
        self.assertEqual(output["M1"][0]["station_id"], "A")
        self.assertEqual(output["M1"][0]["action"], "PICKUP")
        self.assertIn("P1", output["M1"][0]["passenger_ids"])
        
        # Verify DROPOFF
        self.assertEqual(output["M1"][1]["station_id"], "B")
        self.assertEqual(output["M1"][1]["action"], "DROPOFF")
        self.assertIn("P1", output["M1"][1]["passenger_ids"])
    
    def test_call_dummy_optimizer_preserves_existing_route(self):
        """Test that dummy optimizer preserves existing routes."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        existing_route = [
            {"station_id": "C", "action": "DROPOFF", "passenger_ids": ["P2"]}
        ]
        
        input_data = {
            "current_time": 200.0,
            "pending_requests": [
                {
                    "passenger_id": "P1",
                    "origin": "A",
                    "destination": "B",
                    "appear_time": 100.0,
                    "wait_time": 100.0
                }
            ],
            "minibuses": [
                {
                    "minibus_id": "M1",
                    "current_location": "C",
                    "capacity": 6,
                    "current_occupancy": 1,
                    "passengers_onboard": ["P2"],
                    "current_route_plan": existing_route
                }
            ],
            "stations": ["A", "B", "C"]
        }
        
        output = optimizer._call_dummy_optimizer(input_data)
        
        # Verify existing route is preserved
        self.assertEqual(output["M1"], existing_route)
    
    def test_optimize_method_integration(self):
        """Test the main optimize method with mocked components."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        # Create mock data
        pending_requests = [self.mock_passenger]
        minibus_states = [
            {
                "minibus_id": "M1",
                "current_location_id": "A",
                "capacity": 6,
                "occupancy": 0,
                "passenger_ids": [],
                "route_plan": []
            }
        ]
        
        # Call optimize
        result = optimizer.optimize(
            pending_requests=pending_requests,
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Verify result
        self.assertIsInstance(result, dict)
        self.assertIn("M1", result)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        logging.disable(logging.CRITICAL)
    
    def tearDown(self):
        """Clean up after tests."""
        logging.disable(logging.NOTSET)
    
    def test_multiple_minibuses_multiple_passengers(self):
        """Test assignment with multiple minibuses and passengers."""
        from route_optimizer import RouteOptimizer
        
        optimizer = RouteOptimizer(optimizer_type='dummy', config={})
        
        input_data = {
            "current_time": 300.0,
            "pending_requests": [
                {"passenger_id": "P1", "origin": "A", "destination": "B", 
                 "appear_time": 100.0, "wait_time": 200.0},
                {"passenger_id": "P2", "origin": "C", "destination": "D", 
                 "appear_time": 150.0, "wait_time": 150.0},
                {"passenger_id": "P3", "origin": "E", "destination": "F", 
                 "appear_time": 200.0, "wait_time": 100.0}
            ],
            "minibuses": [
                {"minibus_id": "M1", "current_location": "A", "capacity": 6,
                 "current_occupancy": 0, "passengers_onboard": [], "current_route_plan": []},
                {"minibus_id": "M2", "current_location": "C", "capacity": 6,
                 "current_occupancy": 0, "passengers_onboard": [], "current_route_plan": []}
            ],
            "stations": ["A", "B", "C", "D", "E", "F"]
        }
        
        output = optimizer._call_dummy_optimizer(input_data)
        
        # Verify that at least some passengers are assigned
        assigned_count = sum(1 for plan in output.values() if len(plan) > 0)
        self.assertGreater(assigned_count, 0)


def run_tests():
    """Run all tests with detailed output."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestRouteOptimizer))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Note: To run these tests, you need to have route_optimizer.py in the same directory
    # or in your Python path
    
    print("RouteOptimizer Test Suite")
    print("="*70)
    print("Note: This test file expects 'route_optimizer.py' to be importable.")
    print("If you see import errors, make sure the file is in the correct location.")
    print("="*70 + "\n")
    
    success = run_tests()
    sys.exit(0 if success else 1)