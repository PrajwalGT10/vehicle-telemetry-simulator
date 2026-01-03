import os
import json
import math
from datetime import datetime
from statistics import mean, stdev

from shapely.geometry import Point, shape
from shapely.ops import nearest_points
from rtree import index

# ---------------- CONFIG ----------------
VEHICLE_ID = "SE1_KA04AB5794_JETTING"
TRACKER_DIR = f"data/output/tracker/{VEHICLE_ID}"
GEOMETRY_DIR = f"data/output/geometry/{VEHICLE_ID}"
ROADS_PATH = "data/zones/South_East_Bangalore/roads.geojson"
OUTPUT_DIR = "data/output/qa"

EXPECTED_MIN_POINTS = 1200
EXPECTED_MAX_POINTS = 1600
MIN_INTERVAL = 20
MAX_INTERVAL = 30
MAX_JUMP_METERS = 100
MAX_ROAD_DIST = 10
# ----------------------------------------


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_tracker_line(line):
    parts = line.strip().split(",")
    ts = datetime.strptime(parts[5], "%d%m%y%H%M%S")

    lat = float(parts[7]) / 100
    lon = float(parts[9]) / 100
    speed = float(parts[11])
    heading = float(parts[12].replace(";", ""))

    return ts, lat, lon, speed, heading


def build_road_index(roads):
    idx = index.Index()
    geoms = []
    for i, f in enumerate(roads["features"]):
        g = shape(f["geometry"])
        idx.insert(i, g.bounds)
        geoms.append(g)
    return idx, geoms


def distance_to_road(pt, idx, geoms):
    nearest = list(idx.nearest(pt.bounds, 5))
    return min(pt.distance(nearest_points(pt, geoms[i])[1]) for i in nearest)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    roads = json.load(open(ROADS_PATH, encoding="utf-8"))
    road_idx, road_geoms = build_road_index(roads)

    qa_days = []
    interval_violations = 0
    snap_violations = 0
    jump_violations = 0
    dwell_errors = 0

    for fname in sorted(os.listdir(TRACKER_DIR)):
        if not fname.endswith(".txt"):
            continue

        date = fname.replace(".txt", "")
        path = os.path.join(TRACKER_DIR, fname)

        with open(path) as f:
            lines = f.readlines()

        if not lines:
            qa_days.append({"date": date, "status": "EMPTY"})
            continue

        timestamps, lats, lons, speeds = [], [], [], []

        for ln in lines:
            ts, lat, lon, speed, _ = parse_tracker_line(ln)
            timestamps.append(ts)
            lats.append(lat)
            lons.append(lon)
            speeds.append(speed)

        # ---- Temporal ----
        intervals = [
            (timestamps[i] - timestamps[i - 1]).total_seconds()
            for i in range(1, len(timestamps))
        ]

        interval_violations += sum(
            1 for x in intervals if x < MIN_INTERVAL or x > MAX_INTERVAL
        )

        # ---- Spatial ----
        for i in range(1, len(lats)):
            jump = haversine(lats[i-1], lons[i-1], lats[i], lons[i])
            if jump > MAX_JUMP_METERS:
                jump_violations += 1

            pt = Point(lons[i], lats[i])
            if distance_to_road(pt, road_idx, road_geoms) > MAX_ROAD_DIST:
                snap_violations += 1

        # ---- Dwell ----
        for i in range(1, len(speeds)):
            if speeds[i] == 0 and speeds[i-1] == 0:
                if haversine(lats[i-1], lons[i-1], lats[i], lons[i]) > 1:
                    dwell_errors += 1

        qa_days.append({
            "date": date,
            "points": len(lines),
            "avg_interval": mean(intervals),
            "interval_stddev": stdev(intervals) if len(intervals) > 1 else 0
        })

    report = {
        "vehicle_id": VEHICLE_ID,
        "total_days": len(qa_days),
        "interval_violations": interval_violations,
        "road_snap_violations": snap_violations,
        "jump_violations": jump_violations,
        "dwell_errors": dwell_errors,
        "days": qa_days
    }

    out = os.path.join(OUTPUT_DIR, f"{VEHICLE_ID}_2023_qa_report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)

    print("✅ DG-16 QA complete")
    print(f"Report written to: {out}")


if __name__ == "__main__":
    main()
