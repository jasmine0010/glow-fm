"""Module A — flooded-forest detection from a same-track GCOV pair.

Physics: water under trunks forms a corner reflector, so L-band HH rises strongly while HV (volume scattering) barely
changes. Change detection finds *newly* flooded forest; an absolute rule is needed for swamp already wet on the
reference date.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


def to_db(power: np.ndarray, floor: float = 1e-6) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return 10.0 * np.log10(np.clip(power, floor, None))


@dataclass
class PairFeatures:
    """Backscatter features (dB) for a wet/dry pair on the analysis grid."""

    hh_dry: np.ndarray
    hv_dry: np.ndarray
    hh_wet: np.ndarray
    hv_wet: np.ndarray

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.hh_dry) & np.isfinite(self.hv_dry) & np.isfinite(self.hh_wet) & np.isfinite(self.hv_wet)

    @property
    def d_hh(self) -> np.ndarray:
        return self.hh_wet - self.hh_dry

    @property
    def d_hv(self) -> np.ndarray:
        return self.hv_wet - self.hv_dry

    @property
    def ratio_wet(self) -> np.ndarray:
        return self.hh_wet - self.hv_wet

    @property
    def d_ratio(self) -> np.ndarray:
        return (self.hh_wet - self.hv_wet) - (self.hh_dry - self.hv_dry)


def pair_features(dry: dict[str, np.ndarray], wet: dict[str, np.ndarray]) -> PairFeatures:
    """Features from GCOV linear-power dicts (keys ``HHHH``, ``HVHV``) of the dry and wet scenes."""
    return PairFeatures(to_db(dry["HHHH"]), to_db(dry["HVHV"]), to_db(wet["HHHH"]), to_db(wet["HVHV"]))


@dataclass(frozen=True)
class ChangeRule:
    """Flooded forest where the dry-date HV indicates woody cover and HH rose by more than ``d_hh_db``."""

    d_hh_db: float
    forest_hv_db: float = -16.0

    def forest(self, f: PairFeatures) -> np.ndarray:
        return f.valid & (f.hv_dry > self.forest_hv_db)

    def apply(self, f: PairFeatures) -> np.ndarray:
        return self.forest(f) & (f.d_hh > self.d_hh_db)

    def margin_db(self, f: PairFeatures) -> np.ndarray:
        """How far ΔHH sits above the threshold; a simple confidence score (negative = not flagged)."""
        return np.where(self.forest(f), f.d_hh - self.d_hh_db, -np.inf)

    def to_dict(self) -> dict:
        return {"type": "change", **asdict(self)}


@dataclass(frozen=True)
class AbsoluteRule:
    """Flooded forest from the wet scene alone: strong HH and high HH/HV (handbook-style), for already-wet swamp."""

    hh_db: float
    ratio_db: float
    forest_hv_db: float = -16.0

    def apply(self, f: PairFeatures) -> np.ndarray:
        return f.valid & (f.hv_dry > self.forest_hv_db) & (f.hh_wet > self.hh_db) & (f.ratio_wet > self.ratio_db)

    def to_dict(self) -> dict:
        return {"type": "absolute", **asdict(self)}


@dataclass(frozen=True)
class CombinedRule:
    change: ChangeRule
    absolute: AbsoluteRule | None = None

    def apply(self, f: PairFeatures) -> np.ndarray:
        out = self.change.apply(f)
        return out | self.absolute.apply(f) if self.absolute is not None else out

    def to_dict(self) -> dict:
        return {"type": "combined", "change": self.change.to_dict(),
                "absolute": self.absolute.to_dict() if self.absolute else None}
