import math
from typing import Tuple

def calculate_bearing(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> float:
    """Calculates initial compass bearing (0-360)."""
    lat1 = math.radians(start_lat)
    lat2 = math.radians(end_lat)
    diff_long = math.radians(end_lon - start_lon)

    x = math.sin(diff_long) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diff_long))

    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    return (initial_bearing + 360) % 360

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in Meters."""
    R = 6371000 
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) * math.sin(d_lat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) * math.sin(d_lon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- NEW FORMATTERS ---

def decimal_to_ddmm_mmmm(degrees: float, is_longitude: bool = False) -> str:
    """
    Converts decimal degrees to NMEA format.
    Lat: 1255.4187 (2 digits degrees)
    Lon: 07733.1281 (3 digits degrees - Padded with 0)
    """
    if degrees is None:
        return "0000.0000" if not is_longitude else "00000.0000"
    
    absolute = abs(degrees)
    d = int(absolute)
    m = (absolute - d) * 60.0
    
    # Logic: Degrees * 100 + Minutes
    # Longitude requires 3 digits for degrees (e.g. 077)
    # Latitude requires 2 digits for degrees (e.g. 12)
    
    if is_longitude:
        return f"{d:03d}{m:07.4f}" # 07733.1281
    else:
        return f"{d:02d}{m:07.4f}" # 1255.4187

def format_time_hhmmss_ms(dt_obj) -> str:
    """Converts datetime to HHMMSS.000 format."""
    # Matches '060722.000' from your example
    return dt_obj.strftime("%H%M%S.000")