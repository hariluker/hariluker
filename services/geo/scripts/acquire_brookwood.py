"""Fetch Brookwood GC overview imagery (2024 IGIO 6-inch) for hole identification.

Usage: python scripts/acquire_brookwood.py <out_dir>
Produces overview.png (RGB, ~0.6 m/px) plus overview-meta.json with the
georeferencing needed to convert pixel positions back to WGS84.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
from golfgeo.acquisition import fetch_mosaic, record_assets, wgs_to_img

# AOI center: between the clubhouse (40.9887, -85.1685) and the test
# coordinates (~40.992, -85.173); radius covers the whole property.
CENTER = (40.9905, -85.1710)
RADIUS_M = 1300.0
YEAR = 2024
RES_FT = 2.0  # ~0.61 m/px for the overview


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cx, cy = wgs_to_img(*CENTER)
    r_ft = RADIUS_M / 0.3048
    bounds = (cx - r_ft, cy - r_ft, cx + r_ft, cy + r_ft)

    mosaic = fetch_mosaic(bounds, YEAR, RES_FT)
    rgb = np.transpose(mosaic.array[:3], (1, 2, 0))
    Image.fromarray(rgb).save(out_dir / "overview.png")

    meta = {
        "crs": "EPSG:2967",
        "transform": list(mosaic.transform)[:6],
        "shape": [int(rgb.shape[0]), int(rgb.shape[1])],
        "res_ft_per_px": RES_FT,
        "center_wgs84": CENTER,
        "source_year": YEAR,
        "tiles": mosaic.urls,
    }
    (out_dir / "overview-meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    record_assets(mosaic.urls, "orthoimagery", YEAR, 0.1524, out_dir / "assets.json")
    print(f"overview: {rgb.shape[1]}x{rgb.shape[0]} px from {len(mosaic.urls)} tiles")
    for u in mosaic.urls:
        print(" ", u.rsplit('/', 1)[-1])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
