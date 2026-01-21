import os
import shutil
import glob

def load_info_mapping(info_path="configs/Info.txt"):
    mapping = {}
    if not os.path.exists(info_path):
        return mapping
    with open(info_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                imei = parts[3].strip()
                name = parts[2].strip()
                safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
                safe_name = safe_name.replace(' ', '_')
                mapping[imei] = safe_name
    return mapping

def migrate_geojson():
    base_dir = "data"
    source_root = os.path.join(base_dir, "exported_geojson")
    
    if not os.path.exists(source_root):
        print("No source directory found. Migration skipped.")
        return

    mapping = load_info_mapping()
    print(f"Loaded {len(mapping)} vehicle mappings.")
    
    # Existing structure: data/exported_geojson/{IMEI}/{Date}.geojson
    # OR data/exported_geojson/{IMEI}/... if user ran old script
    # User said: "Currently there are geojsons for the vehicle SE1...". 
    # If the folder exists as IMEI (864...), move it to Name/Year/Month.
    
    items = glob.glob(os.path.join(source_root, "*"))
    moved_count = 0
    
    for item in items:
        if not os.path.isdir(item): continue
        
        folder_name = os.path.basename(item)
        
        # Check if folder name is already a vehicle name (from previous run) or IMEI
        # If it's IMEI, map it. If it's already Name, maybe restructure inside?
        # Assuming current state is IMEI folders (864895033188200) based on `ls` output earlier.
        
        imei = folder_name
        vehicle_name = mapping.get(imei, f"Unknown_{imei}")
        
        if vehicle_name == f"Unknown_{imei}":
            # Check if this folder IS actually a vehicle name
            # If folder_name is in mapping.values(), then it's already a Name.
            if folder_name in mapping.values():
                vehicle_name = folder_name
                # It's already named, but does it have Year/Month structure?
                # We'll traverse files and ensure correct path.
        
        files = glob.glob(os.path.join(item, "*.geojson"))
        for file_path in files:
            filename = os.path.basename(file_path)
            # filename: YYYY-MM-DD.geojson
            date_str = filename.replace(".geojson", "")
            try:
                parts = date_str.split("-")
                year, month = parts[0], parts[1]
            except:
                year, month = "Unknown_Year", "Unknown_Month"
                
            # New Path
            dest_dir = os.path.join(source_root, vehicle_name, year, month)
            os.makedirs(dest_dir, exist_ok=True)
            
            dest_path = os.path.join(dest_dir, filename)
            
            # Avoid overwrite if moving effectively to same place
            if os.path.abspath(file_path) != os.path.abspath(dest_path):
                shutil.move(file_path, dest_path)
                moved_count += 1
        
        # Cleanup old IMEI folder if empty
        if not os.listdir(item):
            os.rmdir(item)
        # If it wasn't empty (e.g. subdirs), leave it.
            
    print(f"Migrated {moved_count} GeoJSON files.")

if __name__ == "__main__":
    migrate_geojson()
