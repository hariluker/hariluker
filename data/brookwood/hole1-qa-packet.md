# Brookwood GC Hole 1 — Phase 1 Calibration QA Packet

**Date:** 2026-08-08
**Status:** Geometry calibrated and validation-PASSING; awaiting product-owner confirmation (the §11 human gate). All features carry `provenance=detected`, `verification=unreviewed`.

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

- **Blue tee:** circular built pad at the southeast end of the corridor, beside the entrance drive and practice green, NE of the maintenance buildings (EPSG:2967 ≈ 465206, 2091657).
- **Fairway:** runs WNW from the tee, through A's landing zone, with a gentle dogleg right (~15°) at the bunker cluster.
- **Green:** the northeast oval of the complex at ≈ (464074, 2092735) — 479 m², guarded by a double bunker southeast (approach side) and two front bunkers; pin defaulted to green center (contains point B).
- **Bunkers:** 5 traced as low-confidence suggestions (2 dogleg, 3 greenside) — outlines are approximate and expected to be adjusted in the editor.
- **Elevation:** essentially flat — tee 240.8 m, green 241.1 m (+0.3 m), mild mid-hole rise to 242.7 m (lidar DEM profile).

## 5. Validation result (engine output)

```
Brookwood Golf Club hole 1 (Blue tee): overall PASS
  [PASS] straight_line_vs_scorecard: 522 yd straight vs 520 yd scorecard
  [PASS] centerline_vs_scorecard:    528 yd routed (within 7%)
  [PASS] centerline_endpoints:       starts at tee, ends on green
  [PASS] par_vs_yardage:             520 yd conventional par 5
  [PASS] green_sanity:               valid polygon, 479 m², pin inside
  [PASS] elevation_sanity:           0.3 m tee-green change
  [PASS] degeneracy:                 all geometry well-formed
```

Routed 528 yd vs 522 straight ⇒ nearly straight hole with a slight dogleg right — consistent with the app screenshot's "visually clear routing."

## 6. What needs human confirmation (the gate)

1. **Blue tee position** — is the circular pad NE of the maintenance area the Blue/tip tee? (Alternative: tees hidden in the lawn strip west of the clubhouse; no pads visible there in imagery or lidar relief.)
2. **Green identity** — the green complex has two adjacent ovals; the hypothesis (and point B) selects the northeast one. Confirm hole 1 uses it (the southwest oval would then belong to another hole or be a double-green section).
3. **Bunker outlines** — 5 suggestions need visual adjustment in the editor.
4. **Left of centerline** — whether the opening 200 yd crosses rough or mowed fairway (affects camera framing, not distances).

## 7. Reproduction

```
cd services/geo
pip install -e .[dev]
python scripts/acquire_brookwood.py ../../data/brookwood        # overview + assets
python scripts/calibrate_brookwood_hole1.py ../../data/brookwood # geometry + validation + overlay
python -m pytest                                                 # 24 tests incl. hole1 fixture
```

Artifacts: `hole1.json` (geometry), `hole1-validation.txt`, `hole1-calibration-overlay.png` (visual), `assets.json` (license ledger).
