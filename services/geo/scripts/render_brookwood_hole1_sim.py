"""Phase 3 (pivoted style): HD simulator-look flyover of Brookwood Hole 1.

Synthesizes the ground from verified geometry (turf, stripes, sand, paths),
places stylized trees from deterministic detection, and flies the same
verified camera path. Usage: python scripts/render_brookwood_hole1_sim.py <data_dir>
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from golfgeo.acquisition import fetch_mosaic, wgs_to_img
from golfgeo.camera import CameraParams, US_FOOT_M, solve_camera_path
from golfgeo.draftrender import (OrthoPlane, intrinsics, make_vignette,
                                 overlay_lower_third, render_frame,
                                 rotation_world_to_cam)
from golfgeo.model import FeatureType
from golfgeo.serialization import load_hole
from golfgeo.simrender import (SimScene, build_ground_texture,
                               detect_trees_ndvi, draw_billboards,
                               extract_path_mask, make_tree_sprites, sim_grade)

BOUNDS = (463450.0, 2091350.0, 465600.0, 2093400.0)
DEM_BOUNDS = (463800.0, 2091450.0, 465450.0, 2092950.0)
TEX_RES_FT = 0.5


def main(data_dir: Path) -> None:
    hole = load_hole(data_dir / "hole1.json")
    t_all = time.time()

    def to_ft(lat, lon):
        return wgs_to_img(lat, lon)

    # Simulator surfaces are authoritative renderings: only owner-confirmed
    # features are painted. Unreviewed suggestions stay editor-only.
    from golfgeo.model import Verification
    features_ft = {
        "centerline": [to_ft(*p) for p in hole.centerline.coords],
        "green": [to_ft(*p) for p in hole.green.coords],
        "bunkers": [[to_ft(*p) for p in b.coords]
                    for b in hole.all(FeatureType.BUNKER)
                    if b.verification == Verification.CONFIRMED],
        "tee": to_ft(*hole.tee.point),
    }
    pin_ft = to_ft(*hole.pin.point)
    pin_m = (pin_ft[0] * US_FOOT_M, pin_ft[1] * US_FOOT_M)

    print("fetch ortho (for path extraction + NDVI trees)...")
    ortho = fetch_mosaic(BOUNDS, 2024, 1.0)
    bgr = np.ascontiguousarray(np.transpose(ortho.array[:3], (1, 2, 0))[..., ::-1])
    r = ortho.array[0].astype(np.float32)
    nir = ortho.array[3].astype(np.float32)
    ndvi = (nir - r) / (nir + r + 1e-6)

    print("fetch DEM...")
    dem = fetch_mosaic(DEM_BOUNDS, 2017, 2.5, dem=True)
    dem_arr = dem.array[0].astype(np.float32) * US_FOOT_M
    inv = ~dem.transform

    def ground_z(x_m, y_m):
        col, row = inv * (x_m / US_FOOT_M, y_m / US_FOOT_M)
        rr = int(np.clip(round(row), 0, dem_arr.shape[0] - 1))
        cc = int(np.clip(round(col), 0, dem_arr.shape[1] - 1))
        return float(dem_arr[rr, cc])

    cl_m = [(x * US_FOOT_M, y * US_FOOT_M) for x, y in features_ft["centerline"]]
    plane_z = float(np.mean([ground_z(*p) for p in cl_m]))

    print("detect trees (NDVI)...")
    trees = detect_trees_ndvi(ndvi, BOUNDS, 1.0, BOUNDS)
    print(f"  {len(trees)} trees")

    # Cart-path extraction disabled: dormant winter turf defeats the gray
    # classifier (Phase 1 lesson re-confirmed — detection is suggestion-tier).
    # Paths return when traced/verified vectors exist.
    print("build ground texture...")
    tex = build_ground_texture(BOUNDS, TEX_RES_FT, features_ft,
                               path_mask=None, trees=trees)

    # 3D relief: shade the turf with a hillshade of the real lidar terrain so
    # mounds, green complexes and swales read in 3D.
    gy, gx = np.gradient(dem.array[0].astype(np.float32), 2.5)
    az, alt = np.radians(315), np.radians(50)
    slope = np.arctan(np.hypot(gx, gy) * 1.8)          # relief exaggeration
    aspect = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    hs = np.clip(0.78 + 0.5 * (hs - hs.mean()), 0.72, 1.12).astype(np.float32)
    shade = np.ones(tex.shape[:2], np.float32)
    c0 = int((DEM_BOUNDS[0] - BOUNDS[0]) / TEX_RES_FT)
    r0 = int((BOUNDS[3] - DEM_BOUNDS[3]) / TEX_RES_FT)
    hs_big = cv2.resize(hs, (int((DEM_BOUNDS[2] - DEM_BOUNDS[0]) / TEX_RES_FT),
                             int((DEM_BOUNDS[3] - DEM_BOUNDS[1]) / TEX_RES_FT)),
                        interpolation=cv2.INTER_CUBIC)
    shade[r0:r0 + hs_big.shape[0], c0:c0 + hs_big.shape[1]] = hs_big
    shade = cv2.GaussianBlur(shade, (0, 0), 2.0)
    tex = np.clip(tex.astype(np.float32) * (0.9 + 0.35 * (shade - 0.72) / 0.4
                                            )[..., None], 0, 255).astype(np.uint8)
    cv2.imwrite(str(data_dir / "sim-ground-texture.jpg"), tex,
                [cv2.IMWRITE_JPEG_QUALITY, 90])

    # Low "tree-height" flight profile per owner direction.
    params = CameraParams(par=hole.par, start_back_m=35.0, start_agl_m=12.0,
                          cruise_agl_m=32.0, green_agl_m=22.0, end_agl_m=16.0,
                          lead_scale=0.75)
    path = solve_camera_path(cl_m, pin_m, ground_z, params)
    scene = SimScene(texture=tex, origin_x_ft=BOUNDS[0], origin_y_ft=BOUNDS[3],
                     res_ft=TEX_RES_FT, ground_z_m=plane_z, trees=trees,
                     sprites=make_tree_sprites())
    plane = OrthoPlane(image=tex, origin_x_ft=BOUNDS[0], origin_y_ft=BOUNDS[3],
                       res_ft=TEX_RES_FT, ground_z_m=plane_z)
    K = intrinsics(params.width, params.height, params.hfov_deg)
    vignette = make_vignette(params.width, params.height)
    title = (f"{hole.course_name.upper()}   HOLE {hole.hole_number} · "
             f"PAR {hole.par} · {hole.scorecard_yardage:.0f} YDS")

    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_mp4 = str(data_dir / "hole1-flyover-sim.mp4")
    cmd = [ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{params.width}x{params.height}", "-r", str(params.fps),
           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-x264-params", "threads=4",
           "-fflags", "+bitexact", "-flags", "+bitexact", "-map_metadata", "-1",
           "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    from golfgeo.simrender import COL
    border = tuple(float(c) for c in COL["outer"])
    for i, k in enumerate(path.keyframes):
        frame = render_frame(plane, K, k.pos, k.look_at, k.roll_deg, pin_m=None,
                             haze_start_m=240.0, haze_full_m=750.0,
                             border_bgr=border)
        R = rotation_world_to_cam(k.pos, k.look_at, k.roll_deg)
        frame = draw_billboards(frame, K, R, np.asarray(k.pos), scene, pin_m)
        frame = sim_grade(frame, vignette)
        frame = overlay_lower_third(frame, title, min(1.0, k.t / 0.8) * 0.9)
        proc.stdin.write(frame.tobytes())
        if i % 60 == 0:
            print(f"  frame {i}/{len(path.keyframes)}")
    proc.stdin.close()
    proc.wait()
    stats = {"frames": len(path.keyframes), "trees": len(trees),
             "render_s": round(time.time() - t0, 1),
             "total_s": round(time.time() - t_all, 1),
             "camera_checksum": path.checksum}
    (data_dir / "hole1-sim-stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
