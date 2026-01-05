import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, ValidationError, AliasChoices

# --- 1. Define the Shapes (Schemas) ---

class VehicleConfig(BaseModel):
    """
    Validates content of configs/vehicles/*.yaml
    """
    name: str
    imei: str = Field(..., min_length=15, max_length=15, description="Must be exactly 15 digits")
    device_id: str
    
    # Handle 'vehicle_type' or 'type' from YAML
    vehicle_type: str = Field(validation_alias=AliasChoices('vehicle_type', 'type'))
    
    # We expect this to be populated by the loader
    zone_id: str
    
    max_speed_knots: float = 40.0 # Default

class RouteConfig(BaseModel):
    """
    Validates content of configs/routes/*.yaml
    """
    template_id: str
    zone: str
    vehicle_type: str = Field(validation_alias=AliasChoices('vehicle_type', 'type'))
    description: Optional[str] = None

# --- 2. Define the Loaders ---

def load_vehicle_config(yaml_path: str) -> VehicleConfig:
    """Reads a YAML file, flattens the structure, and validates."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {yaml_path}")

    with open(path, "r") as f:
        raw_data = yaml.safe_load(f)
    
    # --- LOGIC FIX: Handle Nested Structure ---
    # The YAML has 'vehicle' and 'zone' as top-level keys.
    # We combine them into a single dictionary for Pydantic.
    
    flat_data = raw_data.get("vehicle", {}).copy()
    zone_block = raw_data.get("zone", {})
    
    # Extract zone name
    if isinstance(zone_block, dict):
        flat_data["zone_id"] = zone_block.get("name")
    else:
        flat_data["zone_id"] = str(zone_block)

    try:
        return VehicleConfig(**flat_data)
    except ValidationError as e:
        print(f"❌ Configuration Error in {path.name}:")
        raise e

def load_route_config(yaml_path: str) -> RouteConfig:
    """Reads a YAML file and returns a validated RouteConfig object."""
    path = Path(yaml_path)
    with open(path, "r") as f:
        data = yaml.safe_load(f)
        
    return RouteConfig(**data)