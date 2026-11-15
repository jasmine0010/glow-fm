"""Run the frozen method-v2 held-out evaluation once, e.g. ``python scripts/run_frozen_v2.py tangipahoa 105A_jun21``."""

import argparse
import json

from hidden_floods.config import load_site
from hidden_floods.frozen_v2 import evaluate_frozen_v2

parser = argparse.ArgumentParser()
parser.add_argument("site")
parser.add_argument("pair")
args = parser.parse_args()

r = evaluate_frozen_v2(load_site(args.site), args.pair)
short = lambda block: {k: round(block["scores"][k], 3) for k in ("recall", "precision", "csi", "f1")} | {
    "csi_ci95": [round(v, 3) for v in block["ci95"]["csi"]]}
print(json.dumps({"pair": r["pair"], "modules_changed_since_freeze": r["modules_changed_since_freeze"],
                  "v2_threshold_db": round(r["v2_threshold_db"], 3), "truth_ha": r["truth_ha"],
                  "PRIMARY v2 (gauge-supported)": short(r["primary_v2_gauge_supported"]),
                  "secondary v2 (full corridor)": short(r["secondary_v2_full_corridor"]),
                  "baseline v1 (gauge-supported)": short(r["baseline_v1_gauge_supported"])}, indent=2))
