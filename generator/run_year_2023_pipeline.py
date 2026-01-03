import subprocess
from datetime import date, timedelta

YEAR = 2023

def run(cmd):
    print(f"> {cmd}")
    subprocess.run(cmd, shell=True, check=False)

def main():
    start = date(YEAR, 1, 1)
    end = date(YEAR, 12, 31)

    d = start
    while d <= end:
        date_str = d.isoformat()
        print(f"\n===== Processing {date_str} =====")

        # 1. Build road path
        run(f"python generator/dg13_5_build_road_paths.py --date {date_str}")

        # 2. Generate geometry (only if road path exists)
        run(f"python generator/dg14_generate_geometry.py --date {date_str}")

        # 3. Export GeoJSON
        run(f"python generator/dg14_5_export_geojson.py --date {date_str}")

        d += timedelta(days=1)

    print("\n✅ Full year pipeline completed")

if __name__ == "__main__":
    main()
