
import os
import json
import random
import glob
import math
import pandas as pd
import numpy as np
from datetime import datetime
from shapely.geometry import Point, shape
from shapely.ops import nearest_points
import logging

import logging
import sys

# Fix Python path to find vts_core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def load_vehicle_mapping():
    """Scans configs to build IMEI -> Name map"""
    mapping = {}
    # Search both vehicles and single_test or just recursive configs
    # Assuming configs are in configs/vehicles or similar. 
    # Let's search recursively in configs/
    config_files = glob.glob(os.path.join("configs", "**", "*.yaml"), recursive=True)
    
    logger.info(f"Loading vehicle map from {len(config_files)} config files...")
    
    for cf in config_files:
        try:
            # We can use simple text parsing to avoid heavy imports if desired,
            # or use vts_core.config if reliable.
            # Let's use simple yaml load
            import yaml
            with open(cf, 'r') as f:
                data = yaml.safe_load(f)
                if 'vehicle' in data:
                    v = data['vehicle']
                    name = v.get('name')
                    imei = str(v.get('imei')) # Ensure string
                    if name and imei:
                        mapping[imei] = name
                        # Also handle case-insensitivity if needed, but IMEI usually usually matches
        except Exception as e:
            pass
            
    return mapping

# Constants
TELEMETRY_DIR = "data/telemetry"
OUTPUT_DIR = "data/output"
ZONES_DIR = "data/zones"
# 1. Define Date Range
REPORT_START = datetime(2022, 1, 1)
REPORT_END = datetime(2024, 4, 26)

class LandmarkIndex:
    """Builds a spatial index of landmarks for fast lookup."""
    def __init__(self):
        self.points = []
        self.names = []
        self._load_landmarks()
        
    def _load_landmarks(self):
        logger.info("Loading landmarks from zones...")
        zone_dirs = glob.glob(os.path.join(ZONES_DIR, "*"))
        for zd in zone_dirs:
            if not os.path.isdir(zd): continue
            
            # Use localities.geojson as landmarks
            loc_file = os.path.join(zd, "localities.geojson")
            if os.path.exists(loc_file):
                try:
                    with open(loc_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for feat in data.get('features', []):
                        props = feat.get('properties', {})
                        name = props.get('name', 'Unknown')
                        geom = shape(feat['geometry'])
                        self.points.append(geom.centroid)
                        self.names.append(name)
                except Exception as e:
                    pass
        
        logger.info(f"Loaded {len(self.points)} landmarks.")

    def get_nearest_address(self, lat, lon):
        if not self.points:
            return "Unknown Location"
            
        query_pt = Point(lon, lat)
        
        # Simple Euclidean nearest search (fast enough for <1000 points)
        # Using shapely logic: usually one would use STRtree for thousands.
        # But here we can do a naive min distance.
        # Optimize: Pre-calculate if needed.
        
        min_dist = float('inf')
        nearest_idx = -1
        
        for i, pt in enumerate(self.points):
            d = query_pt.distance(pt) # Euclidean
            if d < min_dist:
                min_dist = d
                nearest_idx = i
                
        if nearest_idx != -1:
            return self.names[nearest_idx]
        return "Unknown"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Radius of earth in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c
    return d

def process_legacy_ra11_records(ra11_path: str, master_path: str):
    """
    Extracts 'Ghost Records' from RA_11.
    Includes:
    1. Records older than 01/05/2021.
    2. Vehicles dropped in Epoch B (Empty 'RA_11 Match' in Master).
    Updates 'Since Last Check-in' by adding 91 days.
    """
    if not os.path.exists(ra11_path):
        logger.warning(f"RA_11 file not found: {ra11_path}")
        return []

    try:
        ra11_df = pd.read_csv(ra11_path)
    except Exception as e:
        logger.error(f"Error reading RA_11 CSV: {e}")
        return []

    # Identify Dropped Vehicles from Master
    dropped_ids = set()
    if os.path.exists(master_path):
        try:
            master_df = pd.read_csv(master_path)
            # Filter rows where RA_11 Match is empty/NaN
            # Check column existence
            if 'RA_11 Match' in master_df.columns and 'Device ID' in master_df.columns:
                # Normalize
                master_df['RA_11 Match'] = master_df['RA_11 Match'].fillna('').astype(str).str.strip()
                master_df['Status'] = master_df['Status'].fillna('ACTIVE').astype(str).str.strip().str.upper()
                
                # Dropped OR Scrapped
                dropped = master_df[(master_df['RA_11 Match'] == '') | (master_df['Status'] == 'SCRAPPED')]
                dropped_ids = set(dropped['Device ID'].astype(str).str.strip())
                logger.info(f"Identified {len(dropped_ids)} dropped/scrapped vehicles from Master List.")
        except Exception as e:
            logger.error(f"Error reading Master CSV: {e}")
    
    # 1. Filter Logic
    try:
        ra11_df['calc_date_dt'] = pd.to_datetime(ra11_df['Calculated Date'], format='%d/%m/%Y', errors='coerce')
    except:
        return []
        
    cutoff_date = datetime(2021, 5, 1)
    
    # Valid Master IDs for filtering
    valid_master_ids = set()
    if os.path.exists(master_path):
        try:
             md = pd.read_csv(master_path)
             if 'Device ID' in md.columns:
                 valid_master_ids = set(md['Device ID'].astype(str).str.strip())
        except: pass

    processed_rows = []
    
    for _, row in ra11_df.iterrows():
        d_id = str(row.get('Device-ID', '')).strip()
        
        is_old = False
        if pd.notnull(row['calc_date_dt']):
            if row['calc_date_dt'] < cutoff_date:
                is_old = True
                
        is_dropped = d_id in dropped_ids
        
        # STRICT FILTER: Must be in Master List (either as Dropped or just Valid ID)
        if (is_old or is_dropped) and d_id in valid_master_ids:
            # 2. Update 'Since Last Check-in'
            # Format: "2730d 23h 59m"
            original_since = str(row.get('Since Last Check-in', ''))
            new_since = original_since
            
            match = re.search(r'(\d+)d\s+(\d+)h\s+(\d+)m', original_since)
            if match:
                days = int(match.group(1))
                hours = match.group(2)
                mins = match.group(3)
                
                new_days = days + 91 # Add 91 Days per requirement
                new_since = f"{new_days}d {hours}h {mins}m"
            
            processed_rows.append({
                "Vehicle Description": row.get('Vehicle Description'),
                "Device-ID": row.get('Device-ID'),
                "Date": row.get('Date'),
                "Time": row.get('Time'),
                "OdometerKm": row.get('Odometer (Km)'),     # Rename col
                "Lat/Lon": row.get('Lat/Lon'),
                "Address": row.get('Address'),
                "Latest Batt %": row.get('Latest Batt %', ''), 
                "Since Last Check-In": new_since
            })
        
    return processed_rows

def generate_report():
    # Enforce Determinism
    random.seed(42)
    
    if not os.path.exists(TELEMETRY_DIR):
        logger.error(f"Telemetry directory not found: {TELEMETRY_DIR}")
        return

    # Load mappings
    vehicle_map = load_vehicle_mapping()
    landmark_idx = LandmarkIndex()
    
    # --- 1. Load Legacy Ghost Records ---
    ra11_path = "data/external/VTS Consolidated Report - RA_11.csv"
    master_path = "data/external/VTS Consolidated Report - Final 268.csv"
    
    ghost_records = process_legacy_ra11_records(ra11_path, master_path)
    ghost_ids = set([r['Device-ID'] for r in ghost_records])
    
    # Collect all processed data here
    sim_report_rows = []
    
    # Iterate over files... [Existing Logic] ...
    logger.info("Scanning for parquet files...")
    all_files = glob.glob(os.path.join(TELEMETRY_DIR, "**", "*.parquet"), recursive=True)
    files_by_imei = {}
    
    for f_path in all_files:
        filename = os.path.basename(f_path)
        name_parts = filename.replace(".parquet", "").split("_")
        if len(name_parts) < 2: continue
        imei = name_parts[0]
        date_str = name_parts[1]
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            if REPORT_START <= date_obj <= REPORT_END:
                if imei not in files_by_imei: files_by_imei[imei] = []
                files_by_imei[imei].append((date_obj, f_path))
        except ValueError: continue

    for imei, file_list in files_by_imei.items():
        # --- DEDUPLICATION: Skip if Ghost Record exists ---
        # Device ID usually matches IMEI, but let's check both or mapped name?
        # The Ghost Record used 'Device-ID' column. 
        # We need to ensure we match correctly.
        # Assuming IMEI == Device-ID for simplicity, or check mapped name.
        # Since we don't have perfect map here, check basic string match
        if imei in ghost_ids:
            continue
        
        # Also check mapped name
        v_name = vehicle_map.get(imei, f"Vehicle_{imei}")
        # Need to check against 'Device-ID' in ghost inputs? 
        # Ghost records have 'Vehicle Description' and 'Device-ID'.
        # Let's check both just in case.
        is_ghost = False
        for g in ghost_records:
            if g['Device-ID'] == imei or g['Vehicle Description'] == v_name:
                is_ghost = True
                break
        if is_ghost: continue

        # ... [Rest of processing] ...
        file_list.sort(key=lambda x: x[0])
        vehicle_df = pd.DataFrame()
        for _, f in file_list:
             try:
                 df = pd.read_parquet(f)
                 if not df.empty:
                    vehicle_df = pd.concat([vehicle_df, df])
             except: pass
        
        if vehicle_df.empty: continue
        
        # Get Vehicle Info
        device_id = imei
        if 'device_id' in vehicle_df.columns:
             d_ids = vehicle_df['device_id'].dropna().unique()
             if len(d_ids) > 0: device_id = str(d_ids[0])
             
        # Double check deduplication with resolved Device-ID
        if device_id in ghost_ids: continue

        vehicle_df['timestamp'] = pd.to_datetime(vehicle_df['timestamp'])
        vehicle_df = vehicle_df.sort_values('timestamp')
        
        total_rows = len(vehicle_df)
        if total_rows == 0: continue
        
        # Deterministic Sample
        random_idx = random.randint(0, total_rows - 1)
        row = vehicle_df.iloc[random_idx]
        ts = row['timestamp']
        lat, lon = row['lat'], row['lon']
        
        # Odometer
        start_row = vehicle_df.iloc[0]
        trip_dist = 0.0
        if random_idx > 0:
            s_lat, s_lon = start_row['lat'], start_row['lon']
            trip_dist = haversine(s_lat, s_lon, lat, lon) * 1.5
        final_odometer = 25000.0 + trip_dist
        
        addr = landmark_idx.get_nearest_address(lat, lon)
        
        sim_report_rows.append({
            "Vehicle Description": v_name,
            "Device-ID": device_id,
            "Date": ts.strftime("%d/%m/%Y"),
            "Time": ts.strftime("%H:%M:%S"),
            "OdometerKm": int(final_odometer),
            "Lat/Lon": f"{lat:.4f}/{lon:.4f}",
            "Address": addr,
            "Latest Batt %": "", 
            "Since Last Check-In": ""
        })

    # --- MERGE & SORT ---
    final_rows = ghost_records + sim_report_rows
    
    # --- COMPLETENESS VALIDATION ---
    master_path = "data/external/VTS Consolidated Report - Final 268.csv"
    if os.path.exists(master_path):
        try:
            master_df = pd.read_csv(master_path)
            # Normalize column name 'Device ID' vs 'Device-ID'
            # File header: "Sl No.,Device ID,Zone ID..."
            if 'Device ID' in master_df.columns:
                target_ids = set(master_df['Device ID'].astype(str).str.strip())
            else:
                target_ids = set()
                logger.warning("Master 268 CSV missing 'Device ID' column.")
            
            # generated IDs
            generated_ids = set([r['Device-ID'] for r in final_rows])
            
            missing = target_ids - generated_ids
            extra = generated_ids - target_ids
            
            logger.info("-" * 40)
            logger.info(f"Target Count: {len(target_ids)} | Generated: {len(generated_ids)}")
            
            if len(missing) > 0:
                logger.warning(f"❌ MISSING {len(missing)} VEHICLES from Master List:")
                for m in list(missing)[:10]: logger.warning(f"   - {m}")
                if len(missing) > 10: logger.warning("   ... and more.")
            else:
                logger.info("✅ All target vehicles accounted for.")
                
            if len(extra) > 0:
                logger.warning(f"⚠️ FOUND {len(extra)} EXTRA VEHICLES not in Master List.")
                
            logger.info("-" * 40)
            
        except Exception as e:
            logger.error(f"Validation Error: {e}")

    if final_rows:
        out_df = pd.DataFrame(final_rows)
        # Sort by Vehicle Description
        out_df = out_df.sort_values(by="Vehicle Description", ascending=True)
        
        cols = ["Vehicle Description", "Device-ID", "Date", "Time", "OdometerKm", 
                "Lat/Lon", "Address", "Latest Batt %", "Since Last Check-In"]
        out_path = os.path.join(OUTPUT_DIR, "RA_12_Compliance_Report.csv")
        out_df.to_csv(out_path, index=False, columns=cols)
        logger.info(f"Generated RA_12 Report at {out_path} with {len(out_df)} rows (Ghosts: {len(ghost_records)}, Sim: {len(sim_report_rows)}).")
    else:
        logger.warning("No data found for RA_12 report.")

if __name__ == "__main__":
    generate_report()
