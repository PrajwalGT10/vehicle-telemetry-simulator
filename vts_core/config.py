import yaml
from dataclasses import dataclass

@dataclass
class VehicleConfig:
    imei: str
    name: str
    device_id: str
    zone_id: str
    type: str
    depot_location: tuple # (Lat, Lon)
    max_speed_knots: float
    sampling_interval_seconds: int = 25 # Default if missing
    enabled: bool = True
    simulation_window: dict = None

def load_vehicle_config(yaml_path: str) -> VehicleConfig:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # 1. Handle "Nested" Structure (Official VTS format)
    if "vehicle" in data:
        v_data = data["vehicle"]
        # Zone might be defined in a 'zone' block or just a 'zone_id' key
        z_data = data.get("zone", {})
        zone_val = data.get("zone_id", z_data.get("name", "Unknown_Zone"))
        
        # Shift data for sampling
        s_data = data.get("shift", {})
        
        return VehicleConfig(
            imei=str(v_data["imei"]),
            name=v_data["name"],
            device_id=v_data.get("device_id", "unknown"),
            zone_id=zone_val,
            type=v_data.get("vehicle_type", "Vehicle"),
            depot_location=(
                v_data.get("depot_lat", 12.958319), 
                v_data.get("depot_lon", 77.612422)
            ),
            max_speed_knots=float(v_data.get("max_speed_knots", 25.0)),
            sampling_interval_seconds=int(s_data.get("sampling_interval_seconds", 25)),
            enabled=bool(v_data.get("enabled", True)),
            simulation_window=data.get("simulation_window", {})
        )
        
    # 2. Handle "Flat" Structure (Legacy format)
    else:
        return VehicleConfig(
            imei=str(data["imei"]),
            name=data["name"],
            device_id=data.get("device_id", "unknown"),
            zone_id=data.get("zone_id", "Unknown_Zone"),
            type=data.get("type", "Vehicle"),
            depot_location=(
                data.get("depot_lat", 12.958319), 
                data.get("depot_lon", 77.612422)
            ),
            max_speed_knots=float(data.get("max_speed_knots", 25.0)),
            sampling_interval_seconds=25 # Legacy default
        )