from pathlib import Path
from shapely.geometry import LineString
from shapely.ops import linemerge
from datetime import datetime, timedelta
import random
import math

from vts_core.config import load_vehicle_config
from vts_core.store import SimulationStore
from vts_core.graph import RoadNetwork
from vts_core.agent import VehicleAgent

def run_simulation_day(vehicle_config_path: str, zone_roads_path: str, date: str, output_dir: str = "data"):
    config = load_vehicle_config(vehicle_config_path)
    store = SimulationStore(base_dir=output_dir)
    network = RoadNetwork(zone_roads_path)
    agent = VehicleAgent(config, store)
    
    # --- 1. Smart Route Planning (Target: 11km - 25km) ---
    path_geom = plan_route_with_target_distance(network, min_km=11, max_km=25)
    
    if not path_geom:
        print("❌ Could not find a route of suitable length.")
        return

    route_km = path_geom.length * 111.139
    print(f"🚗 Simulating {config.imei} on {date}")
    print(f"   Route Length: {route_km:.2f} km")

    # --- 2. Smart Stop Planning (5-10 stops) ---
    stops = generate_random_stops(route_km, min_stops=5, max_stops=10)
    print(f"   Planned Stops: {len(stops)}")
    
    # --- 3. Smart Shift Timing ---
    # 70% chance of Standard (9-18), 30% chance of Variation
    if random.random() < 0.7:
        start_hr, end_hr = 9, 18
    else:
        # Pick a variation: Early Start OR Late End OR Both
        start_hr = random.choice([7, 9])
        end_hr = random.choice([18, 19])
    
    print(f"   Shift Hours: {start_hr}:00 to {end_hr}:00")

    # --- 4. Start ---
    agent.start_24h_cycle(date, path_geom, shift_start=start_hr, shift_end=end_hr, stops=stops)
    
    while agent.is_active:
        agent.tick()
        if len(agent.telemetry_buffer) > 1000:
            agent.flush_memory()
    
    agent.flush_memory()
    print(f"✅ Finished.")

def plan_route_with_target_distance(network: RoadNetwork, min_km: float, max_km: float) -> LineString:
    """Tries to find a path within distance range. Retries up to 20 times."""
    nodes = list(network.graph.nodes)
    if len(nodes) < 2: return None

    for attempt in range(20):
        start = random.choice(nodes)
        end = random.choice(nodes)
        
        # Simple A -> B
        path = network.find_shortest_path((start[1], start[0]), (end[1], end[0]))
        if path:
            dist_km = path.length * 111.139
            if min_km <= dist_km <= max_km:
                return path
            
            # If too short, try to add a waypoint (A -> Mid -> B)
            if dist_km < min_km:
                mid = random.choice(nodes)
                leg1 = path
                leg2 = network.find_shortest_path((end[1], end[0]), (mid[1], mid[0]))
                if leg2:
                    total_dist = (leg1.length + leg2.length) * 111.139
                    if min_km <= total_dist <= max_km:
                        coords = list(leg1.coords) + list(leg2.coords)
                        return LineString(coords)

    print("⚠️ Warning: Could not satisfy strict distance constraints. Using best attempt.")
    return path

def generate_random_stops(total_km: float, min_stops: int, max_stops: int):
    """Generates stop definitions distributed along the route."""
    # 1. Define Variables
    num_stops = random.randint(min_stops, max_stops)
    total_meters = total_km * 1000.0
    
    # 2. Pick Random Points (5% to 95% along route)
    stop_points = sorted([random.uniform(0.05, 0.95) for _ in range(num_stops)])
    
    # 3. Create Stop Objects
    stops = []
    for pct in stop_points:
        stops.append({
            "at_meter": total_meters * pct,
            "duration_min": 45,  # Increased to 45 mins
            "duration_max": 90   # Increased to 90 mins
        })
    return stops

def generate_parked_day(vehicle_config_path: str, date: str, output_dir: str="data"):
    config = load_vehicle_config(vehicle_config_path)
    store = SimulationStore(base_dir=output_dir)
    print(f"💤 Simulating {config.imei} on {date} (Parking Mode)...")
    
    start_time = datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S")
    end_time = datetime.strptime(f"{date} 23:59:59", "%Y-%m-%d %H:%M:%S")
    current = start_time
    home_lat, home_lon = 12.9716, 77.5946
    records = []
    
    while current < end_time:
        records.append({
            "timestamp": current, "lat": home_lat, "lon": home_lon,
            "speed": 0.0, "heading": 0.0, "device_id": config.device_id
        })
        current += timedelta(seconds=25) 
        
    store.write_telemetry(config.imei, date, records)
    print(f"✅ Finished Parking.")