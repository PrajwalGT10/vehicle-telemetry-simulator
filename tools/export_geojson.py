import sys
import os
import glob
import json
import pandas as pd
import argparse
from tqdm import tqdm

# Fix Python path to find vts_core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_info_mapping(vehicles_dir="configs/vehicles"):
    mapping = {}
    if not os.path.exists(vehicles_dir): return mapping
    
    yaml_files = glob.glob(os.path.join(vehicles_dir, "*.yaml"))
    print(f"   Mapping from {len(yaml_files)} configs in {vehicles_dir}...")
    
    for vf in yaml_files:
        try:
            # Simple text parse to avoid slow yaml load if possible, 
            # but we need reliability. load_vehicle_config is available if we import it.
            # We already setup sys.path.
            from vts_core.config import load_vehicle_config
            cfg = load_vehicle_config(vf)
            # mapping[imei] = name
            # strip tk_ just in case config has it, though usually likely consistent
            imei = cfg.imei.replace("tk_", "")
            
            # Use the Name from config to ensure match with UI and Logs
            mapping[imei] = cfg.name
        except Exception as e:
            pass
            
    return mapping

# Global mapping cache
VEHICLE_MAPPING = None

def get_vehicle_name(imei):
    global VEHICLE_MAPPING
    if VEHICLE_MAPPING is None:
        VEHICLE_MAPPING = load_info_mapping()
    return VEHICLE_MAPPING.get(imei, f"Unknown_{imei}")

def export_day(parquet_path, output_dir):
    try:

        # 1. Read Data
        df = pd.read_parquet(parquet_path)
        if df.empty: return
        
        df = df.sort_values("timestamp")
        
        # 2. Extract Metadata from filename
        filename = os.path.basename(parquet_path)
        name_parts = filename.replace(".parquet", "").split("_")
        imei = name_parts[0]
        date_str = name_parts[1]
        
        vehicle_name = get_vehicle_name(imei)
        year, month = date_str.split("-")[:2]
        
        # 3. Build GeoJSON LineString
        coordinates = df[["lon", "lat"]].values.tolist()
        
        geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "imei": imei,
                    "vehicle": vehicle_name,
                    "date": date_str,
                    "points": len(coordinates),
                    "distance_km": f"{(df['speed'].mean() * len(df) * 25 / 3600 * 1.852):.2f}"
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                }
            }]
        }
        
        # 4. Save
        # Structure: data/exported_geojson/{VehicleName}/{Year}/{Month}/
        vehicle_dir = os.path.join(output_dir, vehicle_name, year, month)
        os.makedirs(vehicle_dir, exist_ok=True)
        
        out_file = os.path.join(vehicle_dir, f"{date_str}.geojson")
        with open(out_file, "w") as f:
            json.dump(geojson, f)
            
        return True
    except Exception as e:
        print(f"❌ Failed {parquet_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Bulk Parquet to GeoJSON Converter")
    parser.add_argument("--year", default="all", help="Year to export or 'all'")
    parser.add_argument("--imei", help="Specific IMEI (optional)")
    args = parser.parse_args()
    
    # 1. Find Files
    base_dir = "data/telemetry"
    # Support all years by default or specific year if provided
    if args.year == "all":
        pattern = f"{base_dir}/year=*/**/*.parquet"
    else:
        pattern = f"{base_dir}/year={args.year}/**/*.parquet"
        
    print(f"🔍 Searching: {pattern}")
    files = glob.glob(pattern, recursive=True)
    
    # Filter by IMEI if provided
    if args.imei:
        files = [f for f in files if args.imei in f]
        
    print(f"🌍 Found {len(files)} daily logs to convert...")
    
    # 2. Convert
    output_base = "data/exported_geojson"
    count = 0
    
    for f in tqdm(files, desc="Converting"):
        if export_day(f, output_base):
            count += 1
            
    print(f"\n✅ Export Complete!")
    print(f"📂 Files saved in: {output_base}")

if __name__ == "__main__":
    main()