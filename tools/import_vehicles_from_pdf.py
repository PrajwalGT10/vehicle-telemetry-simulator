import re
import os
from pypdf import PdfReader
import yaml

# Zone Mapping Dictionary
ZONE_MAP = {
    "SE1": "South_East_Bangalore",
    "SE2": "South_East_Bangalore",
    "E1": "South_East_Bangalore",
    "E2": "South_East_Bangalore",
    "E3": "South_East_Bangalore",
    "E4": "South_East_Bangalore",
    "S1": "South_East_Bangalore",
    "S2": "South_East_Bangalore",
    "W1": "South_East_Bangalore",
    "N1": "South_East_Bangalore",
    "C1": "South_East_Bangalore",
    "C2": "South_East_Bangalore",
    "C3": "South_East_Bangalore",
    "KC1": "South_East_Bangalore",
    "NE2": "South_East_Bangalore",
    "NE3": "South_East_Bangalore",
}

def get_zone_config(prefix):
    zone_dir = ZONE_MAP.get(prefix, f"Zone_{prefix}")
    if not os.path.exists(f"data/zones/{zone_dir}/roads.geojson"):
        zone_dir = "South_East_Bangalore"

    return {
        "name": zone_dir,
        "roads_geojson": f"data/zones/{zone_dir}/roads.geojson",
        "localities_file": f"data/zones/{zone_dir}/localities.geojson"
    }

def process_pdf(pdf_path, output_dir):
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return

    reader = PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"

    # Regex Strategy
    device_pattern = re.compile(r"([A-Z0-9]+_KA[A-Z0-9]+[_\s][A-Za-z0-9_ ]{1,50})", re.IGNORECASE)
    imei_pattern = re.compile(r"tk_(\d{15})")
    
    raw_ids = device_pattern.findall(full_text)
    imeis = imei_pattern.findall(full_text)
    
    print(f"Found {len(raw_ids)} Potential IDs and {len(imeis)} IMEIs")
    print(f"Sample Raw IDs (First 5): {raw_ids[:5]}")
    
    clean_ids = []
    for rid in raw_ids:
        # Minimal filtering
        if "IMEI" in rid: 
             continue
            
        parts = rid.split("_")
        
        # 1. Clean Prefix
        prefix = parts[0]
        m = re.search(r"([A-Z]+[0-9]+)$", prefix)
        if m:
            clean_prefix = m.group(1)
            parts[0] = clean_prefix
        
        # 2. Check for Trailing Garbage
        last_part = parts[-1]
        m_end = re.search(r"([A-Z]+[0-9]+)$", last_part)
        if m_end:
             possible_garbage = m_end.group(1)
             if len(possible_garbage) < len(last_part):
                 parts[-1] = last_part[:m_end.start()].strip()
        
        # 3. Handle Space-separated Type
        if len(parts) == 2 and " " in parts[1]:
             p2 = parts[1]
             subparts = p2.split(maxsplit=1)
             if len(subparts) == 2:
                parts = [parts[0], subparts[0], subparts[1].replace(" ", "_")]

        clean_id = "_".join(parts)
        clean_id = re.sub(r"_+", "_", clean_id)
        
        # Filter duplicates or empty
        if len(clean_id) > 5:
            clean_ids.append(clean_id)

    print(f"Cleaned IDs: {len(clean_ids)}")
    device_ids = clean_ids
    
    min_len = min(len(device_ids), len(imeis))
    
    for i in range(min_len):
        d_id = device_ids[i]
        imei = imeis[i]
        d_id = d_id.strip()
        
        # Default VType Logic if missing
        parts = d_id.split("_")
        if len(parts) >= 3:
            v_type = parts[-1]
        else:
            v_type = "Vehicle"
        
        prefix = parts[0]
        
        zone_info = get_zone_config(prefix)
        
        data = {
            "vehicle": {
                "name": d_id,
                "imei": imei,
                "device_id": d_id,
                "vehicle_type": v_type,
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
        
        safe_name = re.sub(r'[^\w\-_\.]', '_', d_id)
        file_path = os.path.join(output_dir, f"{safe_name}.yaml")
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False)
            
        print(f"Generated: {file_path}")

if __name__ == "__main__":
    process_pdf("configs/IMEI Details.pdf", "configs/vehicles")
