"""Hole geometry domain model (in-memory form of the HoleGeometryVersion schema).

These objects mirror the persistence schema in docs/PHASE0-ARCHITECTURE.md §9;
Phase 1 works with them directly and serializes to/from JSON files so the
pipeline runs without a database. The PostGIS layer arrives with the API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FeatureType(str, Enum):
    TEE = "tee"
    FAIRWAY_CENTERLINE = "fairway_centerline"
    FAIRWAY = "fairway"
    GREEN = "green"
    BUNKER = "bunker"
    WATER = "water"
    CART_PATH = "cart_path"
    TREE_AREA = "tree_area"
    BUILDING = "building"
    OTHER_HAZARD = "other_hazard"
    PIN = "pin"


class Provenance(str, Enum):
    DETECTED = "detected"
    USER_DRAWN = "user_drawn"
    USER_ADJUSTED = "user_adjusted"
    IMPORTED = "imported"


class Verification(str, Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    REJECTED = "rejected"


@dataclass
class Feature:
    type: FeatureType
    # Geometry as WGS84 coordinates:
    #   point features: [(lat, lon)]
    #   lines:          [(lat, lon), ...] ordered tee -> green
    #   polygons:       [(lat, lon), ...] exterior ring, closed or open
    coords: list[tuple[float, float]]
    name: Optional[str] = None
    elevation_m: Optional[float] = None
    provenance: Provenance = Provenance.USER_DRAWN
    confidence: Optional[float] = None
    verification: Verification = Verification.UNREVIEWED

    @property
    def point(self) -> tuple[float, float]:
        assert len(self.coords) == 1, f"{self.type} is not a point feature"
        return self.coords[0]


@dataclass
class HoleGeometry:
    course_name: str
    hole_number: int
    par: int
    tee_name: str
    scorecard_yardage: float
    features: list[Feature] = field(default_factory=list)

    def one(self, ftype: FeatureType, name: Optional[str] = None) -> Optional[Feature]:
        matches = [
            f for f in self.features
            if f.type == ftype and (name is None or f.name == name)
        ]
        return matches[0] if matches else None

    def all(self, ftype: FeatureType) -> list[Feature]:
        return [f for f in self.features if f.type == ftype]

    @property
    def tee(self) -> Optional[Feature]:
        return self.one(FeatureType.TEE, self.tee_name) or self.one(FeatureType.TEE)

    @property
    def green(self) -> Optional[Feature]:
        return self.one(FeatureType.GREEN)

    @property
    def centerline(self) -> Optional[Feature]:
        return self.one(FeatureType.FAIRWAY_CENTERLINE)

    @property
    def pin(self) -> Optional[Feature]:
        return self.one(FeatureType.PIN)
