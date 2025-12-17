"""
Google Distance Matrix API Data Collection Script
Collects taxi travel times between 22 Fribourg stations
Time range: 15:00-21:00, every 10 minutes (36 time points)
Mode: Driving (taxi)
"""

import googlemaps
import json
import sys
import time
import csv
from datetime import datetime, timedelta
import pytz

def load_stations(json_file):
    """Load station data from JSON file"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['stations']

def generate_time_points(base_date, start_hour=15, start_min=0, end_hour=21, end_min=0, interval_min=10):
    """
    Generate list of datetime objects for departure times
    
    Args:
        base_date: datetime object for the base date (should be a weekday)
        start_hour: starting hour (default 15)
        start_min: starting minute (default 0)
        end_hour: ending hour (default 21)
        end_min: ending minute (default 0)
        interval_min: interval in minutes (default 10)
    
    Returns:
        List of datetime objects in Switzerland timezone
    """
    # Switzerland timezone
    swiss_tz = pytz.timezone('Europe/Zurich')
    
    # Create start datetime
    start_dt = swiss_tz.localize(datetime(
        base_date.year, base_date.month, base_date.day,
        start_hour, start_min, 0
    ))
    
    # Create end datetime
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

def get_distance_matrix(gmaps_client, origins, destinations, departure_time):
    """
    Call Google Distance Matrix API
    
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
            mode="driving",  # Taxi uses driving mode
            departure_time=departure_time,
            traffic_model="best_guess",  # Uses historical traffic data
            units="metric"
        )
        return result
    except Exception as e:
        print(f"Error calling API: {e}")
        return None

def parse_distance_matrix_response(response, stations, departure_time):
    """
    Parse Distance Matrix API response and extract travel times
    
    Args:
        response: API response dict
        stations: List of station dicts
        departure_time: datetime object
    
    Returns:
        List of dicts containing travel time data
    """
    if not response or response.get('status') != 'OK':
        print(f"API returned error status: {response.get('status') if response else 'None'}")
        return []
    
    results = []
    rows = response.get('rows', [])
    
    for i, row in enumerate(rows):
        origin_station = stations[i]
        elements = row.get('elements', [])
        
        for j, element in enumerate(elements):
            dest_station = stations[j]
            
            # Skip if origin == destination
            if i == j:
                continue
            
            status = element.get('status')
            
            if status == 'OK':
                duration = element.get('duration', {}).get('value')  # in seconds
                distance = element.get('distance', {}).get('value')  # in meters
                
                # Check if traffic data is available
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
            else:
                # Record failed requests
                result = {
                    'departure_time': departure_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'origin_station_id': origin_station['station_id'],
                    'origin_name': origin_station['name'],
                    'dest_station_id': dest_station['station_id'],
                    'dest_name': dest_station['name'],
                    'status': status,
                    'error': element.get('status')
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
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasuffix='')
        writer.writeheader()
        
        for result in results:
            # Only write fields that exist
            row = {k: result.get(k, '') for k in fieldnames}
            writer.writerow(row)
    
    print(f"✓ Results saved to: {output_file}")

def main():
    """Main function to orchestrate data collection"""
    
    # Check command line arguments
    if len(sys.argv) < 3:
        print("Usage: python collect_travel_times.py <API_KEY> <stations_json_file>")
        print("Example: python collect_travel_times.py YOUR_API_KEY stations_updated.json")
        sys.exit(1)
    
    API_KEY = sys.argv[1]
    STATIONS_FILE = sys.argv[2]
    
    print("="*80)
    print("Google Distance Matrix API - Travel Time Collection")
    print("="*80)
    
    # Initialize Google Maps client
    print("\n1. Initializing Google Maps client...")
    gmaps = googlemaps.Client(key=API_KEY)
    
    # Load stations
    print(f"2. Loading stations from {STATIONS_FILE}...")
    stations = load_stations(STATIONS_FILE)
    print(f"   Loaded {len(stations)} stations")
    
    # Generate time points - using a Wednesday in December 2025
    base_date = datetime(2025, 12, 17)  # Wednesday, December 17, 2025
    print(f"\n3. Generating time points (base date: {base_date.strftime('%Y-%m-%d %A')})...")
    time_points = generate_time_points(base_date)
    print(f"   Generated {len(time_points)} time points from 15:00 to 21:00")
    
    # Prepare origins and destinations (using coordinates)
    origins = [(station['location'][0], station['location'][1]) for station in stations]
    destinations = origins.copy()
    
    print(f"\n4. API call details:")
    print(f"   Origins: {len(origins)} stations")
    print(f"   Destinations: {len(destinations)} stations")
    print(f"   Elements per request: {len(origins)} × {len(destinations)} = {len(origins) * len(destinations)}")
    print(f"   Total requests: {len(time_points)}")
    print(f"   Total elements: {len(time_points) * len(origins) * len(destinations)}")
    print(f"   Estimated cost: ${len(time_points) * len(origins) * len(destinations) * 0.005:.2f} - ${len(time_points) * len(origins) * len(destinations) * 0.01:.2f}")
    
    # Confirm before starting
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
        
        # Call API
        response = get_distance_matrix(gmaps, origins, destinations, departure_time)
        
        if response:
            # Parse response
            results = parse_distance_matrix_response(response, stations, departure_time)
            all_results.extend(results)
            print(f"   ✓ Received {len(results)} route results")
        else:
            print(f"   ✗ API call failed")
        
        # Rate limiting - wait between requests
        if idx < len(time_points):
            print("   Waiting 1 second before next request...")
            time.sleep(1)
    
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
    print(f"Success rate: {len(all_results) / (len(time_points) * len(stations) * (len(stations) - 1)) * 100:.1f}%")
    print(f"\nOutput file: {output_file}")
    print("="*80)

if __name__ == "__main__":
    main()
