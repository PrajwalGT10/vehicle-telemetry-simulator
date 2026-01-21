import re
import os
import glob
import yaml

# Fallback
DEFAULT_ZONE = "South_East_Bangalore"

def get_zone_config(zone_id):
    """
    Map zone_id (e.g. C1, SE2, WWM) to data/zones/{Prefix}_Zone.
    """
    
    # Extract alpha prefix: C1 -> C, SE2 -> SE
    # Special case: WWM might be its own thing or map to something else.
    # Our fetch script treated WWM as a prefix.
    
    match = re.match(r"([A-Z]+)", zone_id, re.IGNORECASE)
    if match:
        prefix = match.group(1).upper()
        # Constuct folder name
        target_folder = f"{prefix}_Zone"
        
        # Check if it exists
        if os.path.exists(f"data/zones/{target_folder}/roads.geojson"):
            return {
                "name": target_folder,
                "roads_geojson": f"data/zones/{target_folder}/roads.geojson",
                "localities_file": f"data/zones/{target_folder}/localities.geojson"
            }
            
    # Fallback
    return {
        "name": DEFAULT_ZONE,
        "roads_geojson": f"data/zones/{DEFAULT_ZONE}/roads.geojson",
        "localities_file": f"data/zones/{DEFAULT_ZONE}/localities.geojson"
    }

def clean_device_id(raw_id):
    line = raw_id.strip()
    line = re.sub(r'[•\-.]+$', '', line)
    return line.strip()

def process(info_path, output_dir):
    if not os.path.exists(info_path):
        print(f"❌ File not found: {info_path}")
        return

    # Clear old
    existing = glob.glob(os.path.join(output_dir, "*.yaml"))
    for f in existing:
        try:
            os.remove(f)
        except OSError:
            pass
    print(f"Cleared {len(existing)} old config files.")

    count = 0
    with open(info_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line: continue
        
        parts = line.split('\t')
        
        if "Device ID" in parts[0]:
            continue
            
        if len(parts) < 2:
            continue

        d_id = clean_device_id(parts[0])
        
        zone_id = parts[1].strip() if len(parts) > 1 else "SE1"
        veh_no = parts[2].strip() if len(parts) > 2 else ""
        imei = parts[3].strip() if len(parts) > 3 else ""
        
        imei_clean = imei.replace("tk_", "")
        
        v_type = d_id.split('_')[-1]
        
        # Mapping
        zone_info = get_zone_config(zone_id)
        
        safe_name = re.sub(r'[^\w\-_\.]', '_', d_id)
        
        data = {
            "vehicle": {
                "name": d_id,
                "imei": imei_clean,
                "device_id": d_id, 
                "vehicle_type": v_type,
                "vehicle_number": veh_no,
                "zone_id": zone_id, 
                "max_speed_knots": 25.0,
                "depot_lat": 12.958319,
                "depot_lon": 77.612422 
            },
            "zone": zone_info,
            "shift": {
                "timezone": "Asia/Kolkata",
                "start_time": "09:00",
                "end_time": "19:00",
                "sampling_interval_seconds": 25,
                "sampling_jitter_seconds": 5
            },
            "calendar": {
                "working_days": ["MON", "TUE", "WED", "THU", "FRI"],
                "allow_saturdays": True,
                "saturday_probability_per_month": 2,
                "holidays_file": "configs/calendars/india_2023_holidays.json"
            },
            "routes": {
                "templates": ["RT_DEFAULT"]
            },
            "generation": {
                "random_seed": 12345,
                "output_root": "data/output",
                "output_granularity": "per_day"
            }
        }
        
        file_path = os.path.join(output_dir, f"{safe_name}.yaml")
        with open(file_path, 'w', encoding='utf-8') as f_out:
            yaml.dump(data, f_out, sort_keys=False, allow_unicode=True)
            
        count += 1

    print(f"Generated {count} configs from Structured Info.txt with Dynamic Zones")

if __name__ == "__main__":
    process("configs/Info.txt", "configs/vehicles")
