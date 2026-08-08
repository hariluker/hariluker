"""Geodesic math on the WGS84 ellipsoid.

All coordinates are WGS84 (lon, lat) unless stated otherwise. Distances are
meters, bearings are degrees clockwise from true north in [0, 360).

Distance/bearing use Karney's algorithm (GeographicLib) — accurate to
nanometers, unlike haversine's spherical approximation which errs up to
~0.5% on the ellipsoid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from geographiclib.geodesic import Geodesic
from pyproj import Transformer

_WGS84 = Geodesic.WGS84

METERS_PER_YARD = 0.9144


def yards(meters: float) -> float:
    return meters / METERS_PER_YARD


def meters(yds: float) -> float:
    return yds * METERS_PER_YARD


@dataclass(frozen=True)
class GeodesicResult:
    distance_m: float
    bearing_deg: float  # forward azimuth at the first point


def inverse(lat1: float, lon1: float, lat2: float, lon2: float) -> GeodesicResult:
    """Geodesic distance and forward bearing between two WGS84 points."""
    g = _WGS84.Inverse(lat1, lon1, lat2, lon2)
    return GeodesicResult(distance_m=g["s12"], bearing_deg=g["azi1"] % 360.0)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return inverse(lat1, lon1, lat2, lon2).distance_m


def destination(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
    """Point reached by traveling dist_m along bearing_deg from (lat, lon)."""
    g = _WGS84.Direct(lat, lon, bearing_deg, dist_m)
    return g["lat2"], g["lon2"]


def utm_epsg_for(lat: float, lon: float) -> int:
    """EPSG code of the WGS84/UTM zone containing the point."""
    zone = int((lon + 180.0) // 6.0) + 1
    zone = min(max(zone, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


class LocalProjection:
    """WGS84 <-> UTM transformer pinned to a course's zone.

    All planar math (centerline length, areas, offsets, camera splines)
    happens in this projection; conversion occurs once at the boundary.
    """

    def __init__(self, lat: float, lon: float):
        self.epsg = utm_epsg_for(lat, lon)
        self._to_utm = Transformer.from_crs(4326, self.epsg, always_xy=True)
        self._to_wgs = Transformer.from_crs(self.epsg, 4326, always_xy=True)

    def to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        return self._to_utm.transform(lon, lat)

    def to_latlon(self, x: float, y: float) -> tuple[float, float]:
        lon, lat = self._to_wgs.transform(x, y)
        return lat, lon


def polyline_length_m(points_latlon: Sequence[tuple[float, float]]) -> float:
    """Length of a polyline of (lat, lon) vertices, geodesic segment by segment."""
    if len(points_latlon) < 2:
        return 0.0
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(points_latlon, points_latlon[1:]):
        total += distance_m(lat1, lon1, lat2, lon2)
    return total


def bearing_change_deg(b1: float, b2: float) -> float:
    """Signed smallest angular change from bearing b1 to b2, in (-180, 180]."""
    d = (b2 - b1) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


def bbox_around(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) box with ~radius_m padding."""
    north = destination(lat, lon, 0, radius_m)
    south = destination(lat, lon, 180, radius_m)
    east = destination(lat, lon, 90, radius_m)
    west = destination(lat, lon, 270, radius_m)
    return (west[1], south[0], east[1], north[0])
