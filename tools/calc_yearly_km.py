import sys
import os

# --- FIX START ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# --- FIX END ---

import glob
import pandas as pd
from vts_core.utils import haversine_distance

def main():
    # Adjust IMEI to match your config
    imei = "864895033188200" 
    year = "2023"
    
    # Pattern to find all parquet files for this vehicle in 2023
    # Path: data/telemetry/year=2023/month=*/imei_date.parquet
    pattern = f"data/telemetry/year={year}/month=*/*.parquet"
    files = glob.glob(pattern)
    
    vehicle_files = [f for f in files if imei in f]
    print(f"Found {len(vehicle_files)} daily logs for {imei} in {year}")
    
    total_km = 0.0
    
    for f in vehicle_files:
        try:
            df = pd.read_parquet(f)
            if len(df) < 2: continue
            
            # Simple distance sum between points
            # We can approximate by summing speed * time, or using coordinates
            # Let's use the 'speed' column to check 'Active Distance'
            # Or use the Lat/Lon haversine helper
            
            # Fast approx: Sum of (Speed_knots * 1.852 * Time_hours)
            # But simpler: The engine printed the route length. 
            # We can just check the max-min coordinate drift? 
            # No, let's use the haversine from utils.
            
            from vts_core.utils import haversine_distance
            coords = list(zip(df.lat, df.lon))
            day_dist = 0
            for i in range(len(coords)-1):
                day_dist += haversine_distance(
                    coords[i][0], coords[i][1], 
                    coords[i+1][0], coords[i+1][1]
                )
            
            total_km += (day_dist / 1000.0) # Meters to KM
            
        except Exception:
            pass

    print(f"🏁 Total Distance for 2023: {total_km:.2f} km")
    print(f"   Target was: 5670 km")

if __name__ == "__main__":
    main()