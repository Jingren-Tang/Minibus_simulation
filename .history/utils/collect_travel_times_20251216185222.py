"""
Google Distance Matrix API Data Collection Script (FIXED - Batched Version)
Collects taxi travel times between 22 Fribourg stations
Time range: 15:00-21:00, every 10 minutes (37 time points)
Mode: Driving (taxi)

FIX: Splits requests into batches to avoid MAX_ELEMENTS_EXCEEDED error
Google API limit: 100 elements per request
Solution: Query in batches of 10x10 (100 elements)
"""

import googlemaps
import json
import sys
import time
import csv
from datetime import datetime, timedelta
import pytz
import math

def load_stations(json_file):
    """Load station data from JSON file"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['stations']

def generate_time_points(base_date, start_hour=15, start_min=0, end_hour=21, end_min=0, interval_min=10):
    """
    Generate list of datetime objects for departure times
    """
    swiss_tz = pytz.timezone('Europe/Zurich')
    
    start_dt = swiss_tz.localize(datetime(
        base_date.year, base_date.month, base_date.day,
        start_hour, start_min, 0
    ))
    
    end_dt = swiss_tz.localize(datetime(
        base_date.year, base_date.month, base_date.day,
        end_hour, end_min, 0
    ))
    
    time_points = []
    current_dt = start_dt
    
    while current_dt <= end_dt:
        time_points.append(current_dt)
        current_dt += timedelta(minutes=interval_min)
    
    return time_points

def get_distance_matrix_batch(gmaps_client, origins, destinations, departure_time):
    """
    Call Google Distance Matrix API with batch handling
    
    Args:
        gmaps_client: Google Maps client object
        origins: List of origin coordinates (lat,lon tuples)
        destinations: List of destination coordinates (lat,lon tuples)
        departure_time: datetime object for departure time
    
    Returns:
        API response dict
    """
    try:
        result = gmaps_client.distance_matrix(
            origins=origins,
            destinations=destinations,
            mode="driving",
            departure_time=departure_time,
            traffic_model="best_guess",
            units="metric"
        )
        return result
    except Exception as e:
        print(f"Error calling API: {e}")
        return None

def collect_distance_matrix_batched(gmaps_client, stations, departure_time, batch_size=10):
    """
    Collect distance matrix data in batches to avoid MAX_ELEMENTS_EXCEEDED
    
    Args:
        gmaps_client: Google Maps client
        stations: List of all stations
        departure_time: datetime object
        batch_size: Maximum origins/destinations per batch (default 10 for 10x10=100 elements)
    
    Returns:
        List of result dicts
    """
    all_coords = [(s['location'][0], s['location'][1]) for s in stations]
    n_stations = len(stations)
    
    # Calculate number of batches needed
    n_batches = math.ceil(n_stations / batch_size)
    
    all_results = []
    
    for i in range(n_batches):
        for j in range(n_batches):
            # Define batch ranges
            origin_start = i * batch_size
            origin_end = min((i + 1) * batch_size, n_stations)
            dest_start = j * batch_size
            dest_end = min((j + 1) * batch_size, n_stations)
            
            # Get batch of origins and destinations
            origin_batch = all_coords[origin_start:origin_end]
            dest_batch = all_coords[dest_start:dest_end]
            origin_stations = stations[origin_start:origin_end]
            dest_stations = stations[dest_start:dest_end]
            
            elements_in_batch = len(origin_batch) * len(dest_batch)
            
            print(f"   Batch [{i+1},{j+1}] of [{n_batches}×{n_batches}]: {len(origin_batch)}×{len(dest_batch)} = {elements_in_batch} elements", end="")
            
            # Call API for this batch
            response = get_distance_matrix_batch(
                gmaps_client, 
                origin_batch, 
                dest_batch, 
                departure_time
            )
            
            if response:
                # Parse results with correct station indices
                batch_results = parse_batch_response(
                    response, 
                    origin_stations, 
                    dest_stations,
                    departure_time
                )
                all_results.extend(batch_results)
                print(f" ✓ ({len(batch_results)} routes)")
            else:
                print(f" ✗ Failed")
            
            # Small delay between batches
            time.sleep(0.3)
    
    return all_results

def parse_batch_response(response, origin_stations, dest_stations, departure_time):
    """
    Parse Distance Matrix API response for a batch
    """
    if not response or response.get('status') != 'OK':
        return []
    
    results = []
    rows = response.get('rows', [])
    
    for i, row in enumerate(rows):
        origin_station = origin_stations[i]
        elements = row.get('elements', [])
        
        for j, element in enumerate(elements):
            dest_station = dest_stations[j]
            
            # Skip if origin == destination
            if origin_station['station_id'] == dest_station['station_id']:
                continue
            
            status = element.get('status')
            
            if status == 'OK':
                duration = element.get('duration', {}).get('value')
                distance = element.get('distance', {}).get('value')
                duration_in_traffic = element.get('duration_in_traffic', {}).get('value')
                
                result = {
                    'departure_time': departure_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'origin_station_id': origin_station['station_id'],
                    'origin_name': origin_station['name'],
                    'origin_lat': origin_station['location'][0],
                    'origin_lon': origin_station['location'][1],
                    'dest_station_id': dest_station['station_id'],
                    'dest_name': dest_station['name'],
                    'dest_lat': dest_station['location'][0],
                    'dest_lon': dest_station['location'][1],
                    'distance_meters': distance,
                    'duration_seconds': duration,
                    'duration_minutes': round(duration / 60, 2) if duration else None,
                    'duration_in_traffic_seconds': duration_in_traffic,
                    'duration_in_traffic_minutes': round(duration_in_traffic / 60, 2) if duration_in_traffic else None,
                    'status': status
                }
                results.append(result)
    
    return results

def save_to_csv(results, output_file):
    """Save results to CSV file"""
    if not results:
        print("No results to save")
        return
    
    fieldnames = [
        'departure_time', 
        'origin_station_id', 'origin_name', 'origin_lat', 'origin_lon',
        'dest_station_id', 'dest_name', 'dest_lat', 'dest_lon',
        'distance_meters', 'duration_seconds', 'duration_minutes',
        'duration_in_traffic_seconds', 'duration_in_traffic_minutes',
        'status'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            row = {k: result.get(k, '') for k in fieldnames}
            writer.writerow(row)
    
    print(f"✓ Results saved to: {output_file}")

def main():
    """Main function to orchestrate data collection"""
    
    if len(sys.argv) < 3:
        print("Usage: python collect_travel_times_fixed.py <API_KEY> <stations_json_file>")
        print("Example: python collect_travel_times_fixed.py YOUR_API_KEY stations_updated.json")
        sys.exit(1)
    
    API_KEY = sys.argv[1]
    STATIONS_FILE = sys.argv[2]
    
    print("="*80)
    print("Google Distance Matrix API - Travel Time Collection (BATCHED VERSION)")
    print("="*80)
    
    # Initialize
    print("\n1. Initializing Google Maps client...")
    gmaps = googlemaps.Client(key=API_KEY)
    
    # Load stations
    print(f"2. Loading stations from {STATIONS_FILE}...")
    stations = load_stations(STATIONS_FILE)
    print(f"   Loaded {len(stations)} stations")
    
    # Generate time points
    base_date = datetime(2024, 7, 25)  # Thursday, July 25, 2024
    print(f"\n3. Generating time points (base date: {base_date.strftime('%Y-%m-%d %A')})...")
    time_points = generate_time_points(base_date, start_hour=15, end_hour=17, interval_min=20)
    print(f"   Generated {len(time_points)} time points from 15:00 to 17:00 (every 20 minutes)")
    
    # Calculate batches
    batch_size = 10  # 10x10 = 100 elements per batch
    n_batches = math.ceil(len(stations) / batch_size)
    total_api_calls = len(time_points) * n_batches * n_batches
    
    print(f"\n4. Batching strategy:")
    print(f"   Batch size: {batch_size}×{batch_size} = {batch_size*batch_size} elements per batch")
    print(f"   Number of batches: {n_batches}×{n_batches} = {n_batches*n_batches} batches per time point")
    print(f"   Total API calls: {len(time_points)} time points × {n_batches*n_batches} batches = {total_api_calls} calls")
    print(f"   Estimated cost: ${total_api_calls * 100 * 0.005:.2f} - ${total_api_calls * 100 * 0.01:.2f}")
    
    # Confirm
    print("\n" + "="*80)
    response = input("Continue with data collection? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled by user")
        sys.exit(0)
    
    # Collect data
    print("\n" + "="*80)
    print("5. Starting data collection...")
    print("="*80)
    
    all_results = []
    
    for idx, departure_time in enumerate(time_points, 1):
        print(f"\n[{idx}/{len(time_points)}] Querying for {departure_time.strftime('%H:%M')}...")
        
        # Collect in batches
        results = collect_distance_matrix_batched(gmaps, stations, departure_time, batch_size=10)
        all_results.extend(results)
        
        print(f"   Total routes collected for this time: {len(results)}")
        
        # Delay between time points
        if idx < len(time_points):
            print("   Waiting 2 seconds before next time point...")
            time.sleep(2)
    
    # Save results
    print("\n" + "="*80)
    print("6. Saving results...")
    output_file = f"travel_times_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    save_to_csv(all_results, output_file)
    
    # Summary
    print("\n" + "="*80)
    print("COLLECTION SUMMARY:")
    print("="*80)
    print(f"Total time points queried: {len(time_points)}")
    print(f"Total route records: {len(all_results)}")
    print(f"Expected records: {len(time_points) * len(stations) * (len(stations) - 1)}")
    if len(time_points) * len(stations) * (len(stations) - 1) > 0:
        print(f"Success rate: {len(all_results) / (len(time_points) * len(stations) * (len(stations) - 1)) * 100:.1f}%")
    print(f"\nOutput file: {output_file}")
    print("="*80)

if __name__ == "__main__":
    main()