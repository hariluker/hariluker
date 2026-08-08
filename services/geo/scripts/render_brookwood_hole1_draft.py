"""Phase 2: deterministic draft-tier flyover render of Brookwood Hole 1.

Reads the verified hole1.json, solves the camera path, renders the flyover
against the 2024 IGIO orthoimagery, and writes an H.264 MP4 plus the camera
keyframes JSON (the same keyframes later drive the Blender tier).

Usage: python scripts/render_brookwood_hole1_draft.py <data_dir>
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from golfgeo.acquisition import fetch_mosaic, wgs_to_img
from golfgeo.camera import CameraParams, US_FOOT_M, solve_camera_path
from golfgeo.draftrender import OrthoPlane, render_video
from golfgeo.serialization import load_hole

ORTHO_BOUNDS = (463450.0, 2091350.0, 465600.0, 2093400.0)
DEM_BOUNDS = (463800.0, 2091450.0, 465450.0, 2092950.0)
YEAR_ORTHO, YEAR_DEM = 2024, 2017


def main(data_dir: Path) -> None:
    hole = load_hole(data_dir / "hole1.json")
    timings = {}

    t0 = time.time()
    print("fetching ortho mosaic...")
    ortho = fetch_mosaic(ORTHO_BOUNDS, YEAR_ORTHO, 0.5)
    rgb = np.transpose(ortho.array[:3], (1, 2, 0))
    bgr = np.ascontiguousarray(rgb[..., ::-1])
    timings["imagery_s"] = round(time.time() - t0, 1)

    t0 = time.time()
    print("fetching DEM...")
    dem = fetch_mosaic(DEM_BOUNDS, YEAR_DEM, 2.5, dem=True)
    dem_arr = dem.array[0].astype(np.float32) * US_FOOT_M
    inv = ~dem.transform

    def ground_z_m(x_m: float, y_m: float) -> float:
        col, row = inv * (x_m / US_FOOT_M, y_m / US_FOOT_M)
        r = int(np.clip(round(row), 0, dem_arr.shape[0] - 1))
        c = int(np.clip(round(col), 0, dem_arr.shape[1] - 1))
        return float(dem_arr[r, c])

    timings["terrain_s"] = round(time.time() - t0, 1)

    # geometry -> planar meters
    t0 = time.time()
    def to_m(lat, lon):
        x, y = wgs_to_img(lat, lon)
        return (x * US_FOOT_M, y * US_FOOT_M)

    cl_m = [to_m(*p) for p in hole.centerline.coords]
    pin_m = to_m(*hole.pin.point)
    plane_z = float(np.mean([ground_z_m(*p) for p in cl_m]))

    params = CameraParams(par=hole.par)
    path = solve_camera_path(cl_m, pin_m, ground_z_m, params)
    (data_dir / "hole1-camera-path.json").write_text(json.dumps({
        "algorithm_version": "draft-1",
        "params": params.__dict__,
        "checksum": path.checksum,
        "keyframes": [
            {"t": k.t, "pos": k.pos, "look_at": k.look_at, "roll_deg": k.roll_deg}
            for k in path.keyframes
        ],
    }, indent=1) + "\n")
    timings["camera_s"] = round(time.time() - t0, 1)
    print(f"camera path: {len(path.keyframes)} frames, "
          f"duration {params.duration}s, checksum {path.checksum}")

    plane = OrthoPlane(
        image=bgr,
        origin_x_ft=ORTHO_BOUNDS[0],
        origin_y_ft=ORTHO_BOUNDS[3],
        res_ft=0.5,
        ground_z_m=plane_z,
    )
    title = (f"{hole.course_name.upper()}   HOLE {hole.hole_number} · "
             f"PAR {hole.par} · {hole.scorecard_yardage:.0f} YDS")
    print("rendering...")
    stats = render_video(plane, path, pin_m,
                         str(data_dir / "hole1-flyover-draft.mp4"), title=title)
    timings["render_s"] = stats["render_s"]
    stats["timings"] = timings
    (data_dir / "hole1-render-stats.json").write_text(
        json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
