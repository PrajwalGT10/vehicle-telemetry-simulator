from shapely.geometry import LineString, Point
from datetime import datetime, timedelta
import random
import os
import json
import hashlib
import networkx as nx
import math

from vts_core.config import load_vehicle_config
from vts_core.store import SimulationStore
from vts_core.graph import RoadNetwork
from vts_core.agent import VehicleAgent

def get_seeded_rng(identifier: str, date_str: str) -> random.Random:
    """
    Creates a deterministic Random instance based on Vehicle ID and Date.
    """
    seed_str = f"{identifier}_{date_str}"
    # Create a reproducible integer seed
    seed_int = int(hashlib.sha256(seed_str.encode('utf-8')).hexdigest(), 16)
    rng = random.Random(seed_int)
    return rng

def find_stochastic_path(network, start_coords, end_coords, rng):
    """
    Finds a path between coords with stochastic edge weights using the provided RNG.
    Returns (LineString, Distance_Meters).
    """
    start_node = network._get_nearest_node(start_coords) # Lat, Lon
    end_node = network._get_nearest_node(end_coords)
    
    if not start_node or not end_node: 
        return None, 0

    if start_node == end_node:
        return None, 0

    # Define weight function with noise
    def noise_weight(u, v, d):
        base_weight = d.get('weight', 1.0)
        # Add +/- 5% noise
        noise = rng.uniform(0.95, 1.05)
        return base_weight * noise

    try:
        # Use networkx with custom weight function
        path_nodes = nx.shortest_path(network.graph, start_node, end_node, weight=noise_weight)
    except nx.NetworkXNoPath:
        return None, 0
        
    coords = []
    total_len = 0
    
    for i in range(len(path_nodes) - 1):
        u = path_nodes[i]
        v = path_nodes[i+1]
        data = network.graph.get_edge_data(u, v)
        
        # Use actual weight for distance calculation, not noisy one
        edge_len = data.get('weight', 0)
        total_len += edge_len
        
        if 'geometry' in data:
            seg_coords = list(data['geometry'].coords)
            if len(coords) > 0: coords.extend(seg_coords[1:])
            else: coords.extend(seg_coords)
        else:
            coords.append(u)
            coords.append(v)
            
    return LineString(coords) if len(coords) > 1 else None, total_len

def run_simulation_day(vehicle_config_path: str, zone_roads_path: str, date: str, output_dir: str = "data", enable_legacy_logs: bool = True):
    # 1. Load Config (Now includes Depot Coords)
    config = load_vehicle_config(vehicle_config_path)
    if not config.enabled:
        # print(f"   🚫 Vehicle {config.name} is disabled (Scrapped). Skipping.") # Optional verbosity
        return

    # Check Simulation Window Bounds
    if config.simulation_window:
        try:
            current_dt = datetime.strptime(date, "%Y-%m-%d")
            s_str = config.simulation_window.get('start_date')
            e_str = config.simulation_window.get('end_date')
            
            if s_str:
                s_date = datetime.strptime(s_str, "%Y-%m-%d")
                if current_dt < s_date: return # Before start
            if e_str:
                e_date = datetime.strptime(e_str, "%Y-%m-%d")
                if current_dt > e_date: return # After end
        except: pass # Ignore parsing errors, assume valid

    store = SimulationStore(base_dir=output_dir, enable_legacy_logs=enable_legacy_logs)
    
    # 2. Load Graph
    # Extract localities file from config (it's in the dict raw config usually, but let's assume config object has it or we pass it)
    # The config object is VehicleConfig. The attributes are populated from YAML.
    # The YAML has 'zone' -> 'localities_file'.
    # We might need to access the raw dictionary or assume attribute 'zone' exists.
    
    # Assuming config has .zone attribute which is a dict
    loc_file = None
    if hasattr(config, "zone") and isinstance(config.zone, dict):
        loc_file = config.zone.get("localities_file")
    
    network = RoadNetwork(zone_roads_path, localities_path=loc_file)
    agent = VehicleAgent(config, store)
    
    # Load Predefined Routes if available
    zone_dir = os.path.dirname(zone_roads_path)
    routes_file = os.path.join(zone_dir, "routes.json")
    predefined_routes = []
    if os.path.exists(routes_file):
        try:
            with open(routes_file, 'r') as rf:
                rdata = json.load(rf)
                predefined_routes = rdata.get("routes", [])
                print(f"   Loaded {len(predefined_routes)} predefined routes for zone.")
        except Exception as e:
            print(f"⚠️ Error loading routes.json: {e}")
    
    # 3. Use Configured Depot (No more hardcoding)
    depot_lat, depot_lon = config.depot_location
    
    # Check graph connectivity relative to specific depot
    home_node = network._get_nearest_node((depot_lat, depot_lon))
    if not home_node:
        print(f"❌ Error: Depot {config.depot_location} is too far from road network.")
        return
    
    # Initialize Seeded RNG
    # Use IMEI as unique identifier + Date
    rng = get_seeded_rng(config.imei, date)
    print(f"   🎲 RNG initialized for {config.imei} on {date}")

    # 4. Plan Mission
    # Strategy: Pick a random predefined route 80% of the time, else random mission
    mission = None
    
    if predefined_routes and rng.random() < 0.8:
        selected_route = rng.choice(predefined_routes)
        print(f"   🗺️ Assigned Route: {selected_route['route_id']} ({selected_route['name']})")
        
        # Convert waypoints to LineString path
        # waypoints are [[lon, lat], ...]
        mission = plan_mission_from_waypoints(network, home_node, selected_route['waypoints'], rng)
    
    if not mission:
        # Fallback to random generation
        mission = plan_mission_route(network, home_node, min_km=2, max_km=25, rng=rng)
    
    if not mission:
        print(f"❌ No valid mission found for {date}")
        return

    print(f"🚗 {date}: {mission['distance_km']:.2f}km | {len(mission['site_locations'])} Sites")

    stops = generate_mission_stops(mission, rng)
    
    # Variable Shift
    start_hr = rng.randint(7, 9)
    end_hr = rng.randint(18, 20)
    
    
    # 5. External Data Injection (Pre-Load)
    ext_events = []
    try:
        from vts_core.external_data import ExternalLogProvider
        # Uses default path if not provided
        ext_provider = ExternalLogProvider() 
        ext_events = ext_provider.get_events(config.name, date)
        if ext_events:
            print(f"   💉 Injected {len(ext_events)} external checkpoints.")
    except Exception as e:
        print(f"⚠️ External Data Error: {e}")

    agent.start_24h_cycle(date, mission['geometry'], shift_start=start_hr, shift_end=end_hr, stops=stops, external_events=ext_events)
    
    while agent.is_active:
        agent.tick()
        # Removed intermediate flush to prevent log overwriting
        # if len(agent.telemetry_buffer) > 1000: agent.flush_memory()
    


    agent.flush_memory()

def process_external_only(vehicle_config_path: str, date: str, output_dir: str = "data"):
    """
    Checks for external logs (manual entries) and writes them even if the day is skipped.
    """
    config = load_vehicle_config(vehicle_config_path)
    store = SimulationStore(base_dir=output_dir)
    
    try:
        from vts_core.external_data import ExternalLogProvider
        ext_provider = ExternalLogProvider("data/external/VTS Consolidated Report - Final Dataset.csv")
        ext_events = ext_provider.get_events(config.name, date)
        
        if ext_events:
            print(f"   💉 Found {len(ext_events)} external logs for skipped day.")
            # Convert to telemetry format
            records = []
            for e in ext_events:
                records.append({
                    "timestamp": e['timestamp'],
                    "lat": e['lat'],
                    "lon": e['lon'],
                    "speed": e.get('speed', 0.0),
                    "heading": e.get('heading', 0.0),
                    "device_id": config.device_id
                })
            store.write_telemetry(config.imei, date, records, vehicle_name=config.name)
            
    except Exception as e:
        print(f"⚠️ External Data Error: {e}")

def plan_mission_route(network, home_node, min_km, max_km, rng):
    home_pt = (home_node[1], home_node[0]) # (Lat, Lon)
    
    # Try multiple attempts to find a valid route
    for _ in range(50):
        # Layer 1: Combinatorial Destination Shuffling
        num_sites = rng.randint(2, 8)
        
        # Use localities if available - but via internal graph helper which uses global random?
        # graph.py get_random_waypoints uses random module. 
        # Ideally we should pass rng to graph.py, but for now let's just use what we have or accept small indeterminism there?
        # actually, let's implement a local selection if we want strict determinism.
        
        # Accessing localities directly if available to ensure seeded selection
        sites = []
        if network.localities:
             chunk_size = min(len(network.localities), num_sites)
             # Use seeded rng for sample
             chosen_locs = rng.sample(network.localities, chunk_size)
             for loc in chosen_locs:
                 # loc is (lon, lat)
                 node = network._get_nearest_node((loc[1], loc[0]))
                 if node: sites.append(node)
        
        # Fill remainder
        remaining = num_sites - len(sites)
        if remaining > 0 and network.node_list:
            # Seeded choice
            sites.extend([rng.choice(network.node_list) for _ in range(remaining)])

        waypoints = [home_pt] + [(s[1], s[0]) for s in sites] + [home_pt]
        
        full_coords = []
        cumulative_dist = 0.0
        site_locations_meters = []
        valid = True
        
        for i in range(len(waypoints)-1):
            # Layer 2: Stochastic Pathfinding
            geom, length_meters = find_stochastic_path(network, waypoints[i], waypoints[i+1], rng)
            
            if not geom: 
                valid = False; break
            
            cumulative_dist += length_meters
            if i < num_sites: 
                site_locations_meters.append(cumulative_dist)
            
            coords = list(geom.coords)
            if full_coords: full_coords.extend(coords[1:])
            else: full_coords.extend(coords)
            
        total_km = cumulative_dist / 1000.0
        

        
    return {
        "geometry": LineString(full_coords),
        "distance_km": cumulative_dist / 1000.0,
        "site_locations": site_locations_meters
    }

def plan_mission_from_waypoints(network, home_node, waypoints_coords, rng):
    # waypoints_coords: list of [lon, lat]
    if not waypoints_coords: return None
    
    home_pt = (home_node[1], home_node[0])
    
    # 1. Map coords to nodes
    route_nodes = [home_pt]
    for pt in waypoints_coords:
        # pt is [lon, lat]
        node = network._get_nearest_node((pt[1], pt[0])) # lat, lon
        if node:
            route_nodes.append((node[1], node[0])) # lat, lon for finding path? check find_shortest_path
            # find_shortest_path expects (lat, lon) tuples as args?
            # Let's check graph.py usage.
            # find_shortest_path(self, start_coords: tuple, end_coords: tuple)
            # _get_nearest_node returns (lat, lon) according to my review of graph.py
    
    route_nodes.append(home_pt)
    
    # 2. Build Geometry
    full_coords = []
    total_dist = 0.0
    site_dists = []
    
    for i in range(len(route_nodes) - 1):
        u_pt = route_nodes[i] # lat, lon from node
        v_pt = route_nodes[i+1]
        
        # Find shortest path between these two points on graph with noise
        segment_geom, dist = find_stochastic_path(network, u_pt, v_pt, rng)
        
        if segment_geom:
            total_dist += dist
            coords = list(segment_geom.coords)
            if len(full_coords) > 0:
                full_coords.extend(coords[1:])
            else:
                full_coords.extend(coords)
        
        # Record distance for intermediate stops (exclude return to home)
        if i < len(route_nodes) - 2:
            site_dists.append(total_dist)
                
    if len(full_coords) < 2: return None
    
    return {
        "geometry": LineString(full_coords),
        "distance_km": total_dist / 1000.0,
        "site_locations": site_dists # intermediate stops in meters
    }
    return None

def generate_mission_stops(mission, rng):
    stops = []
    # Work Stops
    for site_meter in mission['site_locations']:
        stops.append({
            "at_meter": site_meter - 20, 
            "duration_min": 45, "duration_max": 90, "type": "WORK"
        })
    # Transit Stops
    num_transit = rng.randint(0, 2)
    total_m = mission['distance_km'] * 1000
    for _ in range(num_transit):
        loc = rng.uniform(0.1, 0.9) * total_m
        if not any(abs(loc - s['at_meter']) < 500 for s in stops):
            stops.append({
                "at_meter": loc, "duration_min": 5, "duration_max": 15, "type": "TRANSIT"
            })
    return sorted(stops, key=lambda x: x['at_meter'])

def generate_parked_day(vehicle_config_path: str, date: str, output_dir: str="data"):
    config = load_vehicle_config(vehicle_config_path)
    store = SimulationStore(base_dir=output_dir)
    
    start = datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(f"{date} 23:59:59", "%Y-%m-%d %H:%M:%S")
    current = start
    
    # Use Configured Depot
    lat, lon = config.depot_location
    
    recs = []
    while current < end:
        recs.append({
            "timestamp": current, "lat": lat, "lon": lon,
            "speed": 0.0, "heading": 0.0, "device_id": config.device_id
        })
        current += timedelta(minutes=10) 
    store.write_telemetry(config.imei, date, recs)