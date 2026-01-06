from pathlib import Path
from shapely.geometry import LineString
from datetime import datetime, timedelta
import random
import math

from vts_core.config import load_vehicle_config
from vts_core.store import SimulationStore
from vts_core.graph import RoadNetwork
from vts_core.agent import VehicleAgent

# --- CONFIGURATION ---
# Depot: Koramangala
HOME_BASE_LAT = 12.958319
HOME_BASE_LON = 77.612422

def run_simulation_day(vehicle_config_path: str, zone_roads_path: str, date: str, output_dir: str = "data"):
    config = load_vehicle_config(vehicle_config_path)
    store = SimulationStore(base_dir=output_dir)
    network = RoadNetwork(zone_roads_path)
    agent = VehicleAgent(config, store)
    
    # --- 1. Find Valid Home Node ---
    home_node = network._get_nearest_node((HOME_BASE_LAT, HOME_BASE_LON))
    if not home_node:
        print(f"❌ Error: Home Base disconnected from graph.")
        return
    
    # --- 2. Plan Mission ---
    mission = plan_mission_route(network, home_node, min_km=2, max_km=25)
    
    if not mission:
        print(f"❌ No valid mission found for {date}")
        return

    print(f"🚗 {date}: {mission['distance_km']:.2f}km | {len(mission['site_locations'])} Work Sites")

    # --- 3. Schedule Stops (FIXED) ---
    stops = generate_mission_stops(mission)
    
    # --- 4. Variable Shift ---
    start_hr = random.randint(7, 9)
    end_hr = random.randint(18, 20)
    
    agent.start_24h_cycle(date, mission['geometry'], shift_start=start_hr, shift_end=end_hr, stops=stops)
    
    while agent.is_active:
        agent.tick()
        if len(agent.telemetry_buffer) > 1000: agent.flush_memory()
    agent.flush_memory()

def plan_mission_route(network, home_node, min_km, max_km):
    home_pt = (home_node[1], home_node[0]) # (Lat, Lon)
    
    for _ in range(50):
        num_sites = random.randint(2, 8)
        
        # Pick random sites from valid nodes
        sites = [random.choice(network.node_list) for _ in range(num_sites)]
        waypoints = [home_pt] + [(s[1], s[0]) for s in sites] + [home_pt]
        
        full_coords = []
        cumulative_dist = 0.0
        site_locations_meters = []
        valid = True
        
        for i in range(len(waypoints)-1):
            geom, length_meters = network.find_shortest_path(waypoints[i], waypoints[i+1])
            if not geom: 
                valid = False; break
            
            cumulative_dist += length_meters
            if i < num_sites: 
                site_locations_meters.append(cumulative_dist)
            
            coords = list(geom.coords)
            if full_coords: full_coords.extend(coords[1:])
            else: full_coords.extend(coords)
            
        total_km = cumulative_dist / 1000.0
        
        if valid and min_km <= total_km <= max_km:
            return {
                "geometry": LineString(full_coords),
                "distance_km": total_km,
                "site_locations": site_locations_meters
            }
            
    return None

def generate_mission_stops(mission):
    stops = []
    
    # A. Work Stops (FIXED: Send valid min/max range)
    for site_meter in mission['site_locations']:
        stops.append({
            "at_meter": site_meter - 20, 
            "duration_min": 45, 
            "duration_max": 90,  # Now consistent
            "type": "WORK"
        })
        
    # B. Transit Stops
    num_transit = random.randint(0, 2)
    total_m = mission['distance_km'] * 1000
    
    for _ in range(num_transit):
        loc = random.uniform(0.1, 0.9) * total_m
        is_close = any(abs(loc - s['at_meter']) < 500 for s in stops)
        if not is_close:
            stops.append({
                "at_meter": loc,
                "duration_min": 5,
                "duration_max": 15, # Short stop
                "type": "TRANSIT"
            })
            
    return sorted(stops, key=lambda x: x['at_meter'])

def generate_parked_day(vehicle_config_path: str, date: str, output_dir: str="data"):
    config = load_vehicle_config(vehicle_config_path)
    store = SimulationStore(base_dir=output_dir)
    start = datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(f"{date} 23:59:59", "%Y-%m-%d %H:%M:%S")
    current = start
    recs = []
    while current < end:
        recs.append({
            "timestamp": current, "lat": HOME_BASE_LAT, "lon": HOME_BASE_LON,
            "speed": 0.0, "heading": 0.0, "device_id": config.device_id
        })
        current += timedelta(minutes=10) 
    store.write_telemetry(config.imei, date, recs)