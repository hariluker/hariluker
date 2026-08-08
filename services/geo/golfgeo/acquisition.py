"""Acquisition of Indiana public-domain imagery and DEM via COG range reads.

Sources (verified 2026-08-08, see docs/PHASE0-ARCHITECTURE.md §3):
  - IGIO statewide orthoimagery: s3://gisimageryingov (public, us-east-2),
    prefix imageryoptimized/statewide/{year}/SPE/06in/, 2,500 ft tiles,
    0.5 ft/px RGBI GeoTIFF, CRS EPSG:2967 (NAD83(HARN) Indiana East, ftUS).
  - IGIO bare-earth DEM: same bucket, demoptimized/statewide/{year}/SPE/2.5ft/,
    5,000 ft tiles, 2.5 ft/px GeoTIFF, elevations in feet.

Both are license-free (public domain / CC0). Reads are windowed via
/vsicurl so only the AOI's bytes are transferred.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.merge import merge as rio_merge

BUCKET = "https://gisimageryingov.s3.us-east-2.amazonaws.com"
ORTHO_PREFIX = "imageryoptimized/statewide/{year}/SPE/06in"
DEM_PREFIX = "demoptimized/statewide/{year}/SPE/2.5ft"
ORTHO_TILE_FT = 2500
DEM_TILE_FT = 5000
US_FOOT_M = 0.3048006096012192  # US survey foot

# The imagery CRS. Tile *labels* are the lower-left corner in thousands of
# feet with the fractional .5 truncated (e.g. 462500 -> "0462").
IMG_CRS = "EPSG:2967"

_to_img = Transformer.from_crs(4326, IMG_CRS, always_xy=True)
_to_wgs = Transformer.from_crs(IMG_CRS, 4326, always_xy=True)


def wgs_to_img(lat: float, lon: float) -> tuple[float, float]:
    """WGS84 -> Indiana East ftUS (x=easting ft, y=northing ft)."""
    return _to_img.transform(lon, lat)


def img_to_wgs(x_ft: float, y_ft: float) -> tuple[float, float]:
    lon, lat = _to_wgs.transform(x_ft, y_ft)
    return lat, lon


def _tile_label(v_ft: float) -> str:
    return f"{int(v_ft // 1000):04d}"


def _tile_corners(min_v: float, max_v: float, tile_ft: int) -> list[float]:
    first = (min_v // tile_ft) * tile_ft
    corners = []
    v = first
    while v < max_v:
        corners.append(v)
        v += tile_ft
    return corners


def candidate_keys(bounds_ft: tuple[float, float, float, float],
                   year: int, dem: bool = False) -> list[str]:
    """Object keys whose tiles intersect bounds (minx, miny, maxx, maxy in ft).

    Tile-name casing varies by year, so both cases are returned; callers
    keep whichever exists.
    """
    minx, miny, maxx, maxy = bounds_ft
    tile_ft = DEM_TILE_FT if dem else ORTHO_TILE_FT
    prefix = (DEM_PREFIX if dem else ORTHO_PREFIX).format(year=year)
    suffix = "_12.tif" if dem else "_06.tif"
    keys = []
    for ex in _tile_corners(minx, maxx, tile_ft):
        for ny in _tile_corners(miny, maxy, tile_ft):
            for case in ("in", "IN"):
                keys.append(
                    f"{prefix}/{case}{year}_{_tile_label(ex)}{_tile_label(ny)}{suffix}"
                )
    return keys


def existing_urls(keys: list[str]) -> list[str]:
    urls = []
    for key in keys:
        url = f"{BUCKET}/{key}"
        if requests.head(url, timeout=30).status_code == 200:
            urls.append(url)
    return urls


@dataclass
class MosaicResult:
    array: np.ndarray  # (bands, h, w)
    transform: rasterio.Affine
    urls: list[str]

    def px_to_wgs(self, col: float, row: float) -> tuple[float, float]:
        x, y = self.transform * (col, row)
        return img_to_wgs(x, y)

    def wgs_to_px(self, lat: float, lon: float) -> tuple[float, float]:
        x, y = wgs_to_img(lat, lon)
        col, row = ~self.transform * (x, y)
        return col, row


def fetch_mosaic(bounds_ft: tuple[float, float, float, float], year: int,
                 res_ft: float, dem: bool = False) -> MosaicResult:
    """Mosaic all intersecting tiles windowed to bounds at res_ft per pixel."""
    urls = existing_urls(candidate_keys(bounds_ft, year, dem=dem))
    if not urls:
        raise RuntimeError(f"no tiles found for {bounds_ft} year={year} dem={dem}")
    datasets = [rasterio.open(f"/vsicurl/{u}") for u in urls]
    try:
        array, transform = rio_merge(
            datasets, bounds=bounds_ft, res=res_ft, nodata=0,
        )
    finally:
        for ds in datasets:
            ds.close()
    return MosaicResult(array=array, transform=transform, urls=urls)


def dem_sample_m(dem: MosaicResult, lat: float, lon: float) -> float:
    """Bare-earth elevation in meters at a WGS84 point (DEM stores feet)."""
    col, row = dem.wgs_to_px(lat, lon)
    band = dem.array[0]
    r, c = int(round(row)), int(round(col))
    if not (0 <= r < band.shape[0] and 0 <= c < band.shape[1]):
        raise ValueError("point outside DEM mosaic")
    return float(band[r, c]) * US_FOOT_M


def record_assets(urls: list[str], kind: str, year: int, resolution_m: float,
                  out_path: Path) -> None:
    """Append CourseAsset-style records (license + provenance) to a JSON file."""
    records = json.loads(out_path.read_text()) if out_path.exists() else []
    for url in urls:
        head = requests.head(url, timeout=30)
        records.append({
            "kind": kind,
            "provider": "Indiana Geographic Information Office (IGIO)",
            "provider_ref": url,
            "license": {
                "name": "Public domain / CC0 (IGIO statewide programs)",
                "commercial_use": True,
                "derivative_ok": True,
                "resale_ok": True,
                "attribution": "Imagery/elevation courtesy Indiana Geographic Information Office",
                "terms_url": "https://www.in.gov/gis/",
            },
            "capture_year": year,
            "resolution_m_per_px": resolution_m,
            "crs": IMG_CRS,
            "etag": head.headers.get("ETag", "").strip('"'),
            "size_bytes": int(head.headers.get("Content-Length", 0)),
        })
    out_path.write_text(json.dumps(records, indent=2) + "\n")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
