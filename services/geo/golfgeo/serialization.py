"""JSON round-trip for HoleGeometry (Phase 1 file-based persistence)."""

from __future__ import annotations

import json
from pathlib import Path

from .model import Feature, FeatureType, HoleGeometry, Provenance, Verification


def hole_to_dict(hole: HoleGeometry) -> dict:
    return {
        "course_name": hole.course_name,
        "hole_number": hole.hole_number,
        "par": hole.par,
        "tee_name": hole.tee_name,
        "scorecard_yardage": hole.scorecard_yardage,
        "features": [
            {
                "type": f.type.value,
                "name": f.name,
                "coords": [[lat, lon] for lat, lon in f.coords],
                "elevation_m": f.elevation_m,
                "provenance": f.provenance.value,
                "confidence": f.confidence,
                "verification": f.verification.value,
            }
            for f in hole.features
        ],
    }


def hole_from_dict(data: dict) -> HoleGeometry:
    return HoleGeometry(
        course_name=data["course_name"],
        hole_number=data["hole_number"],
        par=data["par"],
        tee_name=data["tee_name"],
        scorecard_yardage=data["scorecard_yardage"],
        features=[
            Feature(
                type=FeatureType(f["type"]),
                coords=[(lat, lon) for lat, lon in f["coords"]],
                name=f.get("name"),
                elevation_m=f.get("elevation_m"),
                provenance=Provenance(f.get("provenance", "user_drawn")),
                confidence=f.get("confidence"),
                verification=Verification(f.get("verification", "unreviewed")),
            )
            for f in data["features"]
        ],
    )


def save_hole(hole: HoleGeometry, path: Path) -> None:
    path.write_text(json.dumps(hole_to_dict(hole), indent=2) + "\n")


def load_hole(path: Path) -> HoleGeometry:
    return hole_from_dict(json.loads(path.read_text()))
