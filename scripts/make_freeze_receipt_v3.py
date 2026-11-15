"""Write research/freeze_receipt_v3.json: frozen settings plus SHA-256 hashes. Refuses to replace an existing receipt."""

import json

from hidden_floods.frozen_v3 import FROZEN_PAIRS, HASHED_V3, RECEIPT_V3, digest
from hidden_floods.stamps import stamp
from hidden_floods.v3 import LC_OTHER, LC_TREE, LC_WETLAND, T_LATE, V3OtsuRule

if RECEIPT_V3.exists():
    raise SystemExit(f"{RECEIPT_V3} already exists")
rule = V3OtsuRule(smooth_px=3, hand_max_m=6.0, valley_m=4000.0, min_threshold_db=0.5,
                  landcover=(LC_TREE, LC_WETLAND, LC_OTHER), abstain_timing=(T_LATE,))
RECEIPT_V3.write_text(json.dumps({
    **stamp("created_utc"),
    "v3_rule": rule.to_dict(),
    "v2_rule": {"type": "selfcal_v2", "q": 90.0, "hand_max_m": 6.0, "ref_hand_min_m": 12.0, "ref_max_distance_m": 15000.0,
                "forest_hv_db": -16.0, "min_threshold_db": 0.5, "smooth_px": 3},
    "v1_rule": {"type": "change", "d_hh_db": 2.0, "forest_hv_db": -16.0},
    "pairs": {"primary": ["yellow", FROZEN_PAIRS["yellow"][0]], "secondary": ["yellow", FROZEN_PAIRS["yellow"][1]]},
    "metrics": {"primary": "v3 csi, mapped gauge-supported non-permanent-water pixels, instant truth",
                "bootstrap_block_m": 2000.0, "n_boot": 2000, "seed": 0},
    "sha256": {rel: digest(rel) for rel in HASHED_V3},
}, indent=2))
print("wrote", RECEIPT_V3)
