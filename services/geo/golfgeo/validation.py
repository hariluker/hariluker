"""Geometry validation engine (architecture doc §8.2).

Every rule emits PASS/REVIEW/FAIL with a plain-English explanation and the
numbers behind it. The hole's overall verdict is the worst individual result.
FAIL blocks rendering; REVIEW renders but is flagged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from shapely.geometry import LineString, Point, Polygon

from .geodesy import LocalProjection, distance_m, polyline_length_m, yards
from .model import FeatureType, HoleGeometry

PAR_YARDAGE_BANDS = {3: (60, 260), 4: (240, 520), 5: (400, 700)}
GREEN_AREA_BOUNDS_M2 = (150.0, 2500.0)


class Verdict(IntEnum):
    PASS = 0
    REVIEW = 1
    FAIL = 2


@dataclass
class RuleResult:
    rule: str
    verdict: Verdict
    explanation: str
    metrics: dict


@dataclass
class ValidationReport:
    hole: str
    results: list[RuleResult]

    @property
    def verdict(self) -> Verdict:
        return max((r.verdict for r in self.results), default=Verdict.PASS)

    def summary(self) -> str:
        lines = [f"{self.hole}: overall {self.verdict.name}"]
        for r in self.results:
            lines.append(f"  [{r.verdict.name:6}] {r.rule}: {r.explanation}")
        return "\n".join(lines)


def _polygon(coords: list[tuple[float, float]], proj: LocalProjection) -> Polygon:
    return Polygon([proj.to_xy(lat, lon) for lat, lon in coords])


def validate_hole(hole: HoleGeometry) -> ValidationReport:
    results: list[RuleResult] = []
    tee, green, centerline = hole.tee, hole.green, hole.centerline

    # -- Completeness (prerequisite for everything else) ---------------------
    missing = [
        n for n, f in (("tee", tee), ("green", green), ("fairway centerline", centerline))
        if f is None
    ]
    if missing:
        results.append(RuleResult(
            "completeness", Verdict.FAIL,
            f"Missing required geometry: {', '.join(missing)}.",
            {"missing": missing},
        ))
        return ValidationReport(_hole_label(hole), results)
    results.append(RuleResult(
        "completeness", Verdict.PASS, "Tee, green, and centerline are present.", {},
    ))

    tee_lat, tee_lon = tee.point
    proj = LocalProjection(tee_lat, tee_lon)

    green_poly = _polygon(green.coords, proj) if len(green.coords) >= 3 else None
    green_center = _green_center(hole, proj)

    # -- Straight-line vs scorecard ------------------------------------------
    straight_m = distance_m(tee_lat, tee_lon, green_center[0], green_center[1])
    straight_yd = yards(straight_m)
    ratio = straight_yd / hole.scorecard_yardage if hole.scorecard_yardage else 0.0
    if 0.80 <= ratio <= 1.10:
        v, why = Verdict.PASS, (
            f"Tee to green center is {straight_yd:.0f} yd in a straight line, "
            f"consistent with the {hole.scorecard_yardage:.0f} yd scorecard."
        )
    elif 0.60 <= ratio < 0.80:
        v, why = Verdict.REVIEW, (
            f"Tee to green center is only {straight_yd:.0f} yd in a straight line vs "
            f"{hole.scorecard_yardage:.0f} yd on the scorecard ({ratio:.0%}). A strong "
            f"dogleg can explain this — confirm the routing."
        )
    else:
        v, why = Verdict.FAIL, (
            f"Tee and green center are {straight_yd:.0f} yd apart in a straight line, but the "
            f"scorecard says {hole.scorecard_yardage:.0f} yd ({ratio:.0%}). Doglegs shorten the "
            f"straight-line distance, but not this much — one of these points is probably "
            f"misplaced. Check the tee and green positions."
        )
    results.append(RuleResult(
        "straight_line_vs_scorecard", v, why,
        {"straight_yd": straight_yd, "scorecard_yd": hole.scorecard_yardage, "ratio": ratio},
    ))

    # -- Centerline vs scorecard ---------------------------------------------
    cl_yd = yards(polyline_length_m(centerline.coords))
    cl_ratio = cl_yd / hole.scorecard_yardage if hole.scorecard_yardage else 0.0
    if 0.93 <= cl_ratio <= 1.07:
        v, why = Verdict.PASS, (
            f"Fairway centerline measures {cl_yd:.0f} yd, within 7% of the "
            f"{hole.scorecard_yardage:.0f} yd scorecard."
        )
    elif 0.85 <= cl_ratio <= 1.15:
        v, why = Verdict.REVIEW, (
            f"Fairway centerline measures {cl_yd:.0f} yd vs {hole.scorecard_yardage:.0f} yd on "
            f"the scorecard ({cl_ratio:.0%}) — plausible but worth a look (scorecards measure "
            f"along the intended line of play)."
        )
    else:
        v, why = Verdict.FAIL, (
            f"Fairway centerline measures {cl_yd:.0f} yd but the scorecard says "
            f"{hole.scorecard_yardage:.0f} yd ({cl_ratio:.0%}). The traced route does not match "
            f"the published hole length."
        )
    results.append(RuleResult(
        "centerline_vs_scorecard", v, why,
        {"centerline_yd": cl_yd, "scorecard_yd": hole.scorecard_yardage, "ratio": cl_ratio},
    ))

    # -- Centerline endpoints -------------------------------------------------
    start_gap = distance_m(*centerline.coords[0], tee_lat, tee_lon)
    end_ok, end_why = _endpoint_near_green(centerline.coords[-1], green_poly, green_center, proj)
    if start_gap <= 20.0 and end_ok:
        v, why = Verdict.PASS, (
            f"Centerline starts {start_gap:.0f} m from the tee and ends on the green."
        )
    else:
        parts = []
        if start_gap > 20.0:
            parts.append(f"starts {start_gap:.0f} m from the tee (limit 20 m)")
        if not end_ok:
            parts.append(end_why)
        v, why = Verdict.REVIEW, "Centerline " + " and ".join(parts) + "."
    results.append(RuleResult(
        "centerline_endpoints", v, why, {"start_gap_m": start_gap, "end_on_green": end_ok},
    ))

    # -- Par vs yardage plausibility -----------------------------------------
    band = PAR_YARDAGE_BANDS.get(hole.par)
    if band and band[0] <= hole.scorecard_yardage <= band[1]:
        v, why = Verdict.PASS, (
            f"{hole.scorecard_yardage:.0f} yd is a conventional par-{hole.par} length."
        )
    else:
        v, why = Verdict.REVIEW, (
            f"{hole.scorecard_yardage:.0f} yd is unusual for a par {hole.par} "
            f"(typical range {band[0]}-{band[1]} yd)." if band else
            f"Par {hole.par} is not a standard value."
        )
    results.append(RuleResult(
        "par_vs_yardage", v, why, {"par": hole.par, "yardage": hole.scorecard_yardage},
    ))

    # -- Green sanity ---------------------------------------------------------
    if green_poly is None:
        results.append(RuleResult(
            "green_sanity", Verdict.REVIEW,
            "Green is a point, not a polygon — trace the green outline for pin placement "
            "and camera framing.", {},
        ))
    else:
        area = green_poly.area
        problems = []
        verdict = Verdict.PASS
        if not green_poly.is_valid:
            problems.append("the green polygon self-intersects")
            verdict = Verdict.FAIL
        if not (GREEN_AREA_BOUNDS_M2[0] <= area <= GREEN_AREA_BOUNDS_M2[1]):
            problems.append(f"green area {area:.0f} m² is outside the typical 150-2500 m² range")
            verdict = max(verdict, Verdict.REVIEW)
        pin = hole.pin
        if pin is not None:
            pin_xy = proj.to_xy(*pin.point)
            if not green_poly.buffer(1.0).contains(Point(pin_xy)):
                problems.append("the pin is outside the green polygon")
                verdict = Verdict.FAIL
        if problems:
            results.append(RuleResult(
                "green_sanity", verdict, "; ".join(problems).capitalize() + ".",
                {"area_m2": area},
            ))
        else:
            results.append(RuleResult(
                "green_sanity", Verdict.PASS,
                f"Green polygon is valid, {area:.0f} m², pin inside.", {"area_m2": area},
            ))

    # -- Elevation sanity -----------------------------------------------------
    if tee.elevation_m is not None and green.elevation_m is not None:
        delta = abs(tee.elevation_m - green.elevation_m)
        if delta < 60.0:
            v, why = Verdict.PASS, f"Tee-green elevation change is {delta:.1f} m."
        else:
            v, why = Verdict.REVIEW, (
                f"Tee-green elevation change is {delta:.0f} m — unusually large; verify the "
                f"terrain sampling."
            )
        results.append(RuleResult("elevation_sanity", v, why, {"delta_m": delta}))

    # -- Degeneracy -----------------------------------------------------------
    cl_line = LineString([proj.to_xy(lat, lon) for lat, lon in centerline.coords])
    problems = []
    if len(centerline.coords) < 3:
        problems.append(
            f"centerline has only {len(centerline.coords)} vertices — trace the actual "
            f"routing, not a straight line"
        )
    if not cl_line.is_simple:
        problems.append("centerline crosses itself")
    for f in hole.all(FeatureType.BUNKER) + hole.all(FeatureType.WATER):
        if len(f.coords) >= 3 and not _polygon(f.coords, proj).is_valid:
            problems.append(f"{f.type.value} '{f.name or 'unnamed'}' polygon self-intersects")
    if problems:
        results.append(RuleResult(
            "degeneracy", Verdict.FAIL if "crosses" in " ".join(problems) else Verdict.REVIEW,
            "; ".join(problems).capitalize() + ".", {},
        ))
    else:
        results.append(RuleResult(
            "degeneracy", Verdict.PASS, "All geometry is well-formed.", {},
        ))

    return ValidationReport(_hole_label(hole), results)


def _hole_label(hole: HoleGeometry) -> str:
    return f"{hole.course_name} hole {hole.hole_number} ({hole.tee_name} tee)"


def _green_center(hole: HoleGeometry, proj: LocalProjection) -> tuple[float, float]:
    green = hole.green
    assert green is not None
    if len(green.coords) >= 3:
        c = _polygon(green.coords, proj).centroid
        return proj.to_latlon(c.x, c.y)
    return green.coords[0]


def _endpoint_near_green(
    endpoint: tuple[float, float],
    green_poly: Polygon | None,
    green_center: tuple[float, float],
    proj: LocalProjection,
) -> tuple[bool, str]:
    if green_poly is not None:
        inside = green_poly.buffer(15.0).contains(Point(proj.to_xy(*endpoint)))
        return inside, "does not end on or near the green polygon"
    gap = distance_m(*endpoint, *green_center)
    return gap <= 30.0, f"ends {gap:.0f} m from the green center (limit 30 m)"
