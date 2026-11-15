import json

import h5py
import numpy as np
import pytest

from hidden_floods.config import Gauge, load_site
from hidden_floods.grid import Grid, block_mean, grid_from_lonlat_bbox
from hidden_floods.io.gauges import StageSeries, load_nwps, load_usgs, water_surface_navd88_m
from hidden_floods.io.nisar import read_gcov


def test_grid_from_bbox_is_snapped_and_covers_box():
    g = grid_from_lonlat_bbox((-86.02, 30.40, -85.74, 30.86), "EPSG:32616", 50.0)
    assert g.x0 % 50 == 0 and g.y0 % 50 == 0
    x, y = g.to_xy(-85.9, 30.6)
    r, c = g.index_of(x, y)
    assert g.contains_index(r, c)
    assert np.isclose(g.xs[1] - g.xs[0], 50) and np.isclose(g.ys[0] - g.ys[1], 50)


def test_block_mean_ignores_nan_and_drops_partial_blocks():
    a = np.arange(36, dtype=float).reshape(6, 6)
    a[0, 0] = np.nan
    m = block_mean(a, 5)
    assert m.shape == (1, 1)
    assert np.isclose(m[0, 0], np.nanmean(a[:5, :5]))


def _fake_gcov(path, x_edge0=1000.0, y_edge0=2000.0, n=20):
    xc = x_edge0 + 5 + 10 * np.arange(n)
    yc = y_edge0 - 5 - 10 * np.arange(n)
    hh = np.arange(n * n, dtype=np.float32).reshape(n, n)
    with h5py.File(path, "w") as h:
        g = h.create_group("science/LSAR/GCOV/grids/frequencyA")
        g["xCoordinates"], g["yCoordinates"] = xc, yc
        g["xCoordinateSpacing"], g["projection"] = 10.0, 32616
        g["HHHH"], g["HVHV"] = hh, hh / 10
    return hh


def test_read_gcov_block_averages_aligned_window(tmp_path):
    hh = _fake_gcov(tmp_path / "g.h5")
    grid = Grid("EPSG:32616", 1050.0, 1950.0, 50.0, 2, 2)  # starts 5 px right and 5 px down
    out = read_gcov(tmp_path / "g.h5", grid)
    assert out["HHHH"].shape == (2, 2)
    assert np.isclose(out["HHHH"][0, 0], hh[5:10, 5:10].mean())
    assert np.isclose(out["HVHV"][1, 1], hh[10:15, 10:15].mean() / 10)


def test_read_gcov_pads_outside_and_rejects_misalignment(tmp_path):
    _fake_gcov(tmp_path / "g.h5")
    edge = Grid("EPSG:32616", 1150.0, 2000.0, 50.0, 2, 1)  # second column falls off the 200 m wide product
    out = read_gcov(tmp_path / "g.h5", edge)
    assert np.isfinite(out["HHHH"][0, 0]) and np.isnan(out["HHHH"][0, 1])
    with pytest.raises(ValueError):
        read_gcov(tmp_path / "g.h5", Grid("EPSG:32616", 1003.0, 2000.0, 50.0, 1, 1))


def test_stage_series_interpolates_and_refuses_gaps():
    t = np.array(["2026-10-17T11:00", "2026-10-17T11:15", "2026-10-17T13:00"], dtype="datetime64[s]")
    s = StageSeries(t, np.array([10.0, 11.0, 12.0]))
    assert np.isclose(s.at("2026-10-17T11:07:30Z"), 10.5)
    assert s.at("2026-10-17T11:15:00Z") == 11.0
    with pytest.raises(ValueError):
        s.at("2026-10-17T12:00:00Z")


def test_loaders_read_saved_api_shapes(tmp_path):
    (tmp_path / "u.json").write_text(json.dumps({"features": [
        {"properties": {"time": "2026-10-17T11:15:00+00:00", "value": "13.41"}},
        {"properties": {"time": "2026-10-17T11:00:00+00:00", "value": "13.43"}}]}))
    (tmp_path / "n.json").write_text(json.dumps({"data": [{"validTime": "2026-10-09T00:30:00Z", "primary": 0.68}]}))
    u = load_usgs(tmp_path / "u.json")
    assert u.times[0] < u.times[1] and u.stage_ft[0] == 13.43
    assert load_nwps(tmp_path / "n.json").stage_ft[0] == 0.68


def test_water_surface_conversion():
    g = Gauge("Bruce", "USGS-02366500", -85.9, 30.45, 0.0, -0.423)
    assert np.isclose(water_surface_navd88_m(g, 13.43), (13.43 - 0.423) * 0.3048)


def test_site_config_loads():
    s = load_site("choctawhatchee")
    assert s.crs == "EPSG:32616" and len(s.gauges) == 3 and "076A_oct17" in s.pairs
    assert s.gauges[0].name == "Pittman" and s.thresholds_db[0] == 0.5
