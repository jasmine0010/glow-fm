"""POST-HOC, descriptive: how much the frozen scores depend on the reference and on the bootstrap's block size.

Not part of any frozen test; no frozen number changes. It reads the saved layers of the seven judged version-4 runs
(outputs/<river>/<pair>/frozen_v4_layers.npz), first checks that each one gives back its frozen CSI exactly, then asks
three questions the Results page needs answered (Fig. 4 and Fig. 9):

1. Water-surface shift. The reference ("the river's answer") calls a pixel flooded where the interpolated water stands
   more than 0.5 m above the lidar ground, and dry where the ground is 0.5-5 m above the water. Hiding a gauge shows the
   interpolated level can be off by a median 1.14 m (Fig. 9). Here the whole water surface is moved by -1 to +1 m and
   the same frozen map is scored again. Pixels the frozen reference left out for other reasons (the corridor, the
   connection to the river, distance to a gauge, permanent water) stay out; pixels in its unlabelled 1 m band are
   relabelled by depth alone.
2. Block size. The frozen 95% intervals resample 2 km blocks along the valley. Flood extent is correlated over longer
   distances, so the same intervals are recomputed with 5 km and 10 km blocks.
3. Per pass, not pooled: recall and precision under trees on each pass, so no headline rests on pooled pixels.

    python scripts/posthoc_reference_checks.py

Writes app/data/figures/reference_checks.json.
"""

import json

import numpy as np

from hidden_floods.config import REPO_ROOT
from hidden_floods.drivers import LC_TREE
from hidden_floods.metrics import block_bootstrap, block_ids, score

OUT = REPO_ROOT / "app" / "data" / "figures" / "reference_checks.json"
SHIFTS = [-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0]
BLOCKS_M = [2000, 5000, 10000]
WET_ABOVE, DRY_FROM, DRY_TO = 0.5, -5.0, -0.5   # the frozen reference's margins (m of water above ground)


def main():
    metrics = json.loads((REPO_ROOT / "app" / "data" / "metrics.json").read_text())
    frozen = {f"{o['site']} {o['pair']}": o for o in metrics["overbank"]}
    frozen |= {f"{r['site']} {r['pair']}": r for r in metrics["held_out"] if str(r.get("method", "")).startswith("v4")}
    judged = [p for p in json.loads((REPO_ROOT / "app" / "data" / "figures" / "separability.json").read_text())["passes"]]
    out = {"note": "Post hoc and descriptive; no frozen number changes.", "shifts_m": SHIFTS, "blocks_m": BLOCKS_M, "passes": []}
    for p in judged:
        river, pair = p["river"], p["pair"]
        z = np.load(REPO_ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
        pred, wet, dry, region, mapped, depth = z["pred"], z["wet"], z["dry"], z["region"], z["mapped"], z["depth"]
        wet_m, dry_m = wet & mapped, dry & mapped
        base = score(pred, wet_m, dry_m, region)
        f = frozen[f"{river} {pair}"]
        if abs(base.csi - f["csi"]) > 1e-9:
            raise SystemExit(f"{river} {pair}: CSI {base.csi} from the layers, frozen {f['csi']}")
        # Pixels the reference could label: its labelled pixels plus its unlabelled band, all inside the scored region.
        band = np.isfinite(depth) & (np.abs(depth) <= WET_ABOVE)
        eligible = region & mapped & (wet | dry | band)
        shift = []
        for s in SHIFTS:
            d = depth + s
            w2, r2 = eligible & (d > WET_ABOVE), eligible & (d >= DRY_FROM) & (d <= DRY_TO)
            sc = score(pred, w2, r2, region)
            shift.append({"shift_m": s, "csi": sc.csi, "recall": sc.recall, "precision": sc.precision, "wet_px": int(w2.sum())})
        if abs(shift[SHIFTS.index(0.0)]["csi"] - base.csi) > 1e-9:
            raise SystemExit(f"{river} {pair}: the relabelled reference doesn't give back the frozen CSI at zero shift")
        blocks, n_blocks = {}, {}
        labelled = (wet_m | dry_m) & region
        for b in BLOCKS_M:
            ids = block_ids(z["chainage"], b)
            ci = block_bootstrap(pred, wet_m, dry_m, ids, region, n_boot=2000, seed=0, metrics=("csi",))["csi"]
            blocks[str(b)] = list(ci)
            n_blocks[str(b)] = len(np.unique(ids[labelled]))   # fewer than about 5 blocks can't be resampled usefully
        tree = z["landcover"] == LC_TREE
        under = score(pred, wet_m & tree, dry_m & tree, region)
        row = {"river": river, "pair": pair, "csi": base.csi, "trust": p.get("trust"), "shift": shift, "ci_by_block": blocks, "n_blocks": n_blocks,
               "trees": {"recall": under.recall, "precision": under.precision, "wet_px": int((wet_m & tree & region).sum())}}
        if "ci95" in f:
            row["frozen_ci95"] = f["ci95"]
        out["passes"].append(row)
        print(f"{river:13s} {pair:11s} CSI {base.csi:.3f}  shift -1..+1 m: "
              + " ".join(f"{x['csi']:.2f}" for x in shift)
              + "  CI 2/5/10 km: " + " ".join(f"{blocks[str(b)][0]:.2f}-{blocks[str(b)][1]:.2f}" for b in BLOCKS_M)
              + f"  trees R {under.recall:.2f} P {under.precision:.2f}", flush=True)
    # How far the shift moves each score, as a range over -0.5..+0.5 m and -1..+1 m.
    for row in out["passes"]:
        v = {x["shift_m"]: x["csi"] for x in row["shift"]}
        row["range_half_m"] = [min(v[s] for s in (-0.5, -0.25, 0.0, 0.25, 0.5)), max(v[s] for s in (-0.5, -0.25, 0.0, 0.25, 0.5))]
        row["range_1_m"] = [min(v.values()), max(v.values())]
    OUT.write_text(json.dumps(out, indent=1))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
