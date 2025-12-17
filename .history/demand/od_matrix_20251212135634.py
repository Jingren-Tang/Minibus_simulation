"""
OD (Origin-Destination) Matrix Manager

This module handles loading and sampling from OD matrices to generate
realistic passenger demand patterns.
"""

import numpy as np
import json
import logging
from typing import Dict, Tuple, List
from datetime import datetime, timedelta


class ODMatrixManager:
    """
    Manages Origin-Destination demand matrices.
    
    The OD matrix has shape (n_stations, n_stations, n_time_slots) where:
    - First dimension: origin station
    - Second dimension: destination station  
    - Third dimension: time slot
    - Values: expected number of passengers per time slot
    """
    
    def __init__(self, od_matrix_path: str, metadata_path: str):
        """
        Initialize the OD Matrix Manager.
        
        Args:
            od_matrix_path: Path to the OD matrix file (.npy format)
            metadata_path: Path to the metadata JSON file
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing ODMatrixManager from {od_matrix_path}")
        
        # Load OD matrix
        try:
            self.od_matrix = np.load(od_matrix_path)
            self.logger.info(f"Successfully loaded OD matrix from {od_matrix_path}")
        except Exception as e:
            self.logger.error(f"Failed to load OD matrix: {e}")
            raise
        
        # Load metadata
        try:
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
            self.logger.info(f"Successfully loaded metadata from {metadata_path}")
        except Exception as e:
            self.logger.error(f"Failed to load metadata: {e}")
            raise
        
        # Extract metadata
        self.station_ids = self.metadata['station_ids']
        self.n_stations = len(self.station_ids)
        self.n_time_slots = self.metadata.get('n_time_slots', self.od_matrix.shape[2])
        self.time_slot_duration = self.metadata.get('time_slot_duration_seconds', 600)  # Default 10 minutes
        
        # Create station ID to index mapping
        self.station_id_to_index = {
            station_id: idx for idx, station_id in enumerate(self.station_ids)
        }
        
        # Validate matrix shape
        expected_shape = (self.n_stations, self.n_stations, self.n_time_slots)
        if self.od_matrix.shape != expected_shape:
            raise ValueError(
                f"OD matrix shape {self.od_matrix.shape} does not match "
                f"expected shape {expected_shape}"
            )
        
        self.logger.info(f"OD Matrix shape: {self.od_matrix.shape}")
        self.logger.info(f"Number of stations: {self.n_stations}")
        self.logger.info(f"Number of time slots: {self.n_time_slots}")
        self.logger.info(f"Time slot duration: {self.time_slot_duration} seconds ({self.time_slot_duration/60:.1f} minutes)")
        
        # Compute total demand statistics
        self._compute_statistics()
    
    def _compute_statistics(self):
        """Compute and log statistics about the OD matrix."""
        total_demand = np.sum(self.od_matrix)
        avg_demand_per_slot = total_demand / self.n_time_slots
        max_demand_slot = np.max(np.sum(self.od_matrix, axis=(0, 1)))
        min_demand_slot = np.min(np.sum(self.od_matrix, axis=(0, 1)))
        
        self.logger.info(f"Total demand in OD matrix: {total_demand:.1f} passengers")
        self.logger.info(f"Average demand per time slot: {avg_demand_per_slot:.1f} passengers")
        self.logger.info(f"Peak time slot demand: {max_demand_slot:.1f} passengers")
        self.logger.info(f"Minimum time slot demand: {min_demand_slot:.1f} passengers")
    
    def get_time_slot_index(self, simulation_time: float) -> int:
        """
        Get the time slot index for a given simulation time.
        
        Args:
            simulation_time: Time in seconds since simulation start
            
        Returns:
            Time slot index (0 to n_time_slots-1)
        """
        slot_index = int(simulation_time / self.time_slot_duration)
        return min(slot_index, self.n_time_slots - 1)
    
    def get_demand_rate(self, origin_id: str, dest_id: str, simulation_time: float) -> float:
        """
        Get the demand rate (passengers per second) for an OD pair at a given time.
        
        Args:
            origin_id: Origin station ID
            dest_id: Destination station ID
            simulation_time: Time in seconds since simulation start
            
        Returns:
            Demand rate in passengers per second
        """
        if origin_id not in self.station_id_to_index or dest_id not in self.station_id_to_index:
            return 0.0
        
        origin_idx = self.station_id_to_index[origin_id]
        dest_idx = self.station_id_to_index[dest_id]
        time_slot = self.get_time_slot_index(simulation_time)
        
        # Get demand for this time slot (passengers per slot)
        demand_per_slot = self.od_matrix[origin_idx, dest_idx, time_slot]
        
        # Convert to rate (passengers per second)
        demand_rate = demand_per_slot / self.time_slot_duration
        
        return demand_rate
    
    def get_total_demand_rate(self, simulation_time: float) -> float:
        """
        Get the total demand rate across all OD pairs at a given time.
        
        Args:
            simulation_time: Time in seconds since simulation start
            
        Returns:
            Total demand rate in passengers per second
        """
        time_slot = self.get_time_slot_index(simulation_time)
        total_demand_per_slot = np.sum(self.od_matrix[:, :, time_slot])
        return total_demand_per_slot / self.time_slot_duration
    
    def sample_od_pair(self, simulation_time: float, random_state: np.random.RandomState = None) -> Tuple[str, str]:
        """
        Sample an origin-destination pair based on the demand distribution at the given time.
        
        Args:
            simulation_time: Time in seconds since simulation start
            random_state: NumPy random state for reproducibility
            
        Returns:
            Tuple of (origin_station_id, destination_station_id)
        """
        if random_state is None:
            random_state = np.random.RandomState()
        
        time_slot = self.get_time_slot_index(simulation_time)
        
        # Get demand matrix for this time slot
        demand_matrix = self.od_matrix[:, :, time_slot]
        
        # Flatten and normalize to create probability distribution
        demand_flat = demand_matrix.flatten()
        total_demand = np.sum(demand_flat)
        
        if total_demand == 0:
            # No demand at this time, return random OD pair
            self.logger.warning(f"No demand at time slot {time_slot}, sampling random OD pair")
            origin_idx = random_state.randint(0, self.n_stations)
            dest_idx = random_state.randint(0, self.n_stations)
            while dest_idx == origin_idx:
                dest_idx = random_state.randint(0, self.n_stations)
        else:
            # Sample based on demand probabilities
            probabilities = demand_flat / total_demand
            sampled_idx = random_state.choice(len(demand_flat), p=probabilities)
            
            # Convert flat index back to (origin, destination) indices
            origin_idx = sampled_idx // self.n_stations
            dest_idx = sampled_idx % self.n_stations
        
        origin_id = self.station_ids[origin_idx]
        dest_id = self.station_ids[dest_idx]
        
        return origin_id, dest_id
    
    def generate_passengers_for_slot(
        self, 
        time_slot_start: float, 
        random_state: np.random.RandomState = None
    ) -> List[Tuple[str, str, float]]:
        """
        Generate all passengers for a given time slot using Poisson sampling.
        
        Args:
            time_slot_start: Start time of the slot in seconds
            random_state: NumPy random state for reproducibility
            
        Returns:
            List of (origin_id, dest_id, appear_time) tuples
        """
        if random_state is None:
            random_state = np.random.RandomState()
        
        time_slot = self.get_time_slot_index(time_slot_start)
        demand_matrix = self.od_matrix[:, :, time_slot]
        
        passengers = []
        
        # For each OD pair
        for origin_idx in range(self.n_stations):
            for dest_idx in range(self.n_stations):
                if origin_idx == dest_idx:
                    continue
                
                # Get expected number of passengers
                expected_passengers = demand_matrix[origin_idx, dest_idx]
                
                if expected_passengers > 0:
                    # Sample actual number using Poisson distribution
                    n_passengers = random_state.poisson(expected_passengers)
                    
                    # Generate arrival times uniformly within the slot
                    for _ in range(n_passengers):
                        # Uniform arrival time within the slot
                        appear_time = time_slot_start + random_state.uniform(0, self.time_slot_duration)
                        
                        origin_id = self.station_ids[origin_idx]
                        dest_id = self.station_ids[dest_idx]
                        
                        passengers.append((origin_id, dest_id, appear_time))
        
        return passengers
    
    def get_od_pairs_for_slot(self, time_slot: int) -> List[Tuple[str, str, float]]:
        """
        Get all non-zero OD pairs and their demands for a specific time slot.
        
        Args:
            time_slot: Time slot index
            
        Returns:
            List of (origin_id, dest_id, demand) tuples
        """
        demand_matrix = self.od_matrix[:, :, time_slot]
        od_pairs = []
        
        for origin_idx in range(self.n_stations):
            for dest_idx in range(self.n_stations):
                if origin_idx != dest_idx:
                    demand = demand_matrix[origin_idx, dest_idx]
                    if demand > 0:
                        origin_id = self.station_ids[origin_idx]
                        dest_id = self.station_ids[dest_idx]
                        od_pairs.append((origin_id, dest_id, demand))
        
        return od_pairs


if __name__ == "__main__":
    # Test the OD matrix manager
    logging.basicConfig(level=logging.INFO)
    
    od_manager = ODMatrixManager(
        od_matrix_path="data/od_matrix.npy",
        metadata_path="data/od_metadata.json"
    )
    
    # Test sampling
    print("\nTesting OD pair sampling:")
    for i in range(5):
        origin, dest = od_manager.sample_od_pair(simulation_time=3000.0)
        print(f"Sample {i+1}: {origin} -> {dest}")
    
    # Test passenger generation for a slot
    print("\nTesting passenger generation for time slot 0:")
    passengers = od_manager.generate_passengers_for_slot(time_slot_start=0.0)
    print(f"Generated {len(passengers)} passengers")
    if passengers:
        print(f"First 5 passengers: {passengers[:5]}")