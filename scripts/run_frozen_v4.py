"""Run the frozen v4 test once: ``python scripts/run_frozen_v4.py`` scores the three rivers in protocol order."""

import json

from hidden_floods.config import load_site
from hidden_floods.frozen_v4 import PASSES, RECEIPT, SCENES, evaluate_v4, rule_from
from hidden_floods.stack import Scene

rule = rule_from(json.loads(RECEIPT.read_text()))
listing = json.loads(SCENES.read_text())


def short(block):
    if block is None:
        return None
    ci = block["ci95"]["csi"] if block["ci95"] else None
    return {k: None if block["scores"][k] != block["scores"][k] else round(block["scores"][k], 3)
            for k in ("recall", "precision", "csi")} | {"csi_ci95": [round(v, 3) for v in ci] if ci else None}


for river, pair in PASSES.items():
    scenes = [Scene(**s) for s in listing[river]["scenes"]]
    r = evaluate_v4(load_site(river), pair, scenes, rule)
    print(json.dumps({
        "river": river, "pair": pair, "git_head": r["attempt"]["git_head"], "v4_threshold_db": round(r["v4_threshold_db"], 3), "v3_threshold_db": round(r["v3_threshold_db"], 3),
        "used_hh_minus_hv": r["used_hh_minus_hv"], "confident": r["confident"], "low_minus_high_db": r["low_minus_high_db"], "high_ground_db": r["high_ground_db"],
        "upland": r["upland_warning"], "baseline": r["baseline_scenes"], "timing": r["gauge_timing_class"], "coverage": r["coverage_of_confirmed_flooding"], "truth_ha": r["truth_ha"],
        "v4": short(r["primary_v4"]), "v3": short(r["baseline_v3_same_pixels"]), "v1": short(r["baseline_v1_same_pixels"]),
        "v4_ponding": short(r["secondary_v4_ponding_tolerant"]), "v4_single_dry": short(r["secondary_v4_single_dry_pass"]), "v4_corridor": short(r["secondary_v4_full_corridor"]),
        "v4_minus_v3": r["v4_minus_v3_csi"], "v4_minus_v1": r["v4_minus_v1_csi"], "land_cover": {k: short(v) for k, v in r["by_landcover"].items()},
    }), flush=True)
print("V4 RUN DONE", flush=True)
