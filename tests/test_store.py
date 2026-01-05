import pytest
import os
from vts_core.store import SimulationStore

def test_db_initialization(tmp_path):
    # Use a temp directory for testing so we don't mess up real data
    store = SimulationStore(base_dir=str(tmp_path))
    
    assert (tmp_path / "simulation_metadata.db").exists()
    assert (tmp_path / "telemetry").exists()

def test_save_vehicle_and_plan(tmp_path):
    store = SimulationStore(base_dir=str(tmp_path))
    
    # 1. Register a Vehicle
    vehicle_data = {"imei": "123456789012345", "type": "Jetting", "zone_id": "SE1"}
    store.register_vehicle(vehicle_data)
    
    assert store.get_vehicle_count() == 1
    
    # 2. Create a Plan
    store.save_daily_plan(
        date="2023-01-01",
        vehicle_imei="123456789012345",
        route_id="RT_01",
        start_time="08:00:00"
    )
    
    # 3. Verify via raw SQL (just to be sure)
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    cursor = conn.execute("SELECT route_id FROM daily_plans WHERE vehicle_imei=?", ("123456789012345",))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == "RT_01"
    
def test_write_read_telemetry(tmp_path):
    store = SimulationStore(base_dir=str(tmp_path))
    
    # 1. Mock some GPS data
    logs = [
        {"timestamp": "2023-01-01 08:00:00", "lat": 12.9, "lon": 77.5, "speed": 40, "heading": 90},
        {"timestamp": "2023-01-01 08:00:20", "lat": 12.91, "lon": 77.51, "speed": 42, "heading": 92},
    ]
    
    # 2. Write to Parquet
    path = store.write_telemetry("123456789012345", "2023-01-01", logs)
    
    assert path is not None
    assert os.path.exists(path)
    
    # 3. Read back using Pandas to verify content
    import pandas as pd
    df = pd.read_parquet(path)
    
    assert len(df) == 2
    assert df.iloc[0]['speed'] == 40
    assert df.iloc[0]['vehicle_imei'] == "123456789012345"

def test_legacy_export(tmp_path):
    store = SimulationStore(base_dir=str(tmp_path))
    
    # 1. Create dummy data
    logs = [{
        "timestamp": "2023-01-01 08:00:00",
        "lat": 12.9716, 
        "lon": 77.5946,
        "speed": 10.5, 
        "heading": 180.0
    }]
    store.write_telemetry("123456789012345", "2023-01-01", logs)
    
    # 2. Run Export
    txt_path = store.export_legacy_log(
        vehicle_imei="123456789012345",
        date="2023-01-01",
        device_id="DEV001"
    )
    
    # 3. Validate Content
    with open(txt_path, "r") as f:
        content = f.read().strip()
    
    # Expected: 12.9716 -> 1258.2960, 77.5946 -> 7735.6760
    # Expected Time: 010123080000 (ddmmyyHHMMSS)
    expected_part = "A,1258.2960,N,7735.6760,E,10.50,180.00;"
    
    assert "imei:123456789012345" in content
    assert "010123080000" in content
    assert expected_part in content