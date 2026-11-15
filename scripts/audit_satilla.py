"""What did today's flood maps show on the Satilla? Writes research/satilla_audit.json.

Runs after the one-time overbank test and doesn't change it. Same settings as research/BLIND_SPOT_AUDIT.md. Downloads go to a separate folder,
because the water estimate reads every reference-water file in the site's own folder and the frozen result depends on that folder staying as it was.
The primary date is the GFM date nearest the NISAR pass that covers at least 90% of the corridor. Every covered date is reported.
"""

import json
from datetime import datetime

from hidden_floods.audit import exposure, scene_time, truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.fetch import fetch_dswx_s1, fetch_gfm, fetch_osm
from hidden_floods.io.operational import dswx_s1_mosaic, dswx_water, gfm_mosaic
from hidden_floods.trust import worldcover_class, worldcover_on_grid

DATES = ("20260925", "20260930", "20261005", "20261017", "20261024", "20261029", "20261031")   # every GFM day listed over this valley, Sep 25 to Nov 5
NISAR_TIME = "2026-10-15T10:45:42"
AUDIT_DIR = data_root() / "satilla" / "ops_audit"
AREA = 0.25

site = load_site("satilla")
osm = AUDIT_DIR / "osm.json"
for d in DATES:
    g = fetch_gfm(site.bbox, d, AUDIT_DIR)
    x = fetch_dswx_s1(site.bbox, d, AUDIT_DIR)
    print(d, len(g), "GFM files,", len(x), "DSWx-S1 tiles", flush=True)
if not osm.exists():
    try:
        fetch_osm(site.bbox, osm)
    except (RuntimeError, OSError) as e:     # roads and buildings are an extra, and the Overpass service can refuse
        print("OSM not saved:", repr(e), flush=True)

rows = []
for d in DATES:
    try:
        when = scene_time(AUDIT_DIR, d)
    except FileNotFoundError:
        print(d, "no GFM scene", flush=True)
        continue
    ctx = truth_context(site, when)
    t, grid = ctx.truth, ctx.grid
    gfm = gfm_mosaic(AUDIT_DIR, d, grid)
    cover = float(gfm.covered[t.corridor].mean())
    region = ctx.supported & gfm.covered & ~ctx.permanent_water
    wet, dry = t.wet & region, t.dry & region
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    wtr = dswx_s1_mosaic(AUDIT_DIR, d, grid)
    has_dswx = bool(((wtr != 255) & wet).any())
    out_wet = wet & ~gfm.excluded
    row = {"date": d, "scene_time_utc": when, "corridor_coverage": round(cover, 3), "estimated_ha": float(wet.sum() * AREA), "dry_ha": float(dry.sum() * AREA),
           "gauge_wse_navd88_m": {k: round(v, 2) for k, v in ctx.gauge_wse_m.items()},
           "gfm_on_wet_ha": float((gfm.flood & wet).sum() * AREA), "gfm_share": float((gfm.flood & wet).sum() / wet.sum()) if wet.any() else None,
           "wet_share_in_mask": float(gfm.excluded[wet].mean()) if wet.any() else None, "dry_share_in_mask": float(gfm.excluded[dry].mean()) if dry.any() else None,
           "corridor_share_in_mask": float(gfm.excluded[t.corridor & gfm.covered & ~ctx.permanent_water].mean()) if (t.corridor & gfm.covered).any() else None,
           "wet_outside_mask_ha": float(out_wet.sum() * AREA), "gfm_on_wet_outside_mask_ha": float((gfm.flood & out_wet).sum() * AREA),
           "tree_share": float((lc[wet] == 1).mean()) if wet.any() else None,
           "dswx_on_wet_ha": float((dswx_water(wtr) & wet & (wtr != 255)).sum() * AREA) if has_dswx else None,
           "dswx_share": float((dswx_water(wtr) & wet & (wtr != 255)).sum() / max((wet & (wtr != 255)).sum(), 1)) if has_dswx else None}
    if osm.exists() and wet.any():
        row["exposure_unmapped_by_gfm"] = exposure(osm, grid, wet & ~gfm.flood)
    rows.append(row)
    print(json.dumps(row), flush=True)

t0 = datetime.fromisoformat(NISAR_TIME)
ok = [r for r in rows if r["corridor_coverage"] >= 0.9]
primary = min(ok, key=lambda r: abs((datetime.fromisoformat(r["scene_time_utc"].replace("Z", "")) - t0).total_seconds()))["date"] if ok else None
(REPO_ROOT / "research" / "satilla_audit.json").write_text(json.dumps({"nisar_time": NISAR_TIME, "primary_date": primary, "dates": rows}, indent=1, default=float))
print("SATILLA AUDIT DONE, primary", primary, flush=True)
