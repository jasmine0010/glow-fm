"""Create a new audit site from a list of USGS stream gauges on one channel.

Everything needed for hydraulic truth is fetched from public services:
gauge coordinates, datum and drainage area (USGS), NGVD29 -> NAVD88 offsets (NOAA VDatum), 15-min stage (USGS),
and lidar bare earth (USGS 3DEP). The site file is written to ``sites/<name>.toml``.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.fetch import USGS_OGC, fetch_usgs_stage, get_json
from hidden_floods.grid import grid_from_lonlat_bbox
from hidden_floods.io.dem import fetch_3dep

VDATUM = "https://vdatum.noaa.gov/vdatumweb/api/convert"


@dataclass
class GaugeMeta:
    id: str
    name: str
    lon: float
    lat: float
    datum_ft: float
    datum: str
    drainage_area: float | None
    navd88_offset_ft: float = 0.0


def utm_epsg(lon: float, lat: float) -> str:
    """Standard UTM zone of a point. NISAR products may use a neighbouring zone near zone edges; for NISAR pairs set
    the site crs to the product projection (read_gcov refuses a mismatch)."""
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def buffered_bbox(points, buffer_deg: float = 0.06) -> list[float]:
    lons, lats = [p[0] for p in points], [p[1] for p in points]
    return [round(min(lons) - buffer_deg, 4), round(min(lats) - buffer_deg, 4),
            round(max(lons) + buffer_deg, 4), round(max(lats) + buffer_deg, 4)]


def order_upstream_first(gauges: list[GaugeMeta]) -> list[GaugeMeta]:
    """Order by drainage area (smallest = most upstream); keep the given order if any area is unknown."""
    if all(g.drainage_area for g in gauges):
        return sorted(gauges, key=lambda g: g.drainage_area)
    return list(gauges)


def gauge_metadata(site_id: str) -> GaugeMeta:
    sid = site_id if site_id.startswith("USGS-") else f"USGS-{site_id}"
    d = get_json(f"{USGS_OGC}/monitoring-locations/items?" + urllib.parse.urlencode({"f": "json", "id": sid}))
    feats = d.get("features", [])
    if not feats:
        raise ValueError(f"unknown USGS site {sid}")
    p, (lon, lat) = feats[0]["properties"], feats[0]["geometry"]["coordinates"][:2]
    if p.get("altitude") is None or p.get("vertical_datum") not in ("NAVD88", "NGVD29"):
        raise ValueError(f"{sid} has no usable gauge datum ({p.get('altitude')}, {p.get('vertical_datum')})")
    return GaugeMeta(sid, p.get("monitoring_location_name", sid), float(lon), float(lat), float(p["altitude"]),
                     p["vertical_datum"], p.get("drainage_area"))


def ngvd29_to_navd88_ft(lon: float, lat: float) -> float:
    """NOAA VDatum offset (ft) to add to an NGVD29 elevation to get NAVD88. NGVD29 needs the NAD27 input frame."""
    q = {"s_x": lon, "s_y": lat, "s_z": 0, "s_h_frame": "NAD27", "s_v_frame": "NGVD29", "s_v_unit": "us_ft",
         "t_h_frame": "NAD83_2011", "t_v_frame": "NAVD88", "t_v_unit": "us_ft", "region": "contiguous"}
    d = get_json(f"{VDATUM}?" + urllib.parse.urlencode(q))
    if d.get("t_z") in (None, ""):
        raise ValueError(f"VDatum conversion failed at {lon},{lat}: {d}")
    return float(d["t_z"])


def site_toml(name: str, crs: str, bbox, gauges: list[GaugeMeta], description: str = "") -> str:
    lines = [f"# {description or name} (created by hidden_floods.sitegen)", "", f'name = "{name}"', f'crs = "{crs}"',
             "resolution_m = 50.0", f"bbox = {bbox}", "", "[data]", f'root = "{name}"', 'dem = "dem/dem10m.tif"',
             'gauges = "gauges"', 'operational = "ops"', "", "[gcov]", "", "[gunw]", "", "[pairs]", ""]
    for g in gauges:
        lines += ["[[gauges]]", f'name = "{g.name.replace(chr(34), "")}"', f'id = "{g.id}"', f"lon = {g.lon:.6f}",
                  f"lat = {g.lat:.6f}", f"datum_ft = {g.datum_ft}", f"navd88_offset_ft = {g.navd88_offset_ft:.3f}", ""]
    line = ", ".join(f"[{g.lon:.4f}, {g.lat:.4f}]" for g in gauges)
    lines += ["[valley]", f"line = [{line}]", "corridor_m = 4000.0", "", "[truth]", "margin_m = 0.5",
              "max_dry_height_m = 5.0", "", "[split]", "calibration_max_chainage_m = 0.0", "bootstrap_block_m = 2000.0",
              "", "[detector]", "forest_hv_db = -16.0", "thresholds_db = [2.0]", ""]
    return "\n".join(lines)


def create_site(name: str, gauge_ids: list[str], start: str, end: str, description: str = "",
                fetch_dem: bool = True, sites_dir: Path | None = None, overwrite: bool = False):
    """Write ``sites/<name>.toml`` for gauges on one channel and fetch stage records (and the DEM)."""
    path = (sites_dir or REPO_ROOT / "sites") / f"{name}.toml"
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists")
    gauges = order_upstream_first([gauge_metadata(g) for g in gauge_ids])
    if len(gauges) < 2:
        raise ValueError("need at least two gauges on one channel")
    for g in gauges:
        g.navd88_offset_ft = ngvd29_to_navd88_ft(g.lon, g.lat) if g.datum == "NGVD29" else 0.0
    bbox = buffered_bbox([(g.lon, g.lat) for g in gauges])
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    path.write_text(site_toml(name, utm_epsg(cx, cy), bbox, gauges, description))
    site = load_site(name, sites_dir)
    for g in gauges:
        fetch_usgs_stage(g.id, start, end, site.gauges_dir)
    if fetch_dem:
        fetch_3dep(grid_from_lonlat_bbox(site.bbox, site.crs, 10.0, snap=50.0), site.dem_path)
    return site


__all__ = ["create_site", "data_root"]
