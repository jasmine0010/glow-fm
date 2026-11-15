"""Scores against truth labels, with spatial block-bootstrap intervals (neighbouring pixels are not independent)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class Scores:
    tp: int
    fn: int
    fp: int
    tn: int

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else float("nan")

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else float("nan")

    @property
    def csi(self) -> float:
        d = self.tp + self.fn + self.fp
        return self.tp / d if d else float("nan")

    @property
    def f1(self) -> float:
        d = 2 * self.tp + self.fn + self.fp
        return 2 * self.tp / d if d else float("nan")

    def to_dict(self, pixel_area_ha: float | None = None) -> dict:
        out = {**asdict(self), "recall": self.recall, "precision": self.precision, "csi": self.csi, "f1": self.f1}
        if pixel_area_ha:
            out.update({f"{k}_ha": v * pixel_area_ha for k, v in asdict(self).items()})
        return out


def score(pred: np.ndarray, truth_wet: np.ndarray, truth_dry: np.ndarray, region: np.ndarray | None = None) -> Scores:
    """Confusion counts over labelled pixels (optionally restricted to ``region``)."""
    wet, dry = truth_wet, truth_dry
    if region is not None:
        wet, dry = wet & region, dry & region
    return Scores(int((pred & wet).sum()), int((~pred & wet).sum()), int((pred & dry).sum()), int((~pred & dry).sum()))


def block_ids(chainage_m: np.ndarray, block_m: float) -> np.ndarray:
    """Block index of each pixel along the valley; blocks are the bootstrap resampling unit."""
    return np.floor(chainage_m / block_m).astype(np.int64)


def block_bootstrap(pred, truth_wet, truth_dry, blocks, region=None, n_boot: int = 2000, seed: int = 0,
                    metrics=("recall", "precision", "csi", "f1")) -> dict[str, tuple[float, float]]:
    """95% percentile intervals from resampling whole blocks with replacement."""
    labelled = (truth_wet | truth_dry) if region is None else (truth_wet | truth_dry) & region
    ids = blocks[labelled]
    uniq, inv = np.unique(ids, return_inverse=True)
    p, w = pred[labelled], truth_wet[labelled]
    k = len(uniq)
    per = np.zeros((k, 4))
    np.add.at(per, (inv, 0), p & w)
    np.add.at(per, (inv, 1), ~p & w)
    np.add.at(per, (inv, 2), p & ~w)
    np.add.at(per, (inv, 3), ~p & ~w)
    rng = np.random.default_rng(seed)
    draws = per[rng.integers(0, k, size=(n_boot, k))].sum(axis=1)
    tp, fn, fp = draws[:, 0], draws[:, 1], draws[:, 2]
    with np.errstate(invalid="ignore", divide="ignore"):
        vals = {"recall": tp / (tp + fn), "precision": tp / (tp + fp), "csi": tp / (tp + fn + fp),
                "f1": 2 * tp / (2 * tp + fn + fp)}
    return {m: (float(np.nanpercentile(vals[m], 2.5)), float(np.nanpercentile(vals[m], 97.5))) for m in metrics}


def sweep_threshold(score_map: np.ndarray, eligible: np.ndarray, truth_wet, truth_dry, region, thresholds):
    """Score ``eligible & (score_map > t)`` for each threshold; returns rows and the CSI-best threshold."""
    rows = []
    for t in thresholds:
        s = score(eligible & (score_map > t), truth_wet, truth_dry, region)
        rows.append({"threshold": float(t), **s.to_dict()})
    best = max(rows, key=lambda r: (np.nan_to_num(r["csi"], nan=-1.0), -r["threshold"]))
    return rows, best["threshold"]
