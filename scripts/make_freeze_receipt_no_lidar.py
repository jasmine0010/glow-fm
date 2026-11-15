"""Write research/freeze_receipt_no_lidar.json: SHA-256 hashes of what the no-lidar test depends on. Refuses to replace a receipt."""

import json

from hidden_floods.frozen_no_lidar import RECEIPT, SELF, digest
from hidden_floods.stamps import stamp

if RECEIPT.exists():
    raise SystemExit(f"{RECEIPT} already exists")
RECEIPT.write_text(json.dumps({**stamp("created_utc"), "sha256": {rel: digest(rel) for rel in SELF}}, indent=2))
print("wrote", RECEIPT)
