"""Run the frozen held-out evaluation once, e.g. ``python scripts/run_frozen.py pearl 105A_jul03``."""

import argparse
import json

from hidden_floods.config import load_site
from hidden_floods.frozen import evaluate_frozen

parser = argparse.ArgumentParser()
parser.add_argument("site")
parser.add_argument("pair")
args = parser.parse_args()

r = evaluate_frozen(load_site(args.site), args.pair)
print(json.dumps({k: r[k] for k in ("pair", "modules_changed_since_freeze", "rule", "truth_ha", "ci95",
                                     "flagged_ha_in_corridor", "valid_fraction_in_corridor")}, indent=2))
print(json.dumps({k: round(v, 3) for k, v in r["scores"].items() if k in ("recall", "precision", "csi", "f1")}))
