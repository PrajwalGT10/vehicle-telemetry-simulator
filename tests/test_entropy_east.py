import sys
import os
import random
sys.path.append(os.getcwd())

from vts_core.graph import RoadNetwork
from vts_core.engine import plan_mission_route, get_seeded_rng
from vts_core.config import load_vehicle_config

def test_entropy_east():
    print("🧪 Starting EAST ZONE Entropy Verification...")
    
    # 1. Load East Zone Graph
    # Assuming standard structure, but check if correct path exists
    # The user mentioned "East Zone", directory is likely "E_Zone" based on list_dir output earlier
    zone_path = r"d:\vehicle-tracking-system\data\zones\E_Zone\roads.geojson"
    if not os.path.exists(zone_path):
        print(f"❌ Graph file not found at {zone_path}")
        return

    print(f"   Loading Road Network for E_Zone...")
    network = RoadNetwork(zone_path)
    
    if not network.node_list:
        print("❌ Graph failed to load nodes.")
        return

    # 2. Define Vehicles
    v1_config_path = r"d:\vehicle-tracking-system\configs\vehicles\E1_KA04D5122_Tanker.yaml"
    v2_config_path = r"d:\vehicle-tracking-system\configs\vehicles\E2_KA04AB6020_Jetting.yaml"
    
    # Load configs to get real IMEIs? Or just simulate strings if lazily
    # Ideally load real config to verify depot connectivity
    
    try:
        c1 = load_vehicle_config(v1_config_path)
        c2 = load_vehicle_config(v2_config_path)
        print(f"   Loaded Vehicles: {c1.name} ({c1.imei}) and {c2.name} ({c2.imei})")
        
        # Override depot for valid node
        # Using config depot
        depot1 = c1.depot_location
        depot2 = c2.depot_location
        
        node1 = network._get_nearest_node((depot1[0], depot1[1]))
        node2 = network._get_nearest_node((depot2[0], depot2[1]))
        
        if not node1 or not node2:
            print("❌ Start nodes not found near depots.")
            # Fallback to random node for testing logic if depot is bad
            node1 = network.node_list[0]
            node2 = network.node_list[50]
            
    except Exception as e:
        print(f"⚠️ Config Load Error: {e}")
        return

    date_common = "2024-03-01"

    # --- Test 1: Spatial Uniqueness (Two Vehicles, Same Day) ---
    print(f"\n[1/2] Comparing {c1.name} vs {c2.name} on {date_common}...")
    
    rng1 = get_seeded_rng(c1.imei, date_common)
    mission1 = plan_mission_route(network, node1, 2, 25, rng1)
    
    rng2 = get_seeded_rng(c2.imei, date_common)
    mission2 = plan_mission_route(network, node2, 2, 25, rng2) # Using node2 if different start, or node1 if they share depot

    if mission1 and mission2:
        print(f"   Vehicle 1 Route: {mission1['distance_km']:.2f} km, {len(list(mission1['geometry'].coords))} pts")
        print(f"   Vehicle 2 Route: {mission2['distance_km']:.2f} km, {len(list(mission2['geometry'].coords))} pts")
        
        coords1 = list(mission1['geometry'].coords)
        coords2 = list(mission2['geometry'].coords)
        
        if coords1 != coords2:
             print("   ✅ SUCCESS: Routes differ between vehicles.")
        else:
             print("   ⚠️ FAILURE: Routes are identical!")
    else:
        print("   ❌ Failed to plan one or both missions.")

    # --- Test 2: Temporal Variance (Vehicle 1, Diff Day) ---
    date_diff = "2024-03-02"
    print(f"\n[2/2] Comparing {c1.name} on {date_common} vs {date_diff}...")
    
    rng3 = get_seeded_rng(c1.imei, date_diff)
    mission3 = plan_mission_route(network, node1, 2, 25, rng3)
    
    if mission1 and mission3:
        print(f"   Day 1 Route: {mission1['distance_km']:.2f} km")
        print(f"   Day 2 Route: {mission3['distance_km']:.2f} km")
        
        coords3 = list(mission3['geometry'].coords)
        if coords1 != coords3:
             print("   ✅ SUCCESS: Routes differ across dates.")
        else:
              print("   ⚠️ FAILURE: Routes are identical for different dates!")

if __name__ == "__main__":
    test_entropy_east()
