import sys
import os

# Add root folder to Path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

import glob
import argparse
from datetime import datetime, timedelta
from multiprocessing import Pool
import tqdm
import json

from vts_core.engine import run_simulation_day, generate_parked_day
from vts_core.config import load_vehicle_config

def get_date_range(start_year, end_year):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta.days + 1)]

def process_task(task):
    vehicle_file, roads_file, date, calendar_file, out_dir = task
    
    dt = datetime.strptime(date, "%Y-%m-%d")
    is_parked = False
    
    # A. Check Sunday
    if dt.weekday() == 6:
        is_parked = True
        
    # B. Check Holiday File
    if not is_parked and calendar_file and os.path.exists(calendar_file):
        try:
            with open(calendar_file, 'r') as f:
                data = json.load(f)
            
            # Fix nested holidays key
            holidays = data.get('holidays', []) if isinstance(data, dict) else data
            
            # Create set of dates
            holiday_dates = set()
            for h in holidays:
                if isinstance(h, dict) and 'date' in h:
                    holiday_dates.add(h['date'])
                elif isinstance(h, str):
                    holiday_dates.add(h)
            
            if date in holiday_dates:
                is_parked = True
        except Exception:
            pass

    try:
        if is_parked:
            generate_parked_day(vehicle_file, date, out_dir)
            return "P"
        else:
            if not os.path.exists(roads_file): return "E"
            run_simulation_day(vehicle_file, roads_file, date, out_dir)
            return "D"
    except Exception as e:
        return f"X: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicles_dir", required=True)
    parser.add_argument("--zones_dir", required=True)
    parser.add_argument("--calendar")
    parser.add_argument("--years", nargs="+", type=int, default=[2023])
    parser.add_argument("--cores", type=int, default=4)
    args = parser.parse_args()
    
    vehicle_files = glob.glob(os.path.join(args.vehicles_dir, "*.yaml"))
    print(f"📋 Found {len(vehicle_files)} target vehicles.")
    
    all_dates = []
    for year in args.years:
        all_dates.extend(get_date_range(year, year))
    
    tasks = []
    for v_file in vehicle_files:
        try:
            cfg = load_vehicle_config(v_file)
            zone_id = cfg.zone_id
            roads_file = os.path.join(args.zones_dir, zone_id, "roads.geojson")
            for date in all_dates:
                tasks.append((v_file, roads_file, date, args.calendar, "data"))
        except: pass

    print(f"🚀 Launching {len(tasks)} tasks on {args.cores} cores...")
    
    results = {"D": 0, "P": 0, "E": 0, "X": 0}
    num = min(args.cores, len(tasks)) if tasks else 1
    
    with Pool(processes=num) as pool:
        for res in tqdm.tqdm(pool.imap_unordered(process_task, tasks), total=len(tasks)):
            if res.startswith("X"):
                results["X"] += 1
            else:
                results[res] = results.get(res, 0) + 1
                
    print("\n✅ Yearly Batch Complete.")
    print(f"   🚗 Driven Days: {results['D']}")
    print(f"   💤 Parked Days: {results['P']}")
    print(f"   ❌ Errors:      {results['X']}")

if __name__ == "__main__":
    main()