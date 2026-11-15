"""Score the frozen v2 detector by condition across all NISAR pairs and paint per-pixel trust layers.

    python scripts/build_trust_map.py

Writes outputs/trust/trust_table.json, outputs/trust/trust_table.md and one trust GeoTIFF per pair
(0 = outside the valley corridor / no data, 1 green, 2 amber, 3 red, 4 insufficient data).
"""

import json

import numpy as np
import rasterio

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.frozen_v2 import RECEIPT_V2
from hidden_floods.selfcal import SelfCalRule
from hidden_floods.trust import INCIDENCE_EDGES, LANDCOVER, TIMING, TRUST, evaluate_pair, pooled_scores, trust_class

PAIRS = [("choctawhatchee", "076A_oct17", "development"), ("choctawhatchee", "127D_oct21", "development"),
         ("pearl", "105A_jul03", "development"), ("pearl", "156D_jun25", "development"),
         ("tangipahoa", "105A_jun21", "held-out"), ("tangipahoa", "156D_jun25", "held-out")]
OUT = REPO_ROOT / "outputs" / "trust"


def fmt(c):
    ci = c.get("ci95", {}).get("csi")
    return (f"{c['truth_wet_ha']:,.0f} | {c['csi']:.2f}" + (f" ({ci[0]:.2f}-{ci[1]:.2f})" if ci else "")
            + f" | {c['recall']:.2f} | {c['precision']:.2f}")


def paint(ev, two, one):
    """Trust class per pixel from the timing x land-cover table, falling back to timing only (4 = no data)."""
    key = ev.timing.astype(int) * 10 + ev.landcover
    layer = np.zeros(ev.grid.shape, np.uint8)
    for lab in np.unique(key):
        tc = trust_class(two.get(int(lab), {})) or trust_class(one.get(int(lab) // 10, {}))
        layer[key == lab] = tc if tc else 4
    layer[~ev.ctx.truth.corridor] = 0
    return layer


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rec = json.loads(RECEIPT_V2.read_text())
    rule = SelfCalRule(**{k: v for k, v in rec["v2_rule"].items() if k != "type"})
    evals = []
    for site_name, pair, role in PAIRS:
        ev = evaluate_pair(load_site(site_name), pair, rule, data_root() / "worldcover", role)
        print(f"{site_name} {pair}: threshold {ev.threshold_db:.2f} dB, timing classes at gauges "
              f"{sorted({TIMING[int(v)] for v in np.unique(ev.timing)})}")
        evals.append(ev)

    pair_index = {id(e): i for i, e in enumerate(evals)}
    tables = {
        "timing": (pooled_scores(evals, lambda e: e.timing), TIMING),
        "landcover": (pooled_scores(evals, lambda e: e.landcover), LANDCOVER),
        "incidence": (pooled_scores(evals, lambda e: np.digitize(e.incidence, INCIDENCE_EDGES[1:-1])),
                      {i: f"{INCIDENCE_EDGES[i]:.0f}-{INCIDENCE_EDGES[i + 1]:.0f} deg" for i in range(4)}),
        "timing_x_landcover": (pooled_scores(evals, lambda e: e.timing.astype(int) * 10 + e.landcover),
                               {t * 10 + c: f"{TIMING[t]} / {LANDCOVER[c]}" for t in TIMING for c in LANDCOVER}),
        "pair": (pooled_scores(evals, lambda e: np.full(e.grid.shape, pair_index[id(e)])),
                 {i: f"{s} {p} ({r})" for i, (s, p, r) in enumerate(PAIRS)}),
    }
    md = ["# Trust table: frozen method v2, all six NISAR pairs (four development, two held-out)", "",
          "Scores pooled over pairs within each condition; 95% CI from a block bootstrap (pair x 2 km valley blocks).",
          "Development pairs are in-sample for v2, so treat this as a description of behaviour, not a validation.", ""]
    js = {}
    for name, (cells, names) in tables.items():
        md += [f"## By {name.replace('_', ' ')}", "", "| Condition | Flooded truth (ha) | CSI (95% CI) | Recall | Precision | Trust |",
               "|---|---|---|---|---|---|"]
        js[name] = {}
        for lab, c in cells.items():
            tc = trust_class(c)
            js[name][names.get(lab, str(lab))] = {**c, "trust": TRUST[tc]}
            if c["truth_wet_ha"] > 0 or c["fp"] > 0:
                md.append(f"| {names.get(lab, lab)} | {fmt(c)} | {TRUST[tc]} |")
        md.append("")
    (OUT / "trust_table.json").write_text(json.dumps(js, indent=2, default=float))
    (OUT / "trust_table.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))

    # Leave-one-flood-out check: build the timing x land-cover table without a flood, paint that flood, and score
    # the flood's pixels by the trust class they were given. Green should score clearly better than red.
    loo_md = ["## Leave-one-flood-out check", "",
              "Trust table rebuilt without the flood being tested; the flood's pixels are then scored by class.", "",
              "| Held-out flood | Trust class | Flooded truth (ha) | CSI (95% CI) | Recall | Precision |",
              "|---|---|---|---|---|---|"]
    loo = {}
    for held in sorted({e.site for e in evals}):
        train = [e for e in evals if e.site != held]
        test = [e for e in evals if e.site == held]
        two_t, one_t = pooled_scores(train, lambda e: e.timing.astype(int) * 10 + e.landcover), \
            pooled_scores(train, lambda e: e.timing)
        layers = {id(e): paint(e, two_t, one_t) for e in test}
        cells = pooled_scores(test, lambda e, _l=layers: _l[id(e)])
        loo[held] = {TRUST.get(k, "insufficient data") if k != 4 else "insufficient data": v for k, v in cells.items()}
        for k, c in cells.items():
            if k and (c["truth_wet_ha"] > 0 or c["fp"] > 0):
                loo_md.append(f"| {held} | {TRUST.get(k, 'insufficient data') if k != 4 else 'insufficient data'} | "
                              f"{fmt(c)} |")
    js["leave_one_flood_out"] = loo
    (OUT / "trust_table.json").write_text(json.dumps(js, indent=2, default=float))
    md += [*loo_md, ""]
    (OUT / "trust_table.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(loo_md))

    # Per-pixel trust: timing x land-cover cell, falling back to the timing-only cell when the 2-way cell is thin.
    two, one = tables["timing_x_landcover"][0], tables["timing"][0]
    for ev in evals:
        layer = paint(ev, two, one)
        path = OUT / f"{ev.site}_{ev.pair}_trust.tif"
        with rasterio.open(path, "w", driver="GTiff", height=ev.grid.height, width=ev.grid.width, count=1, dtype="uint8",
                           crs=ev.grid.crs, transform=ev.grid.transform, nodata=0, compress="deflate") as dst:
            dst.write(layer, 1)
            dst.write_colormap(1, {0: (0, 0, 0, 0), 1: (46, 160, 67, 255), 2: (230, 170, 30, 255),
                                   3: (210, 50, 50, 255), 4: (150, 150, 150, 255)})
        shares = {TRUST.get(k, "insufficient data"): round(float((layer[ev.ctx.truth.corridor] == k).mean()), 3)
                  for k in (1, 2, 3, 4)}
        print(f"trust layer {path.name}: corridor share {shares}")


if __name__ == "__main__":
    main()
