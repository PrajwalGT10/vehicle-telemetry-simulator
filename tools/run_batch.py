import sys
import os

# --- FIX: Add root folder to Python Path ---
# This allows the script to find 'vts_core' even though it lives in 'tools/'
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)
# -------------------------------------------

import glob
import argparse
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count
import tqdm
import json

# Now these imports will work
from vts_core.engine import run_simulation_day, generate_parked_day
from vts_core.config import load_vehicle_config

def get_date_range(start_year, end_year):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta.days + 1)]

def process_task(task):
    """
    Worker function.
    Task = (vehicle_file, roads_file, date, calendar_file, out_dir)
    """
    vehicle_file, roads_file, date, calendar_file, out_dir = task
    
    # --- 1. Determine Status (Driving vs Parking) ---
    dt = datetime.strptime(date, "%Y-%m-%d")
    is_parked = False
    reason = ""
    
    # A. Check Sunday (Weekday 6 is Sunday)
    if dt.weekday() == 6:
        is_parked = True
        reason = "Sunday"
        
    # B. Check Holiday File
    if not is_parked and calendar_file:
        if os.path.exists(calendar_file):
            try:
                with open(calendar_file) as f:
                    holidays = json.load(f)
                    # Handle [{"date": "2023-...", ...}] format
                    if isinstance(holidays, list) and len(holidays) > 0 and isinstance(holidays[0], dict):
                        holidays = [h.get('date') for h in holidays]
                    
                    if date in holidays:
                        is_parked = True
                        reason = "Holiday"
            except Exception as e:
                return f"X: Calendar Read Error {e}"
        else:
            return f"X: Calendar file not found at {calendar_file}"

    try:
        if is_parked:
            generate_parked_day(vehicle_file, date, out_dir)
            return "P" # Parked
        else:
            if not os.path.exists(roads_file):
                return "E" # Error
            run_simulation_day(vehicle_file, roads_file, date, out_dir)
            return "D" # Drove
            
    except Exception as e:
        return f"X: {e}"
    
def main():
    parser = argparse.ArgumentParser(description="VTS Mass Scale Runner")
    parser.add_argument("--vehicles_dir", required=True)
    parser.add_argument("--zones_dir", required=True)
    parser.add_argument("--calendar", help="Holiday JSON file")
    parser.add_argument("--years", nargs="+", type=int, default=[2023])
    parser.add_argument("--cores", type=int, default=4)
    
    args = parser.parse_args()
    
    # 1. Get Configs
    vehicle_files = glob.glob(os.path.join(args.vehicles_dir, "*.yaml"))
    
    print(f"📋 Found {len(vehicle_files)} target vehicles.")
    
    all_dates = []
    for year in args.years:
        all_dates.extend(get_date_range(year, year))
    print(f"📅 Simulation Span: {len(all_dates)} days (Year {args.years})")
    
    # 2. Build Tasks
    tasks = []
    for v_file in vehicle_files:
        try:
            cfg = load_vehicle_config(v_file)
            zone_id = cfg.zone_id
            roads_file = os.path.join(args.zones_dir, zone_id, "roads.geojson")
            
            for date in all_dates:
                tasks.append((v_file, roads_file, date, args.calendar, "data"))
                
        except Exception as e:
            print(f"⚠️ Skipping {v_file}: {e}")

    print(f"🚀 Launching {len(tasks)} tasks on {args.cores} cores...")
    
    # 3. Execute
    results = {"D": 0, "P": 0, "E": 0, "X": 0}
    
    # Use fewer cores if we have fewer tasks than cores to avoid overhead
    num_processes = min(args.cores, len(tasks)) if tasks else 1
    
    with Pool(processes=num_processes) as pool:
        for res in tqdm.tqdm(pool.imap_unordered(process_task, tasks), total=len(tasks)):
            if res.startswith("X"):
                # Uncomment to see actual errors if things fail
                # print(f"\nTask Failed: {res}") 
                results["X"] += 1
            else:
                results[res] = results.get(res, 0) + 1
                
    print("\n✅ Yearly Batch Complete.")
    print(f"   🚗 Driven Days: {results['D']} (Target ~300)")
    print(f"   💤 Parked Days: {results['P']} (Sundays + Holidays)")
    print(f"   ❌ Errors:      {results['X']}")

if __name__ == "__main__":
    main()