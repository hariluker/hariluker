"""Simulator-style renderer ("HD golf sim" look, product-owner directed).

Instead of draping the orthophoto, the ground texture is SYNTHESIZED from the
verified hole geometry: fairway corridor with mow stripes, bright green with
fringe, clean bunker sand, tee pad, cart paths (extracted deterministically
from imagery), rough gradients, and baked tree shadows. Trees are stylized
billboard sprites placed by deterministic detection. Accuracy contract holds:
every surface position comes from verified vectors + real terrain; only the
*look* is synthetic.

Deterministic: seeded value-noise, fixed-function OpenCV, pinned encode.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from scipy.spatial import cKDTree

from .camera import US_FOOT_M

# ---- palette (BGR float 0-255) ---------------------------------------------
COL = {
    "outer":    np.array([60, 108, 92], np.float32),    # muted olive surround
    "rough":    np.array([58, 122, 74], np.float32),
    "fw_light": np.array([84, 168, 96], np.float32),
    "fw_dark":  np.array([66, 148, 80], np.float32),
    "fringe":   np.array([88, 176, 104], np.float32),
    "gr_light": np.array([110, 200, 122], np.float32),
    "gr_dark":  np.array([96, 184, 108], np.float32),
    "tee":      np.array([92, 178, 100], np.float32),
    "sand":     np.array([168, 214, 232], np.float32),
    "sand_rim": np.array([120, 170, 196], np.float32),
    "path":     np.array([176, 178, 180], np.float32),
    "trunk":    np.array([48, 74, 96], np.float32),
    "conifer":  np.array([46, 96, 40], np.float32),
    "conifer2": np.array([56, 116, 52], np.float32),
}
SUN_DIR_TEX = np.array([0.55, -0.45])   # shadow offset direction in tex px (E, S->N flip handled)


def value_noise(shape, scales, seed, amp=1.0):
    """Deterministic multi-octave smooth noise in [-amp, amp]."""
    rng = np.random.default_rng(seed)
    out = np.zeros(shape, np.float32)
    for i, s in enumerate(scales):
        g = rng.standard_normal((max(2, shape[0] // s), max(2, shape[1] // s))
                                ).astype(np.float32)
        out += cv2.resize(g, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC
                          ) / (2 ** i)
    out /= np.abs(out).max() + 1e-6
    return out * amp


@dataclass
class SimScene:
    texture: np.ndarray          # BGR uint8 ground texture
    origin_x_ft: float
    origin_y_ft: float
    res_ft: float
    ground_z_m: float
    trees: list                  # (x_m, y_m, height_m, radius_m, kind)
    sprites: dict                # kind -> list of BGRA sprites


def chaikin(poly, iters: int = 3) -> np.ndarray:
    """Corner-cutting smoothing -> organic blob outlines from coarse traces."""
    p = np.asarray(poly, np.float64)
    for _ in range(iters):
        nxt = np.roll(p, -1, axis=0)
        a = 0.75 * p + 0.25 * nxt
        b = 0.25 * p + 0.75 * nxt
        p = np.empty((len(p) * 2, 2))
        p[0::2] = a
        p[1::2] = b
    return p


def _to_px(pts_ft, origin_x, origin_y, res):
    a = np.asarray(pts_ft, np.float64)
    return np.stack([(a[:, 0] - origin_x) / res,
                     (origin_y - a[:, 1]) / res], axis=1).astype(np.int32)


def build_ground_texture(bounds_ft, res_ft, features_ft, path_mask=None,
                         trees=None, seed=92) -> np.ndarray:
    """features_ft: dict with 'centerline' [(x,y)...], 'green' poly,
    'bunkers' [poly...], 'tee' (x,y). All EPSG:2967 ft."""
    minx, miny, maxx, maxy = bounds_ft
    w = int((maxx - minx) / res_ft)
    h = int((maxy - miny) / res_ft)
    ox, oy = minx, maxy

    img = np.zeros((h, w, 3), np.float32)
    img[:] = COL["outer"]

    # dense centerline + distance fields (for corridor + stripes)
    cl = np.asarray(features_ft["centerline"], np.float64)
    seg = np.linalg.norm(np.diff(cl, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    dense_s = np.arange(0, s[-1], 2.0)
    dx = np.interp(dense_s, s, cl[:, 0])
    dy = np.interp(dense_s, s, cl[:, 1])
    dense = np.stack([dx, dy], axis=1)
    tree_q = cKDTree(dense)

    yy, xx = np.mgrid[0:h, 0:w]
    px_ft = np.stack([ox + (xx.ravel() + 0.5) * res_ft,
                      oy - (yy.ravel() + 0.5) * res_ft], axis=1)
    dist, idx = tree_q.query(px_ft, workers=4)
    dist = dist.reshape(h, w).astype(np.float32)
    along = dense_s[idx].reshape(h, w).astype(np.float32)

    FT = 1 / US_FOOT_M  # ft per m
    rough_r, fw_r = 42 * FT, 17 * FT
    # rough ring
    img[dist < rough_r] = COL["rough"]
    # fairway with mow stripes (9 m bands), tapered ends
    taper = np.clip((along - 120.0) / 150.0, 0.35, 1.0) \
        * np.clip((dense_s[-1] - along - 30.0) / 120.0 * 0.6 + 0.4, 0.4, 1.0)
    fw_mask = dist < fw_r * taper
    stripe = ((along * US_FOOT_M * res_ft / res_ft // 9).astype(np.int32) % 2
              ).astype(np.float32)
    img[fw_mask & (stripe > 0.5)] = COL["fw_light"]
    img[fw_mask & (stripe <= 0.5)] = COL["fw_dark"]

    # green: fringe ring then checker
    green = chaikin(features_ft["green"], 3)
    gpx = _to_px(green, ox, oy, res_ft)
    fringe = np.zeros((h, w), np.uint8)
    cv2.fillPoly(fringe, [gpx], 1)
    ker = np.ones((int(9 / res_ft) | 1,) * 2, np.uint8)
    fringe_d = cv2.dilate(fringe, ker)
    img[fringe_d > 0] = COL["fringe"]
    gc = green.mean(axis=0)
    u = (px_ft[:, 0] - gc[0]).reshape(h, w)
    v = (px_ft[:, 1] - gc[1]).reshape(h, w)
    checker = (((u + v) // (10 * FT * res_ft / res_ft * 0.3)).astype(np.int32)
               + ((u - v) // (10 * FT * 0.3)).astype(np.int32)) % 2
    gmask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(gmask, [gpx], 1)
    img[(gmask > 0) & (checker == 0)] = COL["gr_light"]
    img[(gmask > 0) & (checker == 1)] = COL["gr_dark"]

    # tee pad: oval aligned to opening bearing
    tee = np.asarray(features_ft["tee"], np.float64)
    d0 = dense[5] - dense[0]
    ang = np.degrees(np.arctan2(-(d0[1]), d0[0]))
    cv2.ellipse(img, (int((tee[0] - ox) / res_ft), int((oy - tee[1]) / res_ft)),
                (int(16 * FT / res_ft), int(8 * FT / res_ft)), ang, 0, 360,
                COL["tee"].tolist(), -1, cv2.LINE_AA)

    # cart paths from imagery mask (deterministic classical extraction)
    if path_mask is not None:
        pm = cv2.resize(path_mask.astype(np.uint8), (w, h),
                        interpolation=cv2.INTER_NEAREST) > 0
        img[pm] = COL["path"]

    # bunkers: rim, sand, inner shading (smoothed to organic outlines)
    for poly in features_ft["bunkers"]:
        bpx = _to_px(chaikin(poly, 3), ox, oy, res_ft)
        cv2.polylines(img, [bpx], True, COL["sand_rim"].tolist(),
                      max(2, int(3 / res_ft)), cv2.LINE_AA)
        cv2.fillPoly(img, [bpx], COL["sand"].tolist(), cv2.LINE_AA)

    # baked tree shadows (sun from SW -> shadows to NE)
    if trees:
        sh = np.ones((h, w), np.float32)
        for (tx, ty, th, tr, kind) in trees:
            cx = int((tx / US_FOOT_M - ox) / res_ft + tr * FT * 0.9 / res_ft)
            cy = int((oy - ty / US_FOOT_M) / res_ft - tr * FT * 0.5 / res_ft)
            r = max(2, int(tr * FT / res_ft))
            cv2.ellipse(sh, (cx, cy), (int(r * 1.5), int(r * 0.9)), -25, 0, 360,
                        0.72, -1, cv2.LINE_AA)
        sh = cv2.GaussianBlur(sh, (0, 0), 2.5)
        img *= sh[..., None]

    # texture variation
    img *= (1.0 + value_noise((h, w), [160, 40, 12], seed, 0.05))[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def extract_path_mask(ortho_bgr: np.ndarray, sand_protect: np.ndarray | None
                      ) -> np.ndarray:
    """Classical gray-surface extraction: low saturation, mid-high value."""
    hsv = cv2.cvtColor(ortho_bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[..., 1].astype(np.float32), hsv[..., 2].astype(np.float32)
    mask = (s < 40) & (v > 120) & (v < 235)
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN,
                            np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros_like(mask)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        wdt, hgt = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        # paths are long/thin: large bbox, modest fill ratio
        if area > 400 and max(wdt, hgt) > 80 and area / (wdt * hgt + 1) < 0.45:
            keep[lab == i] = 1
    if sand_protect is not None:
        keep[sand_protect > 0] = 0
    return keep


def detect_trees_ndvi(ndvi: np.ndarray, bounds_ft, res_ft, aoi_bounds_ft,
                      thr_pct=97.0):
    """Conifer detection from leaf-off NDVI; returns (x_m, y_m, h_m, r_m, kind)."""
    from scipy import ndimage as ndi
    minx, miny, maxx, maxy = bounds_ft
    thr = np.percentile(ndvi, thr_pct)
    mask = ndi.binary_opening(ndvi > thr, iterations=1)
    labels, n = ndi.label(mask)
    trees = []
    a0, b0, a1, b1 = aoi_bounds_ft
    for sl, i in zip(ndi.find_objects(labels), range(1, n + 1)):
        blob = labels[sl] == i
        area_px = int(blob.sum())
        area_m2 = area_px * (res_ft * US_FOOT_M) ** 2
        if not (6.0 <= area_m2 <= 700.0):
            continue
        cy, cx = ndi.center_of_mass(blob)
        x_ft = minx + (sl[1].start + cx) * res_ft
        y_ft = maxy - (sl[0].start + cy) * res_ft
        if not (a0 <= x_ft <= a1 and b0 <= y_ft <= b1):
            continue
        r_m = min(np.sqrt(area_m2 / np.pi), 5.5)
        # large blobs = clumps: emit as one bigger billboard
        h_m = float(np.clip(2.4 * r_m + 3.0, 5.0, 17.0))
        trees.append((x_ft * US_FOOT_M, y_ft * US_FOOT_M, h_m, float(r_m),
                      "conifer"))
    trees.sort(key=lambda t: (t[0], t[1]))
    return trees


def make_tree_sprites(seed=7) -> dict:
    """Pre-rendered stylized BGRA sprites (deterministic)."""
    rng = np.random.default_rng(seed)
    sprites = {"conifer": []}
    for variant in range(3):
        w, h = 256, 384
        img = np.zeros((h, w, 4), np.float32)
        trunk_w = 14 + rng.integers(0, 6)
        cv2.rectangle(img, (w // 2 - trunk_w // 2, h - 60),
                      (w // 2 + trunk_w // 2, h - 4),
                      (*COL["trunk"].tolist(), 255), -1)
        layers = 6
        for i in range(layers):
            frac = i / (layers - 1)
            cy = int(30 + frac * (h - 120))
            half = int((28 + frac * 92) * (1 + rng.uniform(-0.06, 0.06)))
            col = COL["conifer"] * (1 - frac * 0.35) + COL["conifer2"] * (frac * 0.35)
            shade = 0.85 + 0.3 * (1 - frac)
            pts = np.array([[w // 2 - half, cy + 70], [w // 2 + half, cy + 70],
                            [w // 2 + rng.integers(-8, 9), cy - 26]], np.int32)
            cv2.fillPoly(img, [pts], (*(col * shade).tolist(), 255), cv2.LINE_AA)
        img = cv2.GaussianBlur(img, (3, 3), 0)
        sprites["conifer"].append(np.clip(img, 0, 255).astype(np.uint8))
    return sprites


def draw_billboards(frame: np.ndarray, K, R, C, scene: SimScene, pin_m,
                    flag_len_m=2.6):
    """Z-sorted stylized trees + flagstick composited over the ground pass."""
    h, w = frame.shape[:2]
    items = []
    for j, (tx, ty, th, tr, kind) in enumerate(scene.trees):
        base = np.array([tx, ty, scene.ground_z_m])
        cam = R @ (base - C)
        if cam[2] < 3.0:
            continue
        items.append((cam[2], "tree", j, base))
    pin_base = np.array([pin_m[0], pin_m[1], scene.ground_z_m])
    pcam = R @ (pin_base - C)
    if pcam[2] > 1.0:
        items.append((pcam[2], "flag", 0, pin_base))
    items.sort(key=lambda it: -it[0])

    fy = K[1, 1]
    out = frame
    for dist, kind, j, base in items:
        if kind == "flag":
            top = base + [0, 0, flag_len_m]
            pb, pt = K @ (R @ (base - C)), K @ (R @ (top - C))
            pb2, pt2 = pb[:2] / pb[2], pt[:2] / pt[2]
            ph = abs(pb2[1] - pt2[1])
            if 2 < ph < h * 2:
                cv2.line(out, tuple(np.int32(pb2)), tuple(np.int32(pt2)),
                         (240, 240, 245), max(1, int(ph / 40)), cv2.LINE_AA)
                flag = np.array([pt2, pt2 + [ph * 0.30, ph * 0.08],
                                 pt2 + [0, ph * 0.16]], dtype=np.int32)
                cv2.fillPoly(out, [flag], (36, 36, 214), lineType=cv2.LINE_AA)
            continue
        tx, ty, th, tr, tkind = scene.trees[j]
        sprite = scene.sprites[tkind][j % len(scene.sprites[tkind])]
        top = base + [0, 0, th]
        pb = K @ (R @ (base - C))
        pt = K @ (R @ (top - C))
        pb2, pt2 = pb[:2] / pb[2], pt[:2] / pt[2]
        ph = pb2[1] - pt2[1]
        if ph < 2 or pb2[1] < -50 or pt2[1] > h + 50:
            continue
        pw = ph * sprite.shape[1] / sprite.shape[0] * (tr / (th * 0.28))
        pw = min(pw, w * 1.5)
        x0 = int(pb2[0] - pw / 2)
        y0 = int(pt2[1])
        x1, y1 = int(x0 + pw), int(pb2[1])
        if x1 <= 0 or x0 >= w or y1 <= 0 or y0 >= h or x1 - x0 < 1 or y1 - y0 < 2:
            continue
        sp = cv2.resize(sprite, (max(1, x1 - x0), max(1, y1 - y0)),
                        interpolation=cv2.INTER_AREA)
        sx0, sy0 = max(0, -x0), max(0, -y0)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(w, x1), min(h, y1)
        sp = sp[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
        if sp.size == 0:
            continue
        alpha = (sp[..., 3:4].astype(np.float32) / 255.0)
        # distance haze on far trees
        haze = np.clip((dist - 260.0) / 700.0, 0, 0.55)
        col = sp[..., :3].astype(np.float32) * (1 - haze) + \
            np.array([226, 223, 216], np.float32) * haze
        region = out[dy0:dy1, dx0:dx1].astype(np.float32)
        out[dy0:dy1, dx0:dx1] = (region * (1 - alpha) + col * alpha
                                 ).astype(np.uint8)
    return out


def sim_grade(frame: np.ndarray, vignette: np.ndarray) -> np.ndarray:
    """Clean HD-sim grade: saturation lift, crisp S-curve, light vignette."""
    f = frame.astype(np.float32) / 255.0
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.22, 0, 1)
    f = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    f = np.clip(f * 1.05 - 0.015, 0, 1)
    f = f * f * (3 - 2 * f) * 0.30 + f * 0.70
    sharp = cv2.GaussianBlur(f, (0, 0), 1.2)
    f = np.clip(f + (f - sharp) * 0.45, 0, 1)
    f *= (1.0 - (1.0 - vignette) * 0.6)
    return (f * 255 + 0.5).astype(np.uint8)
