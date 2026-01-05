import sys
import os
import json
import pandas as pd
import argparse

# Ensure we can import vts_core from root
sys.path.append(os.getcwd())

from vts_core.store import SimulationStore

def main():
    parser = argparse.ArgumentParser(description="Verify VTS Output")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD to verify")
    parser.add_argument("--imei", default="864895033188200", help="Vehicle IMEI")
    args = parser.parse_args()
    
    print(f"🔍 Verifying Simulation Data for {args.imei} on {args.date}...")
    store = SimulationStore(base_dir="data")

    # --- 1. Verify Log Format ---
    try:
        txt_path = store.export_legacy_log(args.imei, args.date, "DEV_TEST")
        print(f"\n✅ Log File Generated: {txt_path}")
        
        # Count lines
        with open(txt_path, "r") as f:
            lines = f.readlines()
            count = len(lines)
            
        print(f"   📊 Total Records: {count}")
        if count > 3000:
            print("   ✅ Duration Check: PASSED (Data covers full day)")
        else:
            print(f"   ⚠️ Duration Check: WARNING (Only {count} records. Expected ~3500 for 24h)")

        print("\n   [Preview of first 3 lines]")
        print("   " + "-"*60)
        for line in lines[:3]:
            print(f"   {line.strip()}")
        print("   " + "-"*60)
        
        print("\n   [Preview of last 3 lines]")
        print("   " + "-"*60)
        for line in lines[-3:]:
            print(f"   {line.strip()}")
        print("   " + "-"*60)
        
        # Format Check
        first_line = lines[0].strip()
        if first_line.startswith("imei:") and first_line.endswith(";"):
            print("\n   ✅ Format Check: PASSED (No brackets, ends with ;)")
        else:
            print(f"\n   ❌ Format Check: FAILED. Line: {first_line}")
                
    except FileNotFoundError:
        print(f"❌ Error: Telemetry not found for {args.date}. Did you run the simulation?")
        return

    # --- 2. Generate GeoJSON for Visualization ---
    try:
        parquet_path = f"data/telemetry/year={args.date[:4]}/month={args.date[5:7]}/{args.imei}_{args.date}.parquet"
        if os.path.exists(parquet_path):
            df = pd.read_parquet(parquet_path)
            df = df.sort_values("timestamp")
            
            coords = df[["lon", "lat"]].values.tolist()
            
            geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {"imei": args.imei, "date": args.date, "count": len(coords)},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords
                    }
                }]
            }
            
            out_file = f"data/{args.imei}_{args.date}_verify.geojson"
            with open(out_file, "w") as f:
                json.dump(geojson, f)
                
            print(f"\n✅ GeoJSON Map Generated: {out_file}")
    except Exception as e:
        print(f"❌ Failed to generate GeoJSON: {e}")

if __name__ == "__main__":
    main()