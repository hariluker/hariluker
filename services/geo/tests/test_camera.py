"""Camera-path solver tests: clearance, smoothness, determinism, framing."""

import numpy as np
import pytest

from golfgeo.camera import CameraParams, solve_camera_path

# A synthetic dogleg centerline in meters, ~480 m long.
CL = [(0.0, 0.0), (120.0, 60.0), (240.0, 130.0), (330.0, 230.0), (390.0, 340.0)]
PIN = (395.0, 350.0)


def flat_ground(x, y):
    return 240.0


def rolling_ground(x, y):
    return 240.0 + 3.0 * np.sin(x / 60.0) + 2.0 * np.cos(y / 45.0)


@pytest.fixture()
def path():
    return solve_camera_path(CL, PIN, flat_ground, CameraParams(par=5))


def test_frame_count_matches_duration(path):
    p = path.params
    assert len(path.keyframes) == int(p.duration * p.fps) + 1
    assert path.keyframes[-1].t == pytest.approx(p.duration, abs=0.02)


def test_starts_behind_tee_facing_down_hole(path):
    k0 = path.keyframes[0]
    tee = np.array(CL[0])
    pos0 = np.array(k0.pos[:2])
    # behind the tee relative to the opening direction
    d0 = np.array(CL[1]) - tee
    assert np.dot(pos0 - tee, d0) < 0
    # looking toward the hole, not backwards
    look = np.array(k0.look_at[:2])
    assert np.dot(look - pos0, d0) > 0


def test_terrain_clearance(path):
    for k in path.keyframes:
        assert k.pos[2] - flat_ground(*k.pos[:2]) >= path.params.min_clearance_m


def test_terrain_clearance_rolling():
    p = solve_camera_path(CL, PIN, rolling_ground, CameraParams(par=5))
    for k in p.keyframes:
        assert k.pos[2] - rolling_ground(*k.pos[:2]) >= 5.0  # smoothing tolerance


def test_finishes_looking_at_pin(path):
    k = path.keyframes[-1]
    assert k.look_at[0] == pytest.approx(PIN[0], abs=1.0)
    assert k.look_at[1] == pytest.approx(PIN[1], abs=1.0)
    # camera stops short of the pin
    d = np.hypot(k.pos[0] - PIN[0], k.pos[1] - PIN[1])
    assert d >= path.params.end_short_of_pin_m * 0.6


def test_smooth_motion(path):
    pos = np.array([k.pos for k in path.keyframes])
    speed = np.linalg.norm(np.diff(pos[:, :2], axis=0), axis=1) * path.params.fps
    accel = np.diff(speed) * path.params.fps
    assert speed[0] < 8.0 and speed[-1] < 8.0       # eases in and out
    assert speed.max() > 30.0                        # actually flies
    assert np.abs(accel).max() < 25.0                # no jerks


def test_bank_limits(path):
    for k in path.keyframes:
        assert abs(k.roll_deg) <= path.params.max_bank_deg + 1e-6


def test_deterministic():
    a = solve_camera_path(CL, PIN, flat_ground, CameraParams(par=5))
    b = solve_camera_path(CL, PIN, flat_ground, CameraParams(par=5))
    assert a.checksum == b.checksum


def test_duration_by_par():
    assert CameraParams(par=3).duration == 8.0
    assert CameraParams(par=4).duration == 10.0
    assert CameraParams(par=5).duration == 11.5
    assert CameraParams(par=5, duration_s=9.0).duration == 9.0
