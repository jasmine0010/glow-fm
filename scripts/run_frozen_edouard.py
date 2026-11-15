"""Run the frozen Edouard test once: ``python scripts/run_frozen_edouard.py`` scores all four passes in protocol order."""

import json

from hidden_floods.config import load_site
from hidden_floods.frozen_edouard import evaluate_edouard

ORDER = (("village_creek", "134A_sep03"), ("pine_island", "012D_sep07"), ("village_creek", "012D_sep07"), ("pine_island", "134A_sep03"))


def short(block):
    if block is None:
        return None
    ci = block["ci95"]["csi"] if block["ci95"] else None
    return {k: None if block["scores"][k] != block["scores"][k] else round(block["scores"][k], 3)
            for k in ("recall", "precision", "csi")} | {"csi_ci95": [round(v, 3) for v in ci] if ci else None}


for site_name, pair in ORDER:
    r = evaluate_edouard(load_site(site_name), pair)
    print(json.dumps({
        "river": site_name, "pair": pair, "git_head": r["attempt"]["git_head"], "threshold_db": round(r["v3_threshold_db"], 3),
        "timing": r["gauge_timing_class"], "upland": r["upland_warning"], "coverage": r["coverage_of_confirmed_flooding"],
        "truth_ha": r["truth_ha"], "valid": r["valid_share_of_labelled"], "v3": short(r["primary_v3_mapped_area"]),
        "v3_ponding": short(r["secondary_v3_ponding_tolerant"]), "v3_corridor": short(r["secondary_v3_full_corridor"]),
        "v2": short(r["baseline_v2_same_pixels"]), "v1": short(r["baseline_v1_same_pixels"]),
        "v3_minus_v2": r["v3_minus_v2_csi"], "v3_minus_v1": r["v3_minus_v1_csi"],
        "land_cover": {k: short(v) for k, v in r["by_landcover"].items()},
    }), flush=True)
print("EDOUARD RUN DONE", flush=True)
