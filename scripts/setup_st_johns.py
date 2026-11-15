"""Set up the St. Johns River, FL, as a dashboard river: the river of the sealed test (research/SEALED_TEST_PROTOCOL.md).

    python scripts/setup_st_johns.py

Writes sites/st_johns.toml with the sealed test's three USGS gauges (near Cocoa, above Lake Harney near Geneva, and at
Astor) in hidden_floods.sitegen's format, then:
- takes each gauge's datum from its own readings: these gauges publish no datum, but report both gage height (00065)
  and water elevation above NAVD88 (63160), and the difference between the two is the datum;
- saves the NWS flood stages (minor flood, in gage height) of their NWS gauges, COCF1, GENF1 and ASTF1, found by USGS
  id (river_setup.save_nws_levels, which turns levels NWS lists as elevations into gage height);
- replaces the straight gauge-to-gauge valley with the USGS river line (NLDI main stem), since this river winds through
  Lake Harney and Lake Monroe for about 120 km, and widens the box to hold it;
- fetches the stage records and the two ESA WorldCover tiles that cover it;
- takes WorldCover's permanent water (class 80) as its permanent-water mask, since GFM has no reference-water layer
  here, so Lake Harney and Lake Monroe aren't counted as flood (river_setup.worldcover_water_mask);
- fetches USGS 3DEP lidar (bare earth, 10 m) for an 8 km corridor around the river line only, in 10 km tiles that are
  kept as they arrive, so an interrupted run resumes (river_setup.corridor_lidar);
- fetches its OpenStreetMap roads (build_roads.osm_path).

Everything is cached under the data root, so a second run downloads nothing. It adds a river to the dashboard only;
no test or score changes. The sealed test itself works on its own 24 km boxes and is not touched.
"""

import re
from pathlib import Path

from build_roads import osm_path
from river_setup import (
    corridor_lidar,
    datum_from_readings,
    length_km,
    main_stem,
    save_nws_levels,
    valley,
    worldcover_tiles,
    worldcover_water_mask,
)

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.fetch import fetch_usgs_stage
from hidden_floods.live import gauge_datum
from hidden_floods.sitegen import GaugeMeta, buffered_bbox, site_toml, utm_epsg

NAME = "st_johns"
GAUGES = ["USGS-02232400", "USGS-02234000", "USGS-02236125"]      # near Cocoa, above Lake Harney near Geneva, at Astor
START, END = "2026-08-01T00:00:00Z", "2026-11-15T00:00:00Z"


def main():
    path = REPO_ROOT / "sites" / f"{NAME}.toml"
    if not path.exists():
        gauges = []
        for usgs in GAUGES:     # upstream first, as listed
            d = gauge_datum(usgs.removeprefix("USGS-"))
            derived = datum_from_readings(usgs)
            if derived is None:
                raise ValueError(f"{usgs}: its gage height and NAVD88 elevation readings don't give one steady datum")
            gauges.append(GaugeMeta(usgs, d["name"], d["lon"], d["lat"], derived, "NAVD88", None))
            print(usgs, d["name"], "datum", gauges[-1].datum_ft, "ft NAVD88", flush=True)
        bbox = buffered_bbox([(g.lon, g.lat) for g in gauges])
        path.write_text(site_toml(NAME, utm_epsg((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2), bbox, gauges,
                                  "St. Johns River, FL: the sealed test's river, from near Cocoa to Astor. Dashboard river only; no test."))
    site = load_site(NAME)
    stem = main_stem(site.gauges[-1].id, "UM", 200)
    line = valley(stem, (site.gauges[0].lon, site.gauges[0].lat), (site.gauges[-1].lon, site.gauges[-1].lat))
    text = path.read_text()
    text = re.sub(r"(?m)^line = \[.*\]$", "line = [" + ", ".join(f"[{x:.5f}, {y:.5f}]" for x, y in line) + "]", text, count=1)
    text = re.sub(r"(?m)^bbox = \[.*\]$", f"bbox = {buffered_bbox(line)}", text, count=1)
    path.write_text(text)
    site = load_site(NAME)
    print(f"valley: {len(line)} points, {length_km(line):.0f} km; bbox {site.bbox}", flush=True)
    for g in site.gauges:
        if not (Path(site.gauges_dir) / f"usgs_{g.id.removeprefix('USGS-')}_stage_15min.json").exists():
            fetch_usgs_stage(g.id, START, END, site.gauges_dir)
    print("NWS flood stages", save_nws_levels(NAME), flush=True)
    print("WorldCover", [t.name for t in worldcover_tiles(site.bbox)], flush=True)
    print("permanent water", worldcover_water_mask(site).name, flush=True)
    print("roads", f"{osm_path(NAME, site.bbox).stat().st_size / 1e6:.0f} MB", flush=True)
    corridor_lidar(site, site.valley_line, km=8)
    print("lidar", f"{Path(site.dem_path).stat().st_size / 1e6:.0f} MB", flush=True)
    print("ST JOHNS SETUP DONE", flush=True)


if __name__ == "__main__":
    main()
