"""Write research/freeze_receipt_edouard.json: SHA-256 hashes of everything the run depends on. Refuses to replace it."""

import json

from hidden_floods.frozen_edouard import HASHED, PASSES, RECEIPT, WARNING_DB, digest
from hidden_floods.stamps import stamp

if RECEIPT.exists():
    raise SystemExit(f"{RECEIPT} already exists")
RECEIPT.write_text(json.dumps({
    **stamp("created_utc"),
    "method": "v3 unchanged, settings from research/freeze_receipt_v3.json",
    "order": [["village_creek", "134A_sep03"], ["pine_island", "012D_sep07"], ["village_creek", "012D_sep07"], ["pine_island", "134A_sep03"]],
    "passes": PASSES,
    "upland_warning_db": WARNING_DB,
    "sha256": {rel: digest(rel) for rel in HASHED},
}, indent=2))
print("wrote", RECEIPT)
