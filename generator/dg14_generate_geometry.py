import json
import random
import argparse
import os
from datetime import datetime, timedelta
from shapely.geometry import LineString

BASE_INTERVAL = 20
JITTER = 5
VEHICLE_ID = "SE1_KA04AB5794_JETTING"


def normalize_coords(raw):
    """
    Ensure coordinates are [[lon, lat], ...]
    Handles flattened or mixed lists safely.
    """
    cleaned = []

    if not raw or not isinstance(raw, list):
        return cleaned

    # Case 1: already [[lon, lat], ...]
    if isinstance(raw[0], (list, tuple)) and len(raw[0]) == 2:
        for pt in raw:
            if isinstance(pt, (list, tuple)) and len(pt) == 2:
                cleaned.append([float(pt[0]), float(pt[1])])
        return cleaned

    # Case 2: flattened [lon, lat, lon, lat, ...]
    if all(isinstance(x, (int, float)) for x in raw) and len(raw) % 2 == 0:
        for i in range(0, len(raw), 2):
            cleaned.append([float(raw[i]), float(raw[i + 1])])
        return cleaned

    # Mixed garbage → return empty
    return cleaned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    date_str = args.date

    road_path_file = f"data/output/road_paths/{VEHICLE_ID}_{date_str}_road_path.geojson"
    output_dir = f"data/output/geometry/{VEHICLE_ID}"
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(road_path_file):
        print(f"⚠️  Missing road path for {date_str}, skipping.")
        return

    with open(road_path_file, encoding="utf-8") as f:
        geojson = json.load(f)

    raw_coords = geojson["features"][0]["geometry"]["coordinates"]
    coords = normalize_coords(raw_coords)

    if len(coords) < 2:
        print(f"⚠️  Skipping geometry for {date_str}: invalid route ({len(coords)} points)")
        return

    line = LineString(coords)

    start_time = datetime.fromisoformat(f"{date_str}T09:20:00")
    fraction = 0.0
    points = []

    while fraction <= 1.0:
        pt = line.interpolate(fraction, normalized=True)
        points.append({
            "timestamp": start_time.isoformat(),
            "lat": round(pt.y, 6),
            "lon": round(pt.x, 6)
        })

        step = BASE_INTERVAL + random.randint(-JITTER, JITTER)
        start_time += timedelta(seconds=step)
        fraction += 0.002  # ≈500 points

    out_file = f"{output_dir}/{date_str}_geometry.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "vehicle_id": VEHICLE_ID,
            "date": date_str,
            "points": points
        }, f, indent=2)

    print(f"📄 Geometry written: {out_file}")
    print("Points:", len(points))


if __name__ == "__main__":
    main()
