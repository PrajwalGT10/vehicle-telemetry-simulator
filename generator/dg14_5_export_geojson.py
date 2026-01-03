import json
import argparse
from pathlib import Path

VEHICLE_ID = "SE1_KA04AB5794_JETTING"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    date_str = args.date

    input_file = Path(f"data/output/geometry/{VEHICLE_ID}/{date_str}_geometry.json")
    output_dir = Path(f"data/output/geojson/{VEHICLE_ID}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    coordinates = [[p["lon"], p["lat"]] for p in data["points"]]

    geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "vehicle_id": VEHICLE_ID,
                "date": date_str,
                "total_points": len(coordinates)
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        }]
    }

    out_file = output_dir / f"{date_str}_route.geojson"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"📄 GeoJSON written: {out_file}")
    print("Points:", len(coordinates))


if __name__ == "__main__":
    main()
