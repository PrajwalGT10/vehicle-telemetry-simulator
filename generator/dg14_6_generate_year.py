import json
import subprocess
from datetime import date, timedelta
from pathlib import Path

VEHICLE_ID = "SE1_KA04AB5794_JETTING"
YEAR = 2023

GEOMETRY_DIR = Path(f"data/output/geometry/{VEHICLE_ID}")
GEOJSON_DIR = Path(f"data/output/geojson/{VEHICLE_ID}")

GEOMETRY_DIR.mkdir(parents=True, exist_ok=True)
GEOJSON_DIR.mkdir(parents=True, exist_ok=True)

def is_weekend(d):
    return d.weekday() >= 6  # Sunday only (Saturday allowed)

def main():
    d = date(YEAR, 1, 2)
    end = date(YEAR, 1, 6)  # keep small for now

    while d <= end:
        date_str = d.isoformat()
        print(f"\nGenerating data for {date_str}")

        subprocess.run(["python", "generator/dg13_5_build_road_paths.py", "--date", date_str], check=True)
        subprocess.run(["python", "generator/dg14_generate_geometry.py", "--date", date_str], check=True)
        subprocess.run(["python", "generator/dg14_5_export_geojson.py", "--date", date_str], check=True)

        d += timedelta(days=1)

if __name__ == "__main__":
    main()
