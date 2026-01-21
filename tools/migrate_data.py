import os
import shutil
import glob

def load_info_mapping(info_path="configs/Info.txt"):
    mapping = {}
    if not os.path.exists(info_path):
        print("Info.txt not found!")
        return mapping
        
    with open(info_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                imei = parts[3].strip()
                name = parts[2].strip()
                # Ensure Name is safe for path
                safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
                safe_name = safe_name.replace(' ', '_')
                mapping[imei] = safe_name
    return mapping

def migrate():
    base_dir = "data"
    source_root = os.path.join(base_dir, "output", "tracker")
    target_root = os.path.join(base_dir, "tracker")
    
    if not os.path.exists(source_root):
        print("No source directory found ('data/output/tracker'). Migration skipped.")
        return

    mapping = load_info_mapping()
    print(f"Loaded {len(mapping)} vehicle mappings.")
    
    # Walk through source logs
    # Structure: data/output/tracker/{IMEI}/{Date}.txt
    imei_dirs = glob.glob(os.path.join(source_root, "*"))
    
    moved_count = 0
    
    for imei_dir in imei_dirs:
        if not os.path.isdir(imei_dir): continue
        
        imei = os.path.basename(imei_dir)
        vehicle_name = mapping.get(imei, f"Unknown_{imei}")
        
        files = glob.glob(os.path.join(imei_dir, "*.txt"))
        
        for file_path in files:
            filename = os.path.basename(file_path)
            # Filename is date: YYYY-MM-DD.txt
            date_str = filename.replace(".txt", "")
            try:
                parts = date_str.split("-")
                if len(parts) >= 2:
                    year, month = parts[0], parts[1]
                else:
                    # Fallback if filename isn't standard
                    year, month = "Unknown_Year", "Unknown_Month"
            except:
                year, month = "Unknown_Year", "Unknown_Month"
                
            # Target Path
            dest_dir = os.path.join(target_root, vehicle_name, year, month)
            os.makedirs(dest_dir, exist_ok=True)
            
            dest_path = os.path.join(dest_dir, filename)
            
            shutil.move(file_path, dest_path)
            moved_count += 1
            
        # Cleanup empty source dir
        try:
            os.rmdir(imei_dir)
        except: pass
        
    # Cleanup source root if empty
    try:
        os.rmdir(source_root) # data/output/tracker
        os.rmdir(os.path.join(base_dir, "output")) # data/output
    except: pass
    
    print(f"Migrated {moved_count} logs to '{target_root}'.")

if __name__ == "__main__":
    migrate()
