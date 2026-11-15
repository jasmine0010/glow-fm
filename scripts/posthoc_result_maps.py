"""POST-HOC, descriptive: maps of the frozen results (Results, Fig. 4).

Not part of any frozen test and not scored again. It only draws the saved layers of three frozen version-4 runs
(outputs/<river>/<pair>/frozen_v4_layers.npz): a strong pass, a typical one and a failure. For each it checks that the
layers give back the frozen CSI exactly, then writes three pictures on the run's 50 m grid:

- overview: the whole scored reach, each block coloured by its commonest class (so errors aren't exaggerated);
- change: the radar change (smoothed HH, dB) in a 16 x 12 km window where the most flooding was labelled or flagged;
- classes: the same window, every scored pixel as a hit (both flooded), a false alarm (GLOWfm only), a miss (the
  reference only) or both dry. Ground the reference didn't score is left clear.

Colours match the dashboard's "Both" view: blue where the two agree, magenta where only NISAR's map has water, cyan
where only the reference does.

    python scripts/posthoc_result_maps.py

Writes app/data/figures/maps_<river>_<pair>_{overview,change,classes}.png and app/data/figures/maps.json.
"""

import json

import numpy as np
from PIL import Image

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.metrics import score

OUT = REPO_ROOT / "app" / "data" / "figures"
PASSES = [("satilla", "047A_oct15", "strong"), ("st_marys", "098D_oct07", "typical"), ("pee_dee", "098D_jul27", "failed")]
WIN = (240, 320)                       # rows, cols: 12 x 16 km at 50 m
OVERVIEW_MAX = 420                     # longest side of the overview picture, px
DB = (-3.0, 6.0)                       # change ramp, dB
HIT, FALSE_ALARM, MISS, DRY = (111, 162, 238, 255), (214, 58, 214, 255), (40, 201, 224, 255), (120, 132, 140, 120)
COLORS = {1: HIT, 2: FALSE_ALARM, 3: MISS, 4: DRY}


def classes(z):
    """0 unscored, 1 hit, 2 false alarm, 3 miss, 4 both dry, on the frozen run's scored pixels."""
    scored = z["region"] & z["mapped"] & (z["wet"] | z["dry"])
    c = np.zeros(z["pred"].shape, np.uint8)
    c[scored & z["pred"] & z["wet"]] = 1
    c[scored & z["pred"] & z["dry"]] = 2
    c[scored & ~z["pred"] & z["wet"]] = 3
    c[scored & ~z["pred"] & z["dry"]] = 4
    return c


def paint(c):
    rgba = np.zeros((*c.shape, 4), np.uint8)
    for k, col in COLORS.items():
        rgba[c == k] = col
    return Image.fromarray(rgba, "RGBA")


def window(c):
    """Top-left of the WIN window holding the most flooded or flagged scored pixels."""
    h, w = min(WIN[0], c.shape[0]), min(WIN[1], c.shape[1])
    s = np.pad(np.isin(c, (1, 2, 3)).astype(np.int64).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    tot = s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]
    r, q = np.unravel_index(np.argmax(tot), tot.shape)
    return int(r), int(q), h, w


def overview(c):
    """Each block takes its commonest scored class, so a few stray pixels don't colour a whole block."""
    f = int(np.ceil(max(c.shape) / OVERVIEW_MAX))
    H, W = -(-c.shape[0] // f), -(-c.shape[1] // f)
    pad = np.zeros((H * f, W * f), np.uint8)
    pad[: c.shape[0], : c.shape[1]] = c
    blocks = pad.reshape(H, f, W, f).transpose(0, 2, 1, 3).reshape(H, W, f * f)
    counts = np.stack([(blocks == k).sum(-1) for k in range(5)], -1)
    counts[..., 0] = 0
    out = counts.argmax(-1).astype(np.uint8)
    out[counts.sum(-1) == 0] = 0
    return paint(out), f


def main():
    metrics = json.loads((REPO_ROOT / "app" / "data" / "metrics.json").read_text())
    # the frozen test records, with the latest test's trust light where it had one
    frozen = {f"{r['site']} {r['pair']}": r for r in metrics["held_out"] if str(r.get("method", "")).startswith("v4")}
    for o in metrics["overbank"]:
        key = f"{o['site']} {o['pair']}"
        frozen[key] = {**frozen.get(key, {}), **o}
    out = {"note": "Post hoc and descriptive: the saved layers of frozen runs, drawn; nothing re-scored.", "db_range": DB, "passes": []}
    for river, pair, kind in PASSES:
        z = np.load(REPO_ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
        sc = score(z["pred"], z["wet"] & z["mapped"], z["dry"] & z["mapped"], z["region"])
        f = frozen[f"{river} {pair}"]
        if abs(sc.csi - f["csi"]) > 1e-9:
            raise SystemExit(f"{river} {pair}: CSI {sc.csi} from the layers, frozen {f['csi']}")
        site = load_site(river)
        res = float(site.resolution_m)
        c = classes(z)
        # the overview is cropped to the scored reach
        rows, cols = np.where(c > 0)
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        crop = c[r0:r1, c0:c1]
        ov, factor = overview(crop)
        wr, wq, wh, ww = window(c)
        win = c[wr:wr + wh, wq:wq + ww]
        d = z["d_hh"][wr:wr + wh, wq:wq + ww]
        g = np.clip((d - DB[0]) / (DB[1] - DB[0]), 0, 1)
        grey = (40 + 215 * g).astype(np.uint8)
        alpha = np.where(np.isfinite(d) & z["mapped"][wr:wr + wh, wq:wq + ww], 255, 0).astype(np.uint8)
        change = Image.fromarray(np.dstack([grey, grey, grey, alpha]), "RGBA")
        stem = f"maps_{river}_{pair}"
        ov.save(OUT / f"{stem}_overview.png", optimize=True)
        change.save(OUT / f"{stem}_change.png", optimize=True)
        paint(win).save(OUT / f"{stem}_classes.png", optimize=True)
        px_ha = res * res / 1e4
        ha = {k: round(float((c == k).sum() * px_ha)) for k in (1, 2, 3, 4)}
        trust = f.get("signal")   # None: the first version-4 test came before the trust light
        out["passes"].append({
            "river": river, "pair": pair, "kind": kind, "csi": sc.csi, "recall": sc.recall, "precision": sc.precision, "trust": trust,
            "method": f.get("method", "v4, overbank test (frozen)"), "pixel_m": res,
            "hit_ha": ha[1], "false_alarm_ha": ha[2], "miss_ha": ha[3], "dry_ha": ha[4],
            "overview": {"image": f"data/figures/{stem}_overview.png", "px": list(ov.size), "block_m": res * factor,
                         "km": [round((c1 - c0) * res / 1000, 1), round((r1 - r0) * res / 1000, 1)],
                         # the window, as a fraction of the overview picture: x, y, width, height
                         "window_frac": [(wq - c0) / (c1 - c0), (wr - r0) / (r1 - r0), ww / (c1 - c0), wh / (r1 - r0)]},
            "window": {"change": f"data/figures/{stem}_change.png", "classes": f"data/figures/{stem}_classes.png", "px": [ww, wh],
                       "km": [ww * res / 1000, wh * res / 1000]},
        })
        print(f"{river:9s} {pair:11s} {kind:7s} CSI {sc.csi:.3f}  hit {ha[1]} ha, false alarm {ha[2]} ha, miss {ha[3]} ha; "
              f"overview {ov.size} (1 px = {res * factor:.0f} m), window at row {wr}, col {wq}", flush=True)
    (OUT / "maps.json").write_text(json.dumps(out, indent=1))
    print(f"-> {OUT / 'maps.json'}")


if __name__ == "__main__":
    main()
