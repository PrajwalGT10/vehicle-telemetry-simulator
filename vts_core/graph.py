import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString
import math

class RoadNetwork:
    def __init__(self, geojson_path: str):
        print(f"   Loading Road Graph from {geojson_path}...")
        self.gdf = gpd.read_file(geojson_path)
        
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