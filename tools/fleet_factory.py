import os
import csv
import glob
import shutil
import random
import yaml
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Constants
CSV_PATH = os.path.join("data", "external", "VTS Consolidated Report - Final 268.csv")
CONFIG_DIR = os.path.join("configs", "vehicles")
DATA_DIR = "data"
ZONES_DIR = os.path.join("data", "zones")

# Zone Mapping (CSV ID -> Directory Name)
ZONE_MAP = {
    "C": "C_Zone", "E": "E_Zone", "N": "N_Zone", "S": "S_Zone", "W": "W_Zone",
    "NE": "NE_Zone", "NW": "NW_Zone", "SE": "SE_Zone", "SW": "SW_Zone",
    "WWM": "WWM_Zone",
    "C1": "C_Zone", "E1": "E_Zone", "N1": "N_Zone", "S1": "S_Zone", "W1": "W_Zone",
    "SE1": "SE_Zone", "SW1": "SW_Zone", "NE1": "NE_Zone", "NW1": "NW_Zone"
}

# Banglore default center (fallback)
DEFAULT_LAT = 12.9716
DEFAULT_LON = 77.5946

def get_zone_center(zone_name):
    """Calculates the centroid of all localities in a zone."""
    localities_file = os.path.join(ZONES_DIR, zone_name, "localities.geojson")
    if not os.path.exists(localities_file):
        return DEFAULT_LAT, DEFAULT_LON

    try:
        with open(localities_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        feats = data.get('features', [])
        if not feats:
            return DEFAULT_LAT, DEFAULT_LON
            
        lats, lons = [], []
        for feat in feats:
            geom = feat.get('geometry', {})
            coords = geom.get('coordinates', [])
            if not coords:
                continue
            
            # Rough centroid logic
            if geom['type'] == 'Point':
                lons.append(coords[0])
                lats.append(coords[1])
            elif geom['type'] == 'Polygon':
                ring = coords[0]
                ring_lons = [p[0] for p in ring]
                ring_lats = [p[1] for p in ring]
                lons.append(sum(ring_lons) / len(ring_lons))
                lats.append(sum(ring_lats) / len(ring_lats))
                
        if lats and lons:
            return sum(lats)/len(lats), sum(lons)/len(lons)
            
    except Exception as e:
        logger.warning(f"Error reading localities for {zone_name}: {e}")
        
    return DEFAULT_LAT, DEFAULT_LON

def resolve_zone(zone_id_raw):
    """Maps CSV Zone ID to Folder Name."""
    zid = zone_id_raw.strip().upper()
    if zid in ZONE_MAP:
        return ZONE_MAP[zid]
    
    # Heuristic fallback (e.g. C2 -> C_Zone)
    for prefix in ["SE", "SW", "NE", "NW", "WWM"]:
        if zid.startswith(prefix):
             return f"{prefix}_Zone"
             
    for char in ["C", "E", "N", "S", "W"]:
        if zid.startswith(char):
            return f"{char}_Zone"
            
    return "C_Zone" # Default

def create_vehicle_config(name, imei, zone_id_raw, vehicle_type, window_start, window_end, enabled, depot_lat, depot_lon, vehicle_number_raw):
    """Generates the YAML dictionary for a vehicle configuration."""
    
    zone_name = resolve_zone(zone_id_raw)
    
    # Fallback if Imei is missing
    if not imei or imei.lower() == 'na' or not imei.isdigit():
        imei = str(random.randint(100000000000000, 999999999999999))

    # Vehicle Number
    v_number = vehicle_number_raw if vehicle_number_raw else name.split('_')[-1] # Fallback
    
    # Normalize Vehicle Type (Capitalized)
    v_type = vehicle_type.capitalize() if vehicle_type else "Truck"

    config = {
        'vehicle': {
            'name': name,
            'imei': imei,
            'device_id': name, # Using name as device_id for consistency
            'vehicle_type': v_type,
            'vehicle_number': v_number,
            'zone_id': zone_id_raw,
            'max_speed_knots': 25.0,
            'depot_lat': depot_lat,
            'depot_lon': depot_lon,
            'odometer_offset_km': 0,
            'enabled': enabled
        },
        'zone': {
            'name': zone_name,
            'roads_geojson': f"data/zones/{zone_name}/roads.geojson",
            'localities_file': f"data/zones/{zone_name}/localities.geojson"
        },
        'shift': {
            'timezone': 'Asia/Kolkata',
            'start_time': '09:00',
            'end_time': '19:00',
            'sampling_interval_seconds': 900,
            'sampling_jitter_seconds': 0
        },
        'calendar': {
            'working_days': ['MON', 'TUE', 'WED', 'THU', 'FRI'],
            'allow_saturdays': True,
            'saturday_probability_per_month': 2,
            'holidays_file': 'configs/calendars/india_2023_holidays.json'
        },
        'simulation_window': {
             'start_date': window_start,
             'end_date': window_end
        },
        'routes': {
            'templates': ['RT_DEFAULT']
        },
        'generation': {
            'random_seed': 12345,
            'output_root': 'data/output',
            'output_granularity': 'per_day'
        }
    }
    return config

def generate_fleet():
    # 1. Clear configs directory
    if os.path.exists(CONFIG_DIR):
        logger.info(f"Clearing {CONFIG_DIR}...")
        for f in glob.glob(os.path.join(CONFIG_DIR, "*.yaml")):
            os.remove(f)
    else:
        os.makedirs(CONFIG_DIR, exist_ok=True)

    # 2. Read CSV
    logger.info(f"Reading CSV from {CSV_PATH}...")
    zone_cache = {} # Cache centers

    total_epoch_a = 0
    total_epoch_b = 0
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [x.strip() for x in reader.fieldnames]
        
        for row in reader:
            # Common Data
            zone_id = row.get('Zone ID', 'C1').strip()
            v_type = row.get('Vehicle Type', 'Truck').strip()
            imei = row.get('IMEI', '').strip()
            v_num = row.get('Vehicle Number', '').strip()
            status = row.get('Status', '').strip().upper()
            
            # Resolve Depot
            zone_name = resolve_zone(zone_id)
            if zone_name not in zone_cache:
                zone_cache[zone_name] = get_zone_center(zone_name)
            lat, lon = zone_cache[zone_name]

            # --- EPOCH A (May 2021 - Apr 2022) ---
            # Source: 'Device ID'
            dev_id = row.get('Device ID', '').strip()
            if dev_id:
                # Determine enabled status
                is_scrapped = (status == 'SCRAPPED')
                enabled = not is_scrapped
                
                config_a = create_vehicle_config(
                    name=dev_id,
                    imei=imei, # Reusing IMEI as per requirement to inherit
                    zone_id_raw=zone_id,
                    vehicle_type=v_type,
                    window_start='2021-05-01',
                    window_end='2022-04-30',
                    enabled=enabled,
                    depot_lat=lat,
                    depot_lon=lon,
                    vehicle_number_raw=v_num
                )
                
                with open(os.path.join(CONFIG_DIR, f"{dev_id}_A.yaml"), 'w') as f_out:
                    yaml.dump(config_a, f_out, sort_keys=False)
                total_epoch_a += 1

            # --- EPOCH B (May 2022 - Apr 2024) ---
            # Source: 'RA_11 Match'
            ra11 = row.get('RA_11 Match', '').strip()
            
            # Only create if RA_11 Match exists and is not just a duplicate of Device ID (unless required? User said "2 sets... for vehicles valid...").
            # User said: "Generate 183 .yaml config files named {RA_11 Match}.yaml"
            # It implies we only generate if RA_11 Match is present. 
            
            if ra11 and ra11.lower() != 'nan':
                 config_b = create_vehicle_config(
                    name=ra11,
                    imei=imei,
                    zone_id_raw=zone_id,
                    vehicle_type=v_type,
                    window_start='2022-05-01',
                    window_end='2024-04-30',
                    enabled=not is_scrapped, # Apply Scrapped rule to Epoch B as well
                    depot_lat=lat,
                    depot_lon=lon,
                    vehicle_number_raw=v_num
                )
                 
                 with open(os.path.join(CONFIG_DIR, f"{ra11}_B.yaml"), 'w') as f_out:
                    yaml.dump(config_b, f_out, sort_keys=False)
                 total_epoch_b += 1

    logger.info("-" * 30)
    logger.info(f"Fleet Generation Complete.")
    logger.info(f"Epoch A files: {total_epoch_a}")
    logger.info(f"Epoch B files: {total_epoch_b}")
    logger.info(f"Total files: {total_epoch_a + total_epoch_b}")

if __name__ == "__main__":
    generate_fleet()
