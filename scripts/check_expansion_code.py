"""Dry run of the expansion scoring code on a used river, in a temporary folder, before the freeze.

The expansion test scores with the overbank test's ``score_pass`` unchanged, so Yellow Oct 16 must reproduce v4's development
CSI of 0.890845, as scripts/check_overbank_code.py required. No expansion river is read.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_stacks import scenes_for
from frozen_expansion import score_pass

from hidden_floods.config import load_site

EXPECTED = 0.890845
site = load_site("yellow")
pair = "055D_oct16"
with tempfile.TemporaryDirectory() as out:
    r = score_pass(site, pair, scenes_for(site, site.pairs[pair]), {"rainy": False, "note": "placeholder for this check"}, Path(out))
    assert round(r["v4_csi"], 6) == EXPECTED, f"got {r['v4_csi']}, expected {EXPECTED}"
    assert (r["trust_signal"] == "green") == r["confident"]
    json.dumps(r, default=str)
print(f"EXPANSION CODE CHECK PASSED: v4 CSI {r['v4_csi']:.6f}", flush=True)
