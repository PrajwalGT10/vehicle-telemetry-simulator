import json
import yaml
import os
import math
from datetime import datetime

# ---------- CONFIG ----------
GEOMETRY_DIR = "data/output/geometry/SE1_KA04AB5794_JETTING"
VEHICLE_CONFIG_PATH = "configs/vehicles/SE1_KA04AB5794_JETTING.yaml"
OUTPUT_DIR = "data/output/tracker/SE1_KA04AB5794_JETTING"
# ---------------------------


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def dd_to_ddmm(value):
    deg = int(abs(value))
    minutes = (abs(value) - deg) * 60
    return f"{deg*100 + minutes:.4f}"


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing(lat1, lon1, lat2, lon2):
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = (
        math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) -
        math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.cos(math.radians(lon2 - lon1))
    )
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def main():
    vehicle = load_yaml(VEHICLE_CONFIG_PATH)
    imei = vehicle["vehicle"]["imei"]
    device_id = vehicle["vehicle"]["device_id"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for fname in os.listdir(GEOMETRY_DIR):
        if not fname.endswith("_geometry.json"):
            continue

        date = fname.split("_")[0]
        geometry = json.load(open(os.path.join(GEOMETRY_DIR, fname)))

        points = geometry["points"]
        out_lines = []

        prev = None
        last_heading = 0.0

        for p in points:
            ts = datetime.fromisoformat(p["timestamp"])
            lat, lon = p["lat"], p["lon"]

            if prev:
                dt = (ts - prev["ts"]).total_seconds()
                dist = haversine(prev["lat"], prev["lon"], lat, lon)
                speed_knots = min((dist / dt) * 1.94384 if dt > 0 else 0, 30)
                heading = bearing(prev["lat"], prev["lon"], lat, lon)
                last_heading = heading
            else:
                speed_knots = 0.0
                heading = last_heading

            ts_str = ts.strftime("%d%m%y%H%M%S")

            line = (
                f"imei:{imei},tracker,{device_id},,F,"
                f"{ts_str},A,"
                f"{dd_to_ddmm(lat)},N,"
                f"{dd_to_ddmm(lon)},E,"
                f"{speed_knots:.2f},{heading:.2f};"
            )

            out_lines.append(line)

            prev = {"lat": lat, "lon": lon, "ts": ts}

        out_path = os.path.join(OUTPUT_DIR, f"{date}.txt")
        with open(out_path, "w") as f:
            f.write("\n".join(out_lines))

        print(f"Generated tracker file for {date}")

    print("✅ DG-15 tracker log generation complete")


if __name__ == "__main__":
    main()
