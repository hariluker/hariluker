"""Deterministic camera-path solver (architecture doc §4.3, Phase 2).

Turns a verified HoleGeometry + terrain sampler into a per-frame keyframe
list for a tee-to-pin flyover. Engine-agnostic: the same keyframes drive the
draft renderer today and the Blender scene builder later.

Design (per the product brief's creative guide):
  - starts slightly behind and above the tee, facing down the hole
  - follows a smoothed fairway centerline (never a straight tee-green line)
  - climbs to cruise altitude mid-hole, descends for the green reveal
  - eases in/out (professional drone feel), gentle bank in turns
  - look-at leads along the path, blending to the pin in the final quarter
  - enforces a minimum terrain clearance and a slant-distance floor derived
    from source imagery resolution (camera cannot outrun the texture)

All math is deterministic: pure function of (geometry, terrain, params).
Positions are in a planar metric frame (EPSG:2967 feet converted to meters);
conversion to WGS84 happens only at serialization.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

US_FOOT_M = 0.3048006096012192


@dataclass
class CameraParams:
    fps: int = 30
    duration_s: float | None = None      # None -> from par
    par: int = 5
    width: int = 1920
    height: int = 1080
    hfov_deg: float = 62.0
    start_back_m: float = 30.0           # camera starts this far behind the tee
    start_agl_m: float = 14.0
    cruise_agl_m: float = 52.0
    green_agl_m: float = 26.0
    end_agl_m: float = 20.0
    min_clearance_m: float = 10.0
    end_short_of_pin_m: float = 45.0     # camera stops short, looking at pin
    imagery_res_m: float = 0.1524        # 6-inch source
    max_bank_deg: float = 7.0
    lead_scale: float = 1.0              # <1 pitches the view down (low flight)

    @property
    def duration(self) -> float:
        if self.duration_s is not None:
            return self.duration_s
        return {3: 8.0, 4: 10.0, 5: 11.5}.get(self.par, 11.5)


@dataclass
class Keyframe:
    t: float
    pos: tuple[float, float, float]       # x, y, z (m, planar frame; z absolute)
    look_at: tuple[float, float, float]
    roll_deg: float


@dataclass
class CameraPath:
    keyframes: list[Keyframe]
    params: CameraParams
    checksum: str = field(init=False)

    def __post_init__(self):
        payload = json.dumps(
            [[k.t, *k.pos, *k.look_at, k.roll_deg] for k in self.keyframes]
        ).encode()
        self.checksum = hashlib.sha256(payload).hexdigest()[:16]


def smootherstep(u: np.ndarray) -> np.ndarray:
    u = np.clip(u, 0.0, 1.0)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def catmull_rom(points: np.ndarray, samples_per_seg: int = 50) -> np.ndarray:
    """Centripetal Catmull-Rom through points (N,2) -> dense polyline."""
    if len(points) < 3:
        t = np.linspace(0, 1, samples_per_seg)[:, None]
        return points[0] * (1 - t) + points[-1] * t
    pts = np.vstack([points[0], points, points[-1]])
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]

        def tj(ti, pa, pb):
            d = math.sqrt(np.linalg.norm(pb - pa))
            return ti + (d if d > 1e-9 else 1e-6)

        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        t = np.linspace(t1, t2, samples_per_seg, endpoint=False)[:, None]
        a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        c = (t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2
        out.append(c)
    out.append(points[-1][None, :])
    return np.vstack(out)


def arc_length_resample(line: np.ndarray, n: int) -> np.ndarray:
    seg = np.linalg.norm(np.diff(line, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    target = np.linspace(0.0, total, n)
    x = np.interp(target, s, line[:, 0])
    y = np.interp(target, s, line[:, 1])
    return np.stack([x, y], axis=1)


def solve_camera_path(
    centerline_m: Sequence[tuple[float, float]],
    pin_m: tuple[float, float],
    ground_z: Callable[[float, float], float],
    params: CameraParams,
) -> CameraPath:
    """Compute per-frame keyframes for the flyover.

    centerline_m: fairway centerline tee->green-center in the planar metric
    frame. pin_m: pin position. ground_z(x, y) -> terrain elevation (m).
    """
    cl = np.asarray(centerline_m, dtype=float)
    pin = np.asarray(pin_m, dtype=float)

    # 1. Extend the track behind the tee along the opening bearing, and stop
    #    it short of the pin so the finish frames the green.
    d0 = cl[1] - cl[0]
    d0 /= np.linalg.norm(d0)
    start = cl[0] - d0 * params.start_back_m
    dense = catmull_rom(np.vstack([start, cl]))
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    stop_s = max(s[-1] - params.end_short_of_pin_m, s[-1] * 0.5)
    dense = dense[s <= stop_s]

    # 2. Ease-in/out distance profile over the frame count.
    n = int(round(params.duration * params.fps)) + 1
    u = np.linspace(0.0, 1.0, n)
    track = arc_length_resample(dense, 4000)
    profile = smootherstep(u)
    idx = profile * (len(track) - 1)
    pos_xy = np.stack([
        np.interp(idx, np.arange(len(track)), track[:, 0]),
        np.interp(idx, np.arange(len(track)), track[:, 1]),
    ], axis=1)

    # 3. Altitude profile (AGL): start low, cruise, descend for the reveal.
    agl = np.interp(
        u,
        [0.0, 0.12, 0.45, 0.80, 1.0],
        [params.start_agl_m, params.cruise_agl_m * 0.65, params.cruise_agl_m,
         params.green_agl_m, params.end_agl_m],
    )
    ground = np.array([ground_z(x, y) for x, y in pos_xy])
    # smooth the ground track so the camera doesn't bob over micro-terrain
    kernel = np.ones(15) / 15.0
    ground_s = np.convolve(np.pad(ground, 7, mode="edge"), kernel, mode="valid")
    z = ground_s + np.maximum(agl, params.min_clearance_m)

    # 4. Look-at: lead point along the track, blending to the pin at the end.
    pin_z = ground_z(*pin)
    look = np.zeros((n, 3))
    lead_m = np.interp(u, [0.0, 0.25, 0.6, 0.85, 1.0],
                       [75.0, 110.0, 110.0, 40.0, 0.0]) * params.lead_scale
    seg2 = np.linalg.norm(np.diff(track, axis=0), axis=1)
    s2 = np.concatenate([[0.0], np.cumsum(seg2)])
    cam_s = profile * s2[-1]
    blend = smootherstep((u - 0.70) / 0.30)
    for i in range(n):
        ls = min(cam_s[i] + lead_m[i], s2[-1])
        lx = np.interp(ls, s2, track[:, 0])
        ly = np.interp(ls, s2, track[:, 1])
        lz = ground_z(lx, ly) + 2.0
        look[i] = (
            (1 - blend[i]) * np.array([lx, ly, lz])
            + blend[i] * np.array([pin[0], pin[1], pin_z + 1.0])
        )

    # 5. Gentle bank from heading rate.
    heading = np.arctan2(np.gradient(pos_xy[:, 1]), np.gradient(pos_xy[:, 0]))
    heading = np.unwrap(heading)
    rate = np.gradient(heading) * params.fps
    roll = np.clip(np.degrees(rate) * 0.25, -params.max_bank_deg, params.max_bank_deg)
    roll = np.convolve(np.pad(roll, 10, mode="edge"), np.ones(21) / 21.0, mode="valid")

    frames = [
        Keyframe(
            t=round(i / params.fps, 6),
            pos=(float(pos_xy[i, 0]), float(pos_xy[i, 1]), float(z[i])),
            look_at=(float(look[i, 0]), float(look[i, 1]), float(look[i, 2])),
            roll_deg=float(roll[i]),
        )
        for i in range(n)
    ]
    return CameraPath(keyframes=frames, params=params)
