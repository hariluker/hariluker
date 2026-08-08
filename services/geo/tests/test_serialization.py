from golfgeo.model import Feature, FeatureType, HoleGeometry, Provenance, Verification
from golfgeo.serialization import hole_from_dict, hole_to_dict, load_hole, save_hole


def _hole():
    return HoleGeometry(
        course_name="Brookwood Golf Club",
        hole_number=1,
        par=5,
        tee_name="Back",
        scorecard_yardage=520.0,
        features=[
            Feature(FeatureType.TEE, [(40.991, -85.172)], name="Back",
                    elevation_m=241.5, provenance=Provenance.USER_DRAWN,
                    verification=Verification.CONFIRMED),
            Feature(FeatureType.BUNKER, [(40.992, -85.173), (40.9921, -85.173),
                                         (40.9921, -85.1731)],
                    provenance=Provenance.DETECTED, confidence=0.82),
        ],
    )


def test_round_trip_dict():
    hole = _hole()
    restored = hole_from_dict(hole_to_dict(hole))
    assert restored == hole


def test_round_trip_file(tmp_path):
    hole = _hole()
    path = tmp_path / "hole.json"
    save_hole(hole, path)
    assert load_hole(path) == hole
