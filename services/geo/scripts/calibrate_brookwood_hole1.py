"""Brookwood GC Hole 1 calibration (Phase 1, architecture doc §10 steps 3-6).

Constructs the Hole 1 geometry hypothesis derived from visual analysis of the
2024 IGIO 6-inch orthoimagery and 2017 lidar DEM, runs the validation engine
against the researched scorecard (par 5, 520 yd, Blue tee), and renders a
calibration overlay for product-owner confirmation.

All features carry provenance='detected' and verification='unreviewed':
the analysis is machine+analyst-derived and explicitly awaits the human gate.

Feature positions are expressed in EPSG:2967 feet (the imagery grid) and
converted to WGS84 at the boundary.

Usage: python scripts/calibrate_brookwood_hole1.py <data_dir>
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent.parent))
from golfgeo.acquisition import fetch_mosaic, img_to_wgs, dem_sample_m
from golfgeo.model import Feature, FeatureType, HoleGeometry, Provenance
from golfgeo.serialization import save_hole
from golfgeo.validation import validate_hole

# ---- Geometry hypothesis in EPSG:2967 ft (from imagery/DEM analysis) --------

TEE_BLUE = (465206.0, 2091657.0)  # circular built pad NE of maintenance area
GREEN_OUTLINE = [
    (464038.5, 2092764.5), (464066.0, 2092777.0), (464101.0, 2092767.0),
    (464114.5, 2092739.5), (464107.5, 2092709.5), (464076.0, 2092693.0),
    (464046.0, 2092702.0), (464031.0, 2092732.0),
]
GREEN_CENTER = (464074.0, 2092735.0)
CENTERLINE = [
    TEE_BLUE,
    (465030.0, 2091800.0),
    (464800.0, 2091990.0),
    (464523.0, 2092169.0),   # test point A: the landing zone
    (464350.0, 2092350.0),
    (464200.0, 2092530.0),
    (464090.0, 2092680.0),
    GREEN_CENTER,
]
# Major bunkers (approximate outlines; confidence noted per feature)
BUNKERS = {
    "dogleg right cluster N": [
        (464606.0, 2092330.0), (464645.0, 2092354.0), (464678.0, 2092335.0),
        (464660.0, 2092305.0), (464618.0, 2092302.0),
    ],
    "dogleg right cluster S": [
        (464565.0, 2092240.0), (464600.0, 2092267.0), (464648.0, 2092250.0),
        (464630.0, 2092210.0), (464580.0, 2092205.0),
    ],
    "greenside SE double": [
        (464118.0, 2092717.0), (464130.0, 2092755.0), (464161.0, 2092762.0),
        (464160.0, 2092725.0), (464140.0, 2092710.0),
    ],
    "green front left": [
        (464026.0, 2092660.0), (464050.0, 2092680.0), (464070.0, 2092670.0),
        (464060.0, 2092647.0), (464035.0, 2092645.0),
    ],
    "green front right": [
        (464060.0, 2092690.0), (464081.0, 2092697.0), (464085.0, 2092675.0),
        (464068.0, 2092668.0),
    ],
}

SCORECARD = {"par": 5, "yardage": 520.0, "tee": "Blue"}


def ft_to_latlon(pts):
    return [img_to_wgs(x, y) for x, y in pts]


def build_hole(dem) -> HoleGeometry:
    tee_ll = img_to_wgs(*TEE_BLUE)
    green_ll = ft_to_latlon(GREEN_OUTLINE)
    cl_ll = ft_to_latlon(CENTERLINE)
    pin_ll = img_to_wgs(*GREEN_CENTER)
    feats = [
        Feature(FeatureType.TEE, [tee_ll], name="Blue",
                elevation_m=dem_sample_m(dem, *tee_ll),
                provenance=Provenance.DETECTED, confidence=0.7),
        Feature(FeatureType.FAIRWAY_CENTERLINE, cl_ll,
                provenance=Provenance.DETECTED, confidence=0.75),
        Feature(FeatureType.GREEN, green_ll,
                elevation_m=dem_sample_m(dem, *pin_ll),
                provenance=Provenance.DETECTED, confidence=0.8),
        Feature(FeatureType.PIN, [pin_ll], name="center",
                provenance=Provenance.DETECTED, confidence=0.8),
    ]
    for name, outline in BUNKERS.items():
        feats.append(Feature(FeatureType.BUNKER, ft_to_latlon(outline),
                             name=name, provenance=Provenance.DETECTED,
                             confidence=0.55))
    return HoleGeometry(
        course_name="Brookwood Golf Club",
        hole_number=1,
        par=SCORECARD["par"],
        tee_name=SCORECARD["tee"],
        scorecard_yardage=SCORECARD["yardage"],
        features=feats,
    )


def render_overlay(out_path: Path) -> None:
    bounds = (463800.0, 2091450.0, 465450.0, 2092950.0)
    m = fetch_mosaic(bounds, 2024, 1.0)
    im = Image.fromarray(np.transpose(m.array[:3], (1, 2, 0)))
    d = ImageDraw.Draw(im)
    inv = ~m.transform

    def px(p):
        c, r = inv * p
        return (c, r)

    d.line([px(p) for p in CENTERLINE], fill=(255, 235, 60), width=4)
    d.polygon([px(p) for p in GREEN_OUTLINE], outline=(60, 255, 90), width=4)
    for outline in BUNKERS.values():
        d.polygon([px(p) for p in outline], outline=(255, 150, 40), width=3)
    tc, tr = px(TEE_BLUE)
    d.ellipse([tc-12, tr-12, tc+12, tr+12], outline=(80, 160, 255), width=5)
    d.text((tc+16, tr-10), "BLUE TEE (hypothesis)", fill=(80, 160, 255))
    gc, gr = px(GREEN_CENTER)
    d.text((gc+14, gr-10), "GREEN / PIN", fill=(60, 255, 90))
    # the two disputed test points
    for (lat, lon), label, color in [
        ((40.991165803512786, -85.17242986112421), "A (was 'tee')", (255, 60, 60)),
        ((40.99273417763863, -85.17405958051316), "B (was 'green')", (60, 120, 255)),
    ]:
        from golfgeo.acquisition import wgs_to_img
        c, r = px(wgs_to_img(lat, lon))
        d.ellipse([c-9, r-9, c+9, r+9], outline=color, width=4)
        d.text((c+12, r+6), label, fill=color)
    im.save(out_path)


def main(data_dir: Path) -> None:
    dem_bounds = (463800.0, 2091450.0, 465450.0, 2092950.0)
    dem = fetch_mosaic(dem_bounds, 2017, 2.5, dem=True)

    hole = build_hole(dem)
    report = validate_hole(hole)
    print(report.summary())

    save_hole(hole, data_dir / "hole1.json")
    (data_dir / "hole1-validation.txt").write_text(report.summary() + "\n")

    # Elevation profile along centerline
    from golfgeo.geodesy import polyline_length_m, yards
    cl = hole.centerline.coords
    prof = []
    for lat, lon in cl:
        prof.append(dem_sample_m(dem, lat, lon))
    print("\nElevation profile (m):",
          " -> ".join(f"{e:.1f}" for e in prof))
    print(f"Centerline length: {yards(polyline_length_m(cl)):.0f} yd "
          f"(scorecard {hole.scorecard_yardage:.0f} yd)")

    render_overlay(data_dir / "hole1-calibration-overlay.png")
    print("\nWrote hole1.json, hole1-validation.txt, hole1-calibration-overlay.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
