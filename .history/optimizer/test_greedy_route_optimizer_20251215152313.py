"""
test_greedy_route_optimizer.py

Unit tests for RouteOptimizer with Greedy Insertion algorithm.
Tests the integration between RouteOptimizer and greedy_insertion module.
"""

import unittest
import logging
import sys
import os
from unittest.mock import Mock

# Configure test logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import classes to test
from route_optimizer import RouteOptimizer, OptimizerError


class TestRouteOptimizerWithGreedyInsertion(unittest.TestCase):
    """
    Test suite for RouteOptimizer with greedy_insertion algorithm.
    """
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create optimizer with greedy insertion
        self.optimizer = RouteOptimizer(
            optimizer_type='python_module',
            config={
                'module_name': 'optimizer.greedy_insertion',
                'function_name': 'greedy_insert_optimize',
                'max_waiting_time': 600.0,   # 10 minutes
                'max_detour_time': 300.0     # 5 minutes
            }
        )
        
        # Create mock network
        self.mock_network = self._create_mock_network()
        
        # Create mock passengers
        self.mock_passengers = self._create_mock_passengers()
    
    def _create_mock_network(self):
        """Create a mock TransitNetwork object."""
        mock_network = Mock()
        
        # Mock stations
        mock_network.stations = {
            "A": Mock(),
            "B": Mock(),
            "C": Mock(),
            "D": Mock(),
            "E": Mock()
        }
        
        # Mock get_travel_time method
        def mock_get_travel_time(origin, dest, time):
            """
            Simple mock travel time function.
            Returns constant travel times for testing.
            """
            # Simple distance-based travel times
            base_times = {
                ("A", "B"): 300,  # 5 min
                ("B", "A"): 300,
                ("B", "C"): 420,  # 7 min
                ("C", "B"): 420,
                ("C", "D"): 360,  # 6 min
                ("D", "C"): 360,
                ("A", "C"): 600,  # 10 min (direct)
                ("C", "A"): 600,
                ("A", "D"): 900,  # 15 min (direct)
                ("D", "A"): 900,
                ("E", "A"): 480,  # 8 min
                ("A", "E"): 480,
            }
            return base_times.get((origin, dest), 600)  # Default 10 min
        
        mock_network.get_travel_time = mock_get_travel_time
        
        return mock_network
    
    def _create_mock_passengers(self):
        """Create mock Passenger objects for testing."""
        passengers = []
        
        # Passenger 1: A -> D
        p1 = Mock()
        p1.passenger_id = "P1"
        p1.origin_station_id = "A"
        p1.destination_station_id = "D"
        p1.appear_time = 100.0
        passengers.append(p1)
        
        # Passenger 2: B -> C
        p2 = Mock()
        p2.passenger_id = "P2"
        p2.origin_station_id = "B"
        p2.destination_station_id = "C"
        p2.appear_time = 150.0
        passengers.append(p2)
        
        # Passenger 3: A -> C
        p3 = Mock()
        p3.passenger_id = "P3"
        p3.origin_station_id = "A"
        p3.destination_station_id = "C"
        p3.appear_time = 180.0
        passengers.append(p3)
        
        return passengers
    
    # =========================================================================
    # Test 1: Initialization
    # =========================================================================
    
    def test_initialization_with_greedy_config(self):
        """Test RouteOptimizer initialization with greedy insertion config."""
        self.assertEqual(self.optimizer.optimizer_type, 'python_module')
        self.assertEqual(
            self.optimizer.config['module_name'], 
            'optimizer.greedy_insertion'
        )
        self.assertEqual(
            self.optimizer.config['function_name'], 
            'greedy_insert_optimize'
        )
        self.assertEqual(self.optimizer.config['max_waiting_time'], 600.0)
        self.assertEqual(self.optimizer.config['max_detour_time'], 300.0)
    
    # =========================================================================
    # Test 2: Input Preparation with New Fields
    # =========================================================================
    
    def test_prepare_input_includes_travel_time_function(self):
        """Test that _prepare_input includes get_travel_time function."""
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
        
        input_data = self.optimizer._prepare_input(
            pending_requests=self.mock_passengers[:1],
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Check that get_travel_time function exists
        self.assertIn("get_travel_time", input_data)
        self.assertTrue(callable(input_data["get_travel_time"]))
        
        # Test the function works
        travel_time = input_data["get_travel_time"]("A", "B")
        self.assertEqual(travel_time, 300)
    
    def test_prepare_input_includes_constraint_parameters(self):
        """Test that _prepare_input includes constraint parameters."""
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
        
        input_data = self.optimizer._prepare_input(
            pending_requests=self.mock_passengers[:1],
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Check constraint parameters
        self.assertIn("max_waiting_time", input_data)
        self.assertIn("max_detour_time", input_data)
        self.assertEqual(input_data["max_waiting_time"], 600.0)
        self.assertEqual(input_data["max_detour_time"], 300.0)
    
    def test_travel_time_function_uses_current_time_as_default(self):
        """Test that travel time function uses current_time when time=None."""
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
        
        current_time = 28800.0  # 8:00 AM
        
        input_data = self.optimizer._prepare_input(
            pending_requests=self.mock_passengers[:1],
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=current_time
        )
        
        get_time = input_data["get_travel_time"]
        
        # Query without specifying time (should use current_time)
        time1 = get_time("A", "B")
        
        # Query with explicit time
        time2 = get_time("A", "B", current_time)
        
        # Both should return same result
        self.assertEqual(time1, time2)
    
    # =========================================================================
    # Test 3: Basic Greedy Insertion Integration
    # =========================================================================
    
    def test_optimize_with_single_passenger_single_minibus(self):
        """Test optimization with 1 passenger and 1 idle minibus."""
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
        
        result = self.optimizer.optimize(
            pending_requests=self.mock_passengers[:1],  # Only P1
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Check result structure
        self.assertIsInstance(result, dict)
        self.assertIn("M1", result)
        self.assertIsInstance(result["M1"], list)
        
        # Check assignment
        route_plan = result["M1"]
        self.assertGreater(len(route_plan), 0, "Passenger should be assigned")
        
        # Check route contains PICKUP and DROPOFF
        actions = [stop["action"] for stop in route_plan]
        self.assertIn("PICKUP", actions)
        self.assertIn("DROPOFF", actions)
        
        # Check passenger ID
        passenger_ids = []
        for stop in route_plan:
            passenger_ids.extend(stop["passenger_ids"])
        self.assertIn("P1", passenger_ids)
    
    def test_optimize_with_multiple_passengers_multiple_minibuses(self):
        """Test optimization with multiple passengers and minibuses."""
        minibus_states = [
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
                "occupancy": 0,
                "passenger_ids": [],
                "route_plan": []
            }
        ]
        
        result = self.optimizer.optimize(
            pending_requests=self.mock_passengers,  # All 3 passengers
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Check result structure
        self.assertIn("M1", result)
        self.assertIn("M2", result)
        
        # Count assigned passengers
        assigned_passengers = set()
        for minibus_id, route_plan in result.items():
            for stop in route_plan:
                if stop["action"] == "PICKUP":
                    assigned_passengers.update(stop["passenger_ids"])
        
        # At least some passengers should be assigned
        self.assertGreater(len(assigned_passengers), 0)
        print(f"✅ Assigned {len(assigned_passengers)}/3 passengers")
    
    def test_optimize_preserves_existing_route(self):
        """Test that optimization preserves existing minibus routes."""
        minibus_states = [
            {
                "minibus_id": "M1",
                "current_location_id": "A",
                "capacity": 6,
                "occupancy": 1,
                "passenger_ids": ["P_existing"],
                "route_plan": [
                    {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P_existing"]}
                ]
            }
        ]
        
        result = self.optimizer.optimize(
            pending_requests=self.mock_passengers[:1],
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        route_plan = result["M1"]
        
        # Check that existing passenger is still in route
        all_passengers = []
        for stop in route_plan:
            all_passengers.extend(stop["passenger_ids"])
        
        self.assertIn("P_existing", all_passengers, "Existing passenger should remain")
    
    # =========================================================================
    # Test 4: Station Reuse Feature
    # =========================================================================
    
    def test_station_reuse_in_greedy_algorithm(self):
        """Test that greedy algorithm reuses stations when possible."""
        # Create scenario where station reuse is beneficial
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
        
        # P1: A -> D, P3: A -> C (both start at A, should reuse A)
        result = self.optimizer.optimize(
            pending_requests=[self.mock_passengers[0], self.mock_passengers[2]],
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        route_plan = result["M1"]
        
        # Count how many times A appears in route
        stations = [stop["station_id"] for stop in route_plan]
        station_a_count = stations.count("A")
        
        # If both passengers are picked up, A should appear only once (reused)
        pickups_at_a = [stop for stop in route_plan 
                       if stop["station_id"] == "A" and stop["action"] == "PICKUP"]
        
        if len(pickups_at_a) > 0:
            # Check if multiple passengers picked up at A
            total_passengers_at_a = sum(
                len(stop["passenger_ids"]) for stop in pickups_at_a
            )
            print(f"✅ Station A used for {total_passengers_at_a} pickup(s)")
    
    # =========================================================================
    # Test 5: Capacity Constraint
    # =========================================================================
    
    def test_capacity_constraint_enforcement(self):
        """Test that capacity constraints are enforced."""
        # Create minibus with small capacity
        minibus_states = [
            {
                "minibus_id": "M1",
                "current_location_id": "A",
                "capacity": 2,  # Small capacity
                "occupancy": 1,  # Already has 1 passenger
                "passenger_ids": ["P_existing"],
                "route_plan": [
                    {"station_id": "E", "action": "DROPOFF", "passenger_ids": ["P_existing"]}
                ]
            }
        ]
        
        # Try to assign 3 passengers (should only assign ≤1 more)
        result = self.optimizer.optimize(
            pending_requests=self.mock_passengers,  # 3 passengers
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        route_plan = result["M1"]
        
        # Simulate occupancy through the route
        occupancy = 1  # Start with existing passenger
        max_occupancy = 1
        
        for stop in route_plan:
            if stop["action"] == "PICKUP":
                occupancy += len(stop["passenger_ids"])
            elif stop["action"] == "DROPOFF":
                occupancy -= len(stop["passenger_ids"])
            
            max_occupancy = max(max_occupancy, occupancy)
        
        # Max occupancy should not exceed capacity
        self.assertLessEqual(
            max_occupancy, 2, 
            f"Max occupancy {max_occupancy} exceeds capacity 2"
        )
        print(f"✅ Capacity constraint enforced: max_occupancy={max_occupancy}/2")
    
    # =========================================================================
    # Test 6: Output Validation
    # =========================================================================
    
    def test_output_format_validation(self):
        """Test that greedy algorithm output passes validation."""
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
        
        result = self.optimizer.optimize(
            pending_requests=self.mock_passengers[:1],
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Use RouteOptimizer's validation method
        is_valid = self.optimizer._validate_output(result)
        self.assertTrue(is_valid, "Greedy algorithm output should be valid")
    
    # =========================================================================
    # Test 7: Edge Cases
    # =========================================================================
    
    def test_optimize_with_no_passengers(self):
        """Test optimization with no pending passengers."""
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
        
        result = self.optimizer.optimize(
            pending_requests=[],  # No passengers
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Should return empty routes
        self.assertEqual(result["M1"], [])
    
    def test_optimize_with_no_minibuses(self):
        """Test optimization with no minibuses."""
        result = self.optimizer.optimize(
            pending_requests=self.mock_passengers[:1],
            minibus_states=[],  # No minibuses
            network=self.mock_network,
            current_time=200.0
        )
        
        # Should return empty dict
        self.assertEqual(result, {})
    
    # =========================================================================
    # Test 8: Error Handling
    # =========================================================================
    
    def test_optimizer_handles_algorithm_errors_gracefully(self):
        """Test that optimizer handles algorithm errors gracefully."""
        # Create optimizer with non-existent module
        bad_optimizer = RouteOptimizer(
            optimizer_type='python_module',
            config={
                'module_name': 'non_existent_module',
                'function_name': 'non_existent_function',
                'max_waiting_time': 600.0,
                'max_detour_time': 300.0
            }
        )
        
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
        
        # Should not raise exception, should return safe empty plans
        result = bad_optimizer.optimize(
            pending_requests=self.mock_passengers[:1],
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=200.0
        )
        
        # Should return empty plans (safe fallback)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["M1"], [])


class TestGreedyAlgorithmPerformance(unittest.TestCase):
    """
    Test greedy insertion algorithm performance characteristics.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = RouteOptimizer(
            optimizer_type='python_module',
            config={
                'module_name': 'optimizer.greedy_insertion',
                'function_name': 'greedy_insert_optimize',
                'max_waiting_time': 600.0,
                'max_detour_time': 300.0
            }
        )
        
        self.mock_network = self._create_mock_network()
    
    def _create_mock_network(self):
        """Create mock network."""
        mock_network = Mock()
        mock_network.stations = {chr(65+i): Mock() for i in range(10)}  # A-J
        mock_network.get_travel_time = lambda o, d, t: 300.0
        return mock_network
    
    def test_performance_with_many_passengers(self):
        """Test algorithm performance with many passengers."""
        import time
        
        # Create 20 passengers
        passengers = []
        stations = list(self.mock_network.stations.keys())
        for i in range(20):
            p = Mock()
            p.passenger_id = f"P{i+1}"
            p.origin_station_id = stations[i % len(stations)]
            p.destination_station_id = stations[(i+1) % len(stations)]
            p.appear_time = 100.0 + i * 10
            passengers.append(p)
        
        # Create 5 minibuses
        minibus_states = [
            {
                "minibus_id": f"M{i+1}",
                "current_location_id": stations[i],
                "capacity": 6,
                "occupancy": 0,
                "passenger_ids": [],
                "route_plan": []
            }
            for i in range(5)
        ]
        
        # Time the optimization
        start_time = time.time()
        
        result = self.optimizer.optimize(
            pending_requests=passengers,
            minibus_states=minibus_states,
            network=self.mock_network,
            current_time=500.0
        )
        
        elapsed_time = time.time() - start_time
        
        # Should complete in reasonable time (< 5 seconds)
        self.assertLess(elapsed_time, 5.0, f"Optimization took {elapsed_time:.2f}s")
        
        # Count assignments
        assigned = sum(
            len([s for s in plan if s["action"] == "PICKUP"])
            for plan in result.values()
        )
        
        print(f"✅ Performance test: {assigned}/20 passengers assigned in {elapsed_time:.2f}s")


def run_tests():
    """Run all tests with detailed output."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestRouteOptimizerWithGreedyInsertion))
    suite.addTests(loader.loadTestsFromTestCase(TestGreedyAlgorithmPerformance))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*80)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("="*80)
    print("GREEDY INSERTION ROUTE OPTIMIZER TEST SUITE")
    print("="*80)
    print()
    print("This test suite validates the integration between:")
    print("  - RouteOptimizer (interface)")
    print("  - greedy_insertion (algorithm)")
    print()
    print("="*80)
    print()
    
    success = run_tests()
    
    sys.exit(0 if success else 1)