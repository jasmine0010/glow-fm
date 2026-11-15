"""Site configuration: one TOML file per study site under ``sites/``."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = Path("C:/Users/Jasmi/nisar-data")


def data_root() -> Path:
    """Root folder for large data, kept outside the repository (and outside OneDrive)."""
    return Path(os.environ.get("HIDDEN_FLOODS_DATA", DEFAULT_DATA_ROOT))


@dataclass(frozen=True)
class Gauge:
    name: str
    id: str
    lon: float
    lat: float
    datum_ft: float
    navd88_offset_ft: float


@dataclass(frozen=True)
class Pair:
    name: str
    wet: str
    dry: str
    wet_time: str
    dry_time: str


@dataclass(frozen=True)
class Site:
    name: str
    crs: str
    resolution_m: float
    bbox: tuple[float, float, float, float]
    data_dir: Path
    dem_path: Path
    gauges_dir: Path
    operational_dir: Path
    gcov: dict[str, str]
    gunw: dict[str, str]
    pairs: dict[str, Pair]
    gauges: tuple[Gauge, ...]
    valley_line: tuple[tuple[float, float], ...]
    corridor_m: float
    margin_m: float
    max_dry_height_m: float
    calibration_max_chainage_m: float
    bootstrap_block_m: float
    forest_hv_db: float
    thresholds_db: tuple[float, ...]

    def gcov_path(self, key: str) -> Path:
        return self.data_dir / f"{self.gcov[key]}.h5"

    def gunw_path(self, key: str) -> Path:
        return self.data_dir / f"{self.gunw[key]}.h5"


def load_site(name: str, sites_dir: Path | None = None) -> Site:
    path = (sites_dir or REPO_ROOT / "sites") / f"{name}.toml"
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    data_dir = data_root() / raw["data"]["root"]
    return Site(
        name=raw["name"],
        crs=raw["crs"],
        resolution_m=float(raw["resolution_m"]),
        bbox=tuple(raw["bbox"]),
        data_dir=data_dir,
        dem_path=data_dir / raw["data"]["dem"],
        gauges_dir=data_dir / raw["data"]["gauges"],
        operational_dir=data_dir / raw["data"]["operational"],
        gcov=dict(raw["gcov"]),
        gunw=dict(raw["gunw"]),
        pairs={k: Pair(name=k, **v) for k, v in raw["pairs"].items()},
        gauges=tuple(Gauge(**g) for g in raw["gauges"]),
        valley_line=tuple(tuple(p) for p in raw["valley"]["line"]),
        corridor_m=float(raw["valley"]["corridor_m"]),
        margin_m=float(raw["truth"]["margin_m"]),
        max_dry_height_m=float(raw["truth"]["max_dry_height_m"]),
        calibration_max_chainage_m=float(raw["split"]["calibration_max_chainage_m"]),
        bootstrap_block_m=float(raw["split"]["bootstrap_block_m"]),
        forest_hv_db=float(raw["detector"]["forest_hv_db"]),
        thresholds_db=tuple(float(t) for t in raw["detector"]["thresholds_db"]),
    )
