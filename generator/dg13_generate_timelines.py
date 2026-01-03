import json
import yaml
import os
import hashlib
import random
from datetime import datetime, timedelta
import pytz

# ---------- CONFIG ----------
STOPS_PATH = "data/output/stops/SE1_KA04AB5794_JETTING_2023_stops.json"
VEHICLE_CONFIG_PATH = "configs/vehicles/SE1_KA04AB5794_JETTING.yaml"
OUTPUT_DIR = "data/output/timelines"
# ---------------------------


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def rng_for(seed_str):
    h = hashlib.sha256(seed_str.encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def main():
    stops_data = load_json(STOPS_PATH)
    vehicle_cfg = load_yaml(VEHICLE_CONFIG_PATH)

    tz = pytz.timezone(vehicle_cfg["shift"]["timezone"])
    shift_start_str = vehicle_cfg["shift"]["start_time"]
    shift_end_str = vehicle_cfg["shift"]["end_time"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_days = []

    for day in stops_data["days"]:
        date_str = day["date"]
        stops = day["stops"]

        if not stops:
            output_days.append({
                "date": date_str,
                "stops": []
            })
            continue

        date_obj = datetime.fromisoformat(date_str)
        shift_start = tz.localize(
            datetime.combine(date_obj, datetime.strptime(shift_start_str, "%H:%M").time())
        )
        shift_end = tz.localize(
            datetime.combine(date_obj, datetime.strptime(shift_end_str, "%H:%M").time())
        )

        current_time = shift_start
        timed_stops = []

        for stop in stops:
            idx = stop["stop_index"]
            role = stop["role"]

            rng = rng_for(f"{stops_data['vehicle_id']}:{date_str}:{idx}")

            arrival = current_time

            if role == "DEPOT_START":
                dwell = 0
            elif role == "WORK_STOP":
                dwell = rng.randint(20, 30)
            else:  # DEPOT_END
                dwell = rng.randint(5, 10)

            departure = arrival + timedelta(minutes=dwell)

            timed_stops.append({
                **stop,
                "arrival_time": arrival.isoformat(),
                "departure_time": departure.isoformat(),
                "dwell_minutes": dwell
            })

            if role != "DEPOT_END":
                travel_minutes = rng.randint(10, 25)
                current_time = departure + timedelta(minutes=travel_minutes)
            else:
                current_time = departure

        output_days.append({
            "date": date_str,
            "shift_start": shift_start.isoformat(),
            "shift_end": shift_end.isoformat(),
            "stops": timed_stops
        })

    output = {
        "vehicle_id": stops_data["vehicle_id"],
        "year": stops_data["year"],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "days": output_days
    }

    out_path = os.path.join(
        OUTPUT_DIR,
        f"{stops_data['vehicle_id']}_{stops_data['year']}_timeline.json"
    )

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ DG-13 timeline generated: {out_path}")


if __name__ == "__main__":
    main()
