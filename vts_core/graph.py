import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString
import math

class RoadNetwork:
    def __init__(self, geojson_path: str):
        print(f"   Loading Road Graph from {geojson_path}...")
        self.gdf = gpd.read_file(geojson_path)
        
        # 1. Build Directed Graph
        self.graph = nx.DiGraph()
        
        for _, row in self.gdf.iterrows():
            geom = row.geometry
            if geom.geom_type == 'LineString':
                # Precision rounding to merge close nodes
                start = (round(geom.coords[0][0], 5), round(geom.coords[0][1], 5))
                end = (round(geom.coords[-1][0], 5), round(geom.coords[-1][1], 5))
                length = geom.length * 111139.0 
                
                # Add Edges (2-way for simulation connectivity)
                # We default to straight lines if geometry breaks, but here we store the real one
                self.graph.add_edge(start, end, weight=length, geometry=geom)
                self.graph.add_edge(end, start, weight=length, geometry=LineString(list(geom.coords)[::-1]))

        # 2. ISOLATION REMOVAL (Crucial Fix)
        # We only keep the "Main City Component". Any road not connected to this is deleted.
        if len(self.graph) > 0:
            largest_cc = max(nx.weakly_connected_components(self.graph), key=len)
            self.main_graph = self.graph.subgraph(largest_cc).copy()
            
            removed = len(self.graph) - len(self.main_graph)
            print(f"   Graph Cleaned: Kept {len(self.main_graph)} nodes. (Deleted {removed} isolated nodes).")
            self.graph = self.main_graph
        else:
            print("   ⚠️ Warning: Graph is empty!")

        # Create a spatial index (list of nodes) for fast lookup
        self.node_list = list(self.graph.nodes)

    def find_shortest_path(self, start_coords: tuple, end_coords: tuple) -> LineString:
        start_node = self._get_nearest_node(start_coords)
        end_node = self._get_nearest_node(end_coords)
        
        if not start_node or not end_node: return None

        try:
            path_nodes = nx.shortest_path(self.graph, start_node, end_node, weight='weight')
        except nx.NetworkXNoPath:
            return None
            
        # 3. Stitch Geometry with "Zig-Zag Prevention"
        coords = []
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i+1]
            data = self.graph.get_edge_data(u, v)
            
            # Use the road geometry if it exists, otherwise straight line
            if 'geometry' in data:
                seg_coords = list(data['geometry'].coords)
            else:
                seg_coords = [u, v]

            # Append to path (avoiding duplicates at join points)
            if len(coords) > 0:
                coords.extend(seg_coords[1:])
            else:
                coords.extend(seg_coords)
                
        return LineString(coords) if len(coords) > 1 else None

    def _get_nearest_node(self, point_coords):
        """Finds the nearest node that exists in the MAIN CONNECTED GRAPH."""
        target_lon = point_coords[1]
        target_lat = point_coords[0]
        
        best_node = None
        min_dist = float('inf')
        
        # Optimization: Check 2000 random nodes if graph is huge, or simple scan
        # For robustness, we scan all (fast enough for 20k nodes in C-based Python)
        for node in self.node_list:
            dist = (node[0] - target_lon)**2 + (node[1] - target_lat)**2
            if dist < min_dist:
                min_dist = dist
                best_node = node
        return best_node