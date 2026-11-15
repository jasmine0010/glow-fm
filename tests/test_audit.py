import json

import numpy as np

from hidden_floods.audit import TruthContext, audit_mask, exposure
from hidden_floods.grid import Grid
from hidden_floods.truth import TruthLabels


def _ctx(wet, dry):
    shape = wet.shape
    grid = Grid("EPSG:32616", 500000.0, 3400000.0, 50.0, shape[1], shape[0])
    chain = np.repeat(np.arange(shape[0])[:, None] * 50.0, shape[1], axis=1)
    t = TruthLabels(wet, dry, np.zeros(shape), np.zeros(shape), np.zeros(shape), chain, np.ones(shape, bool))
    return TruthContext(grid, t, np.ones(shape, bool), np.zeros(shape, bool), "2026-01-01T00:00:00Z", {})


def test_audit_share_mapped_and_exclusion():
    wet = np.zeros((40, 10), bool)
    wet[:, :4] = True
    ctx = _ctx(wet, ~wet)
    mapped = np.zeros_like(wet)
    mapped[:10, :4] = True                 # a quarter of the flooding is mapped
    excluded = np.zeros_like(wet)
    excluded[:, :2] = True                 # half of it is inside the exclusion mask
    r = audit_mask(ctx, mapped, np.ones_like(wet), excluded, n_boot=200)
    assert np.isclose(r["share_mapped"], 0.25) and np.isclose(r["share_inside_exclusion_mask"], 0.5)
    lo, hi = r["share_mapped_ci95"]
    assert lo <= 0.25 <= hi
    assert r["truth_wet_ha"] == wet.sum() * 0.25


def test_audit_ignores_uncovered_and_permanent_water():
    wet = np.ones((10, 10), bool)
    ctx = _ctx(wet, np.zeros_like(wet))
    ctx.permanent_water[:, 0] = True
    covered = np.ones_like(wet)
    covered[:, -1] = False
    r = audit_mask(ctx, np.zeros_like(wet), covered, n_boot=50)
    assert r["truth_wet_ha"] == 80 * 0.25 and r["share_mapped"] == 0.0


def test_exposure_counts_roads_and_buildings_inside_mask(tmp_path):
    grid = Grid("EPSG:32616", 500000.0, 3400000.0, 50.0, 40, 40)
    mask = np.zeros(grid.shape, bool)
    mask[:, :20] = True                      # western half flooded
    lon0, lat = grid.to_lonlat(500000.0, 3399000.0)
    lon1, _ = grid.to_lonlat(502000.0, 3399000.0)
    blon, blat = grid.to_lonlat(500300.0, 3399500.0)
    osm = {"elements": [
        {"type": "way", "tags": {"highway": "residential"}, "geometry": [{"lon": lon0, "lat": lat}, {"lon": lon1, "lat": lat}]},
        {"type": "way", "tags": {"highway": "primary", "bridge": "yes"}, "geometry": [{"lon": lon0, "lat": lat}, {"lon": lon1, "lat": lat}]},
        {"type": "way", "tags": {"building": "yes"}, "geometry": [{"lon": blon, "lat": blat}] * 3}]}
    p = tmp_path / "osm.json"
    p.write_text(json.dumps(osm), encoding="utf-8")
    e = exposure(p, grid, mask)
    assert abs(e["road_km"] - 1.0) < 0.05 and e["buildings"] == 1 and "primary" not in e["road_km_by_class"]
