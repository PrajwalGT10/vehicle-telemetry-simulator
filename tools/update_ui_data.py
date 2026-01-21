import sys
import os
import json
import glob
from pathlib import Path

# Add root to path so we can import vts_core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vts_core.config import load_vehicle_config

def main():
    # 1. Setup Paths
    vehicles_dir = "configs/vehicles"
    output_path = "ui/data/vehicles.json"
    
    # Ensure ui/data exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print("🔄 Generating UI data from configs...")
    
    yaml_files = glob.glob(os.path.join(vehicles_dir, "*.yaml"))
    ui_data = {}
    
    # 2. Process each vehicle
    for f in yaml_files:
        try:
            cfg = load_vehicle_config(f) # load_vehicle_config should handle encoding, let's check it.
            # actually load_vehicle_config calls open(path, 'r'), which uses default encoding (cp1252 on windows).
            # We should fix vts_core/config.py, but for now let's see if we can just fix it there.
            # checking vts_core/config.py is better. Use view_file first.
            # We use IMEI as the key so the UI passes IMEI to the map loader
            ui_data[cfg.imei] = {
                "imei": cfg.imei,
                "vehicle_name": cfg.name,
                "equipment_type": getattr(cfg, "type", "Vehicle") # Handle missing type
            }
        except Exception as e:
            print(f"⚠️ Skipping {f}: {e}")
            
    # 3. Save JSON
    with open(output_path, "w") as f:
        json.dump(ui_data, f, indent=2)
        
    print(f"✅ Created {output_path} with {len(ui_data)} vehicles.")

if __name__ == "__main__":
    main()