import tomllib

import numpy as np
import pytest
import rasterio

from hidden_floods.audit import TruthContext, audit_mask, report_markdown, scene_time
from hidden_floods.cli import build_parser
from hidden_floods.grid import Grid, warp_to_grid
from hidden_floods.sitegen import GaugeMeta, buffered_bbox, order_upstream_first, site_toml, utm_epsg
from hidden_floods.truth import TruthLabels


def test_utm_epsg_and_bbox():
    assert utm_epsg(-85.9, 30.6) == "EPSG:32616" and utm_epsg(-90.5, 30.6) == "EPSG:32615"
    assert buffered_bbox([(-86.0, 30.5), (-85.8, 30.9)], 0.1) == [-86.1, 30.4, -85.7, 31.0]


def test_gauges_sorted_by_drainage_area():
    g = [GaugeMeta("USGS-2", "down", 0, 0, 0, "NAVD88", 900.0), GaugeMeta("USGS-1", "up", 0, 0, 0, "NAVD88", 100.0)]
    assert [x.name for x in order_upstream_first(g)] == ["up", "down"]
    g[0].drainage_area = None
    assert [x.name for x in order_upstream_first(g)] == ["down", "up"]


def test_site_toml_round_trips_through_load_site(tmp_path):
    gauges = [GaugeMeta("USGS-1", 'A "quoted" gauge', -86.0, 30.9, 50.0, "NGVD29", 100.0, -0.3),
              GaugeMeta("USGS-2", "B", -85.9, 30.5, 0.0, "NAVD88", 900.0, 0.0)]
    text = site_toml("demo", "EPSG:32616", [-86.1, 30.4, -85.8, 31.0], gauges)
    raw = tomllib.loads(text)
    assert raw["gauges"][0]["navd88_offset_ft"] == -0.3 and len(raw["valley"]["line"]) == 2
    (tmp_path / "demo.toml").write_text(text)
    from hidden_floods.config import load_site
    s = load_site("demo", tmp_path)
    assert s.gauges[0].name == "A quoted gauge" and s.pairs == {}


def test_scene_time_parses_gfm_names(tmp_path):
    for stamp in ("20261022T234522", "20261022T234452"):
        (tmp_path / f"GFM_{stamp}_ensemble_flood_extent.tif").write_bytes(b"x")
    assert scene_time(tmp_path, "20261022") == "2026-10-22T23:44:52Z"
    with pytest.raises(FileNotFoundError):
        scene_time(tmp_path, "20261023")


def test_warped_categorical_raster_drives_audit(tmp_path):
    grid = Grid("EPSG:32616", 500000.0, 3400000.0, 50.0, 20, 20)
    data = np.zeros((40, 40), np.uint8)
    data[:, :20] = 1                         # western half mapped as flood (class 1) at 25 m
    data[:, -4:] = 255                       # eastern strip not covered
    path = tmp_path / "map.tif"
    with rasterio.open(path, "w", driver="GTiff", height=40, width=40, count=1, dtype="uint8", crs=grid.crs,
                       transform=rasterio.transform.from_origin(500000.0, 3400000.0, 25.0, 25.0), nodata=255) as d:
        d.write(data, 1)
    arr = warp_to_grid(path, grid, categorical=True, nodata=255)
    wet = np.ones(grid.shape, bool)
    chain = np.repeat(np.arange(20)[:, None] * 50.0, 20, axis=1)
    t = TruthLabels(wet, ~wet, np.zeros(grid.shape), np.zeros(grid.shape), np.zeros(grid.shape), chain, wet)
    ctx = TruthContext(grid, t, wet, np.zeros(grid.shape, bool), "t", {})
    r = audit_mask(ctx, arr == 1, arr != 255, n_boot=50)
    assert np.isclose(r["share_mapped"], 10 / 18)  # 10 mapped columns of 18 covered
    md = report_markdown([{"site": "demo", "product": "map.tif", "truth_time_utc": "t", "audit": r}])
    assert "55.6%" in md


def test_cli_parses_subcommands():
    p = build_parser()
    a = p.parse_args(["audit-raster", "pearl", "x.tif", "--time", "2026-06-28T00:00:00Z", "--flood-values", "1", "3"])
    assert a.flood_values == [1, 3] and a.func.__name__ == "cmd_audit_raster"
    a = p.parse_args(["create-site", "yellow", "02368000", "02368500", "--start", "2026-10-01", "--end", "2026-10-31"])
    assert a.gauges == ["02368000", "02368500"]
