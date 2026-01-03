import json
import yaml
import os
import hashlib
import random
from datetime import datetime

# ---------- CONFIG ----------
DAILY_PLAN_PATH = "data/output/plans/SE1_KA04AB5794_JETTING_2023_daily_plan.json"
VEHICLE_CONFIG_PATH = "configs/vehicles/SE1_KA04AB5794_JETTING.yaml"
ROUTES_DIR = "configs/routes/South_East_Bangalore"
TEMPLATE_LOCALITY_MAP_PATH = "configs/routes/South_East_Bangalore/template_locality_map.yaml"
OUTPUT_DIR = "data/output/stops"
# ---------------------------


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def deterministic_rng(seed_str: str) -> random.Random:
    h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)
    return random.Random(seed_int)


def main():
    daily_plan = load_json(DAILY_PLAN_PATH)
    vehicle_cfg = load_yaml(VEHICLE_CONFIG_PATH)
    template_map = load_yaml(TEMPLATE_LOCALITY_MAP_PATH)

    vehicle_id = daily_plan["vehicle_id"]
    year = daily_plan["year"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load all route templates
    route_templates = {}
    for fname in os.listdir(ROUTES_DIR):
        if fname.endswith(".yaml") and fname.startswith("RT_"):
            path = os.path.join(ROUTES_DIR, fname)
            route_templates[fname.replace(".yaml", "")] = load_yaml(path)

    output_days = []

    for day in daily_plan["days"]:
        date_str = day["date"]
        is_operational = day["is_operational"]
        selected_template = day["selected_route_template"]

        if not is_operational:
            output_days.append({
                "date": date_str,
                "route_template": None,
                "stops": []
            })
            continue

        template = route_templates[selected_template]
        locality_pool = template_map["templates"][selected_template]["allowed_localities"]

        depot_locality = template["start_end"]["locality_id"]

        min_stops = template["daily_stops"]["min"]
        max_stops = template["daily_stops"]["max"]

        rng = deterministic_rng(f"{vehicle_id}:{date_str}:{selected_template}")
        
        # Exclude depot from work localities
        candidate_localities = [
            loc for loc in locality_pool if loc != depot_locality
        ]
        
        total_stops = rng.randint(min_stops, max_stops)

        max_possible_work_stops = len(candidate_localities)
        work_stop_count = min(total_stops - 2, max_possible_work_stops)


        

        if work_stop_count > len(candidate_localities):
            raise RuntimeError(
                f"Not enough localities for {selected_template} on {date_str}"
            )

        selected_work_localities = rng.sample(candidate_localities, work_stop_count)
        rng.shuffle(selected_work_localities)

        stops = []

        # Depot start
        stops.append({
            "stop_index": 0,
            "locality_id": depot_locality,
            "role": "DEPOT_START"
        })

        # Work stops
        for idx, loc in enumerate(selected_work_localities, start=1):
            stops.append({
                "stop_index": idx,
                "locality_id": loc,
                "role": "WORK_STOP"
            })

        # Depot end
        stops.append({
            "stop_index": len(stops),
            "locality_id": depot_locality,
            "role": "DEPOT_END"
        })

        output_days.append({
            "date": date_str,
            "route_template": selected_template,
            "stops": stops
        })

    output = {
        "vehicle_id": vehicle_id,
        "year": year,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "days": output_days
    }

    out_path = os.path.join(
        OUTPUT_DIR,
        f"{vehicle_id}_{year}_stops.json"
    )

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ DG-12 stop plan generated: {out_path}")
    print(f"Total days processed: {len(output_days)}")


if __name__ == "__main__":
    main()
