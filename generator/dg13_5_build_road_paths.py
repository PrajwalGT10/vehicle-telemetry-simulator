import json
import argparse
import random
from pathlib import Path
import networkx as nx
from shapely.geometry import Point, shape, LineString

# ---------------- CONFIG ----------------

VEHICLE_ID = "SE1_KA04AB5794_JETTING"

ROADS_PATH = "data/zones/South_East_Bangalore/roads.geojson"
LOCALITIES_PATH = "data/zones/South_East_Bangalore/localities.geojson"
STOPS_PATH = "data/output/stops/SE1_KA04AB5794_JETTING_2023_stops.json"

OUTPUT_DIR = Path("data/output/road_paths")

DEPOT_LAT = 12.958308
DEPOT_LON = 77.612350

RANDOM_WEIGHT_JITTER = 0.15
LOOP_RADIUS_METERS = 600
LOOP_NODES_MIN = 2
LOOP_NODES_MAX = 4

# ----------------------------------------


def load_road_graph():
    with open(ROADS_PATH, encoding="utf-8") as f:
        roads = json.load(f)

    G = nx.Graph()

    for feature in roads["features"]:
        geom = shape(feature["geometry"])
        if not isinstance(geom, LineString):
            continue

        coords = list(geom.coords)
        for i in range(len(coords) - 1):
            a = coords[i]
            b = coords[i + 1]
            dist = Point(a).distance(Point(b))

            jitter = random.uniform(
                1 - RANDOM_WEIGHT_JITTER,
                1 + RANDOM_WEIGHT_JITTER
            )

            G.add_edge(a, b, weight=dist * jitter)

    return G


def snap_to_graph(graph, lon, lat):
    p = Point(lon, lat)
    return min(graph.nodes, key=lambda n: Point(n).distance(p))


def load_locality_nodes(graph):
    with open(LOCALITIES_PATH, encoding="utf-8") as f:
        geo = json.load(f)

    nodes = list(graph.nodes)
    mapping = {}

    for ftr in geo["features"]:
        loc_id = ftr["properties"]["locality_id"]
        c = shape(ftr["geometry"]).centroid
        centroid = (c.x, c.y)

        nearest = min(nodes, key=lambda n: Point(n).distance(Point(centroid)))
        mapping[loc_id] = nearest

    return mapping


def load_stops_for_date(date_str):
    with open(STOPS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    for day in data["days"]:
        if day["date"] == date_str:
            return day["stops"]

    return []


def build_path(graph, a, b):
    try:
        return nx.shortest_path(graph, a, b, weight="weight")
    except nx.NetworkXNoPath:
        return []


def force_random_loop(graph, depot_node):
    """Pure random patrol loop using nearby road nodes"""
    depot_point = Point(depot_node)

    nearby = [
        n for n in graph.nodes
        if Point(n).distance(depot_point) * 111_000 <= LOOP_RADIUS_METERS
        and n != depot_node
    ]

    if len(nearby) < LOOP_NODES_MIN:
        raise RuntimeError("Not enough nearby nodes to form loop")

    loop_nodes = random.sample(
        nearby,
        random.randint(LOOP_NODES_MIN, min(LOOP_NODES_MAX, len(nearby)))
    )

    route = []
    hops = [depot_node] + loop_nodes + [depot_node]

    for i in range(len(hops) - 1):
        seg = build_path(graph, hops[i], hops[i + 1])
        if not seg:
            continue
        if route:
            seg = seg[1:]
        route.extend(seg)

    return route


def build_day_route(graph, date_str):
    depot_node = snap_to_graph(graph, DEPOT_LON, DEPOT_LAT)
    locality_nodes = load_locality_nodes(graph)
    stops = load_stops_for_date(date_str)

    waypoints = [depot_node]

    for stop in stops:
        loc_id = stop["locality_id"]
        if loc_id in locality_nodes:
            waypoints.append(locality_nodes[loc_id])

    waypoints.append(depot_node)

    route = []

    for i in range(len(waypoints) - 1):
        seg = build_path(graph, waypoints[i], waypoints[i + 1])
        if not seg:
            continue
        if route:
            seg = seg[1:]
        route.extend(seg)

    # 🔥 COLLAPSE DETECTION
    if len(set(route)) < 2:
        print("⚠️  Collapsed route detected — forcing patrol loop")
        route = force_random_loop(graph, depot_node)

    return route


def write_geojson(coords, date_str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"type": "start"},
                "geometry": {
                    "type": "Point",
                    "coordinates": [DEPOT_LON, DEPOT_LAT]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "type": "route",
                    "vehicle_id": VEHICLE_ID,
                    "date": date_str
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                }
            },
            {
                "type": "Feature",
                "properties": {"type": "end"},
                "geometry": {
                    "type": "Point",
                    "coordinates": [DEPOT_LON, DEPOT_LAT]
                }
            }
        ]
    }

    out = OUTPUT_DIR / f"{VEHICLE_ID}_{date_str}_road_path.geojson"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"✅ Road path written: {out}")
    print(f"Segments: {len(coords)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    print(f"🚧 Building road path for {VEHICLE_ID} on {args.date}")

    graph = load_road_graph()
    coords = build_day_route(graph, args.date)

    if len(coords) < 2:
        raise RuntimeError("Invariant violation: route still collapsed")

    write_geojson(coords, args.date)


if __name__ == "__main__":
    main()
