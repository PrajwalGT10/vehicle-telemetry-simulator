from typing import List, Tuple
import random
import math
from shapely.geometry import LineString, Point
from shapely.ops import substring

def interpolate_points_along_path(
    path_linestring: LineString, 
    speed_knots: float, 
    interval_seconds: int = 20, 
    jitter_seconds: int = 5
) -> List[Tuple[float, float, float]]:
    """
    Generates points along a LineString based on speed and time intervals.
    
    Args:
        path_linestring: The Shapely LineString representing the road path.
        speed_knots: Vehicle speed in knots.
        interval_seconds: Target time between points (default 20s).
        jitter_seconds: Random variation in timing (+/- 5s).
        
    Returns:
        List of tuples: (latitude, longitude, bearing_at_point)
    """
    
    # 1 Knot = 0.514444 m/s
    speed_mps = speed_knots * 0.514444
    
    total_length_meters = 0
    # Approximate length conversion (deg to meters) for simple interpolation
    # A more rigorous projection (UTM) is recommended for Phase 2, 
    # but this keeps existing logic functional.
    # 1 deg lat approx 111,139 meters.
    PROJECTED_RATIO = 111139.0 
    
    # We estimate total meters by length * ratio (simplified for WGS84)
    total_length_deg = path_linestring.length
    total_length_meters = total_length_deg * PROJECTED_RATIO
    
    current_dist_meters = 0.0
    points_data = []
    
    last_point = None

    while current_dist_meters < total_length_meters:
        # 1. Calculate step distance
        # Randomize time interval: e.g., 20s +/- 5s -> 15s to 25s
        actual_interval = interval_seconds + random.randint(-jitter_seconds, jitter_seconds)
        step_dist_meters = speed_mps * actual_interval
        
        current_dist_meters += step_dist_meters
        if current_dist_meters > total_length_meters:
            break
            
        # 2. Convert back to "degree distance" for Shapely interpolation
        current_dist_deg = current_dist_meters / PROJECTED_RATIO
        
        # 3. Get the point
        geo_point = path_linestring.interpolate(current_dist_deg)
        
        # 4. Calculate Bearing (Instantaneous)
        # We look slightly ahead (1 meter) to get the tangent direction
        next_dist_deg = (current_dist_meters + 1) / PROJECTED_RATIO
        lookahead_point = path_linestring.interpolate(next_dist_deg)
        
        bearing = calculate_bearing_shapely(geo_point, lookahead_point)
        
        points_data.append((geo_point.y, geo_point.x, bearing))
        
    return points_data

def calculate_bearing_shapely(p1: Point, p2: Point) -> float:
    """Helper to calculate bearing between two Shapely points."""
    lat1 = math.radians(p1.y)
    lat2 = math.radians(p2.y)
    diff_long = math.radians(p2.x - p1.x)

    x = math.sin(diff_long) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diff_long))

    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return compass_bearing