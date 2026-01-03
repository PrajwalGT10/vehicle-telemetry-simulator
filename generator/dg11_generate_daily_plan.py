import json
import os
import hashlib
import random
from datetime import datetime

# ---------- CONFIG ----------
CALENDAR_PATH = "data/output/calendars/SE1_KA04AB5794_JETTING_2023_operational_calendar.json"
OUTPUT_DIR = "data/output/plans"
# ---------------------------


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def deterministic_rng(seed_str: str) -> random.Random:
    """
    Create a deterministic RNG from a string seed.
    """
    h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)
    return random.Random(seed_int)


def main():
    calendar = load_json(CALENDAR_PATH)

    vehicle_id = calendar["vehicle_id"]
    year = calendar["year"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    daily_plan = []

    for day in calendar["days"]:
        date_str = day["date"]
        day_type = day["day_type"]
        is_operational = day["is_operational"]
        eligible = day["eligible_route_templates"]

        if not is_operational:
            selected_template = None
        else:
            if not eligible:
                raise RuntimeError(
                    f"Operational day {date_str} has no eligible templates"
                )

            rng = deterministic_rng(f"{vehicle_id}:{date_str}")
            selected_template = rng.choice(eligible)

        daily_plan.append({
            "date": date_str,
            "day_type": day_type,
            "is_operational": is_operational,
            "selected_route_template": selected_template
        })

    output = {
        "vehicle_id": vehicle_id,
        "year": year,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "days": daily_plan
    }

    out_path = os.path.join(
        OUTPUT_DIR,
        f"{vehicle_id}_{year}_daily_plan.json"
    )

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ DG-11 daily plan generated: {out_path}")
    print(f"Total days planned: {len(daily_plan)}")


if __name__ == "__main__":
    main()
