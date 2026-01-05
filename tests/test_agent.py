import pytest
from shapely.geometry import LineString
from vts_core.agent import VehicleAgent
from vts_core.config import VehicleConfig
from vts_core.store import SimulationStore
from datetime import datetime

@pytest.fixture
def mock_store(tmp_path):
    return SimulationStore(base_dir=str(tmp_path))

@pytest.fixture
def mock_vehicle():
    return VehicleConfig(
        name="TestCar",
        imei="123456789012345",
        device_id="DEV01",
        type="Jetting",
        zone_id="Z1",
        max_speed_knots=60.0 # ~30m/s
    )

def test_agent_lifecycle(mock_store, mock_vehicle):
    agent = VehicleAgent(mock_vehicle, mock_store)
    
    # 1. Define a route (Straight line 0,0 to 0,0.1 approx 11km North)
    route = LineString([(0, 0), (0, 0.1)])
    
    # 2. Start Day
    agent.start_day("2023-01-01", route, "08:00:00")
    
    assert agent.is_active is True
    assert agent.current_location == (0.0, 0.0)
    
    # 3. Tick (Move 20 seconds)
    # Speed 30m/s * 20s = 600m
    agent.tick(duration_seconds=20)
    
    # Should have moved North (Lat > 0, Lon = 0)
    lat, lon = agent.current_location
    assert lat > 0.0
    assert lon == 0.0
    assert len(agent.telemetry_buffer) == 1
    
    # 4. Flush to Disk
    agent.flush_memory()
    assert len(agent.telemetry_buffer) == 0
    
    # Verify file existence via Store check
    # We check if we can export the log (proof it exists)
    outfile = mock_store.export_legacy_log(
        vehicle_imei="123456789012345", 
        date="2023-01-01", 
        device_id="DEV01"
    )
    assert "2023-01-01" in outfile