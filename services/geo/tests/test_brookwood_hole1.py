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


def test_hole1_verification_reflects_owner_review(hole):
    # 2026-08-08 product-owner review: tee position corrected (initial
    # hypothesis was the 10th tee), green/pin/centerline confirmed, two
    # greenside + one left-fairway bunker confirmed, dogleg suggestions
    # left unreviewed. Nothing may be silently unverified except those.
    assert hole.tee.verification == Verification.CORRECTED
    assert hole.tee.provenance == Provenance.USER_ADJUSTED
    assert hole.green.verification == Verification.CONFIRMED
    assert hole.pin.verification == Verification.CONFIRMED
    # centerline redrawn onto the NE corridor after the owner flagged the
    # first route as following the 10th; awaiting re-confirmation
    assert hole.centerline.verification == Verification.UNREVIEWED
    assert hole.centerline.provenance == Provenance.USER_ADJUSTED
    unreviewed = {f.name or f.type.value for f in hole.features
                  if f.verification == Verification.UNREVIEWED}
    assert unreviewed == {"fairway_centerline", "dogleg right cluster N",
                          "dogleg right cluster S"}
    for f in hole.features:
        if f.provenance == Provenance.DETECTED:
            assert f.confidence is not None


def test_hole1_has_required_features(hole):
    assert hole.tee is not None and hole.tee.name == "Blue"
    assert hole.green is not None and len(hole.green.coords) >= 8
    assert hole.pin is not None
    assert len(hole.all(FeatureType.BUNKER)) >= 5
    assert hole.par == 5 and hole.scorecard_yardage == 520.0
