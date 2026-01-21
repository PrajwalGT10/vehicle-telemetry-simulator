
import sys
import os
# Ensure we can import vts_core
sys.path.append(os.getcwd())

from datetime import datetime
from shapely.geometry import LineString
from vts_core.agent import VehicleAgent
from vts_core.config import VehicleConfig
from vts_core.store import SimulationStore

def run_test():
    # 1. Mock Config
    config = VehicleConfig(
        imei="123456789012345",
        name="TestVehicle",
        device_id="test_dev_01",
        zone_id="Zone1",
        type="Truck",
        depot_location=(12.0, 77.0),
        max_speed_knots=30.0
    )

    # 2. Mock Store to capture output
    class MockStore(SimulationStore):
        def __init__(self):
            self.last_records = []
        def write_telemetry(self, imei, date_str, records):
            self.last_records.extend(records)

    store = MockStore()
    agent = VehicleAgent(config, store)

    # 3. Mock Path: A line going North-East
    # (Lon, Lat) format for LineString usually, but check codebase usage.
    # codebase: start_pt = path_geometry.coords[0] -> current_location = (start_pt[1], start_pt[0])
    # So path_geometry.coords is (Lon, Lat).
    # And current_location is (Lat, Lon).
    path = LineString([(77.000, 12.000), (77.010, 12.010)]) 

    # 4. Start Cycle
    print("Starting Cycle...")
    agent.start_24h_cycle(
        date_str="2023-01-01", 
        path_geometry=path, 
        shift_start=8, 
        shift_end=17, 
        stops=[]
    )

    # 5. Fast forward until 09:00 when shift starts
    # We'll just force the time to just before 9:00 to save steps
    agent.current_time = datetime(2023, 1, 1, 8, 59, 0)
    
    # 6. Run simulation steps
    print("Simulating Steps...")
    for _ in range(50):
        agent.tick()
        if agent.state == "ROUTE_FINISHED":
            break
            
    agent.flush_memory()

    # 7. Analyze Results
    records = store.last_records
    print(f"Total Records Captured: {len(records)}")
    
    if not records:
        print("❌ No records found.")
        return

    speeds = [r['speed'] for r in records]
    headings = [r['heading'] for r in records]
    
    max_speed = max(speeds)
    max_heading = max(headings)
    
    print(f"Max Speed Recorded: {max_speed}")
    print(f"Max Heading Recorded: {max_heading}")
    
    if max_speed == 0.0 and max_heading == 0.0:
        print("❌ FAILURE: Speed and Heading are consistently ZERO.")
    elif max_speed == 0.0:
        print("❌ FAILURE: Speed is consistently ZERO.")
    elif max_heading == 0.0:
        print("❌ FAILURE: Heading is consistently ZERO.")
    else:
        print("✅ SUCCESS: Non-zero values detected.")
        print(f"Sample: Speed={speeds[-1]:.2f}, Heading={headings[-1]:.2f}")

if __name__ == "__main__":
    run_test()
