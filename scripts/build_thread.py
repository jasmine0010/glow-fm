"""The act cards' particles (app/acts.js): real pixels of the Satilla flood on its frozen test pass, Oct 15.

    python scripts/build_thread.py

Writes app/data/story/thread.json. The particles are a fixed sample of the scored pixels of the hero pass (the opening
map), one per SAMPLE pixels, read from the frozen run's saved layers (outputs/satilla/047A_oct15/frozen_v4_layers.npz)
and the official map's (Copernicus GFM) scene on the audit date, as build_app.build_hero() reads them. No radar is
re-read and nothing is re-scored. Each particle keeps what the story's formations draw: where it is, what the river's
answer says, whether NISAR flagged it, the HH change (dB, as in Fig. 2), the water's height above the ground, whether
it's under trees, and whether the official map's own exclusion mask covers it.

The checks below hold the sample to the frozen record before anything is written.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_app import DATA, HERO_GFM_DATE, HERO_PASS, HERO_RIVER

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.drivers import LC_TREE
from hidden_floods.io.operational import gfm_mosaic
from hidden_floods.metrics import score
from hidden_floods.pipeline import analysis_grid

SAMPLE = 10          # one particle per this many pixels
SEED = 0


def r(x, k=2):
    return round(float(x), k)


def main():
    site = load_site(HERO_RIVER)
    grid = analysis_grid(site)
    pair = site.pairs[HERO_PASS]
    z = np.load(REPO_ROOT / "outputs" / HERO_RIVER / HERO_PASS / "frozen_v4_layers.npz")
    if z["wet"].shape != grid.shape:
        raise SystemExit(f"layers {z['wet'].shape} don't match the analysis grid {grid.shape}")
    frozen = json.loads((REPO_ROOT / "research" / f"overbank_{HERO_RIVER}_{HERO_PASS}_frozen_metrics.json").read_text())
    scored = z["region"] & z["mapped"]
    s = score(z["pred"], z["wet"], z["dry"], scored)
    if abs(s.csi - frozen["v4_csi"]) > 1e-9:
        raise SystemExit(f"layers score {s.csi}, frozen {frozen['v4_csi']}")
    gfm = gfm_mosaic(data_root() / HERO_RIVER / "ops_audit", HERO_GFM_DATE, grid)
    ok = np.isfinite(z["d_hh"]) & np.isfinite(z["depth"])
    wet, dry = z["wet"] & scored & ok, z["dry"] & scored & ok

    rng = np.random.default_rng(SEED)
    pick_wet = np.flatnonzero(wet.ravel())
    pick_wet = np.sort(rng.choice(pick_wet, size=len(pick_wet) // SAMPLE, replace=False))
    pick_dry = np.flatnonzero(dry.ravel())
    pick_dry = np.sort(rng.choice(pick_dry, size=min(len(pick_dry) // SAMPLE, len(pick_wet)), replace=False))
    idx = np.concatenate([pick_wet, pick_dry])
    rows, cols = np.unravel_index(idx, grid.shape)
    x = grid.x0 + (cols + 0.5) * grid.res
    y = grid.y0 - (rows + 0.5) * grid.res
    lon, lat = grid.to_lonlat(x, y)
    flat = lambda a: np.asarray(a).ravel()[idx]
    is_wet = np.r_[np.ones(len(pick_wet), bool), np.zeros(len(pick_dry), bool)]
    pred, d_hh, depth = flat(z["pred"]), flat(z["d_hh"]), flat(z["depth"])
    tree = flat(z["landcover"] == LC_TREE)
    covered, excluded = flat(gfm.covered), flat(gfm.excluded & gfm.covered)
    chain = flat(z["chainage"])

    # ---------- checks against the frozen record ----------
    px_ha = grid.res * grid.res / 1e4
    wet_ha_all = wet.sum() * px_ha
    recall_all = (z["pred"] & wet).sum() / wet.sum()
    recall_sample = pred[is_wet].mean()
    assert abs(len(pick_wet) * SAMPLE * px_ha - wet_ha_all) / wet_ha_all < 0.01, "sampled area doesn't match the estimate"
    assert abs(recall_sample - recall_all) < 0.03, f"sample recall {recall_sample:.3f} vs all {recall_all:.3f}"
    assert abs(recall_all - s.recall) < 0.01, "flooded pixels with finite inputs give a different recall"
    mask_all = (gfm.excluded & gfm.covered & wet).sum() / max(1, (gfm.covered & wet).sum())
    mask_sample = excluded[is_wet].sum() / max(1, covered[is_wet].sum())
    assert abs(mask_sample - mask_all) < 0.03, f"sample mask share {mask_sample:.3f} vs all {mask_all:.3f}"
    hero = json.loads((DATA / "manifest.json").read_text(encoding="utf8"))["hero"]["corners"]
    w, n = hero[0]
    e, s_ = hero[2]
    assert np.all((lon >= w) & (lon <= e) & (lat >= s_) & (lat <= n)), "a particle lies outside the opening map"
    assert np.all(depth[is_wet] > 0) and np.all(depth[~is_wet] < 0), "the river's answer and the water height disagree"

    out = {
        "site": HERO_RIVER, "pass": HERO_PASS, "time": pair.wet_time, "gfm_date": HERO_GFM_DATE, "sample": SAMPLE,
        "unit_ha": r(SAMPLE * px_ha, 3), "wet_ha": r(wet_ha_all, 1), "dry_ha": r(dry.sum() * px_ha, 1),
        "recall": r(recall_all, 4), "csi": r(s.csi, 4), "mask_share_wet": r(mask_all, 4), "covered_share_wet": r((gfm.covered & wet).sum() / wet.sum(), 4),
        "tree_share_wet": r((wet & (z["landcover"] == LC_TREE)).sum() / wet.sum(), 4),
        "fields": ["lon", "lat", "wet", "nisar", "d_hh_db", "water_m", "tree", "gfm_covered", "gfm_excluded", "chainage_km"],
        "particles": [[r(a, 5), r(b, 5), int(c), int(d), r(e_, 2), r(f, 2), int(g), int(h), int(i), r(j / 1000, 2)]
                      for a, b, c, d, e_, f, g, h, i, j in zip(lon, lat, is_wet, pred, d_hh, depth, tree, covered, excluded, chain, strict=True)],
    }
    path = DATA / "story" / "thread.json"
    path.write_text(json.dumps(out, separators=(",", ":"), allow_nan=False))
    print(f"thread: {len(pick_wet)} flooded + {len(pick_dry)} dry particles, 1 per {SAMPLE} px ({out['unit_ha']} ha); recall {recall_sample:.3f} "
          f"(all {recall_all:.3f}); mask share {mask_sample:.3f} (all {mask_all:.3f}); {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
