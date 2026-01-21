import os
import glob
import shutil

DATA_DIR = r"d:\vehicle-tracking-system\data"
DIRS_TO_REMOVE = ["telemetry", "tracker", "exported_geojson", "output"]
FILES_TO_REMOVE_PATTERNS = ["*.txt", "*.geojson", "*.db", "*.log"]
# Note: "zones" and "external" are preserved as they likely contain input data.

def cleanup():
    print(f"Cleaning up {DATA_DIR}...")
    
    # Remove specific directories
    for d in DIRS_TO_REMOVE:
        path = os.path.join(DATA_DIR, d)
        if os.path.exists(path):
            print(f"Removing directory: {path}")
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"Failed to remove {path}: {e}")
        else:
            print(f"Directory not found (already clean): {path}")

    # Remove specific file patterns in root of data
    for pattern in FILES_TO_REMOVE_PATTERNS:
        for f in glob.glob(os.path.join(DATA_DIR, pattern)):
            print(f"Removing file: {f}")
            try:
                os.remove(f)
            except Exception as e:
                print(f"Failed to remove {f}: {e}")

if __name__ == "__main__":
    cleanup()
