from pathlib import Path
from shapely.geometry import LineString
from datetime import datetime, timedelta
import random
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
    # We must ensure Home is part of the connected graph
    home_node = network._get_nearest_node((HOME_BASE_LAT, HOME_BASE_LON))
    if not home_node:
        print(f"❌ Error: Home Base {HOME_BASE_LAT},{HOME_BASE_LON} is too far from any road.")
        return
    
    # --- 2. Plan Route ---
    path_info = plan_dynamic_route(network, home_node, min_km=2, max_km=25)
    
    if not path_info:
        print(f"❌ No valid route found for {date} (Tried 100 routes from Home)")
        return

    path_geom = path_info['geometry']
    print(f"🚗 {date}: {path_info['distance']:.2f}km | {path_info['sites']} Sites")

    # --- 3. Run Simulation ---
    stops = generate_random_stops(path_info['distance'])
    start_hr = random.randint(7, 9)
    end_hr = random.randint(18, 20)
    
    agent.start_24h_cycle(date, path_geom, shift_start=start_hr, shift_end=end_hr, stops=stops)
    
    while agent.is_active:
        agent.tick()
        if len(agent.telemetry_buffer) > 1000: agent.flush_memory()
    agent.flush_memory()

def plan_dynamic_route(network, home_node, min_km, max_km):
    home_pt = (home_node[1], home_node[0]) # (Lat, Lon)
    nodes = network.node_list
    
    for _ in range(100):
        # 1-3 Sites
        num_sites = 1 if random.random() < 0.6 else random.randint(2, 3)
        
        waypoints = [home_pt]
        for _ in range(num_sites):
            t = random.choice(nodes) # Pick random node from CLEANED graph
            waypoints.append((t[1], t[0]))
        waypoints.append(home_pt) 
        
        # Build Path
        full_coords = []
        total_dist = 0
        valid = True
        
        for i in range(len(waypoints)-1):
            geom = network.find_shortest_path(waypoints[i], waypoints[i+1])
            if not geom: 
                valid = False; break
            
            coords = list(geom.coords)
            if full_coords: full_coords.extend(coords[1:])
            else: full_coords.extend(coords)
            
            total_dist += geom.length * 111.139
            
        if valid and min_km <= total_dist <= max_km:
            return {"geometry": LineString(full_coords), "distance": total_dist, "sites": num_sites}
            
    return None

def generate_random_stops(total_km):
    count = random.randint(5, 10) if total_km > 5 else random.randint(2, 4)
    total_m = total_km * 1000
    points = sorted([random.uniform(0.1, 0.9) for _ in range(count)])
    return [{"at_meter": p * total_m, "duration_min": 45, "duration_max": 90} for p in points]

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