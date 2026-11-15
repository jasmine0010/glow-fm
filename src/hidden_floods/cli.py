"""Command line for the flood-map auditor.

    hidden-floods create-site yellow 02368000 02368500 --start <date> --end <date>
    hidden-floods fetch yellow 20261010 20261022           # GFM + DSWx-S1 + OSM (+ reference water)
    hidden-floods audit yellow 20261010 20261022           # GFM and DSWx-S1 against gauge + lidar truth
    hidden-floods audit-raster yellow my_map.tif --time 2026-10-17T11:02:00Z --flood-values 1 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hidden_floods.config import REPO_ROOT, load_site


def _out_dir(site_name: str) -> Path:
    d = REPO_ROOT / "outputs" / "audit" / site_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_create_site(a) -> int:
    from hidden_floods.sitegen import create_site

    site = create_site(a.name, a.gauges, f"{a.start}T00:00:00Z", f"{a.end}T00:00:00Z", a.description,
                       fetch_dem=not a.no_dem, overwrite=a.overwrite)
    print(f"created sites/{site.name}.toml: {[g.name for g in site.gauges]}, crs {site.crs}, bbox {site.bbox}")
    return 0


def cmd_fetch(a) -> int:
    from hidden_floods.fetch import fetch_dswx_s1, fetch_gfm, fetch_osm

    site = load_site(a.site)
    for d in a.dates:
        g = fetch_gfm(site.bbox, d, site.operational_dir)
        x = [] if a.no_dswx else fetch_dswx_s1(site.bbox, d, site.operational_dir)
        print(f"{site.name} {d}: {len(g)} GFM files, {len(x)} DSWx-S1 tiles")
    osm = site.operational_dir / "osm.json"
    if not a.no_osm and not osm.exists():
        fetch_osm(site.bbox, osm)
        print(f"{site.name}: OSM roads/buildings saved")
    return 0


def cmd_audit(a) -> int:
    from hidden_floods.audit import audit_date, exposure, report_markdown, scene_time, truth_context
    from hidden_floods.io.dem import dem_on_grid
    from hidden_floods.pipeline import analysis_grid

    site = load_site(a.site)
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    rows = []
    for d in a.dates:
        ctx = truth_context(site, scene_time(site.operational_dir, d), dem=dem, grid=grid)
        res, ctx, gfm = audit_date(site, d, ctx)
        if gfm.covered[ctx.truth.corridor].mean() < 0.5:
            res["warning"] = "GFM scenes on this date cover less than half of the corridor"
        osm = site.operational_dir / "osm.json"
        if osm.exists():
            unmapped = ctx.truth.wet & ctx.supported & gfm.covered & ~ctx.permanent_water & ~gfm.flood
            res["exposure_unmapped_by_gfm"] = exposure(osm, grid, unmapped)
        rows.append(res)
    out = _out_dir(site.name)
    (out / "audit.json").write_text(json.dumps(rows, indent=2, default=float))
    md = report_markdown(rows)
    (out / "audit.md").write_text(md, encoding="utf-8")
    print(md)
    for r in rows:
        if "warning" in r:
            print(f"warning {r['date']}: {r['warning']}")
    return 0


def cmd_audit_raster(a) -> int:
    from hidden_floods.audit import audit_raster, report_markdown

    site = load_site(a.site)
    r = audit_raster(site, a.time, Path(a.raster), a.flood_values, nodata=a.nodata)
    out = _out_dir(site.name)
    (out / f"audit_{Path(a.raster).stem}.json").write_text(json.dumps(r, indent=2, default=float))
    print(report_markdown([r]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hidden-floods", description="Audit flood maps against gauge + lidar truth.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("create-site", help="new site from USGS gauge IDs on one channel")
    s.add_argument("name")
    s.add_argument("gauges", nargs="+", help="USGS site numbers, any order (sorted by drainage area)")
    s.add_argument("--start", required=True, help="YYYY-MM-DD, start of the stage record to fetch")
    s.add_argument("--end", required=True, help="YYYY-MM-DD")
    s.add_argument("--description", default="")
    s.add_argument("--no-dem", action="store_true")
    s.add_argument("--overwrite", action="store_true")
    s.set_defaults(func=cmd_create_site)

    s = sub.add_parser("fetch", help="download GFM, DSWx-S1 and OSM for dates")
    s.add_argument("site")
    s.add_argument("dates", nargs="+", help="YYYYMMDD")
    s.add_argument("--no-dswx", action="store_true")
    s.add_argument("--no-osm", action="store_true")
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("audit", help="audit GFM and DSWx-S1 on dates")
    s.add_argument("site")
    s.add_argument("dates", nargs="+", help="YYYYMMDD")
    s.set_defaults(func=cmd_audit)

    s = sub.add_parser("audit-raster", help="audit any categorical flood raster")
    s.add_argument("site")
    s.add_argument("raster")
    s.add_argument("--time", required=True, help="acquisition time, ISO UTC")
    s.add_argument("--flood-values", type=int, nargs="+", required=True)
    s.add_argument("--nodata", type=int, default=None)
    s.set_defaults(func=cmd_audit_raster)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
