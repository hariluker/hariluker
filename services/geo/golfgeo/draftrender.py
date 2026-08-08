"""Draft-tier deterministic flyover renderer (architecture doc §4.2 fallback).

Renders the camera path against the real orthoimagery via planar projection:
the ground is treated as a plane at the hole's mean terrain elevation, and
each frame is a single homography warp of the ortho mosaic. On Brookwood
Hole 1 total relief is < 2 m over 500 m, so planar error is negligible; this
tier exists for instant previews and CPU-only environments. The Blender tier
(real terrain mesh, sun/sky, 3D trees) supersedes it for premium output.

Deterministic by construction: fixed-function numpy/OpenCV math, seeded
grain, pinned encoder settings.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .camera import CameraPath, US_FOOT_M

SKY_TOP = np.array([235, 148, 66], dtype=np.float32)      # BGR: vivid clear blue
SKY_HORIZON = np.array([252, 232, 205], dtype=np.float32) # BGR: bright pale blue


@dataclass
class OrthoPlane:
    """Ortho mosaic + georeferencing for planar rendering (meters frame)."""
    image: np.ndarray            # BGR uint8
    origin_x_ft: float           # EPSG:2967 ft of pixel (0,0) top-left
    origin_y_ft: float
    res_ft: float
    ground_z_m: float            # plane elevation

    @property
    def g_matrix(self) -> np.ndarray:
        """3x3: ortho pixel (u, v, 1) -> world meters (X, Y, 1)."""
        f = US_FOOT_M
        return np.array([
            [self.res_ft * f, 0.0, self.origin_x_ft * f],
            [0.0, -self.res_ft * f, self.origin_y_ft * f],
            [0.0, 0.0, 1.0],
        ])


def intrinsics(width: int, height: int, hfov_deg: float) -> np.ndarray:
    fx = (width / 2.0) / np.tan(np.radians(hfov_deg) / 2.0)
    return np.array([
        [fx, 0.0, width / 2.0],
        [0.0, fx, height / 2.0],
        [0.0, 0.0, 1.0],
    ])


def rotation_world_to_cam(pos, look_at, roll_deg: float) -> np.ndarray:
    """Rows: right, down, forward (pinhole convention), with roll applied."""
    f = np.asarray(look_at, float) - np.asarray(pos, float)
    f /= np.linalg.norm(f)
    up = np.array([0.0, 0.0, 1.0])
    r = np.cross(f, up)
    n = np.linalg.norm(r)
    if n < 1e-9:
        r = np.array([1.0, 0.0, 0.0])
    else:
        r /= n
    u = np.cross(r, f)
    if abs(roll_deg) > 1e-9:
        a = np.radians(roll_deg)
        r, u = np.cos(a) * r + np.sin(a) * u, -np.sin(a) * r + np.cos(a) * u
    return np.stack([r, -u, f])


def render_frame(plane: OrthoPlane, K: np.ndarray, pos, look_at, roll_deg,
                 pin_m=None, haze_start_m: float = 220.0,
                 haze_full_m: float = 900.0,
                 border_bgr: tuple | None = None) -> np.ndarray:
    h, w = int(K[1, 2] * 2), int(K[0, 2] * 2)
    R = rotation_world_to_cam(pos, look_at, roll_deg)
    C = np.asarray(pos, float)
    z0 = plane.ground_z_m

    # Homography: world ground plane -> image, then ortho px -> image.
    M = np.array([
        [1.0, 0.0, -C[0]],
        [0.0, 1.0, -C[1]],
        [0.0, 0.0, z0 - C[2]],
    ])
    H_world = K @ R @ M
    H = H_world @ plane.g_matrix
    if border_bgr is None:
        ground = cv2.warpPerspective(
            plane.image, H, (w, h),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    else:
        ground = cv2.warpPerspective(
            plane.image, H, (w, h), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=border_bgr)

    # Per-pixel ray direction (coarse grid, upsampled) for sky mask + haze.
    step = 8
    us, vs = np.meshgrid(np.arange(0, w, step) + 0.5, np.arange(0, h, step) + 0.5)
    pix = np.stack([us, vs, np.ones_like(us)], axis=-1)
    Kinv = np.linalg.inv(K)
    rays = pix @ Kinv.T @ R  # world-frame directions (rows of R = axes)
    rz = rays[..., 2]
    below = rz < -1e-6
    dist = np.full(rz.shape, haze_full_m, dtype=np.float32)
    dz = z0 - C[2]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(below, dz / rz, np.inf)
    horiz = np.linalg.norm(rays[..., :2], axis=-1)
    dist = np.where(below, np.clip(t * horiz, 0, haze_full_m), haze_full_m
                    ).astype(np.float32)
    sky_frac = np.clip((dist - haze_start_m) / (haze_full_m - haze_start_m), 0, 1)
    sky_frac = cv2.resize(sky_frac, (w, h), interpolation=cv2.INTER_LINEAR)
    ground_mask = cv2.resize(below.astype(np.float32), (w, h),
                             interpolation=cv2.INTER_LINEAR)

    # Sky gradient by ray elevation angle.
    elev = cv2.resize((rz / np.maximum(np.linalg.norm(rays, axis=-1), 1e-9)
                       ).astype(np.float32), (w, h))
    sky_mix = np.clip(elev * 4.0 + 0.15, 0, 1)[..., None]
    sky = SKY_HORIZON * (1 - sky_mix) + SKY_TOP * sky_mix

    out = ground.astype(np.float32)
    haze = sky_frac[..., None]
    out = out * (1 - haze) + SKY_HORIZON * haze
    gm = ground_mask[..., None]
    out = out * gm + sky * (1 - gm)

    # Flagstick at the pin (deterministic 3D overlay).
    if pin_m is not None:
        base = np.array([pin_m[0], pin_m[1], z0])
        top = base + [0.0, 0.0, 2.4]
        pb = K @ (R @ (base - C))
        pt = K @ (R @ (top - C))
        if pb[2] > 1.0 and pt[2] > 1.0:
            pb2, pt2 = (pb[:2] / pb[2]), (pt[:2] / pt[2])
            px_h = abs(pb2[1] - pt2[1])
            if 2.0 < px_h < h and -w <= pb2[0] <= 2 * w:
                thick = max(1, int(px_h / 45))
                cv2.line(out, tuple(np.int32(pb2)), tuple(np.int32(pt2)),
                         (235, 235, 240), thick, cv2.LINE_AA)
                flag = np.array([pt2, pt2 + [px_h * 0.28, px_h * 0.07],
                                 pt2 + [0, px_h * 0.14]], dtype=np.int32)
                cv2.fillPoly(out, [flag], (40, 40, 210), lineType=cv2.LINE_AA)

    return np.clip(out, 0, 255).astype(np.uint8)


def grade(frame: np.ndarray, seed_frame_idx: int, vignette: np.ndarray,
          grain_sigma: float = 2.2) -> np.ndarray:
    """Deterministic broadcast-style grade: S-curve, warmth, vignette, grain."""
    f = frame.astype(np.float32) / 255.0
    # gentle filmic S-curve
    f = np.clip(f * 1.06 - 0.02, 0, 1)
    f = f * f * (3.0 - 2.0 * f) * 0.35 + f * 0.65
    # subtle warmth and turf lift
    f[..., 1] *= 1.03   # green
    f[..., 2] *= 1.02   # red (BGR)
    f = np.clip(f, 0, 1)
    f *= vignette
    rng = np.random.default_rng(9200 + seed_frame_idx)  # seeded per frame
    noise = rng.standard_normal(f.shape[:2]).astype(np.float32) * (grain_sigma / 255.0)
    f = np.clip(f + noise[..., None], 0, 1)
    return (f * 255.0 + 0.5).astype(np.uint8)


def make_vignette(w: int, h: int, strength: float = 0.16) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (x - w / 2) / (w / 2)
    ny = (y - h / 2) / (h / 2)
    r2 = nx * nx + ny * ny
    return (1.0 - strength * np.clip(r2 - 0.25, 0, 1.5) / 1.5)[..., None]


def overlay_lower_third(frame: np.ndarray, text: str, alpha: float) -> np.ndarray:
    """Deterministic text overlay (Hershey font — never AI-generated text)."""
    if alpha <= 0.0:
        return frame
    out = frame.copy()
    h, w = frame.shape[:2]
    scale, thick = h / 1080 * 0.85, max(1, int(h / 1080 * 2))
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, thick)
    x, y = int(w * 0.045), int(h * 0.93)
    ov = out.copy()
    cv2.putText(ov, text, (x + 2, y + 2), cv2.FONT_HERSHEY_DUPLEX, scale,
                (20, 20, 20), thick + 2, cv2.LINE_AA)
    cv2.putText(ov, text, (x, y), cv2.FONT_HERSHEY_DUPLEX, scale,
                (245, 245, 245), thick, cv2.LINE_AA)
    return cv2.addWeighted(ov, alpha, out, 1 - alpha, 0)


def render_video(plane: OrthoPlane, path: CameraPath, pin_m, out_mp4: str,
                 title: str | None = None, progress_every: int = 60) -> dict:
    import subprocess
    import time

    import imageio_ffmpeg

    p = path.params
    K = intrinsics(p.width, p.height, p.hfov_deg)
    vignette = make_vignette(p.width, p.height)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{p.width}x{p.height}", "-r", str(p.fps), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p", "-x264-params", "threads=4",
        "-fflags", "+bitexact", "-flags", "+bitexact", "-map_metadata", "-1",
        "-movflags", "+faststart", out_mp4,
    ]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n = len(path.keyframes)
    for i, k in enumerate(path.keyframes):
        frame = render_frame(plane, K, k.pos, k.look_at, k.roll_deg, pin_m=pin_m)
        frame = grade(frame, i, vignette)
        if title:
            t = k.t
            dur = p.duration
            alpha = min(1.0, t / 0.8) * min(1.0, max(0.0, (dur - 1.0 - t) / 0.8 + 1.0))
            alpha = min(1.0, t / 0.8)
            frame = overlay_lower_third(frame, title, alpha * 0.9)
        proc.stdin.write(frame.tobytes())
        if progress_every and i % progress_every == 0:
            print(f"  frame {i}/{n}")
    proc.stdin.close()
    proc.wait()
    return {"frames": n, "render_s": round(time.time() - t0, 1),
            "camera_checksum": path.checksum}
