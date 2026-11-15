"""How much of GFM's blind spot is just the mask's size? Writes research/audit_base_rate.json.

Compares estimated flooded ground with estimated dry ground in the same corridor, so the base rate is the fair one. Also
reports what GFM mapped outside its mask, which is the only part that tests detection, and land cover of each group.
"""

import json

import numpy as np

from hidden_floods.audit import scene_time, truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.io.operational import dswx_s1_mosaic, dswx_water, gfm_mosaic
from hidden_floods.metrics import block_ids
from hidden_floods.trust import worldcover_class, worldcover_on_grid

PASSES = (("choctawhatchee", "20261010"), ("choctawhatchee", "20261022"), ("pearl", "20260628"), ("pearl", "20260705"), ("yellow", "20261010"), ("yellow", "20261022"))
LC = {1: "tree", 2: "wetland", 0: "other", 3: "crop_grass_shrub"}


def cover(lc, m):
    return {LC[k]: round(float((lc[m] == k).mean()), 3) for k in LC} if m.any() else None


def difference_ci(wet, dry, excluded, blocks, n=2000, seed=0):
    """Interval for (share of wet in mask) - (share of dry in mask), resampling 2 km blocks along the valley."""
    lab = wet | dry
    uniq, inv = np.unique(blocks[lab], return_inverse=True)
    per = np.zeros((len(uniq), 4))
    for i, m in enumerate((wet[lab] & excluded[lab], wet[lab], dry[lab] & excluded[lab], dry[lab])):
        np.add.at(per, (inv, i), m)
    draws = per[np.random.default_rng(seed).integers(0, len(uniq), size=(n, len(uniq)))].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        diff = draws[:, 0] / draws[:, 1] - draws[:, 2] / draws[:, 3]
    return [float(np.nanpercentile(diff, 2.5)), float(np.nanpercentile(diff, 97.5))]


def main():
    rows = []
    for name, date in PASSES:
        site = load_site(name)
        ctx = truth_context(site, scene_time(site.operational_dir, date))
        grid, t = ctx.grid, ctx.truth
        gfm = gfm_mosaic(site.operational_dir, date, grid)
        lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
        region = ctx.supported & gfm.covered & ~ctx.permanent_water
        wet, dry = t.wet & region, t.dry & region
        a = grid.pixel_area_ha
        out_wet, out_dry = wet & ~gfm.excluded, dry & ~gfm.excluded
        wtr = dswx_s1_mosaic(site.operational_dir, date, grid)
        has_dswx = (wtr != 255).any()
        water = dswx_water(wtr) if has_dswx else None
        rows.append({
            "site": name, "date": date, "estimated_ha": float(wet.sum() * a), "dry_ha": float(dry.sum() * a),
            "box_share_in_mask": float(gfm.excluded[gfm.covered].mean()),
            "corridor_share_in_mask": float(gfm.excluded[(t.corridor) & gfm.covered & ~ctx.permanent_water].mean()),
            "wet_share_in_mask": float(gfm.excluded[wet].mean()), "dry_share_in_mask": float(gfm.excluded[dry].mean()),
            "difference_ci95": difference_ci(wet, dry, gfm.excluded, block_ids(t.chainage_m, 2000.0)),
            "gfm_on_wet_ha": float((gfm.flood & wet).sum() * a), "gfm_on_wet_in_mask_ha": float((gfm.flood & wet & gfm.excluded).sum() * a),
            "wet_outside_mask_ha": float(out_wet.sum() * a), "gfm_on_wet_outside_mask_ha": float((gfm.flood & out_wet).sum() * a),
            "recall_outside_mask": float((gfm.flood & out_wet).sum() / out_wet.sum()) if out_wet.any() else None,
            "dry_outside_mask_ha": float(out_dry.sum() * a), "gfm_on_dry_outside_mask_ha": float((gfm.flood & out_dry).sum() * a),
            "land_cover_wet": cover(lc, wet), "land_cover_wet_outside_mask": cover(lc, out_wet), "land_cover_wet_in_mask": cover(lc, wet & gfm.excluded),
            "dswx_recall_inside_mask": float((water & wet & gfm.excluded & (wtr != 255)).sum() / max((wet & gfm.excluded & (wtr != 255)).sum(), 1)) if has_dswx else None,
            "dswx_recall_outside_mask": float((water & out_wet & (wtr != 255)).sum() / max((out_wet & (wtr != 255)).sum(), 1)) if has_dswx else None,
        })
        print(json.dumps(rows[-1]), flush=True)
    (REPO_ROOT / "research" / "audit_base_rate.json").write_text(json.dumps(rows, indent=1))
    print("BASE RATE DONE", flush=True)


if __name__ == "__main__":
    main()
