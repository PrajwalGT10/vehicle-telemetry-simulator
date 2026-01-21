import re
import os
import glob
from pypdf import PdfReader
import yaml

ZONE_MAP = {
    "SE1": "South_East_Bangalore",
    "SE2": "South_East_Bangalore",
    # ... (Map others to SE as fallback or specific if known)
}

def get_zone_config(name):
    # Try to extract prefix from name: "SE1_..." or "WWM_KC1_..."
    # Heuristic: Find first part before underscore
    parts = name.split('_')
    prefix = parts[0]
    
    # If WWM or similar, look deeper
    if prefix.upper() == "WWM":
        if len(parts) > 1: prefix = parts[1]
    
    # Clean prefix
    prefix = re.sub(r'[^A-Z0-9]', '', prefix.upper())
    
    zone_dir = "South_East_Bangalore" # Default
    
    # Check if specific zone folder exists (optional enhancement)
    
    return {
        "name": zone_dir,
        "roads_geojson": f"data/zones/{zone_dir}/roads.geojson",
        "localities_file": f"data/zones/{zone_dir}/localities.geojson"
    }

def clean_info_name(raw_line):
    # Remove bullets, trailing dashes/dots
    # "C3_KA04AA9028_Desilting •" -> "C3_KA04AA9028_Desilting"
    # "C3_KA04C5156_Jetting-." -> "C3_KA04C5156_Jetting"
    line = raw_line.strip()
    line = re.sub(r'[•\-.]+$', '', line)
    line = line.strip()
    return line

def process(info_path, pdf_path, output_dir):
    # 1. Read Names
    with open(info_path, 'r') as f:
        names = [clean_info_name(l) for l in f if l.strip()]
        
    print(f"Loaded {len(names)} vehicle names from Info.txt")
    
    # 2. Read PDF for IMEIs
    reader = PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"
        
    # We need to map Name -> IMEI
    # Strategy: Find the name (fuzzy match?), find the subsequent "tk_(\d+)"
    
    # To handle PDF artifacts (spaces inside names), we might need to normalize PDF text space.
    # e.g. "C1_ KA04" -> "C1_KA04"
    
    pdf_text_norm = re.sub(r'\s+', ' ', full_text) # single spaces
    pdf_text_compact = re.sub(r'\s+', '', full_text) # remove all spaces (careful)
    
    generated_count = 0
    
    # Clear output dir?
    # existing = glob.glob(os.path.join(output_dir, "*.yaml"))
    # for f in existing: os.remove(f)
    
    for name in names:
        # Search strategy
        # 1. Exact match in full text?
        # 2. Match in compact text?
        
        # Name in Info: "C1_KA04AA9013_Desilting"
        # PDF might have "C1_KA04AA9013_ Desilting"
        
        # We search for a "signature" of the name: the KA part?
        # Or construct a regex from the name allowing spaces?
        
        name_clean = name.replace(" ", "")
        
        # Regex to find this name's chars with optional spaces between them
        # "C1" -> "C\s*1"
        escaped = re.escape(name_clean)
        # simplistic Approach: Find the KA part, its usually key.
        # But let's try searching for the Name in the consolidated text.
        
        # Locate index of name in pdf_text_compact
        # Then map back? Hard.
        
        # Alternative: The PDF has (Name) ... (IMEI).
        # We can find all matches of `tk_(\d+)`, store their usage.
        
        # Let's try locating the name in the original text (with spaces normalized)
        # Create a regex from the name that allows whitespace
        # "C1_KA..." -> "C1\s*_\s*K\s*A..."
        
        # Robust regex construction:
        regex_str = ""
        for char in name:
            if char.isalnum():
                regex_str += char + r"\s*"
            else:
                 regex_str += re.escape(char) + r"\s*"
        
        pattern = re.compile(regex_str, re.IGNORECASE)
        match = pattern.search(full_text)
        
        imei = "000000000000000" # Default
        if match:
            start_idx = match.end()
            # Look ahead for tk_
            # Limit lookahead
            chunk = full_text[start_idx:start_idx+200]
            m_imei = re.search(r"tk_(\d{15})", chunk)
            if m_imei:
                imei = m_imei.group(1)
            else:
                # print(f"⚠️ IMEI not found for {name}")
                pass
        else:
            print(f"⚠️ Name not found in PDF: {name}")
        
        # Generate YAML
        safe_name = re.sub(r'[^\w\-_\.]', '_', name) # match file system
        
        zone_info = get_zone_config(name)
        
        data = {
            "vehicle": {
                "name": name, # Original Name from Info.txt
                "imei": imei,
                "device_id": safe_name,
                "vehicle_type": name.split('_')[-1] if '_' in name else "Vehicle",
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
        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False)
            
        generated_count += 1

    print(f"Generated {generated_count} configs from Info.txt")

if __name__ == "__main__":
    process("configs/Info.txt", "configs/IMEI Details.pdf", "configs/vehicles")
