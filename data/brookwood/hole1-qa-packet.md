# Brookwood GC Hole 1 — Phase 1 Calibration QA Packet

**Date:** 2026-08-08
**Status:** VERIFIED — product-owner review completed 2026-08-08; corrections applied; validation PASS. Remaining unreviewed suggestions: the two dogleg-cluster bunkers only.

---

## 1. Scorecard ground truth (researched)

Brookwood Golf Club, 10304 Bluffton Rd, Fort Wayne, IN 46809. 18-hole regulation course (Harry Collis, 1925), par 72, back tee = **Blue** (~6,746 yd total).

**Hole 1: par 5, 520 yd from Blue, handicap 13** — confirmed across multiple independent scorecard sources; per-tee yardages for other tees not yet verified.

## 2. Data used (all public domain, license ledger in assets.json)

| Asset | Source | Vintage | Resolution |
|---|---|---|---|
| Orthoimagery (4-band RGBI) | Indiana IGIO statewide program, AWS Open Data (`gisimageryingov`) | **2024** (newest covering Allen County) | 6 in (15 cm)/px |
| Bare-earth DEM | Indiana IGIO (same bucket, `demoptimized`), from 2017 QL2 lidar | 2017 | 2.5 ft/px |

Both are public domain / CC0 — commercial derivative use and resale confirmed (architecture doc §3). 18 imagery tiles + 2 DEM tiles recorded with ETags in `assets.json`. Note the 7-year imagery/DEM vintage gap: acceptable on this very flat site (total relief on the hole < 2 m), revisit when the 2025–28 QL1 lidar lands.

## 3. Resolution of the disputed A/B coordinates

The two coordinates collected during earlier testing, plotted on the 2024 imagery:

- **A** `40.9911658, -85.1724299` — lands **mid-fairway**, at the hole's landing zone near the dogleg bunkers. It is **not a tee**. 242 yd from B ⇒ consistent with a route-line waypoint or landing-zone marker from the golf app.
- **B** `40.9927342, -85.1740596` — lands **on a green** (the northeast oval of a two-green complex). Very likely a correctly-captured hole-1 green/pin point.

The original assignment (A=tee, B=green) failed validation exactly as designed: 242 yd straight-line vs 520 yd scorecard (47%, FAIL). Root cause: **A is a mid-hole waypoint, not the tee.**

## 4. Calibrated geometry hypothesis

Derived by visual analysis of imagery + lidar local-relief (tee pads/greens are built platforms), constrained by the 520-yd scorecard:

- **Blue tee (owner-corrected):** the circular pad initially proposed is the **10th tee**; the 1st tee is the large oval pad immediately east of it, between the cart path and the parking lot (EPSG:2967 ≈ 465290, 2091665; marker placed west-center of the pad).
- **Fairway:** runs WNW from the tee, through A's landing zone, with a gentle dogleg right (~15°) at the bunker cluster.
- **Green (owner-confirmed):** the northeast oval of the complex at ≈ (464074, 2092735) — 479 m²; pin defaulted to green center (contains point B). The southwest oval is the **12th green**.
- **Bunkers (owner-corrected):** exactly 2 greenside (the SE double and the front-right); the initially marked "front left" bunker belongs to hole 12 (its right-side bunker) and was removed. One additional owner-reported bunker added on the left of the fairway ~2/3 up (≈ 464305, 2092338, beside the neighboring green). The two dogleg-right cluster suggestions remain unreviewed.
- **Elevation:** essentially flat — tee 240.8 m, green 241.1 m (+0.3 m), mild mid-hole rise to 242.7 m (lidar DEM profile).

## 5. Validation result (engine output)

```
Brookwood Golf Club hole 1 (Blue tee): overall PASS
  [PASS] straight_line_vs_scorecard: 540 yd straight vs 520 yd scorecard
  [PASS] centerline_vs_scorecard:    550 yd routed (within 7%)
  [PASS] centerline_endpoints:       starts at tee, ends on green
  [PASS] par_vs_yardage:             520 yd conventional par 5
  [PASS] green_sanity:               valid polygon, 479 m², pin inside
  [PASS] elevation_sanity:           0.3 m tee-green change
  [PASS] degeneracy:                 all geometry well-formed
```

Routed 550 yd vs 540 straight ⇒ nearly straight hole with a slight dogleg right. The measured length runs ~5% over the 520 scorecard — within tolerance; scorecards typically measure from permanent mid-pad markers along the intended playing line, and the marker was placed at the pad's west-center. Not a blocker.

## 6. Human gate outcome (2026-08-08 review)

| Item | Owner verdict | Action taken |
|---|---|---|
| Blue tee = circular pad | **Wrong — that is the 10th tee**; 1st tee is just east of it | Tee moved to the oval pad east of the circle; provenance `user_adjusted`, verification `corrected` |
| Green = NE oval | **Correct** | Verification `confirmed` |
| Greenside bunkers | Only 2 exist; the leftmost marking is the **12th hole's right-side bunker** | Removed the 12th's bunker; SE double + front right `confirmed` |
| Fairway-left bunker ~2/3 up | **Missing from the map** | Traced and added, `confirmed` |
| Course currency | Hole unchanged since 2024 imagery | Imagery vintage accepted |

Still open (non-blocking): the two dogleg-right bunker outlines remain `unreviewed`; adjust or confirm in the editor when it exists.

## 7. Reproduction

```
cd services/geo
pip install -e .[dev]
python scripts/acquire_brookwood.py ../../data/brookwood        # overview + assets
python scripts/calibrate_brookwood_hole1.py ../../data/brookwood # geometry + validation + overlay
python -m pytest                                                 # 24 tests incl. hole1 fixture
```

Artifacts: `hole1.json` (geometry), `hole1-validation.txt`, `hole1-calibration-overlay.png` (visual), `assets.json` (license ledger).
