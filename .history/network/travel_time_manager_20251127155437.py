"""
Travel Time Manager for Mixed Traffic Simulation System

This module manages pre-computed travel time matrices for efficient lookup
during simulation. It handles fixed-route buses and flexible-route minibuses
with time-varying travel times stored in 3D numpy arrays.
"""

import json
import logging
from functools import lru_cache
from typing import Dict, Tuple

import numpy as np


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TravelTimeManager:
    """
    Manages travel time queries for a transportation network simulation.
    
    The travel times are pre-stored in a 3D numpy matrix with dimensions:
    [origin_station_index, destination_station_index, time_slot_index]
    
    Time slots represent fixed intervals (default 10 minutes) throughout
    the simulation period, allowing for time-varying travel times.
    
    Attributes:
        travel_time_matrix (np.ndarray): 3D array of shape (N_stations, N_stations, N_time_slots)
        station_mapping (dict): Maps station IDs to matrix indices, e.g., {"A": 0, "B": 1}
        reverse_mapping (dict): Maps indices back to station IDs, e.g., {0: "A", 1: "B"}
        time_slot_duration (int): Duration of each time slot in minutes (default 10)
        simulation_start_time (float): Simulation start time in seconds (default 0)
        num_stations (int): Total number of stations in the network
        num_time_slots (int): Total number of time slots
    """
    
    def __init__(self, matrix_path: str, metadata_path: str):
        """
        Initialize the TravelTimeManager by loading the matrix and metadata.
        
        Args:
            matrix_path (str): Path to the .npy file containing the travel time matrix
            metadata_path (str): Path to the JSON file containing metadata
            
        Raises:
            ValueError: If matrix dimensions don't match metadata
            FileNotFoundError: If files don't exist
        """
        logger.info(f"Initializing TravelTimeManager from {matrix_path}")
        
        # Load matrix and metadata
        self.travel_time_matrix = self.load_matrix(matrix_path)
        metadata = self.load_metadata(metadata_path)
        
        # Extract metadata
        self.station_mapping = metadata['station_mapping']
        self.time_slot_duration = metadata.get('time_slot_duration', 10)
        self.simulation_start_time = metadata.get('start_time', 0.0)
        
        # Create reverse mapping for index -> station_id lookups
        self.reverse_mapping = {idx: station_id for station_id, idx in self.station_mapping.items()}
        
        # Store dimensions
        self.num_stations = self.travel_time_matrix.shape[0]
        self.num_time_slots = self.travel_time_matrix.shape[2]
        
        # Validate consistency between matrix and metadata
        if len(self.station_mapping) != self.num_stations:
            raise ValueError(
                f"Station mapping size ({len(self.station_mapping)}) "
                f"doesn't match matrix dimension ({self.num_stations})"
            )
        
        # Log initialization info
        logger.info(f"Matrix shape: {self.travel_time_matrix.shape}")
        logger.info(f"Number of stations: {self.num_stations}")
        logger.info(f"Number of time slots: {self.num_time_slots}")
        logger.info(f"Time slot duration: {self.time_slot_duration} minutes")
        
        # Validate matrix integrity
        if not self.validate_matrix():
            logger.warning("Matrix validation found issues - check logs")
    
    def load_matrix(self, matrix_path: str) -> np.ndarray:
        """
        Load the travel time matrix from a .npy file.
        
        Args:
            matrix_path (str): Path to the .npy file
            
        Returns:
            np.ndarray: Loaded 3D travel time matrix
            
        Raises:
            ValueError: If the loaded array is not 3D
            FileNotFoundError: If file doesn't exist
        """
        try:
            matrix = np.load(matrix_path)
        except FileNotFoundError:
            logger.error(f"Matrix file not found: {matrix_path}")
            raise
        
        # Validate that matrix is 3D
        if matrix.ndim != 3:
            raise ValueError(
                f"Expected 3D matrix, got {matrix.ndim}D array with shape {matrix.shape}"
            )
        
        logger.info(f"Successfully loaded matrix from {matrix_path}")
        return matrix
    
    def load_metadata(self, metadata_path: str) -> dict:
        """
        Load metadata from a JSON file.
        
        Required fields:
            - station_mapping: dict mapping station IDs to indices
            - time_slot_duration: int duration in minutes
            
        Optional fields:
            - start_time: simulation start time
            - end_time: simulation end time
            - date: date of the data
            
        Args:
            metadata_path (str): Path to the JSON metadata file
            
        Returns:
            dict: Metadata dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            KeyError: If required fields are missing
            json.JSONDecodeError: If JSON is invalid
        """
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        except FileNotFoundError:
            logger.error(f"Metadata file not found: {metadata_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {metadata_path}: {e}")
            raise
        
        # Validate required fields
        required_fields = ['station_mapping', 'time_slot_duration']
        for field in required_fields:
            if field not in metadata:
                raise KeyError(f"Required field '{field}' missing from metadata")
        
        logger.info(f"Successfully loaded metadata from {metadata_path}")
        return metadata
    
    @lru_cache(maxsize=1024)
    def get_travel_time(self, origin_id: str, dest_id: str, current_time: float) -> float:
        """
        Get the travel time between two stations at a specific simulation time.
        
        This is a performance-critical method that's called frequently during simulation.
        Results are cached using LRU cache for repeated queries.
        
        Args:
            origin_id (str): Origin station ID
            dest_id (str): Destination station ID
            current_time (float): Current simulation time in seconds
            
        Returns:
            float: Travel time in seconds
            
        Raises:
            ValueError: If station IDs are invalid or time is negative
            
        Examples:
            >>> manager.get_travel_time("A", "B", 2100.0)
            450.0
        """
        # Special case: same origin and destination
        if origin_id == dest_id:
            return 0.0
        
        # Convert station IDs to indices
        origin_idx = self.get_station_index(origin_id)
        dest_idx = self.get_station_index(dest_id)
        
        # Convert time to slot index
        slot_idx = self.time_to_slot_index(current_time)
        
        # Lookup travel time from matrix
        travel_time = self.travel_time_matrix[origin_idx, dest_idx, slot_idx]
        
        return float(travel_time)
    
    def time_to_slot_index(self, current_time: float) -> int:
        """
        Convert simulation time (in seconds) to a time slot index.
        
        Args:
            current_time (float): Current simulation time in seconds
            
        Returns:
            int: Time slot index (0-indexed)
            
        Raises:
            ValueError: If current_time is negative
            
        Examples:
            >>> manager.time_to_slot_index(2100.0)  # 2100 seconds / 600 seconds per slot
            3
        """
        if current_time < 0:
            raise ValueError(f"current_time must be non-negative, got {current_time}")
        
        # Convert time from seconds to slot index
        # time_slot_duration is in minutes, so multiply by 60 for seconds
        slot_duration_seconds = self.time_slot_duration * 60
        slot_index = int(current_time // slot_duration_seconds)
        
        # Handle boundary case: if index exceeds available slots, use last slot
        if slot_index >= self.num_time_slots:
            logger.debug(
                f"Time {current_time}s (slot {slot_index}) exceeds available slots "
                f"({self.num_time_slots}), using last slot"
            )
            slot_index = self.num_time_slots - 1
        
        return slot_index
    
    @lru_cache(maxsize=512)
    def get_station_index(self, station_id: str) -> int:
        """
        Get the matrix index for a given station ID.
        
        This method is cached to improve performance for repeated lookups.
        
        Args:
            station_id (str): Station identifier
            
        Returns:
            int: Index in the travel time matrix
            
        Raises:
            ValueError: If station_id doesn't exist in the mapping
        """
        if station_id not in self.station_mapping:
            raise ValueError(
                f"Station ID '{station_id}' not found in station mapping. "
                f"Available stations: {list(self.station_mapping.keys())}"
            )
        
        return self.station_mapping[station_id]
    
    def get_station_id(self, index: int) -> str:
        """
        Get the station ID for a given matrix index.
        
        Args:
            index (int): Matrix index
            
        Returns:
            str: Station identifier
            
        Raises:
            ValueError: If index is invalid
        """
        if index < 0 or index >= self.num_stations:
            raise ValueError(
                f"Invalid station index {index}. "
                f"Valid range: [0, {self.num_stations - 1}]"
            )
        
        if index not in self.reverse_mapping:
            raise ValueError(f"No station ID found for index {index}")
        
        return self.reverse_mapping[index]
    
    def validate_matrix(self) -> bool:
        """
        Validate the integrity of the travel time matrix.
        
        Checks performed:
            - Correct shape (3D)
            - Diagonal elements are zero (same station travel time)
            - All values are non-negative
            - No NaN or Inf values
            
        Returns:
            bool: True if all validation checks pass
        """
        logger.info("Validating travel time matrix...")
        
        all_valid = True
        
        # Check 1: Shape is 3D
        if self.travel_time_matrix.ndim != 3:
            logger.error(f"Matrix is not 3D: shape {self.travel_time_matrix.shape}")
            all_valid = False
        
        # Check 2: Diagonal elements should be 0 (same origin and destination)
        for time_slot in range(self.num_time_slots):
            diagonal = np.diagonal(self.travel_time_matrix[:, :, time_slot])
            if not np.allclose(diagonal, 0):
                logger.warning(
                    f"Time slot {time_slot}: diagonal contains non-zero values. "
                    f"Max diagonal value: {np.max(np.abs(diagonal))}"
                )
                all_valid = False
        
        # Check 3: All values should be non-negative
        if np.any(self.travel_time_matrix < 0):
            negative_count = np.sum(self.travel_time_matrix < 0)
            logger.error(f"Found {negative_count} negative travel times")
            all_valid = False
        
        # Check 4: No NaN or Inf values
        if np.any(np.isnan(self.travel_time_matrix)):
            nan_count = np.sum(np.isnan(self.travel_time_matrix))
            logger.error(f"Found {nan_count} NaN values in matrix")
            all_valid = False
        
        if np.any(np.isinf(self.travel_time_matrix)):
            inf_count = np.sum(np.isinf(self.travel_time_matrix))
            logger.error(f"Found {inf_count} Inf values in matrix")
            all_valid = False
        
        if all_valid:
            logger.info("Matrix validation passed all checks")
        else:
            logger.warning("Matrix validation found issues")
        
        return all_valid
    
    def get_matrix_stats(self) -> dict:
        """
        Get statistical information about the travel time matrix.
        
        Useful for debugging and validation purposes.
        
        Returns:
            dict: Dictionary containing statistics including:
                - min: minimum travel time
                - max: maximum travel time
                - mean: average travel time
                - std: standard deviation
                - temporal_variance: variance across time slots for each OD pair
        """
        # Mask diagonal (same-station) values for meaningful statistics
        mask = np.ones_like(self.travel_time_matrix, dtype=bool)
        for i in range(self.num_stations):
            mask[i, i, :] = False
        
        masked_matrix = self.travel_time_matrix[mask]
        
        stats = {
            'min': float(np.min(masked_matrix)),
            'max': float(np.max(masked_matrix)),
            'mean': float(np.mean(masked_matrix)),
            'std': float(np.std(masked_matrix)),
            'median': float(np.median(masked_matrix)),
        }
        
        # Calculate temporal variance: how much do travel times vary over time?
        # For each OD pair, compute variance across time slots
        temporal_variances = []
        for i in range(self.num_stations):
            for j in range(self.num_stations):
                if i != j:  # Skip diagonal
                    time_series = self.travel_time_matrix[i, j, :]
                    temporal_variances.append(np.var(time_series))
        
        stats['temporal_variance_mean'] = float(np.mean(temporal_variances))
        stats['temporal_variance_max'] = float(np.max(temporal_variances))
        
        return stats
    
    def __repr__(self) -> str:
        """
        Return a readable string representation of the TravelTimeManager.
        
        Returns:
            str: String representation
        """
        return (
            f"TravelTimeManager("
            f"stations={self.num_stations}, "
            f"time_slots={self.num_time_slots}, "
            f"slot_duration={self.time_slot_duration}min)"
        )
    

# simple testing (should be removed in production)
if __name__ == "__main__":
    # This section demonstrates how to use the TravelTimeManager
    # In production, this would be in a separate test file
    
    # Example: Create sample data for testing
    import os
    
    # Create sample matrix (5 stations, 5 stations, 72 time slots)
    # Dimensions: (origin_stations, destination_stations, time_slots)
    n_stations = 5
    n_time_slots = 72
    
    sample_matrix = np.random.uniform(300, 900, (n_stations, n_stations, n_time_slots))
    
    # Set diagonal to 0 (same station to same station has 0 travel time)
    for t in range(n_time_slots):
        np.fill_diagonal(sample_matrix[:, :, t], 0)
    
    # Create sample metadata
    sample_metadata = {
        'station_mapping': {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4},
        'time_slot_duration': 10,
        'start_time': 0.0,
        'date': '2024-01-01'
    }
    
    # Save sample files
    os.makedirs('data', exist_ok=True)
    np.save('data/travel_time_matrix.npy', sample_matrix)
    with open('data/matrix_metadata.json', 'w') as f:
        json.dump(sample_metadata, f)
    
    # Initialize manager
    manager = TravelTimeManager(
        'data/travel_time_matrix.npy',
        'data/matrix_metadata.json'
    )
    
    # Test queries
    print(f"\n{manager}")
    print(f"\nTravel time A->B at t=2100s: {manager.get_travel_time('A', 'B', 2100.0):.1f}s")
    print(f"Time slot for t=2100s: {manager.time_to_slot_index(2100.0)}")
    print(f"\nMatrix stats: {manager.get_matrix_stats()}")