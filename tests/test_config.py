import pytest
import yaml
from pathlib import Path
from pydantic import ValidationError
from vts_core.config import load_vehicle_config

def test_valid_vehicle_config(tmp_path):
    """Create a temporary valid YAML file and try to load it."""
    
    # 1. Create a fake YAML file
    config_content = {
        "vehicle": {
            "name": "Test_Vehicle",
            "imei": "123456789012345",  # 15 digits
            "device_id": "DEV001",
            "type": "Jetting_Machine"
        },
        "zone": {
            "name": "Test_Zone_A"
        }
    }
    
    f = tmp_path / "test_vehicle.yaml"
    f.write_text(yaml.dump(config_content))
    
    # 2. Load it
    config = load_vehicle_config(str(f))
    
    # 3. Verify
    assert config.imei == "123456789012345"
    assert config.zone_id == "Test_Zone_A"
    assert config.vehicle_type == "Jetting_Machine"

def test_invalid_imei(tmp_path):
    """Ensure it fails if IMEI is short."""
    config_content = {
        "vehicle": {
            "name": "Bad_Vehicle",
            "imei": "123",  # Too short!
            "device_id": "DEV001",
            "type": "Truck"
        },
        "zone": "ZoneA"
    }
    
    f = tmp_path / "bad_vehicle.yaml"
    f.write_text(yaml.dump(config_content))
    
    # We expect a ValidationError to be raised
    with pytest.raises(ValidationError):
        load_vehicle_config(str(f))