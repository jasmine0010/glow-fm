"""Flood-map auditor: how much *hydraulically confirmed* flooding did an operational flood map show?

Truth is computed at the flood map's own acquisition time from river gauges and lidar (Module C), so the audit does
not depend on any NISAR detector. Pixels of permanent water (GFM reference water) are excluded from the audit, so
the question is purely about floodplain flooding.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

from hidden_floods.config import Site
from hidden_floods.frozen import reference_water
from hidden_floods.grid import Grid, warp_to_grid
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.operational import dswx_s1_mosaic, dswx_water, gfm_mosaic
from hidden_floods.metrics import block_bootstrap, block_ids
from hidden_floods.pipeline import analysis_grid, gauge_water_surfaces
from hidden_floods.selfcal import gauge_supported
from hidden_floods.truth import TruthLabels, ValleyLine, hydraulic_truth, refine_centerline

GAUGE_SUPPORT_M = 10000.0   # same truth-confidence rule as method v2
BLOCK_M = 2000.0


@dataclass
class TruthContext:
    grid: Grid
    truth: TruthLabels
    supported: np.ndarray
    permanent_water: np.ndarray
    when: str
    gauge_wse_m: dict[str, float]
    gauge_chainage_m: tuple[float, ...] = ()
    line: ValleyLine | None = None


def scene_time(ops_dir: Path, date: str) -> str:
    """Earliest GFM scene time on ``date`` (YYYYMMDD) as ISO UTC, from the saved file names."""
    stamps = sorted({m.group(1) for p in Path(ops_dir).glob(f"GFM_{date}T*_ensemble_flood_extent.tif")
                     if (m := re.search(r"GFM_(\d{8}T\d{6})_", p.name))})
    if not stamps:
        raise FileNotFoundError(f"no GFM scenes for {date}")
    s = stamps[0]
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}Z"


def truth_context(site: Site, when: str, dem=None, grid: Grid | None = None) -> TruthContext:
    grid = grid or analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid) if dem is None else dem
    perm = reference_water(site.operational_dir, grid)
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist0, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, perm & (dist0 < site.corridor_m), grid)
    gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    _, g_chain = line.project(*map(np.array, zip(*gxy, strict=True)))
    wse = gauge_water_surfaces(site, when)
    truth = hydraulic_truth(grid, dem, line, gxy, [wse[g.name] for g in site.gauges], site.corridor_m,
                            site.margin_m, site.max_dry_height_m, channel_seeds=perm)
    supported = gauge_supported(truth.chainage_m, g_chain, GAUGE_SUPPORT_M)
    return TruthContext(grid, truth, supported, perm, when, wse, tuple(float(c) for c in g_chain), line)


def audit_mask(ctx: TruthContext, mapped: np.ndarray, covered: np.ndarray, excluded: np.ndarray | None = None,
               n_boot: int = 2000, seed: int = 0) -> dict:
    """Share of confirmed floodplain flooding that ``mapped`` shows, with a block-bootstrap interval."""
    t = ctx.truth
    region = ctx.supported & covered & ~ctx.permanent_water
    wet = t.wet & region
    area = ctx.grid.pixel_area_ha
    out = {"truth_wet_ha": float(wet.sum() * area), "mapped_ha": float((mapped & wet).sum() * area)}
    if wet.sum() == 0:
        return out | {"share_mapped": None}
    out["share_mapped"] = float((mapped & wet).sum() / wet.sum())
    ci = block_bootstrap(mapped, t.wet, t.dry, block_ids(t.chainage_m, BLOCK_M), region, n_boot=n_boot, seed=seed,
                         metrics=("recall",))
    out["share_mapped_ci95"] = ci["recall"]
    dry = t.dry & region
    out["mapped_on_truth_dry_ha"] = float((mapped & dry).sum() * area)
    if excluded is not None:
        out["share_inside_exclusion_mask"] = float((excluded & wet).sum() / wet.sum())
    return out


def audit_date(site: Site, date: str, ctx: TruthContext | None = None) -> dict:
    """Audit GFM and DSWx-S1 for one date at the site."""
    when = scene_time(site.operational_dir, date)
    ctx = ctx or truth_context(site, when)
    gfm = gfm_mosaic(site.operational_dir, date, ctx.grid)
    res = {"site": site.name, "date": date, "truth_time_utc": when,
           "gauge_wse_navd88_m": {k: round(v, 3) for k, v in ctx.gauge_wse_m.items()},
           "gfm": audit_mask(ctx, gfm.flood, gfm.covered, gfm.excluded)}
    wtr = dswx_s1_mosaic(site.operational_dir, date, ctx.grid)
    covered = wtr != 255
    if covered.any():
        res["dswx_s1"] = audit_mask(ctx, dswx_water(wtr), covered)
        both = gfm.covered & covered
        res["gfm_or_dswx_s1"] = audit_mask(ctx, gfm.flood | dswx_water(wtr), both, gfm.excluded)
    return res, ctx, gfm


def exposure(osm_path: Path, grid: Grid, mask: np.ndarray, step_m: float = 10.0) -> dict:
    """Drivable OSM road length (bridges excluded) and building count whose centroid falls inside ``mask``."""
    osm = json.loads(Path(osm_path).read_text(encoding="utf-8"))
    skip = {"footway", "path", "steps", "cycleway", "pedestrian", "bridleway", "corridor", "proposed", "construction"}
    km, by_class, buildings = 0.0, {}, 0
    for el in osm.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        tags = el.get("tags", {})
        lon = np.array([p["lon"] for p in el["geometry"]])
        lat = np.array([p["lat"] for p in el["geometry"]])
        x, y = grid.to_xy(lon, lat)
        x, y = np.asarray(x), np.asarray(y)
        if "building" in tags:
            r, c = grid.index_of(x.mean(), y.mean())
            buildings += int(grid.contains_index(r, c) and mask[r, c])
            continue
        hw = tags.get("highway", "")
        if hw in skip or tags.get("bridge") not in (None, "no"):
            continue
        for i in range(len(x) - 1):
            seg = float(np.hypot(x[i + 1] - x[i], y[i + 1] - y[i]))
            n = max(int(seg // step_m), 1)
            f = (np.arange(n) + 0.5) / n
            r, c = grid.index_of(x[i] + f * (x[i + 1] - x[i]), y[i] + f * (y[i + 1] - y[i]))
            ok = grid.contains_index(r, c)
            hit = np.zeros(n, bool)
            hit[ok] = mask[r[ok], c[ok]]
            add = hit.sum() * seg / n / 1000.0
            km += add
            by_class[hw] = by_class.get(hw, 0.0) + add
    return {"road_km": round(km, 2), "road_km_by_class": {k: round(v, 2) for k, v in sorted(by_class.items(),
            key=lambda kv: -kv[1]) if v >= 0.05}, "buildings": buildings}


def audit_raster(site: Site, when: str, raster_path: Path, flood_values, nodata=None,
                 ctx: TruthContext | None = None) -> dict:
    """Audit any categorical flood raster (e.g. a NISAR-derived map or DSWx-NI) acquired at ``when`` (ISO UTC).

    ``flood_values`` are the class values that mean "flooded"; pixels equal to ``nodata`` (or the file's own nodata)
    count as not covered. Exclusion masks are not known for arbitrary products, so only coverage is used.
    """
    ctx = ctx or truth_context(site, when)
    with rasterio.open(raster_path) as src:
        nd = nodata if nodata is not None else (src.nodata if src.nodata is not None else 255)
    arr = warp_to_grid(raster_path, ctx.grid, categorical=True, nodata=nd)
    mapped = np.isin(arr, np.asarray(flood_values))
    return {"site": site.name, "product": Path(raster_path).name, "truth_time_utc": when,
            "flood_values": list(map(int, flood_values)),
            "audit": audit_mask(ctx, mapped, arr != nd)}


def report_markdown(rows: list[dict]) -> str:
    """Human-readable summary of audit rows from :func:`audit_date` / :func:`audit_raster`."""

    def pct(x):
        return "n/a" if x is None else f"{100 * x:.1f}%"

    def ci(a):
        return "" if not a.get("share_mapped_ci95") else " ({:.1f}-{:.1f})".format(*[100 * v for v in a["share_mapped_ci95"]])

    out = ["| Site | Product | Truth time (UTC) | Confirmed flooding (ha) | Share mapped (95% CI) | Inside GFM exclusion |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        blocks = [(k, r[k]) for k in ("gfm", "dswx_s1") if k in r] or [(r.get("product", "raster"), r["audit"])]
        for label, a in blocks:
            excl = pct(a.get("share_inside_exclusion_mask")) if "share_inside_exclusion_mask" in a else "-"
            out.append(f"| {r['site']} | {label} | {r['truth_time_utc']} | {a['truth_wet_ha']:,.0f} | "
                       f"{pct(a.get('share_mapped'))}{ci(a)} | {excl} |")
    return "\n".join(out) + "\n"
