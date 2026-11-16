"""Write research/freeze_receipt_expansion.json: SHA-256 hashes of everything the test depends on. Refuses to replace a receipt."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frozen_expansion import RECEIPT, digest, hashed_files

from hidden_floods.stamps import stamp

if RECEIPT.exists():
    raise SystemExit(f"{RECEIPT} already exists")
RECEIPT.write_text(json.dumps({**stamp("created_utc"), "sha256": {rel: digest(rel) for rel in hashed_files()}}, indent=2))
print("wrote", RECEIPT)
