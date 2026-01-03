import json
import yaml
from datetime import date, datetime, timedelta
from collections import defaultdict
import random
import os

# ---------- CONFIG ----------
VEHICLE_CONFIG_PATH = "configs/vehicles/SE1_KA04AB5794_JETTING.yaml"
HOLIDAYS_PATH = "configs/calendars/india_2023_holidays.json"
OUTPUT_DIR = "data/output/calendars"
YEAR = 2023
# ----------------------------


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def daterange(start, end):
    curr = start
    while curr <= end:
        yield curr
        curr += timedelta(days=1)


def main():
    vehicle_cfg = load_yaml(VEHICLE_CONFIG_PATH)
    holidays_cfg = load_json(HOLIDAYS_PATH)

    vehicle_id = vehicle_cfg["vehicle"]["name"]
    zone = vehicle_cfg["zone"]["name"]
    timezone = vehicle_cfg["shift"]["timezone"]
    allow_saturdays = vehicle_cfg["calendar"]["allow_saturdays"]
    saturday_quota = vehicle_cfg["calendar"]["saturday_probability_per_month"]
    seed = vehicle_cfg["generation"]["random_seed"]

    holiday_map = {
        h["date"]: h["name"]
        for h in holidays_cfg["holidays"]
    }

    # Prepare output
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    rng = random.Random(seed)
    calendar_days = []

    start_date = date(YEAR, 1, 1)
    end_date = date(YEAR, 12, 31)

    # Track Saturday usage per month
    saturday_usage = defaultdict(int)

    for d in daterange(start_date, end_date):
        iso_date = d.isoformat()
        weekday_idx = d.weekday()  # Monday=0 ... Sunday=6
        weekday_name = d.strftime("%A").upper()
        month_key = (d.year, d.month)

        day_type = None
        is_operational = False
        eligible_templates = []
        notes = None

        # ---- Rule precedence ----
        if iso_date in holiday_map:
            day_type = "HOLIDAY_OFF"
            notes = holiday_map[iso_date]

        elif weekday_idx == 6:
            day_type = "SUNDAY_OFF"

        elif weekday_idx == 5:
            if allow_saturdays and saturday_usage[month_key] < saturday_quota:
                day_type = "SATURDAY_WORKING"
                is_operational = True
                saturday_usage[month_key] += 1
                eligible_templates = ["RT_SE_01", "RT_SE_02"]
            else:
                day_type = "SUNDAY_OFF"

        else:
            day_type = "WORKDAY"
            is_operational = True
            eligible_templates = ["RT_SE_01", "RT_SE_02", "RT_SE_03"]

        calendar_days.append({
            "date": iso_date,
            "weekday": weekday_name,
            "day_type": day_type,
            "is_operational": is_operational,
            "eligible_route_templates": eligible_templates,
            "notes": notes
        })

    output = {
        "vehicle_id": vehicle_id,
        "zone": zone,
        "year": YEAR,
        "timezone": timezone,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "days": calendar_days
    }

    out_path = os.path.join(
        OUTPUT_DIR,
        f"{vehicle_id}_{YEAR}_operational_calendar.json"
    )

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ DG-10 calendar generated: {out_path}")
    print(f"Total days: {len(calendar_days)}")


if __name__ == "__main__":
    main()
