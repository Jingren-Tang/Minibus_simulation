"""
TransitNetwork class for managing the transit network infrastructure.

This module provides the main container class for the entire transit network,
managing all stations and providing interfaces for travel time queries.
"""

import json
import logging
import math
from typing import Dict, List, Optional

from station import Station
from travel_time_manager import TravelTimeManager

# Configure logging
logger = logging.getLogger(__name__)


class TransitNetwork:
    """
    Main container class for the transit network.
    
    Manages all stations in the network and provides interfaces for querying
    travel times and distances. Serves as the central access point for network
    information used by other simulation components.
    
    Attributes:
        stations (Dict[str, Station]): Dictionary mapping station IDs to Station objects
        station_list (List[str]): Ordered list of station IDs
        travel_time_manager (TravelTimeManager): Manager for travel time queries
        num_stations (int): Total number of stations in the network
    """
    
    def __init__(self, stations_file: str, matrix_path: str, metadata_path: str):
        """
        Initialize the transit network.
        
        Loads station information, creates travel time manager, and validates
        that station mappings are consistent with the travel time matrix.
        
        Args:
            stations_file: Path to JSON file containing station information
            matrix_path: Path to numpy file containing travel time matrix
            metadata_path: Path to JSON file containing matrix metadata
            
        Raises:
            ValueError: If station mappings don't match matrix metadata
            FileNotFoundError: If any required file is not found
        """
        logger.info(f"Initializing TransitNetwork from {stations_file}")
        
        # Load stations from JSON file
        self.stations: Dict[str, Station] = self.load_stations(stations_file)
        self.station_list: List[str] = sorted(self.stations.keys())
        self.num_stations: int = len(self.stations)
        
        logger.info(f"Loaded {self.num_stations} stations")
        
        # Initialize travel time manager
        self.travel_time_manager = TravelTimeManager(matrix_path, metadata_path)
        
        # Validate that station mappings match the matrix metadata
        self._validate_station_mapping()
        
        logger.info("TransitNetwork initialization complete")
    
    def load_stations(self, stations_file: str) -> Dict[str, Station]:
        """
        Load station information from JSON file.
        
        Expected JSON format:
        {
            "stations": [
                {
                    "station_id": "A",
                    "name": "Station A",
                    "location": [47.3769, 8.5417],
                    "index": 0
                },
                ...
            ]
        }
        
        Args:
            stations_file: Path to the JSON file containing station data
            
        Returns:
            Dictionary mapping station IDs to Station objects
            
        Raises:
            FileNotFoundError: If the stations file doesn't exist
            json.JSONDecodeError: If the JSON file is malformed
            KeyError: If required fields are missing in the JSON
        """
        logger.info(f"Loading stations from {stations_file}")
        
        try:
            with open(stations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Stations file not found: {stations_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in stations file: {e}")
            raise
        
        stations_dict = {}
        
        # Parse station data and create Station objects
        for station_data in data.get('stations', []):
            try:
                station = Station(
                    station_id=station_data['station_id'],
                    name=station_data['name'],
                    location=tuple(station_data['location']),
                    index=station_data['index']
                )
                stations_dict[station.station_id] = station
                logger.debug(f"Loaded station: {station.station_id} - {station.name}")
            except KeyError as e:
                logger.error(f"Missing required field in station data: {e}")
                raise ValueError(f"Station data missing required field: {e}")
        
        if not stations_dict:
            raise ValueError("No stations found in the stations file")
        
        return stations_dict


    def _validate_station_mapping(self) -> None:
        """
        Validate that station mappings are consistent with matrix metadata.
        
        Ensures that all stations have valid indices and that they match
        the travel time matrix dimensions.
        
        Raises:
            ValueError: If station mapping is inconsistent with matrix
        """
        logger.info("Validating station mapping against matrix metadata")
        
        # Get matrix metadata - use station_mapping instead of station_id_to_index
        matrix_stations = self.travel_time_manager.station_mapping
        matrix_size = len(matrix_stations)
        
        # Check if station counts match
        if self.num_stations != matrix_size:
            raise ValueError(
                f"Station count mismatch: {self.num_stations} stations loaded, "
                f"but matrix has {matrix_size} stations"
            )
        
        # Verify all stations exist in matrix and indices match
        for station_id, station in self.stations.items():
            if station_id not in matrix_stations:
                raise ValueError(
                    f"Station '{station_id}' not found in matrix metadata"
                )
            
            matrix_index = matrix_stations[station_id]
            if station.index != matrix_index:
                logger.warning(
                    f"Index mismatch for station '{station_id}': "
                    f"station.index={station.index}, matrix_index={matrix_index}"
                )
        
        logger.info("Station mapping validation successful")
    
    def add_station(self, station: Station) -> None:
        """
        Add a new station to the network.
        
        Args:
            station: Station object to add
            
        Raises:
            ValueError: If a station with the same ID already exists
        """
        if station.station_id in self.stations:
            raise ValueError(
                f"Station '{station.station_id}' already exists in the network"
            )
        
        self.stations[station.station_id] = station
        self.station_list = sorted(self.stations.keys())
        self.num_stations = len(self.stations)
        
        logger.info(f"Added station: {station.station_id} - {station.name}")
    
    def get_station(self, station_id: str) -> Station:
        """
        Get station object by ID.
        
        This is a high-frequency operation, so it's implemented for efficiency.
        
        Args:
            station_id: The ID of the station to retrieve
            
        Returns:
            The Station object corresponding to the given ID
            
        Raises:
            KeyError: If the station ID is not found in the network
        """
        try:
            return self.stations[station_id]
        except KeyError:
            # Provide helpful error message with available stations
            available = ', '.join(sorted(self.stations.keys()))
            raise KeyError(
                f"Station '{station_id}' not found in network. "
                f"Available stations: {available}"
            )
    
    def get_all_stations(self) -> List[Station]:
        """
        Get all stations in the network.
        
        Returns a copy of the station list to prevent external modification.
        
        Returns:
            List of all Station objects in the network
        """
        return list(self.stations.values())
    
    def get_station_ids(self) -> List[str]:
        """
        Get all station IDs in the network.
        
        Returns a copy to prevent external modification.
        
        Returns:
            List of all station IDs
        """
        return self.station_list.copy()
    
    def get_travel_time(
        self, 
        origin_id: str, 
        dest_id: str, 
        current_time: float
    ) -> float:
        """
        Query travel time between two stations.
        
        This is a high-frequency operation that delegates to the travel time
        manager. Includes parameter validation to ensure both stations exist.
        
        Args:
            origin_id: ID of the origin station
            dest_id: ID of the destination station
            current_time: Current simulation time in seconds
            
        Returns:
            Travel time in seconds between the two stations
            
        Raises:
            KeyError: If either station ID is not found in the network
        """
        # Validate that both stations exist (raises KeyError if not)
        self.get_station(origin_id)
        self.get_station(dest_id)
        
        # Delegate to travel time manager
        return self.travel_time_manager.get_travel_time(
            origin_id, 
            dest_id, 
            current_time
        )
    
    def get_distance_estimate(self, origin_id: str, dest_id: str) -> float:
        """
        Estimate straight-line distance between two stations using Haversine formula.
        
        This provides a distance estimate based on geographical coordinates.
        Useful for debugging or as a fallback distance metric.
        
        Args:
            origin_id: ID of the origin station
            dest_id: ID of the destination station
            
        Returns:
            Estimated distance in kilometers
            
        Raises:
            KeyError: If either station ID is not found in the network
        """
        origin = self.get_station(origin_id)
        dest = self.get_station(dest_id)
        
        # Haversine formula for great-circle distance
        lat1, lon1 = math.radians(origin.location[0]), math.radians(origin.location[1])
        lat2, lon2 = math.radians(dest.location[0]), math.radians(dest.location[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        earth_radius = 6371.0
        distance = earth_radius * c
        
        return distance
    
    def validate_network(self) -> bool:
        """
        Validate network integrity.
        
        Performs comprehensive validation checks:
        - All stations have valid indices
        - Station mapping is consistent with matrix
        - All station IDs are unique
        
        Returns:
            True if all validation checks pass, False otherwise
        """
        logger.info("Validating network integrity")
        is_valid = True
        
        # Check for duplicate station IDs
        station_ids = [s.station_id for s in self.stations.values()]
        if len(station_ids) != len(set(station_ids)):
            logger.error("Duplicate station IDs found")
            is_valid = False
        
        # Check that all stations have valid indices
        indices = [s.index for s in self.stations.values()]
        expected_indices = set(range(self.num_stations))
        actual_indices = set(indices)
        
        if actual_indices != expected_indices:
            missing = expected_indices - actual_indices
            extra = actual_indices - expected_indices
            if missing:
                logger.error(f"Missing station indices: {missing}")
            if extra:
                logger.error(f"Extra/invalid station indices: {extra}")
            is_valid = False
        
        # Validate station mapping with matrix
        try:
            self._validate_station_mapping()
        except ValueError as e:
            logger.error(f"Station mapping validation failed: {e}")
            is_valid = False
        
        if is_valid:
            logger.info("Network validation passed")
        else:
            logger.warning("Network validation failed")
        
        return is_valid
    
    def get_network_info(self) -> Dict:
        """
        Get summary information about the network.
        
        Useful for debugging, logging, and monitoring purposes.
        
        Returns:
            Dictionary containing network statistics and information
        """
        return {
            'num_stations': self.num_stations,
            'station_ids': self.station_list,
            'station_names': [s.name for s in self.stations.values()],
            'matrix_info': {
                'has_time_dependent': self.travel_time_manager.has_time_dependent_matrix,
                'num_time_slots': len(self.travel_time_manager.time_slots) 
                    if self.travel_time_manager.has_time_dependent_matrix else 0
            }
        }
    
    def __repr__(self) -> str:
        """
        Return a readable string representation of the network.
        
        Returns:
            String representation in the format: TransitNetwork(stations=N)
        """
        return f"TransitNetwork(stations={self.num_stations})"
    
    def __contains__(self, station_id: str) -> bool:
        """
        Check if a station exists in the network.
        
        Enables the use of 'in' operator: 'A' in network
        
        Args:
            station_id: The station ID to check
            
        Returns:
            True if the station exists in the network, False otherwise
        """
        return station_id in self.stations