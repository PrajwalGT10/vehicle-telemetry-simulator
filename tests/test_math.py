import pytest
from shapely.geometry import LineString
from vts_core.utils import calculate_bearing, haversine_distance
from vts_core.geo import interpolate_points_along_path

def test_bearing_calculation():
    """Verify bearing logic for cardinal directions."""
    # Point A to Point B (Directly North)
    # Lat increases, Lon stays same
    bearing_north = calculate_bearing(12.0, 77.0, 13.0, 77.0)
    assert pytest.approx(bearing_north, 0.1) == 0.0

    # Point A to Point B (Directly East)
    # Lat same, Lon increases
    bearing_east = calculate_bearing(12.0, 77.0, 12.0, 78.0)
    assert pytest.approx(bearing_east, 0.1) == 90.0

def test_haversine_distance():
    """Verify distance calculation against known values."""
    # Distance between Bangalore (12.9716, 77.5946) and Mysore (12.2958, 76.6394)
    # Approx 125km - 130km straight line
    dist = haversine_distance(12.9716, 77.5946, 12.2958, 76.6394)
    assert 120000 < dist < 140000  # Broad check in meters

def test_interpolation():
    """Verify that we generate points along a line."""
    # 11km straight road
    road = LineString([(0, 0), (0, 0.1)])
    
    # Speed 40 knots (~20m/s), Interval 20s => ~400m per step
    points = interpolate_points_along_path(road, speed_knots=40.0, interval_seconds=20, jitter_seconds=0)
    
    # We expect roughly 11,000m / 400m = ~27 points
    assert len(points) > 20
    assert len(points) < 35
    
    # Check structure of result (Lat, Lon, Bearing)
    first_point = points[0]
    assert len(first_point) == 3
    # Bearing should be North (0.0)
    assert pytest.approx(first_point[2], abs=1.0) == 0.0