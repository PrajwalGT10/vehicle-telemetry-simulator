import argparse
import os
import json
from vts_core.engine import run_simulation_day, generate_parked_day

def is_holiday(date_str, calendar_path):
    """Checks if the date is in the holiday list."""
    if not calendar_path or not os.path.exists(calendar_path):
        return False
        
    with open(calendar_path, 'r') as f:
        data = json.load(f)
        
    # Handle two common formats:
    # 1. List of strings: ["2023-01-26", "2023-08-15"]
    # 2. List of objs: [{"date": "2023-01-26", "name": "Republic Day"}]
    
    if isinstance(data, list):
        if not data: return False
        
        # Check first item type
        if isinstance(data[0], str):
            return date_str in data
        elif isinstance(data[0], dict):
            # Extract dates from dict
            holidays = [item.get("date") for item in data]
            return date_str in holidays
            
    return False

def main():
    parser = argparse.ArgumentParser(description="Vehicle Telemetry Simulator (VTS) Production CLI")
    
    parser.add_argument("--vehicle", required=True, help="Path to vehicle YAML config")
    parser.add_argument("--roads", required=True, help="Path to roads.geojson")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD to simulate")
    parser.add_argument("--calendar", help="Path to holiday JSON file", default=None)
    
    args = parser.parse_args()
    
    # 1. Check Files
    if not os.path.exists(args.vehicle):
        print(f"❌ Vehicle config not found: {args.vehicle}")
        return
        
    # 2. Check Calendar
    on_holiday = False
    if args.calendar:
        if is_holiday(args.date, args.calendar):
            print(f"📅 Date {args.date} is a Holiday! Vehicle will be parked.")
            on_holiday = True
        else:
            print(f"📅 Date {args.date} is a Work Day.")

    # 3. Dispatch
    if on_holiday:
        # We don't need roads for parking
        generate_parked_day(args.vehicle, args.date)
    else:
        # We need roads for driving
        if not os.path.exists(args.roads):
            print(f"❌ Roads file not found: {args.roads}")
            return
            
        run_simulation_day(
            vehicle_config_path=args.vehicle,
            zone_roads_path=args.roads,
            date=args.date
        )

if __name__ == "__main__":
    main()