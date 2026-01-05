import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely.ops import linemerge
import math

class RoadNetwork:
    def __init__(self, geojson_path: str):
        print(f"   Loading Road Graph from {geojson_path}...")
        self.gdf = gpd.read_file(geojson_path)
        
        # 1. Build Full Graph
        full_graph = nx.Graph()
        
        for _, row in self.gdf.iterrows():
            geom = row.geometry
            if geom.geom_type == 'LineString':
                start = geom.coords[0]
                end = geom.coords[-1]
                length = geom.length * 111139.0 
                
                # Store geometry in edge data
                full_graph.add_node(start, pos=start)
                full_graph.add_node(end, pos=end)
                full_graph.add_edge(start, end, weight=length, geometry=geom)

        # 2. Extract Largest Connected Component
        if full_graph.number_of_nodes() > 0:
            largest_cc_nodes = max(nx.connected_components(full_graph), key=len)
            self.graph = full_graph.subgraph(largest_cc_nodes).copy()
            removed_nodes = full_graph.number_of_nodes() - self.graph.number_of_nodes()
            print(f"   Graph Cleaned: Kept {self.graph.number_of_nodes()} nodes (Removed {removed_nodes} disconnected nodes).")
        else:
            self.graph = full_graph

        print(f"   Graph Ready: {self.graph.number_of_edges()} drivable edges.")

    def find_shortest_path(self, start_coords: tuple, end_coords: tuple) -> LineString:
        """
        Finds route from Start (Lat, Lon) to End (Lat, Lon).
        Returns a merged LineString of the path.
        """
        # Shapely uses (Lon, Lat)
        p1 = (start_coords[1], start_coords[0])
        p2 = (end_coords[1], end_coords[0])
        
        start_node = self._get_nearest_node(p1)
        end_node = self._get_nearest_node(p2)
        
        if not start_node or not end_node:
            return None

        try:
            path_nodes = nx.shortest_path(self.graph, start_node, end_node, weight='weight')
        except nx.NetworkXNoPath:
            return None
            
        # 3. Reconstruct Geometry (With STRICT Direction Fix)
        lines = []
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i+1]
            data = self.graph.get_edge_data(u, v)
            
            if 'geometry' in data:
                geom = data['geometry']
                # Correct orientation: The geometry must start at 'u' and end at 'v'
                geom = self._fix_geometry_orientation(geom, u, v)
                lines.append(geom)
            else:
                lines.append(LineString([u, v]))
                
        # Merge segments
        if len(lines) == 0:
            return LineString([p1, p2])
        elif len(lines) == 1:
            return lines[0]
        else:
            coords = []
            for line in lines:
                line_coords = list(line.coords)
                # Avoid duplicating the join point
                if len(coords) > 0:
                    coords.extend(line_coords[1:])
                else:
                    coords.extend(line_coords)
            return LineString(coords)

    def _fix_geometry_orientation(self, geom, start_node, end_node):
        """
        Ensures the geometry starts near start_node and ends near end_node.
        If it's backwards, reverse it.
        """
        geom_start = Point(geom.coords[0])
        geom_end = Point(geom.coords[-1])
        
        node_start = Point(start_node)
        
        # Calculate distances to see which end matches 'start_node'
        dist_start_to_start = geom_start.distance(node_start)
        dist_end_to_start = geom_end.distance(node_start)
        
        # If the geometry's END is closer to our START node, we are driving backwards.
        # So we reverse the geometry.
        if dist_end_to_start < dist_start_to_start:
            return LineString(list(geom.coords)[::-1])
            
        return geom

    def _get_nearest_node(self, point_coords):
        best_node = None
        min_dist = float('inf')
        ref_point = Point(point_coords)
        for node in self.graph.nodes:
            dist = ref_point.distance(Point(node))
            if dist < min_dist:
                min_dist = dist
                best_node = node
        return best_node