"""Geodesy tests against known reference values."""

import math

import pytest

from golfgeo.geodesy import (
    LocalProjection,
    bbox_around,
    bearing_change_deg,
    destination,
    distance_m,
    inverse,
    meters,
    polyline_length_m,
    utm_epsg_for,
    yards,
)

# Reference: JFK -> LHR geodesic distance is ~5554.6 km (Karney/GeographicLib).
JFK = (40.6413, -73.7781)
LHR = (51.4700, -0.4543)


def test_known_long_geodesic():
    d = distance_m(*JFK, *LHR)
    assert d == pytest.approx(5_554_600, rel=0.002)


def test_short_distance_matches_utm_planar():
    # Over ~200 m, geodesic and UTM planar distance agree to centimeters.
    a = (40.991165803512786, -85.17242986112421)
    b = (40.99273417763863, -85.17405958051316)
    geodesic = distance_m(*a, *b)
    proj = LocalProjection(*a)
    ax, ay = proj.to_xy(*a)
    bx, by = proj.to_xy(*b)
    planar = math.hypot(bx - ax, by - ay)
    assert geodesic == pytest.approx(planar, abs=0.15)


def test_brookwood_test_points_distance():
    # The two coordinates collected during product testing are ~242 yd apart —
    # the documented conflict with the ~520 yd scorecard (architecture §8.1).
    a = (40.991165803512786, -85.17242986112421)
    b = (40.99273417763863, -85.17405958051316)
    r = inverse(*a, *b)
    assert yards(r.distance_m) == pytest.approx(242.4, abs=0.5)
    assert r.bearing_deg == pytest.approx(321.9, abs=0.5)


def test_destination_roundtrip():
    lat, lon = 40.99, -85.17
    for bearing in (0, 45, 137.5, 270):
        lat2, lon2 = destination(lat, lon, bearing, 500)
        assert distance_m(lat, lon, lat2, lon2) == pytest.approx(500, abs=0.01)


def test_yard_meter_conversion():
    assert meters(520) == pytest.approx(475.49, abs=0.01)
    assert yards(meters(123.4)) == pytest.approx(123.4)


def test_utm_zone_selection():
    assert utm_epsg_for(40.99, -85.17) == 32616  # Fort Wayne -> UTM 16N
    assert utm_epsg_for(51.47, -0.45) == 32630
    assert utm_epsg_for(-33.86, 151.21) == 32756  # Sydney -> southern hemisphere


def test_local_projection_roundtrip():
    proj = LocalProjection(40.99, -85.17)
    x, y = proj.to_xy(40.99, -85.17)
    lat, lon = proj.to_latlon(x, y)
    assert lat == pytest.approx(40.99, abs=1e-9)
    assert lon == pytest.approx(-85.17, abs=1e-9)


def test_polyline_length():
    # Three points, two ~100 m legs due north.
    p0 = (40.99, -85.17)
    p1 = destination(*p0, 0, 100)
    p2 = destination(*p1, 0, 100)
    assert polyline_length_m([p0, p1, p2]) == pytest.approx(200, abs=0.01)
    assert polyline_length_m([p0]) == 0.0


def test_bearing_change():
    assert bearing_change_deg(350, 10) == pytest.approx(20)
    assert bearing_change_deg(10, 350) == pytest.approx(-20)
    assert bearing_change_deg(90, 270) == pytest.approx(180)


def test_bbox_around():
    w, s, e, n = bbox_around(40.99, -85.17, 1000)
    assert w < -85.17 < e
    assert s < 40.99 < n
    assert distance_m(40.99, w, 40.99, e) == pytest.approx(2000, rel=0.01)
