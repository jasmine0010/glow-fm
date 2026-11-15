"""River and bay gauge records saved from the USGS Water Data OGC API and the NWS NWPS API.

The NWPS API keeps only about 30 days of observations, so the project works from saved JSON copies in the
site's ``gauges`` folder: ``usgs_<site>_stage_15min.json`` and ``nwps_<lid>_observed_<date>.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hidden_floods.config import Gauge

FT_TO_M = 0.3048


@dataclass
class StageSeries:
    """Stage in feet against UTC times (numpy datetime64[s]), sorted."""

    times: np.ndarray
    stage_ft: np.ndarray

    def at(self, when: str | np.datetime64, max_gap_minutes: float = 30.0) -> float:
        """Stage at ``when``, linearly interpolated between neighbours no more than ``max_gap_minutes`` apart."""
        t = np.datetime64(str(when).replace("Z", ""), "s")
        i = int(np.searchsorted(self.times, t))
        if i < len(self.times) and self.times[i] == t:
            return float(self.stage_ft[i])
        if i == 0 or i == len(self.times):
            raise ValueError(f"{when} is outside the record")
        t0, t1 = self.times[i - 1], self.times[i]
        if (t1 - t0) > np.timedelta64(int(max_gap_minutes * 60), "s"):
            raise ValueError(f"record gap around {when}: {t0} .. {t1}")
        w = (t - t0) / (t1 - t0)
        return float(self.stage_ft[i - 1] + w * (self.stage_ft[i] - self.stage_ft[i - 1]))


def _series(pairs) -> StageSeries:
    pairs = sorted((np.datetime64(t[:19], "s"), float(v)) for t, v in pairs if v not in (None, ""))
    times = np.array([p[0] for p in pairs], dtype="datetime64[s]")
    return StageSeries(times, np.array([p[1] for p in pairs]))


def load_usgs(path: Path) -> StageSeries:
    """USGS OGC ``continuous`` collection response (GeoJSON features with time/value)."""
    d = json.loads(Path(path).read_text())
    return _series((f["properties"]["time"], f["properties"]["value"]) for f in d.get("features", []))


def load_nwps(path: Path) -> StageSeries:
    """NWS NWPS ``stageflow/observed`` response (``data`` list with validTime/primary)."""
    d = json.loads(Path(path).read_text())
    return _series((r["validTime"], r["primary"]) for r in d.get("data", []))


def usgs_series(gauges_dir: Path, gauge: Gauge) -> StageSeries:
    site = gauge.id.removeprefix("USGS-")
    return load_usgs(Path(gauges_dir) / f"usgs_{site}_stage_15min.json")


def nwps_series(gauges_dir: Path, lid: str) -> StageSeries:
    matches = sorted(Path(gauges_dir).glob(f"nwps_{lid}_observed_*.json"))
    if not matches:
        raise FileNotFoundError(f"no saved NWPS record for {lid}")
    return load_nwps(matches[-1])


def water_surface_navd88_m(gauge: Gauge, stage_ft: float) -> float:
    """Water-surface elevation (NAVD88 m) from stage above the gauge datum (NGVD29 ft)."""
    return (gauge.datum_ft + stage_ft + gauge.navd88_offset_ft) * FT_TO_M
