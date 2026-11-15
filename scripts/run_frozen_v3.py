"""Run the frozen method-v3 test once: ``python scripts/run_frozen_v3.py yellow 004A_oct12``."""

import argparse
import json

from hidden_floods.config import load_site
from hidden_floods.frozen_v3 import evaluate_frozen_v3

parser = argparse.ArgumentParser()
parser.add_argument("site")
parser.add_argument("pair")
args = parser.parse_args()

r = evaluate_frozen_v3(load_site(args.site), args.pair)


def short(block):
    return {k: round(block["scores"][k], 3) for k in ("recall", "precision", "csi", "f1")} | {
        "csi_ci95": [round(v, 3) for v in block["ci95"]["csi"]]}


print(json.dumps({
    "pair": r["pair"], "git_head": r["attempt"]["git_head"], "changed_since_freeze": r["changed_since_freeze"],
    "v3_threshold_db": round(r["v3_threshold_db"], 3), "gauge_timing_class": r["gauge_timing_class"],
    "coverage_of_confirmed_flooding": r["coverage_of_confirmed_flooding"], "truth_ha": r["truth_ha"],
    "valid_share_of_labelled": r["valid_share_of_labelled"],
    "PRIMARY v3 (mapped area)": short(r["primary_v3_mapped_area"]),
    "secondary v3 ponding-tolerant": short(r["secondary_v3_ponding_tolerant"]),
    "secondary v3 no abstention": short(r["secondary_v3_no_abstention"]),
    "secondary v3 full corridor": short(r["secondary_v3_full_corridor"]),
    "baseline v2 (same pixels)": short(r["baseline_v2_same_pixels"]),
    "baseline v1 (same pixels)": short(r["baseline_v1_same_pixels"]),
    "v3 minus v2 CSI": r["v3_minus_v2_csi"], "v3 minus v1 CSI": r["v3_minus_v1_csi"],
    "by land cover": {k: short(v) for k, v in r["by_landcover"].items()},
}, indent=2))
