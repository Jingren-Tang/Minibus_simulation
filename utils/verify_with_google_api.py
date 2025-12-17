

import googlemaps
import json
import sys
import folium
import time

if len(sys.argv) < 2:
    print("Usage: python verify_with_google_api.py YOUR_API_KEY")
    sys.exit(1)

API_KEY = sys.argv[1]
gmaps = googlemaps.Client(key=API_KEY)

stations = {
  "stations": [
    {
      "station_id": "8589141",
      "name": "Fribourg, Chaley",
      "location": [46.806281, 7.175601],
      "index": 0
    },
    {
      "station_id": "8589152",
      "name": "Fribourg, Mon-Repos",
      "location": [46.806711, 7.172136],
      "index": 1
    },
    {
      "station_id": "8589138",
      "name": "Fribourg, Cité-Jardins",
      "location": [46.809385, 7.170446],
      "index": 2
    },
    {
      "station_id": "8591766",
      "name": "Fribourg, Boschung",
      "location": [46.811451, 7.171016],
      "index": 3
    },
    {
      "station_id": "8587255",
      "name": "Fribourg, Tilleul/Cathédrale",
      "location": [46.80609, 7.161261],
      "index": 4
    },
    {
      "station_id": "8589161",
      "name": "Fribourg, St-Pierre",
      "location": [46.803911, 7.155266],
      "index": 5
    },
    {
      "station_id": "8592374",
      "name": "Fribourg/Freiburg, Pl. Gare",
      "location": [46.802898, 7.15141],
      "index": 6
    },
    {
      "station_id": "8589130",
      "name": "Villars-sur-Glâne, Méridienne",
      "location": [46.794173, 7.111828],
      "index": 7
    },
    {
      "station_id": "8589131",
      "name": "Villars-sur-Glâne, Moncor",
      "location": [46.79857, 7.120788],
      "index": 8
    },
    {
      "station_id": "8588344",
      "name": "Villars-sur-Glâne, Belle-Croix",
      "location": [46.800233, 7.125455],
      "index": 9
    },
    {
      "station_id": "8577786",
      "name": "Villars-sur-Glâne,Villars-Vert",
      "location": [46.798991, 7.131395],
      "index": 10
    },
    {
      "station_id": "8577785",
      "name": "Fribourg, Bertigny",
      "location": [46.8013, 7.138046],
      "index": 11
    },
    {
      "station_id": "8504622",
      "name": "Fribourg, Bellevue",
      "location": [46.81092671540513, 7.171932726075358],
      "index": 12
    },
    {
      "station_id": "8589271",
      "name": "Fribourg, Schönberg Dunant",
      "location": [46.80542535842347, 7.178406780411913],
      "index": 13
    },
    {
      "station_id": "8592375",
      "name": "Fribourg, Guintzet",
      "location": [46.80549, 7.140123],
      "index": 14
    },
    {
      "station_id": "8592378",
      "name": "Villars-sur-Glâne,Jean Paul II",
      "location": [46.803893, 7.137545],
      "index": 15
    },
    {
      "station_id": "8592377",
      "name": "Villars-sur-Glâne, Hôp. cant.",
      "location": [46.801851, 7.13667],
      "index": 16
    },
    {
      "station_id": "8591767",
      "name": "Fribourg, Route-de-Tavel",
      "location": [46.811223, 7.172643],
      "index": 17
    },
    {
      "station_id": "8589270",
      "name": "Fribourg, Kessler",
      "location": [46.812081, 7.173246],
      "index": 18
    },
    {
      "station_id": "8589147",
      "name": "Fribourg, Ploetscha",
      "location": [46.813063, 7.173218],
      "index": 19
    },
    {
      "station_id": "8589158",
      "name": "Fribourg, Windig",
      "location": [46.816016, 7.17397],
      "index": 20
    },
    {
      "station_id": "8587356",
      "name": "Fribourg, Pont-Zaehringen",
      "location": [46.807676, 7.168025],
      "index": 21
    }
  ]
}

stations_list = stations['stations']

results = []
print("\nVerifying station names with Google Maps Geocoding API...")
print("="*80)

for station in stations_list:
    name = station['name']
    original_lat, original_lon = station['location']
    
    try:
        # Geocode the station name
        geocode_result = gmaps.geocode(name + ", Switzerland")
        
        if geocode_result:
            google_location = geocode_result[0]['geometry']['location']
            google_lat = google_location['lat']
            google_lon = google_location['lng']
            formatted_address = geocode_result[0]['formatted_address']
            
            # Calculate distance difference (rough estimate in meters)
            lat_diff = abs(google_lat - original_lat) * 111000
            lon_diff = abs(google_lon - original_lon) * 111000 * 0.7
            distance_diff = (lat_diff**2 + lon_diff**2)**0.5
            
            results.append({
                'station': station,
                'google_lat': google_lat,
                'google_lon': google_lon,
                'formatted_address': formatted_address,
                'distance_diff': distance_diff,
                'found': True
            })
            
            status = "✓ FOUND" if distance_diff < 500 else "⚠ FOUND (far from original)"
            print(f"{status:25} {name}")
            print(f"  Original: [{original_lat:.6f}, {original_lon:.6f}]")
            print(f"  Google:   [{google_lat:.6f}, {google_lon:.6f}]")
            print(f"  Address:  {formatted_address}")
            print(f"  Distance: {distance_diff:.0f}m")
        else:
            results.append({
                'station': station,
                'found': False
            })
            print(f"✗ NOT FOUND            {name}")
        
        print()
        time.sleep(0.2)  # Rate limiting
        
    except Exception as e:
        print(f"✗ ERROR                {name}: {str(e)}")
        results.append({
            'station': station,
            'found': False,
            'error': str(e)
        })
        print()

# Create comparison map
print("="*80)
print("Creating comparison map...")
avg_lat = sum(s['location'][0] for s in stations_list) / len(stations_list)
avg_lon = sum(s['location'][1] for s in stations_list) / len(stations_list)

m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13)

for result in results:
    if result['found']:
        station = result['station']
        original_lat, original_lon = station['location']
        google_lat = result['google_lat']
        google_lon = result['google_lon']
        
        # Original location (red)
        folium.CircleMarker(
            location=[original_lat, original_lon],
            radius=8,
            color='red',
            fill=True,
            fillColor='red',
            fillOpacity=0.6,
            popup=f"<b>Original:</b> {station['name']}"
        ).add_to(m)
        
        # Google location (green)
        folium.CircleMarker(
            location=[google_lat, google_lon],
            radius=8,
            color='green',
            fill=True,
            fillColor='green',
            fillOpacity=0.6,
            popup=f"<b>Google:</b> {station['name']}<br>{result['formatted_address']}<br>Distance: {result['distance_diff']:.0f}m"
        ).add_to(m)
        
        # Draw line between them
        folium.PolyLine(
            locations=[[original_lat, original_lon], [google_lat, google_lon]],
            color='blue',
            weight=2,
            opacity=0.5
        ).add_to(m)

output_file = 'google_geocoding_comparison.html'
m.save(output_file)
print(f"Map saved to: {output_file}")

# Summary
print("\n" + "="*80)
print("SUMMARY:")
print("="*80)
found = sum(1 for r in results if r['found'])
print(f"Found by Google: {found}/{len(results)}")
close = sum(1 for r in results if r.get('found') and r.get('distance_diff', 1000) < 100)
print(f"Within 100m: {close}/{len(results)}")
moderate = sum(1 for r in results if r.get('found') and 100 <= r.get('distance_diff', 1000) < 500)
print(f"100-500m away: {moderate}/{len(results)}")
far = sum(1 for r in results if r.get('found') and r.get('distance_diff', 0) >= 500)
print(f"More than 500m away: {far}/{len(results)}")

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
if far > 0:
    print("⚠ Some stations are far from original coordinates.")
    print("Using station names with Google Maps API is recommended.")
else:
    print("✓ Most stations match well with original coordinates.")
    print("You can use either station names or coordinates.")