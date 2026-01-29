import sys
import os
sys.path.append(os.getcwd())
from vts_core.engine import run_simulation_day

# Config for C1_KA041A7291_Jetting
# CSV Data: 5/4/2022 (April 5) -> 10:05:48 -> 12.9828/77.5851
vehicle_config = r"d:\vehicle-tracking-system\configs\vehicles\C1_KA041A7291_Jetting.yaml"
# Assuming C_Zone
zone_roads = r"d:\vehicle-tracking-system\data\zones\C_Zone\roads.geojson"
date = "2022-04-05"

print(f"🚀 Verifying Hybrid Injection for {date}...")
try:
    # Run simulation
    run_simulation_day(vehicle_config, zone_roads, date, output_dir="data", enable_legacy_logs=True)
    print("✅ Simulation completed without error.")
except Exception as e:
    print(f"❌ Simulation failed: {e}")
