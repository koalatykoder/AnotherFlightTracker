import math

def heading_to_cardinal(heading_deg: float) -> str:
    """Converts heading degrees (0-360) to cardinal direction representation (e.g. '185° S')."""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((heading_deg + 11.25) / 22.5) % 16
    return f"{int(heading_deg)}° {dirs[idx]}"


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates ground distance between two geographic coordinates in miles."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_slant_range(ground_dist_miles: float, altitude_ft: int) -> float:
    """Calculates 3D line-of-sight slant range distance in miles."""
    alt_miles = altitude_ft / 5280.0
    return math.sqrt(ground_dist_miles ** 2 + alt_miles ** 2)


def calculate_elevation_angle(ground_dist_miles: float, altitude_ft: int) -> float:
    """Calculates observer elevation angle above horizon in degrees (0-90°)."""
    if ground_dist_miles <= 0:
        return 90.0
    alt_miles = altitude_ft / 5280.0
    elevation_rad = math.atan(alt_miles / ground_dist_miles)
    return math.degrees(elevation_rad)


def calculate_bounding_box(lat: float, lon: float, radius_miles: float = 15.0) -> dict:
    """Calculates min/max lat/lon box around center point in miles."""
    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))
    return {
        "lamin": lat - lat_delta,
        "lamax": lat + lat_delta,
        "lomin": lon - lon_delta,
        "lomax": lon + lon_delta,
    }
