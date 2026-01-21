import os
import json
import glob
import random

def generate_routes():
    base_dir = "data/zones"
    zones = glob.glob(os.path.join(base_dir, "*"))
    
    for zone_path in zones:
        if not os.path.isdir(zone_path): continue
        zone_name = os.path.basename(zone_path)
        
        # Load Localities
        loc_file = os.path.join(zone_path, "localities.geojson")
        if not os.path.exists(loc_file):
            print(f"Skipping {zone_name}: No localities.")
            continue
            
        with open(loc_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            features = data.get('features', [])
            
        if len(features) < 2:
            print(f"Skipping {zone_name}: Not enough localities ({len(features)}).")
            continue
            
        # Extract centroids
        points = []
        names = []
        for feat in features:
            props = feat.get('properties', {})
            geom = feat.get('geometry', {})
            coords = geom.get('coordinates', [])
            
            # Simple centroid calc for Polygon
            if geom['type'] == 'Polygon':
                # avg of ring
                ring = coords[0]
                lon = sum(p[0] for p in ring) / len(ring)
                lat = sum(p[1] for p in ring) / len(ring)
                points.append((lon, lat))
                names.append(props.get('name', 'Unknown'))
            elif geom['type'] == 'Point':
                points.append(coords)
                names.append(props.get('name', 'Unknown'))
                
        # Generate 15 Routes
        routes = []
        for i in range(1, 16):
            route_id = f"RT_{zone_name}_{i:02d}"
            
            # Pick 3 to 6 stops
            num_stops = random.randint(3, 6)
            stops_indices = random.sample(range(len(points)), min(num_stops, len(points)))
            
            waypoints = [points[idx] for idx in stops_indices]
            stop_names = [names[idx] for idx in stops_indices]
            
            route_def = {
                "route_id": route_id,
                "name": f"Route {i}: {' - '.join(stop_names[:3])}...",
                "waypoints": waypoints, # [[lon, lat], ...]
                "stops": stop_names
            }
            routes.append(route_def)
            
        # Save
        out_file = os.path.join(zone_path, "routes.json")
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump({"routes": routes}, f, indent=2)
            
        print(f"Generated {len(routes)} routes for {zone_name}")

if __name__ == "__main__":
    generate_routes()
