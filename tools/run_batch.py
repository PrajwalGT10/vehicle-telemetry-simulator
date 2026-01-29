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

from vts_core.engine import run_simulation_day, generate_parked_day, process_external_only
from vts_core.config import load_vehicle_config
from vts_core.graph import RoadNetwork  # We will load this inside the worker
from vts_core.store import SimulationStore # For conversion

def get_date_range(start_date_str, end_date_str):
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = datetime.strptime(end_date_str, "%Y-%m-%d")
    delta = end - start
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta.days + 1)]

def process_vehicle_year(task):
    """
    Simulates a Range of Dates for ONE VEHICLE in a single process.
    This allows loading the Graph only ONCE per vehicle, massive speedup.
    """
    vehicle_file, zone_dir, calendar_file, start_date, end_date, output_dir = task
    
    results = {"D": 0, "S": 0, "E": 0}
    
    try:
        # 1. Load Resources ONCE
        config = load_vehicle_config(vehicle_file)
        roads_file = os.path.join(zone_dir, config.zone_id, "roads.geojson")
        
        if not os.path.exists(roads_file):
            return f"Error: Road file missing {roads_file}"
            
        # Load Holiday Calendar
        # Load Holiday Calendar(s)
        # Supports: 
        # 1. Single file passed via args.calendar
        # 2. Folder passed via args.calendar (looking for india_{year}_holidays.json)
        # 3. Default search in configs/calendars if args.calendar is minimal
        
        holidays = set()
        
        # Determine Years to load
        # We need to look at start_date and end_date
        s_y = int(start_date.split("-")[0])
        e_y = int(end_date.split("-")[0])
        years_to_load = range(s_y, e_y + 1)
        
        # Helper to load one file
        def load_cal_file(fpath):
            subset = set()
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r') as f: data = json.load(f)
                    h_list = data.get('holidays', []) if isinstance(data, dict) else data
                    subset = {h['date'] if isinstance(h, dict) else h for h in h_list}
                except: pass
            return subset

        # If User provided a specific file, load it (Legacy/Override)
        if calendar_file and os.path.isfile(calendar_file):
             holidays.update(load_cal_file(calendar_file))
        
        # Else, try to load year-specific files from calendar directory
        # If calendar_file is a dir, use it. Else default to configs/calendars
        cal_dir = "configs/calendars"
        if calendar_file and os.path.isdir(calendar_file):
            cal_dir = calendar_file
            
        for y in years_to_load:
            # Try india_{year}_holidays.json
            f_name = f"india_{y}_holidays.json"
            f_path = os.path.join(cal_dir, f_name)
            if os.path.exists(f_path):
                holidays.update(load_cal_file(f_path))

        # 2. Loop through every day of the range
        dates = get_date_range(start_date, end_date)

        
        # 2. Loop through every day of the range
        dates = get_date_range(start_date, end_date)
        processed_dates = []

        for date in dates:
            dt = datetime.strptime(date, "%Y-%m-%d")
            
            # Parking Logic (SKIPPED per User Requirement)
            if dt.weekday() == 6 or date in holidays:
                process_external_only(vehicle_file, date, output_dir)
                results["S"] += 1 # Skipped
            else:
                # Disable legacy logs for speed
                run_simulation_day(vehicle_file, roads_file, date, output_dir, enable_legacy_logs=False)
                processed_dates.append(date) # Track for post-processing
                results["D"] += 1

        # 3. Post-Processing Phase (Convert Parquet to Text)
        # This decouples the expensive text I/O from the physics loop
        # We process all valid dates for this vehicle now.
        if processed_dates:
            store = SimulationStore(base_dir=output_dir, enable_legacy_logs=False) # Helper instance
            year_map = {} # Cache paths if needed, but simple loop is fine
            
            for date in processed_dates:
                 year, month, _ = date.split("-")
                 # Reconstruct path logic (keep in sync with store.py)
                 parquet_dir = store.telemetry_dir / f"year={year}" / f"month={month}"
                 parquet_path = parquet_dir / f"{config.imei}_{date}.parquet"
                 
                 if parquet_path.exists():
                     store.generate_legacy_log_from_parquet(parquet_path, config.name, config.imei, date)
        
        return f"✅ {config.imei}: {results['D']} Drives, {results['S']} Skipped"
        
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error {vehicle_file}: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicles_dir", required=True)
    parser.add_argument("--zones_dir", required=True)
    parser.add_argument("--calendar")
    # parser.add_argument("--years", nargs="+", type=int, default=[2023])
    parser.add_argument("--start_date", help="YYYY-MM-DD", default="2023-01-01")
    parser.add_argument("--end_date", help="YYYY-MM-DD", default="2023-12-31")
    parser.add_argument("--zone", help="Filter vehicles by Zone ID (e.g. C_Zone)", default=None)
    parser.add_argument("--cores", type=int, default=4)
    args = parser.parse_args()
    
    all_files = glob.glob(os.path.join(args.vehicles_dir, "*.yaml"))
    vehicle_files = []
    
    # Filter by Zone
    if args.zone:
        print(f"🔍 Filtering for Zone: {args.zone}")
        for vf in all_files:
            try:
                # Quick check without full load if possible, or just load
                # Loading is safer
                cfg = load_vehicle_config(vf)
                if cfg.zone_id == args.zone:
                    vehicle_files.append(vf)
            except: pass
    else:
        vehicle_files = all_files
    
    # Task = One Vehicle (Processing date range)
    tasks = [
        (v_file, args.zones_dir, args.calendar, args.start_date, args.end_date, "data") 
        for v_file in vehicle_files
    ]

    print(f"🚀 Simulating {len(tasks)} Vehicles from {args.start_date} to {args.end_date} on {args.cores} cores...")
    
    print(f"🚀 Simulating {len(tasks)} Vehicles from {args.start_date} to {args.end_date} on {args.cores} cores...")
    
    # Strictly enforce core count passed by user
    # Avoid 'len(tasks) or 1' unless tasks are fewer than cores
    pool_size = min(args.cores, len(tasks)) if len(tasks) > 0 else 1
    
    total_tasks = len(tasks)
    completed = 0
    
    with Pool(pool_size) as pool:
        # Use imap_unordered for responsiveness
        for res in pool.imap_unordered(process_vehicle_year, tasks):
            completed += 1
            
            # Heartbeat Log (Every 5%)
            if total_tasks >= 20 and completed % (total_tasks // 20) == 0:
                pct = (completed / total_tasks) * 100
                print(f"   ❤️ Progress: {pct:.1f}% ({completed}/{total_tasks})")
            
            # Optional: Verbose printing
            # print(res)
            # Only print errors or final summary? Let's keep existing print(res) for now but maybe squelch if too noisy
            print(res)

if __name__ == "__main__":
    main()