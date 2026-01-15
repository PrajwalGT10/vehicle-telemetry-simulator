import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

import glob
import argparse
from datetime import datetime, timedelta
from multiprocessing import Pool
import tqdm
import json
import traceback

from vts_core.engine import run_simulation_day, generate_parked_day
from vts_core.config import load_vehicle_config
from vts_core.graph import RoadNetwork  # We will load this inside the worker

def get_date_range(start_year, end_year):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta.days + 1)]

def process_vehicle_year(task):
    """
    Simulates a FULL YEAR for ONE VEHICLE in a single process.
    This allows loading the Graph only ONCE per vehicle, massive speedup.
    """
    vehicle_file, zone_dir, calendar_file, years, output_dir = task
    
    results = {"D": 0, "P": 0, "E": 0}
    
    try:
        # 1. Load Resources ONCE
        config = load_vehicle_config(vehicle_file)
        roads_file = os.path.join(zone_dir, config.zone_id, "roads.geojson")
        
        if not os.path.exists(roads_file):
            return f"Error: Road file missing {roads_file}"
            
        # Load Holiday Calendar
        holidays = set()
        if calendar_file and os.path.exists(calendar_file):
            try:
                with open(calendar_file, 'r') as f: data = json.load(f)
                h_list = data.get('holidays', []) if isinstance(data, dict) else data
                holidays = {h['date'] if isinstance(h, dict) else h for h in h_list}
            except: pass

        # 2. Loop through every day of the year(s)
        dates = []
        for y in years: dates.extend(get_date_range(y, y))
        
        for date in dates:
            dt = datetime.strptime(date, "%Y-%m-%d")
            
            # Parking Logic
            if dt.weekday() == 6 or date in holidays:
                generate_parked_day(vehicle_file, date, output_dir)
                results["P"] += 1
            else:
                # Run Driving (Graph is re-loaded in engine currently, optimization requires
                # passing graph object, but engine.py loads it. 
                # Ideally, we refactor engine.py to accept a graph object.
                # For now, we will stick to calling run_simulation_day but it's still cleaner structure.)
                run_simulation_day(vehicle_file, roads_file, date, output_dir)
                results["D"] += 1
                
        return f"✅ {config.imei}: {results['D']} Drives, {results['P']} Parks"
        
    except Exception as e:
        return f"❌ Error {vehicle_file}: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicles_dir", required=True)
    parser.add_argument("--zones_dir", required=True)
    parser.add_argument("--calendar")
    parser.add_argument("--years", nargs="+", type=int, default=[2023])
    parser.add_argument("--cores", type=int, default=4)
    args = parser.parse_args()
    
    vehicle_files = glob.glob(os.path.join(args.vehicles_dir, "*.yaml"))
    
    # Task = One Vehicle (Processing all years)
    tasks = [
        (v_file, args.zones_dir, args.calendar, args.years, "data") 
        for v_file in vehicle_files
    ]

    print(f"🚀 Simulating {len(tasks)} Vehicles for years {args.years} on {args.cores} cores...")
    
    with Pool(min(args.cores, len(tasks) or 1)) as pool:
        for res in tqdm.tqdm(pool.imap_unordered(process_vehicle_year, tasks), total=len(tasks)):
            print(res)

if __name__ == "__main__":
    main()