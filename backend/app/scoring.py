import math

#
def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """Returns distance in kilometers between two lat/lon points."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    a = min(1.0, max(0.0, a))  # Avoid floating-point errors at antipodal points.
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
