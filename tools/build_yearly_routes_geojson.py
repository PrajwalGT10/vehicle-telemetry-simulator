import os
import json

# -------- CONFIG --------
VEHICLE_ID = "SE1_KA04AB5794_JETTING"
YEAR = "2023"

GEOMETRY_DIR = f"data/output/geometry/{VEHICLE_ID}"
OUTPUT_DIR = "data/output/geojson"
OUTPUT_FILE = f"{OUTPUT_DIR}/{VEHICLE_ID}_{YEAR}_routes.geojson"
# ------------------------


def main():
    if not os.path.exists(GEOMETRY_DIR):
        raise FileNotFoundError(f"Geometry folder not found: {GEOMETRY_DIR}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    features = []

    for fname in sorted(os.listdir(GEOMETRY_DIR)):
        if not fname.endswith("_geometry.json"):
            continue

        date = fname.replace("_geometry.json", "")

        with open(os.path.join(GEOMETRY_DIR, fname), "r", encoding="utf-8") as f:
            daily = json.load(f)

        points = daily.get("points", [])
        if len(points) < 2:
            continue

        coordinates = [[p["lon"], p["lat"]] for p in points]

        features.append({
            "type": "Feature",
            "properties": {
                "vehicle_id": VEHICLE_ID,
                "date": date
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(geojson, f)

    print("✅ Yearly routes GeoJSON created")
    print(f"📄 File: {OUTPUT_FILE}")
    print(f"🛣️ Days included: {len(features)}")


if __name__ == "__main__":
    main()
