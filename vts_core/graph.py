import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString
import math
import os
import random

class RoadNetwork:
    def __init__(self, geojson_path: str, localities_path: str = None):
        print(f"   Loading Road Graph from {geojson_path}...")
        self.gdf = gpd.read_file(geojson_path)
        self.localities = []

        if localities_path and os.path.exists(localities_path):
             try:
                 loc_gdf = gpd.read_file(localities_path)
                 print(f"   Loading {len(loc_gdf)} localities from {localities_path}...")
                 # Store (Lon, Lat) tuples
                 for _, row in loc_gdf.iterrows():
                     geom = row.geometry
                     if geom.geom_type == 'Point':
                         self.localities.append((geom.x, geom.y))
                     elif geom.geom_type in ['Polygon', 'MultiPolygon']:
                         c = geom.centroid
                         self.localities.append((c.x, c.y))
             except Exception as e:
                 print(f"⚠️ Error loading localities: {e}")
        
        # 1. Build Directed Graph (Respects One-Ways if data has them, currently forcing 2-way for connectivity)
        raw_graph = nx.DiGraph()
        
        for _, row in self.gdf.iterrows():
            geom = row.geometry
            if geom.geom_type == 'LineString':
                # Precision rounding (5 decimals approx 1 meter) to merge nodes
                start = (round(geom.coords[0][0], 5), round(geom.coords[0][1], 5))
                end = (round(geom.coords[-1][0], 5), round(geom.coords[-1][1], 5))
                length = geom.length * 111139.0 
                
                # Add Forward Edge
                raw_graph.add_edge(start, end, weight=length, geometry=geom)
                
                # Add Backward Edge (Assuming local roads are accessible both ways)
                rev_geom = LineString(list(geom.coords)[::-1])
                raw_graph.add_edge(end, start, weight=length, geometry=rev_geom)

        # 2. CLEANUP: Remove isolated islands (Objective #7)
        if len(raw_graph) > 0:
            undirected = raw_graph.to_undirected()
            largest_cc = max(nx.connected_components(undirected), key=len)
            self.graph = raw_graph.subgraph(largest_cc).copy()
            
            removed = len(raw_graph) - len(self.graph)
            print(f"   Graph Cleaned: Kept {len(self.graph)} nodes (Removed {removed} disconnected nodes).")
        else:
            self.graph = raw_graph

        # Pre-cache nodes for fast lookup
        self.node_list = list(self.graph.nodes)
        print(f"   Graph Ready: {self.graph.number_of_edges()} drivable edges.")

    def get_random_waypoints(self, n=5):
        """
        Returns 'n' random nodes.
        Prioritizes localities (mapped to nearest road node) if available.
        """
        waypoints = []
        
        # 1. Try to use localities
        if self.localities:
            # Pick random localities
            chunk_size = min(len(self.localities), n)
            chosen_locs = random.sample(self.localities, chunk_size)
            
            for loc in chosen_locs:
                # Find nearest graph node to this locality
                node = self._get_nearest_node((loc[1], loc[0])) # Lat, Lon
                if node: waypoints.append(node)
                
        # 2. Fill remainder with random nodes
        remaining = n - len(waypoints)
        if remaining > 0 and self.node_list:
            waypoints.extend([random.choice(self.node_list) for _ in range(remaining)])
            
        return waypoints

    def find_shortest_path(self, start_coords: tuple, end_coords: tuple):
        """Returns (LineString, Distance_Meters)"""
        start_node = self._get_nearest_node(start_coords)
        end_node = self._get_nearest_node(end_coords)
        
        if not start_node or not end_node: return None, 0

        try:
            path_nodes = nx.shortest_path(self.graph, start_node, end_node, weight='weight')
        except nx.NetworkXNoPath:
            return None, 0
            
        coords = []
        total_len = 0
        
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i+1]
            data = self.graph.get_edge_data(u, v)
            
            edge_len = data.get('weight', 0)
            total_len += edge_len
            
            if 'geometry' in data:
                seg_coords = list(data['geometry'].coords)
                if len(coords) > 0: coords.extend(seg_coords[1:])
                else: coords.extend(seg_coords)
            else:
                coords.append(u)
                coords.append(v)
                
        return LineString(coords) if len(coords) > 1 else None, total_len

    def _get_nearest_node(self, point_coords):
        target_lon = point_coords[1]
        target_lat = point_coords[0]
        best_node = None
        min_dist = float('inf')
        
        # Optimization: Simple linear scan is robust for <50k nodes
        for node in self.node_list:
            dist = (node[0] - target_lon)**2 + (node[1] - target_lat)**2
            if dist < min_dist:
                min_dist = dist
                best_node = node
        return best_node