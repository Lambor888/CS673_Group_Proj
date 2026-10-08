import math
from app.scoring import haversine_distance

def test_same_points_returns_zero():
    assert haversine_distance(40.7128, -74.0060, 40.7128, -74.0060) == 0

def test_known_distance_nyc_to_london():
    distance = haversine_distance(40.7128, -74.0060, 51.5074, -0.1278)
    assert math.isclose(distance, 5570.8, rel_tol=0.02)