import os
import glob
import json
import yaml
import pandas as pd
from datetime import datetime, timedelta
import logging

# Setup Logger
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Constants
CONFIGS_DIR = "configs/vehicles"
CALENDAR_DIR = "configs/calendars"
RA11_PATH = "data/external/VTS Consolidated Report - RA_11.csv"
OUTPUT_FILE = "data/output/generation_forecast.csv"

def load_holidays():
    """Aggregates holidays from all years."""
    holidays = set()
    files = glob.glob(os.path.join(CALENDAR_DIR, "*.json"))
    for f in files:
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                for h in data.get('holidays', []):
                    holidays.add(h['date'])
        except Exception as e:
            logger.error(f"Error loading {f}: {e}")
    return holidays

def get_ghost_ids():
    """Returns set of Device-IDs that are Ghost Records in RA_11"""
    if not os.path.exists(RA11_PATH):
        logger.warning("RA_11 file missing.")
        return set()
    
    try:
        df = pd.read_csv(RA11_PATH)
        # Filter < May 2021
        df['calc_dt'] = pd.to_datetime(df['Calculated Date'], format='%d/%m/%Y', errors='coerce')
        cutoff = datetime(2021, 5, 1)
        ghosts = df[df['calc_dt'] < cutoff]
        
        # Return ID set. 
        # Note: Configs use 'imei', Report uses 'Device-ID'.
        # Assuming 1:1 or logic handles it. 
        # Ideally we map both.
        return set(ghosts['Device-ID'].astype(str).tolist())
    except Exception as e:
        logger.error(f"Error parse RA_11: {e}")
        return set()

def calculate_valid_days(start_str, end_str, holidays):
    """Counts valid operating days (Mon-Sat usually, exclude Sun & Hols)."""
    # Assuming standard Mon-Sat?
    # Configs usually specify 'working_days'.
    # For manifest, let's assume standard: Mon-Fri+Sat(Probability) or just Mon-Sat?
    # Config has 'working_days': ['MON', 'TUE'...]
    # Let's default to standard logic: All days strictly between start/end, 
    # minus Sundays, minus Holidays.
    
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
    except:
        return 0
        
    delta = end - start
    valid_days = 0
    
    for i in range(delta.days + 1):
        day = start + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        
        # 1. Check Holiday
        if day_str in holidays:
            continue
            
        # 2. Check Sunday (Weekday 6)
        if day.weekday() == 6:
            continue
            
        valid_days += 1
        
    return valid_days

def scan_fleet():
    logger.info("🚀 Starting Forecast Scan...")
    
    holidays = load_holidays()
    ghost_ids = get_ghost_ids()
    
    configs = glob.glob(os.path.join(CONFIGS_DIR, "*.yaml"))
    
    unique_ids = set()
    report_rows = []
    
    for cf in configs:
        try:
            with open(cf, 'r') as f:
                data = yaml.safe_load(f)
                
            if 'vehicle' not in data: continue
            
            v = data['vehicle']
            imei = str(v.get('imei'))
            name = v.get('name')
            enabled = bool(v.get('enabled', True))
            
            # Epoch Logic
            # Epoch A: 2021-2022. Epoch B: 2022-2024.
            # Based on file naming or start date?
            # Start date is in 'simulation_window'
            sim = data.get('simulation_window', {})
            start_date = sim.get('start_date', '2022-01-01')
            end_date = sim.get('end_date', '2022-01-01')
            
            epoch = "B" if "2022-05" in start_date or start_date >= "2022-05-01" else "A"
            # Or simplified: Epoch A ends April 30 2022.
            
            shift = data.get('shift', {})
            interval = int(shift.get('sampling_interval_seconds', 900))
            # Duration in hours
            s_time = datetime.strptime(shift.get('start_time', '09:00'), "%H:%M")
            e_time = datetime.strptime(shift.get('end_time', '18:00'), "%H:%M")
            duration_hrs = (e_time - s_time).seconds / 3600.0
            
            # --- LOGIC ---
            status = "ACTIVE" if enabled else "SCRAPPED"
            is_ghost = imei in ghost_ids # Naive Imei match
            # Also try device_id match
            d_id = v.get('device_id')
            if d_id and d_id in ghost_ids: is_ghost = True

            source = "SIMULATION"
            valid_days = 0
            est_logs = 0
            
            if is_ghost:
                source = "LEGACY/GHOST"
                status = "LEGACY"
                est_logs = 1
                valid_days = 0 # N/A
            elif not enabled:
                source = "SCRAPPED"
                est_logs = 0
                valid_days = 0
            else:
                valid_days = calculate_valid_days(start_date, end_date, holidays)
                daily_logs = (duration_hrs * 3600) / interval
                est_logs = int(valid_days * daily_logs)
            
            report_rows.append({
                "Vehicle Name": name,
                "Device ID": d_id or imei,
                "Epoch": epoch,
                "Start Date": start_date,
                "End Date": end_date,
                "Status": status,
                "Source": source,
                "Ghost Record?": "Yes" if is_ghost else "No",
                "Total Valid Days": valid_days,
                "Estimated Log Entries": est_logs
            })
            
            unique_ids.add(imei)
            
        except Exception as e:
            logger.error(f"Error parsing {cf}: {e}")

    # Save
    out_df = pd.DataFrame(report_rows)
    out_df = out_df.sort_values("Vehicle Name")
    out_df.to_csv(OUTPUT_FILE, index=False)
    
    logger.info("-" * 40)
    logger.info(f"Forecast Generated: {len(report_rows)} Vehicles Configured.")
    logger.info(f"Saved to: {OUTPUT_FILE}")
    logger.info("-" * 40)

if __name__ == "__main__":
    scan_fleet()
