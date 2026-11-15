"""Downloads for the auditor: gauge records, operational flood maps, OSM roads/buildings, lidar DEM.

Earthdata-protected files (OPERA DSWx-S1) need a ``~/.netrc`` entry for ``urs.earthdata.nasa.gov``; GFM (EODC STAC),
the USGS APIs, NOAA VDatum and OpenStreetMap are open.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

STAC = "https://stac.eodc.eu/api/v1/search"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
USGS_OGC = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
GFM_ASSETS = ("ensemble_flood_extent", "exclusion_mask", "reference_water_mask")
USER_AGENT = "hidden-floods-auditor/0.1"


def get_json(url: str, timeout: int = 120, retries: int = 3) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def download(url: str, out: Path, netrc: bool = False) -> Path:
    """curl download (follows redirects; uses ~/.netrc and a cookie jar for Earthdata). Skips existing files."""
    out = Path(out)
    if out.exists() and out.stat().st_size > 0:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["curl", "-s", "-L", "--fail", "--retry", "3", "--max-time", "900", "-o", str(out)]
    if netrc:
        jar = str(out.parent / "cookies.txt")
        cmd += ["-n", "-c", jar, "-b", jar]
    subprocess.run([*cmd, url], check=True)
    return out


def _day_range(date: str) -> tuple[str, str]:
    day = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    return f"{day}T00:00:00Z", f"{day}T23:59:59Z"


def fetch_gfm(bbox, date: str, out_dir: Path) -> list[Path]:
    """All GFM scenes intersecting ``bbox`` on ``date`` (YYYYMMDD): flood extent, exclusion mask, reference water."""
    t0, t1 = _day_range(date)
    q = urllib.parse.urlencode({"collections": "GFM", "bbox": ",".join(map(str, bbox)), "limit": 100,
                                "datetime": f"{t0}/{t1}"})
    files = []
    for f in get_json(f"{STAC}?{q}").get("features", []):
        stamp = f["properties"]["datetime"][:19].replace("-", "").replace(":", "")
        for asset in GFM_ASSETS:
            if asset in f["assets"]:
                files.append(download(f["assets"][asset]["href"], Path(out_dir) / f"GFM_{stamp}_{asset}.tif"))
    return files


def fetch_dswx_s1(bbox, date: str, out_dir: Path) -> list[Path]:
    """OPERA DSWx-S1 WTR tiles intersecting ``bbox`` on ``date`` (needs Earthdata login)."""
    t0, t1 = _day_range(date)
    q = urllib.parse.urlencode({"short_name": "OPERA_L3_DSWX-S1_V1", "bounding_box": ",".join(map(str, bbox)),
                                "page_size": 200, "temporal": f"{t0},{t1}"})
    files = []
    for it in get_json(f"{CMR}?{q}").get("items", []):
        for u in it["umm"].get("RelatedUrls", []):
            if u["URL"].startswith("https") and u["URL"].endswith("_B01_WTR.tif"):
                files.append(download(u["URL"], Path(out_dir) / u["URL"].rsplit("/", 1)[1], netrc=True))
    return files


def fetch_usgs_stage(site_id: str, start: str, end: str, out_dir: Path) -> Path:
    """15-min stage (parameter 00065) for ``USGS-<id>`` between ISO times, saved in the shape gauges.load_usgs reads."""
    feats, url = [], (f"{USGS_OGC}/continuous/items?" + urllib.parse.urlencode(
        {"f": "json", "monitoring_location_id": site_id, "parameter_code": "00065", "time": f"{start}/{end}",
         "limit": 10000}))
    while url:
        page = get_json(url, timeout=300)
        feats += page.get("features", [])
        url = next((ln["href"] for ln in page.get("links", []) if ln.get("rel") == "next"), None)
    out = Path(out_dir) / f"usgs_{site_id.removeprefix('USGS-')}_stage_15min.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"features": feats}))
    return out


def fetch_osm(bbox, out: Path) -> Path:
    """OSM ways tagged highway or building inside ``bbox`` (Overpass; falls back to a mirror)."""
    w, s, e, n = bbox
    query = f'[out:json][timeout:300];(way["highway"]({s},{w},{n},{e});way["building"]({s},{w},{n},{e}););out geom;'
    last = None
    for base in OVERPASS:
        try:
            req = urllib.request.Request(base + "?" + urllib.parse.urlencode({"data": query}),
                                         headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_bytes(data)
            return Path(out)
        except OSError as exc:  # network error or HTTP error: try the next mirror
            last = exc
    raise RuntimeError(f"OSM download failed: {last}")
