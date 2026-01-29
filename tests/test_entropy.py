import sys
import os
import random
# Add project root to path
sys.path.append(os.getcwd())

from vts_core.graph import RoadNetwork
from vts_core.engine import plan_mission_route, get_seeded_rng

def test_entropy():
    print("🧪 Starting Entropy Verification...")
    
    # 1. Load Real Graph (Subset or Full)
    zone_path = r"d:\vehicle-tracking-system\data\zones\C_Zone\roads.geojson"
    if not os.path.exists(zone_path):
        print(f"❌ Graph file not found at {zone_path}")
        return

    print("   Loading Road Network...")
    network = RoadNetwork(zone_path)
    
    # Pick a random node as Home
    home_node = network.node_list[0]
    print(f"   Home Node: {home_node}")

    # --- Test 1: Determinism (Same Vehicle, Same Date) ---
    print("\n[1/3] Testing Determinism...")
    v1 = "VEHICLE_A"
    d1 = "2024-01-01"
    
    rng1 = get_seeded_rng(v1, d1)
    mission1 = plan_mission_route(network, home_node, 2, 25, rng1)
    
    rng2 = get_seeded_rng(v1, d1) # Re-seed
    mission2 = plan_mission_route(network, home_node, 2, 25, rng2)
    
    # Check Geometry Equality
    # Compare coordinate sequences
    coords1 = list(mission1['geometry'].coords)
    coords2 = list(mission2['geometry'].coords)
    
    if coords1 == coords2:
        print("   ✅ SUCCESS: Identical inputs produced identical routes.")
    else:
        print("   ❌ FAILURE: Routes differed for strictly identical inputs!")
        print(f"      Route 1: {len(coords1)} points")
        print(f"      Route 2: {len(coords2)} points")

    # --- Test 2: Temporal Variance (Same Vehicle, Diff Date) ---
    print("\n[2/3] Testing Temporal Variance...")
    d2 = "2024-01-02"
    rng3 = get_seeded_rng(v1, d2)
    mission3 = plan_mission_route(network, home_node, 2, 25, rng3)
    
    coords3 = list(mission3['geometry'].coords)
    if coords1 != coords3:
         print("   ✅ SUCCESS: Different dates produced different routes.")
    else:
         print("   ⚠️ WARNING: Routes identical for different dates (Low Probability Collision or Broken Entropy).")

    # --- Test 3: Spatial Uniqueness (Diff Vehicle, Same Date) ---
    print("\n[3/3] Testing Spatial Uniqueness...")
    v2 = "VEHICLE_B"
    rng4 = get_seeded_rng(v2, d1)
    mission4 = plan_mission_route(network, home_node, 2, 25, rng4)
    
    coords4 = list(mission4['geometry'].coords)
    if coords1 != coords4:
         print("   ✅ SUCCESS: Different vehicles produced different routes.")
    else:
         print("   ⚠️ WARNING: Routes identical for different vehicles (Unique Seeding Check Failed).")

if __name__ == "__main__":
    test_entropy()
