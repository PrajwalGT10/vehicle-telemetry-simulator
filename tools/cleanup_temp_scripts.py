import os
import glob

def cleanup():
    files_to_remove = [
        "tools/fetch_zones_overpass.py",
        "tools/fetch_failed_zones.py",
        "tools/fetch_zones_light.py",
        "tools/fetch_localities.py",
        "tools/fetch_localities_light.py",
        "tools/fetch_localities_retry.py",
        "tools/fetch_localities_final.py",
        "tools/fetch_locality_polygons.py",
        "tools/fetch_locality_polygons_robust.py",
        "tools/fetch_locality_polygons_micro.py",
        "tools/check_zone_stats.py",
        "tools/check_geometry_type.py",
        # "tools/generate_zone_routes.py", # Keeping this as it might be useful for regenerating routes
    ]
    
    removed_count = 0
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Removed: {file_path}")
                removed_count += 1
            except Exception as e:
                print(f"Error removing {file_path}: {e}")
        else:
            print(f"Skipped (not found): {file_path}")
            
    print(f"Cleanup complete. Removed {removed_count} files.")

if __name__ == "__main__":
    cleanup()
