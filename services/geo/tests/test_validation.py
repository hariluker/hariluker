"""Validation engine tests, including the Brookwood A/B coordinate fixture."""

import pytest

from golfgeo.geodesy import destination
from golfgeo.model import Feature, FeatureType, HoleGeometry, Provenance
from golfgeo.validation import Verdict, validate_hole

# The two coordinates collected during product testing (architecture §8.1).
POINT_A = (40.991165803512786, -85.17242986112421)
POINT_B = (40.99273417763863, -85.17405958051316)


def _square_around(lat, lon, half_m):
    n = destination(lat, lon, 0, half_m)[0]
    s = destination(lat, lon, 180, half_m)[0]
    e = destination(lat, lon, 90, half_m)[1]
    w = destination(lat, lon, 270, half_m)[1]
    return [(n, w), (n, e), (s, e), (s, w)]


def _synthetic_hole(yardage=520.0, par=5, dogleg=False):
    """A geometrically consistent hole: tee at origin, green at scorecard distance."""
    tee = (40.9900, -85.1700)
    total_m = yardage * 0.9144
    if dogleg:
        # Two legs at a 45-degree turn whose path length equals the scorecard.
        mid = destination(*tee, 315, total_m * 0.55)
        green_c = destination(*mid, 270, total_m * 0.45)
        cl = [tee, destination(*tee, 315, total_m * 0.3), mid,
              destination(*mid, 270, total_m * 0.2), green_c]
    else:
        green_c = destination(*tee, 315, total_m)
        cl = [tee, destination(*tee, 315, total_m * 0.33),
              destination(*tee, 315, total_m * 0.66), green_c]
    return HoleGeometry(
        course_name="Test GC",
        hole_number=1,
        par=par,
        tee_name="Back",
        scorecard_yardage=yardage,
        features=[
            Feature(FeatureType.TEE, [tee], name="Back"),
            Feature(FeatureType.FAIRWAY_CENTERLINE, cl),
            Feature(FeatureType.GREEN, _square_around(*green_c, 15)),
            Feature(FeatureType.PIN, [green_c]),
        ],
    )


def test_consistent_straight_hole_passes():
    report = validate_hole(_synthetic_hole())
    assert report.verdict == Verdict.PASS, report.summary()


def test_consistent_dogleg_hole_does_not_fail():
    # Dogleg: straight-line < scorecard, but centerline matches -> at worst REVIEW.
    report = validate_hole(_synthetic_hole(dogleg=True))
    assert report.verdict in (Verdict.PASS, Verdict.REVIEW), report.summary()
    straight = next(r for r in report.results if r.rule == "straight_line_vs_scorecard")
    assert straight.verdict != Verdict.FAIL
    centerline = next(r for r in report.results if r.rule == "centerline_vs_scorecard")
    assert centerline.verdict == Verdict.PASS


def test_brookwood_ab_coordinates_fail():
    """The documented product fixture: points A/B against a 520 yd scorecard.

    242 yd straight-line vs 520 yd scorecard (47%) must FAIL, with an
    explanation a course employee can act on.
    """
    hole = HoleGeometry(
        course_name="Brookwood Golf Club",
        hole_number=1,
        par=5,
        tee_name="Back",
        scorecard_yardage=520.0,
        features=[
            Feature(FeatureType.TEE, [POINT_A], name="Back",
                    provenance=Provenance.IMPORTED),
            Feature(FeatureType.FAIRWAY_CENTERLINE, [POINT_A, POINT_B],
                    provenance=Provenance.IMPORTED),
            Feature(FeatureType.GREEN, [POINT_B], provenance=Provenance.IMPORTED),
        ],
    )
    report = validate_hole(hole)
    assert report.verdict == Verdict.FAIL
    straight = next(r for r in report.results if r.rule == "straight_line_vs_scorecard")
    assert straight.verdict == Verdict.FAIL
    assert straight.metrics["ratio"] == pytest.approx(0.466, abs=0.01)
    assert "misplaced" in straight.explanation


def test_missing_geometry_fails_fast():
    hole = HoleGeometry("Test GC", 1, 4, "Back", 400.0, features=[])
    report = validate_hole(hole)
    assert report.verdict == Verdict.FAIL
    assert "Missing required geometry" in report.results[0].explanation


def test_pin_outside_green_fails():
    hole = _synthetic_hole()
    hole.pin.coords[0] = destination(*hole.pin.coords[0], 90, 200)
    report = validate_hole(hole)
    green = next(r for r in report.results if r.rule == "green_sanity")
    assert green.verdict == Verdict.FAIL
    assert "pin is outside" in green.explanation


def test_two_vertex_centerline_flagged():
    hole = _synthetic_hole()
    cl = hole.centerline
    cl.coords = [cl.coords[0], cl.coords[-1]]
    report = validate_hole(hole)
    degeneracy = next(r for r in report.results if r.rule == "degeneracy")
    assert degeneracy.verdict == Verdict.REVIEW
    assert "vertices" in degeneracy.explanation


def test_par3_yardage_band():
    hole = _synthetic_hole(yardage=155.0, par=3)
    report = validate_hole(hole)
    par_rule = next(r for r in report.results if r.rule == "par_vs_yardage")
    assert par_rule.verdict == Verdict.PASS

    hole = _synthetic_hole(yardage=400.0, par=3)
    report = validate_hole(hole)
    par_rule = next(r for r in report.results if r.rule == "par_vs_yardage")
    assert par_rule.verdict == Verdict.REVIEW


def test_explanations_are_plain_english():
    report = validate_hole(_synthetic_hole())
    for r in report.results:
        assert r.explanation.endswith(".")
        assert len(r.explanation) > 10
