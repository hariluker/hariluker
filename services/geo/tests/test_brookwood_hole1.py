"""Integration fixture: the calibrated Brookwood Hole 1 geometry must validate.

Uses the persisted hole1.json produced by scripts/calibrate_brookwood_hole1.py
(no network access needed). If the calibrated geometry or the validation rules
change incompatibly, this test catches it.
"""

from pathlib import Path

import pytest

from golfgeo.geodesy import polyline_length_m, yards
from golfgeo.model import FeatureType, Provenance, Verification
from golfgeo.serialization import load_hole
from golfgeo.validation import Verdict, validate_hole

HOLE1 = Path(__file__).parent.parent.parent.parent / "data" / "brookwood" / "hole1.json"


@pytest.fixture()
def hole():
    if not HOLE1.exists():
        pytest.skip("hole1.json not generated")
    return load_hole(HOLE1)


def test_calibrated_hole1_passes_validation(hole):
    report = validate_hole(hole)
    assert report.verdict == Verdict.PASS, report.summary()


def test_hole1_centerline_matches_scorecard(hole):
    cl_yd = yards(polyline_length_m(hole.centerline.coords))
    assert cl_yd == pytest.approx(520, rel=0.07)


def test_hole1_detected_features_await_verification(hole):
    # The calibration output is machine-derived: everything must be flagged
    # as detected and unreviewed until the product owner confirms it.
    for f in hole.features:
        assert f.provenance == Provenance.DETECTED
        assert f.verification == Verification.UNREVIEWED
        assert f.confidence is not None


def test_hole1_has_required_features(hole):
    assert hole.tee is not None and hole.tee.name == "Blue"
    assert hole.green is not None and len(hole.green.coords) >= 8
    assert hole.pin is not None
    assert len(hole.all(FeatureType.BUNKER)) >= 5
    assert hole.par == 5 and hole.scorecard_yardage == 520.0
