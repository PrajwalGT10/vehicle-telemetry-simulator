import sys
import os
import glob
import json
import pandas as pd
import argparse
from tqdm import tqdm

# Fix Python path to find vts_core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def export_day(parquet_path, output_dir):
    try:
        # 1. Read Data
        df = pd.read_parquet(parquet_path)
        if df.empty: return
        
        df = df.sort_values("timestamp")
        
        # 2. Extract Metadata from filename
        # Filename format: {imei}_{date}.parquet
        filename = os.path.basename(parquet_path)
        name_parts = filename.replace(".parquet", "").split("_")
        imei = name_parts[0]
        date = name_parts[1]
        
        # 3. Build GeoJSON LineString
        coordinates = df[["lon", "lat"]].values.tolist()
        
        geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "imei": imei, 
                    "date": date,
                    "points": len(coordinates),
                    "distance_km": f"{(df['speed'].mean() * len(df) * 25 / 3600 * 1.852):.2f}" # Approx dist
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                }
            }]
        }
        
        # 4. Save
        # Structure: data/geojson/{imei}/
        vehicle_dir = os.path.join(output_dir, imei)
        os.makedirs(vehicle_dir, exist_ok=True)
        
        out_file = os.path.join(vehicle_dir, f"{date}.geojson")
        with open(out_file, "w") as f:
            json.dump(geojson, f)
            
        return True
    except Exception as e:
        print(f"❌ Failed {parquet_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Bulk Parquet to GeoJSON Converter")
    parser.add_argument("--year", default="2023", help="Year to export")
    parser.add_argument("--imei", help="Specific IMEI (optional)")
    args = parser.parse_args()
    
    # 1. Find Files
    base_dir = "data/telemetry"
    pattern = f"{base_dir}/year={args.year}/**/*.parquet"
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