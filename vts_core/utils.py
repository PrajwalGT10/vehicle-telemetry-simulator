import math

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculates bearing between two points."""
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = math.radians(lat2), math.radians(lon2)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    return (initial_bearing + 360) % 360

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in Meters."""
    R = 6371000 
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) * math.sin(d_lat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) * math.sin(d_lon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def decimal_to_nmea(decimal_degrees, is_longitude=False):
    """
    Converts decimal degrees to NMEA format (DDMM.MMMM or DDDMM.MMMM).
    Example Lat: 12.9236 -> "1255.4160"
    Example Lon: 77.5550 -> "07733.3000"
    """
    if decimal_degrees is None: return ""
    
    val = abs(decimal_degrees)
    degrees = int(val)
    minutes = (val - degrees) * 60
    
    # Format: DDMM.MMMM (Lat) or DDDMM.MMMM (Lon)
    if is_longitude:
        # Longitude is 3 digits for degrees
        return f"{degrees:03d}{minutes:07.4f}"
    else:
        # Latitude is 2 digits for degrees
        return f"{degrees:02d}{minutes:07.4f}"

def get_hemisphere(val, is_lon=False):
    """Returns the NMEA hemisphere character (N/S/E/W)."""
    if is_lon:
        return 'E' if val >= 0 else 'W'
    return 'N' if val >= 0 else 'S'