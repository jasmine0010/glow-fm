"""Write research/freeze_receipt_v4.json: frozen settings plus SHA-256 hashes. Refuses to replace an existing receipt."""

import json

from hidden_floods.frozen_v4 import HASHED, PASSES, RECEIPT, digest
from hidden_floods.stamps import stamp
from hidden_floods.v4 import V4Rule

if RECEIPT.exists():
    raise SystemExit(f"{RECEIPT} already exists")
rule = V4Rule(baseline="median", signal="adaptive", flood_check_db=None, confidence_db=0.5, wet_scene_db=0.5)
RECEIPT.write_text(json.dumps({
    **stamp("created_utc"),
    "v4_rule": rule.to_dict(),
    "order": list(PASSES.items()),
    "sha256": {rel: digest(rel) for rel in HASHED},
}, indent=2))
print("wrote", RECEIPT)
