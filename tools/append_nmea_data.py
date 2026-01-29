import os
import yaml
import re
import math
from datetime import datetime, timedelta

def load_vehicle_map(config_dir):
    """
    Loads vehicle configurations and maps Registration Number to IMEI and Directory Name.
    """
    vehicle_map = {}
    vehicles_dir = os.path.join(config_dir, 'vehicles')
    
    if not os.path.exists(vehicles_dir):
        print(f"Error: Vehicles directory not found at {vehicles_dir}")
        return vehicle_map

    for filename in os.listdir(vehicles_dir):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(vehicles_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    vehicle_data = config.get('vehicle', {})
                    
                    # Extract required fields
                    reg_no = vehicle_data.get('vehicle_number')
                    imei = vehicle_data.get('imei')
                    # Use provided name or filename (without extension) as directory name hint
                    # But the task implies we need to match existing folder structures which seem to be named after the config filename largely?
                    # Let's check the list_dir output from step 26.
                    # Directories are like "C3_KA04AA7688_Desilting".
                    # Config "C3_KA04AA7688_desilting.yaml" -> vehicle name "C3_KA04AA7688_Desilting".
                    # So we can efficiently use the directory name derived from the file name (case insensitive match maybe?) or the vehicle name.
                    # Let's rely on vehicle name from config if it matches directory conventions, 
                    # OR simply use the filename without extension which often matches the directory name.
                    
                    # Based on step 26, directory names match the vehicle name often but with case differences sometimes?
                    # Actually, looking at configs, "vehicle:name" seems to match the directory name.
                    dir_name = vehicle_data.get('name') 
                    
                    if reg_no and imei and dir_name:
                        # Normalize regex for matching from the input file
                        # Input file has "C2_KA04AA7688_DESILTING"
                        # We need to extract RegNo from that or map that full string to our config.
                        # The plan said "Extract RegNo from Vehicle Name", e.g. "C2_KA04AA7688_DESILTING" -> "KA04AA7688"
                        # We will store the RegNo as key.
                        vehicle_map[reg_no.replace(' ', '').upper()] = {
                            'imei': str(imei),
                            'dir_name': dir_name,
                            'full_name': vehicle_data.get('name')
                        }
            except Exception as e:
                print(f"Warning: Could not read {filename}: {e}")
                
    return vehicle_map

def decimal_to_nmea(decimal_degrees, is_latitude):
    """
    Converts decimal degrees to NMEA format (ddmm.mmmm).
    """
    if decimal_degrees is None:
        return ""
        
    try:
        val = float(decimal_degrees)
    except ValueError:
        return ""

    degrees = int(abs(val))
    minutes = (abs(val) - degrees) * 60
    
    # Format minutes to have 4 decimal places, but NMEA standard usually expects variable length or fixed?
    # Looking at sample file: 1258.2458
    # 12 degrees, 58.2458 minutes.
    
    nmea_val = float(f"{degrees * 100 + minutes:.4f}")
    
    # Format to string with correct padding
    # Latitude: ddmm.mmmm (2 digits for degrees)
    # Longitude: dddmm.mmmm (3 digits for degrees)
    
    if is_latitude:
        # e.g. 1258.2458
        nmea_str = f"{nmea_val:09.4f}" # 2+2+1+4 = 9 chars? No. 
        # 1258.2458 is 9 chars.
        # If deg is 9, 0958.2458
        nmea_str = f"{nmea_val:09.4f}"
    else:
        # e.g. 07735.9551 -> 77 deg, 35.9551 min
        # Total digits: 3 (deg) + 2 (min) + 1 (point) + 4 (decimal) = 10
        nmea_str = f"{nmea_val:010.4f}"
        
    return nmea_str

def get_hemisphere(val, is_latitude):
    if is_latitude:
        return 'N' if val >= 0 else 'S'
    else:
        return 'E' if val >= 0 else 'W'

def parse_append_data(filepath, vehicle_map, tracker_root):
    """
    Parses the Append_data.txt and processes each line.
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Skip header
    data_lines = lines[1:]
    
    success_count = 0
    fail_count = 0
    
    for line_num, line in enumerate(data_lines, start=2):
        line = line.strip()
        if not line:
            continue
            
        # Split by tab
        parts = line.split('\t')
        if len(parts) < 4:
            print(f"Line {line_num}: Not enough columns. Skipping.")
            fail_count += 1
            continue
            
        veh_name_input = parts[0]
        date_str = parts[1]
        time_str = parts[2]
        lat_lon_str = parts[3]
        
        # Extract RegNo
        # Expecting format like PREFIX_REGNO_SUFFIX or just something containing the REGNO
        # We have a map of REGNO -> Info.
        # Let's try to find which REGNO is in the veh_name_input
        found_vehicle = None
        for reg_no, info in vehicle_map.items():
            if reg_no in veh_name_input.replace('_', '').replace(' ', '').upper():
                found_vehicle = info
                break
        
        if not found_vehicle:
            # Try looser match or manual extraction if standard format
            # Format: C2_KA04AA7688_DESILTING -> KA04AA7688 is the middle part usually
            match = re.search(r'KA\d+[A-Z]+\d+', veh_name_input.replace('_', ''))
            if match:
                extracted_reg = match.group(0)
                if extracted_reg in vehicle_map:
                    found_vehicle = vehicle_map[extracted_reg]
                else:
                    # Maybe partial match?
                    pass

        if not found_vehicle:
            print(f"Line {line_num}: Vehicle '{veh_name_input}' not found in configs. Skipping.")
            fail_count += 1
            continue
            
        # Parse Date and Time
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
        except ValueError:
            print(f"Line {line_num}: Invalid date/time format '{date_str} {time_str}'. Skipping.")
            fail_count += 1
            continue
            
        # Parse Lat/Lon
        try:
            lat_str, lon_str = lat_lon_str.split('/')
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            print(f"Line {line_num}: Invalid lat/lon format '{lat_lon_str}'. Skipping.")
            fail_count += 1
            continue
            
        # Format Data
        imei = found_vehicle['imei']
        timestamp_short = dt.strftime("%y%m%d%H%M%S") # 230105080003
        time_nmea = dt.strftime("%H%M%S.000")
        date_folder = dt.strftime("%Y-%m-%d")
        
        lat_nmea = decimal_to_nmea(lat, True)
        lon_nmea = decimal_to_nmea(lon, False)
        ns = get_hemisphere(lat, True)
        ew = get_hemisphere(lon, False)
        
        # Construct NMEA Line
        # imei:868683022802015,tracker,230105080003,,F,080003.000,A,1258.2458,N,07735.9551,E,11.57,286.36;
        # Speed and Course are missing in input, defaulting to 0.00
        nmea_line = f"imei:{imei},tracker,{timestamp_short},,F,{time_nmea},A,{lat_nmea},{ns},{lon_nmea},{ew},0.00,0.00;"
        
        # Determine Output File
        # data/tracker/{DirName}/{YYYY}/{MM}/{YYYY-MM-DD}.txt
        year_str = dt.strftime("%Y")
        month_str = dt.strftime("%m")
        dir_name = found_vehicle['dir_name']
        
        target_dir = os.path.join(tracker_root, dir_name, year_str, month_str)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        target_file = os.path.join(target_dir, f"{date_folder}.txt")
        
        # Append to file
        try:
            with open(target_file, 'a') as f_out:
                f_out.write(nmea_line + "\n")
            success_count += 1
            print(f"Line {line_num}: Appended to {target_file}")
        except Exception as e:
            print(f"Line {line_num}: Failed to write to file: {e}")
            fail_count += 1

    print(f"\nProcessing complete. Success: {success_count}, Failed: {fail_count}")

def main():
    base_dir = r"d:\vehicle-tracking-system"
    config_dir = os.path.join(base_dir, "configs")
    tracker_root = os.path.join(base_dir, "data", "tracker")
    input_file = os.path.join(config_dir, "Append_data.txt")
    
    print("Loading vehicle maps...")
    vehicle_map = load_vehicle_map(config_dir)
    print(f"Loaded {len(vehicle_map)} vehicles.")
    
    print(f"Processing {input_file}...")
    parse_append_data(input_file, vehicle_map, tracker_root)

if __name__ == "__main__":
    main()
