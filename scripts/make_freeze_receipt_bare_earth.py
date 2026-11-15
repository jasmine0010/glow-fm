"""Write research/freeze_receipt_bare_earth.json: SHA-256 hashes of what the bare-earth test depends on. Refuses to replace a receipt."""

import json

from hidden_floods.frozen_bare_earth import RECEIPT, SELF, digest
from hidden_floods.stamps import stamp

if RECEIPT.exists():
    raise SystemExit(f"{RECEIPT} already exists")
RECEIPT.write_text(json.dumps({**stamp("created_utc"), "sha256": {rel: digest(rel) for rel in SELF}}, indent=2))
print("wrote", RECEIPT)
