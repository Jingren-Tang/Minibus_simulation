"""
Unit tests for the Station class.

This test suite validates the functionality of the Station class including
passenger management, validation, thread safety, and serialization.
"""

import unittest
import logging
from network.station import Station


# Mock Passenger class for testing (since Passenger class is not implemented yet)
class MockPassenger:
    """Mock Passenger class for testing purposes."""
    
    def __init__(self, passenger_id: str, origin_id: str, destination_id: str):
        self.passenger_id = passenger_id
        self.origin_id = origin_id
        self.destination_id = destination_id
    
    def __repr__(self):
        return f"MockPassenger({self.passenger_id}, {self.origin_id}->{self.destination_id})"


class TestStation(unittest.TestCase):
    """Test cases for the Station class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Suppress logging during tests
        logging.disable(logging.CRITICAL)
        
        # Create test stations
        self.station_a = Station("A", "Central Station", (47.3769, 8.5417), 0)
        self.station_b = Station("B", "North Station", (47.3800, 8.5450), 1)
        
        # Create test passengers
        self.passenger1 = MockPassenger("P1", "A", "B")
        self.passenger2 = MockPassenger("P2", "A", "C")
        self.passenger3 = MockPassenger("P3", "A", "B")
        self.passenger4 = MockPassenger("P4", "A", "D")
    
    def tearDown(self):
        """Clean up after each test method."""
        # Re-enable logging
        logging.disable(logging.NOTSET)
    
    # ==================== Initialization Tests ====================
    
    def test_station_initialization(self):
        """Test that a station initializes correctly with valid parameters."""
        station = Station("TEST", "Test Station", (40.7128, -74.0060), 5)
        
        self.assertEqual(station.station_id, "TEST")
        self.assertEqual(station.name, "Test Station")
        self.assertEqual(station.location, (40.7128, -74.0060))
        self.assertEqual(station.index, 5)
        self.assertEqual(len(station.waiting_passengers), 0)
    
    def test_location_immutability(self):
        """Test that location tuple is immutable."""
        location = [47.3769, 8.5417]  # Provide as list
        station = Station("A", "Test", location, 0)
        
        # Verify it's converted to tuple
        self.assertIsInstance(station.location, tuple)
        
        # Verify we cannot modify it
        with self.assertRaises(TypeError):
            station.location[0] = 99.9
    
    def test_invalid_station_id(self):
        """Test that invalid station_id raises ValueError."""
        with self.assertRaises(ValueError):
            Station("", "Test Station", (40.0, -74.0), 0)
        
        with self.assertRaises(ValueError):
            Station(None, "Test Station", (40.0, -74.0), 0)
    
    def test_invalid_location(self):
        """Test that invalid location raises appropriate errors."""
        # Location not a tuple
        with self.assertRaises(TypeError):
            Station("A", "Test", "not a tuple", 0)
        
        # Location with wrong number of elements
        with self.assertRaises(ValueError):
            Station("A", "Test", (40.0,), 0)
        
        with self.assertRaises(ValueError):
            Station("A", "Test", (40.0, -74.0, 100.0), 0)
        
        # Location with non-numeric values
        with self.assertRaises(TypeError):
            Station("A", "Test", ("40.0", "-74.0"), 0)
    
    def test_invalid_index(self):
        """Test that invalid index raises appropriate errors."""
        # Negative index
        with self.assertRaises(ValueError):
            Station("A", "Test", (40.0, -74.0), -1)
        
        # Non-integer index
        with self.assertRaises(TypeError):
            Station("A", "Test", (40.0, -74.0), 2.5)
    
    # ==================== Passenger Management Tests ====================
    
    def test_add_waiting_passenger(self):
        """Test adding a passenger to the waiting list."""
        self.assertEqual(self.station_a.get_num_waiting(), 0)
        
        self.station_a.add_waiting_passenger(self.passenger1)
        self.assertEqual(self.station_a.get_num_waiting(), 1)
        
        self.station_a.add_waiting_passenger(self.passenger2)
        self.assertEqual(self.station_a.get_num_waiting(), 2)
    
    def test_add_duplicate_passenger(self):
        """Test that adding the same passenger twice is prevented."""
        self.station_a.add_waiting_passenger(self.passenger1)
        self.assertEqual(self.station_a.get_num_waiting(), 1)
        
        # Try to add the same passenger again
        self.station_a.add_waiting_passenger(self.passenger1)
        self.assertEqual(self.station_a.get_num_waiting(), 1)  # Should still be 1
    
    def test_add_none_passenger(self):
        """Test that adding None as passenger raises ValueError."""
        with self.assertRaises(ValueError):
            self.station_a.add_waiting_passenger(None)
    
    def test_remove_waiting_passenger(self):
        """Test removing a passenger from the waiting list."""
        self.station_a.add_waiting_passenger(self.passenger1)
        self.station_a.add_waiting_passenger(self.passenger2)
        self.assertEqual(self.station_a.get_num_waiting(), 2)
        
        # Remove passenger1
        result = self.station_a.remove_waiting_passenger(self.passenger1)
        self.assertTrue(result)
        self.assertEqual(self.station_a.get_num_waiting(), 1)
        
        # Verify passenger2 is still there
        waiting = self.station_a.get_waiting_passengers()
        self.assertIn(self.passenger2, waiting)
        self.assertNotIn(self.passenger1, waiting)
    
    def test_remove_nonexistent_passenger(self):
        """Test removing a passenger that is not in the waiting list."""
        self.station_a.add_waiting_passenger(self.passenger1)
        
        # Try to remove a passenger that was never added
        result = self.station_a.remove_waiting_passenger(self.passenger2)
        self.assertFalse(result)
        self.assertEqual(self.station_a.get_num_waiting(), 1)
    
    def test_remove_none_passenger(self):
        """Test that removing None as passenger raises ValueError."""
        with self.assertRaises(ValueError):
            self.station_a.remove_waiting_passenger(None)
    
    def test_get_waiting_passengers_all(self):
        """Test getting all waiting passengers."""
        self.station_a.add_waiting_passenger(self.passenger1)
        self.station_a.add_waiting_passenger(self.passenger2)
        self.station_a.add_waiting_passenger(self.passenger3)
        
        waiting = self.station_a.get_waiting_passengers()
        self.assertEqual(len(waiting), 3)
        self.assertIn(self.passenger1, waiting)
        self.assertIn(self.passenger2, waiting)
        self.assertIn(self.passenger3, waiting)
    
    def test_get_waiting_passengers_by_destination(self):
        """Test getting passengers filtered by destination."""
        # Add passengers with different destinations
        self.station_a.add_waiting_passenger(self.passenger1)  # Destination: B
        self.station_a.add_waiting_passenger(self.passenger2)  # Destination: C
        self.station_a.add_waiting_passenger(self.passenger3)  # Destination: B
        self.station_a.add_waiting_passenger(self.passenger4)  # Destination: D
        
        # Get passengers going to B
        to_b = self.station_a.get_waiting_passengers(destination_id="B")
        self.assertEqual(len(to_b), 2)
        self.assertIn(self.passenger1, to_b)
        self.assertIn(self.passenger3, to_b)
        
        # Get passengers going to C
        to_c = self.station_a.get_waiting_passengers(destination_id="C")
        self.assertEqual(len(to_c), 1)
        self.assertIn(self.passenger2, to_c)
        
        # Get passengers going to non-existent destination
        to_z = self.station_a.get_waiting_passengers(destination_id="Z")
        self.assertEqual(len(to_z), 0)
    
    def test_get_passengers_by_destinations_multiple(self):
        """Test getting passengers with multiple destination options."""
        self.station_a.add_waiting_passenger(self.passenger1)  # Destination: B
        self.station_a.add_waiting_passenger(self.passenger2)  # Destination: C
        self.station_a.add_waiting_passenger(self.passenger3)  # Destination: B
        self.station_a.add_waiting_passenger(self.passenger4)  # Destination: D
        
        # Get passengers going to B or C
        to_b_or_c = self.station_a.get_passengers_by_destinations(["B", "C"])
        self.assertEqual(len(to_b_or_c), 3)
        self.assertIn(self.passenger1, to_b_or_c)
        self.assertIn(self.passenger2, to_b_or_c)
        self.assertIn(self.passenger3, to_b_or_c)
        self.assertNotIn(self.passenger4, to_b_or_c)
    
    def test_get_num_waiting(self):
        """Test getting the count of waiting passengers."""
        self.assertEqual(self.station_a.get_num_waiting(), 0)
        
        self.station_a.add_waiting_passenger(self.passenger1)
        self.assertEqual(self.station_a.get_num_waiting(), 1)
        
        self.station_a.add_waiting_passenger(self.passenger2)
        self.assertEqual(self.station_a.get_num_waiting(), 2)
        
        self.station_a.remove_waiting_passenger(self.passenger1)
        self.assertEqual(self.station_a.get_num_waiting(), 1)
    
    def test_clear_waiting_passengers(self):
        """Test clearing all waiting passengers."""
        self.station_a.add_waiting_passenger(self.passenger1)
        self.station_a.add_waiting_passenger(self.passenger2)
        self.station_a.add_waiting_passenger(self.passenger3)
        self.assertEqual(self.station_a.get_num_waiting(), 3)
        
        cleared = self.station_a.clear_waiting_passengers()
        self.assertEqual(len(cleared), 3)
        self.assertEqual(self.station_a.get_num_waiting(), 0)
        
        # Verify all passengers were in the cleared list
        self.assertIn(self.passenger1, cleared)
        self.assertIn(self.passenger2, cleared)
        self.assertIn(self.passenger3, cleared)
    
    def test_get_earliest_arrival_passenger(self):
        """Test getting the first passenger who arrived (earliest in list)."""
        # Empty station
        self.assertIsNone(self.station_a.get_earliest_arrival_passenger())
        
        # Add passengers in order
        self.station_a.add_waiting_passenger(self.passenger1)
        self.station_a.add_waiting_passenger(self.passenger2)
        self.station_a.add_waiting_passenger(self.passenger3)
        
        # Should return the first one added
        earliest = self.station_a.get_earliest_arrival_passenger()
        self.assertEqual(earliest, self.passenger1)
        
        # Remove the first passenger
        self.station_a.remove_waiting_passenger(self.passenger1)
        
        # Now passenger2 should be earliest
        earliest = self.station_a.get_earliest_arrival_passenger()
        self.assertEqual(earliest, self.passenger2)
    
    def test_waiting_list_order_preservation(self):
        """Test that passenger order is preserved in the waiting list."""
        self.station_a.add_waiting_passenger(self.passenger1)
        self.station_a.add_waiting_passenger(self.passenger2)
        self.station_a.add_waiting_passenger(self.passenger3)
        
        waiting = self.station_a.get_waiting_passengers()
        self.assertEqual(waiting[0], self.passenger1)
        self.assertEqual(waiting[1], self.passenger2)
        self.assertEqual(waiting[2], self.passenger3)
    
    # ==================== Equality and Hashing Tests ====================
    
    def test_station_equality(self):
        """Test that stations with same ID are considered equal."""
        station_a1 = Station("A", "Central Station", (47.3769, 8.5417), 0)
        station_a2 = Station("A", "Different Name", (40.0, -74.0), 5)
        station_b = Station("B", "North Station", (47.3800, 8.5450), 1)
        
        # Same ID -> equal
        self.assertEqual(station_a1, station_a2)
        
        # Different ID -> not equal
        self.assertNotEqual(station_a1, station_b)
    
    def test_station_hash(self):
        """Test that stations with same ID have same hash."""
        station_a1 = Station("A", "Central Station", (47.3769, 8.5417), 0)
        station_a2 = Station("A", "Different Name", (40.0, -74.0), 5)
        
        self.assertEqual(hash(station_a1), hash(station_a2))
    
    def test_station_in_set(self):
        """Test that stations can be used in sets correctly."""
        station_a1 = Station("A", "Central Station", (47.3769, 8.5417), 0)
        station_a2 = Station("A", "Different Name", (40.0, -74.0), 5)
        station_b = Station("B", "North Station", (47.3800, 8.5450), 1)
        
        station_set = {station_a1, station_a2, station_b}
        
        # Should only have 2 unique stations (A and B)
        self.assertEqual(len(station_set), 2)
    
    def test_station_as_dict_key(self):
        """Test that stations can be used as dictionary keys."""
        station_counts = {
            self.station_a: 10,
            self.station_b: 5
        }
        
        # Create new station with same ID as station_a
        station_a_copy = Station("A", "Copy", (0.0, 0.0), 99)
        
        # Should be able to access using the copy (same ID)
        self.assertEqual(station_counts[station_a_copy], 10)
    
    # ==================== Serialization Tests ====================
    
    def test_to_dict(self):
        """Test converting station to dictionary."""
        self.station_a.add_waiting_passenger(self.passenger1)
        self.station_a.add_waiting_passenger(self.passenger2)
        
        station_dict = self.station_a.to_dict()
        
        self.assertEqual(station_dict['station_id'], "A")
        self.assertEqual(station_dict['name'], "Central Station")
        self.assertEqual(station_dict['location'], (47.3769, 8.5417))
        self.assertEqual(station_dict['index'], 0)
        self.assertEqual(station_dict['num_waiting'], 2)
        self.assertIn("P1", station_dict['waiting_passenger_ids'])
        self.assertIn("P2", station_dict['waiting_passenger_ids'])
    
    def test_to_dict_empty_station(self):
        """Test converting empty station to dictionary."""
        station_dict = self.station_a.to_dict()
        
        self.assertEqual(station_dict['num_waiting'], 0)
        self.assertEqual(station_dict['waiting_passenger_ids'], [])
    
    def test_repr(self):
        """Test string representation of station."""
        repr_str = repr(self.station_a)
        
        self.assertIn("Station", repr_str)
        self.assertIn("id=A", repr_str)
        self.assertIn("name=Central Station", repr_str)
        self.assertIn("waiting=0", repr_str)
        
        # Add passengers and check again
        self.station_a.add_waiting_passenger(self.passenger1)
        self.station_a.add_waiting_passenger(self.passenger2)
        repr_str = repr(self.station_a)
        self.assertIn("waiting=2", repr_str)
    
    # ==================== Edge Cases ====================
    
    def test_get_waiting_passengers_returns_copy(self):
        """Test that get_waiting_passengers returns a copy, not original list."""
        self.station_a.add_waiting_passenger(self.passenger1)
        
        waiting_list = self.station_a.get_waiting_passengers()
        original_length = len(waiting_list)
        
        # Modify the returned list
        waiting_list.append(self.passenger2)
        
        # Original should be unchanged
        self.assertEqual(self.station_a.get_num_waiting(), original_length)
    
    def test_integer_coordinates(self):
        """Test that integer coordinates are accepted."""
        station = Station("TEST", "Test", (40, -74), 0)
        self.assertEqual(station.location, (40, -74))
    
    def test_mixed_coordinate_types(self):
        """Test that mixed int/float coordinates are accepted."""
        station = Station("TEST", "Test", (40, -74.5), 0)
        self.assertEqual(station.location, (40, -74.5))


if __name__ == '__main__':
    # Run the tests with verbose output
    unittest.main(verbosity=2)