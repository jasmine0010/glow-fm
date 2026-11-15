"""Dry run of the overbank scoring code on a used river, in a temporary folder. Yellow Oct 16 must reproduce v4's development 0.890845."""

import json
import tempfile
from pathlib import Path

from fetch_stacks import scenes_for

from hidden_floods.config import load_site
from hidden_floods.frozen_overbank import score_pass

EXPECTED = 0.890845
site = load_site("yellow")
pair = "055D_oct16"
with tempfile.TemporaryDirectory() as out:
    r = score_pass(site, pair, scenes_for(site, site.pairs[pair]), {"rainy": False, "note": "placeholder for this check"}, Path(out))
    print(json.dumps(r, indent=1, default=str)[:6000], flush=True)
    assert round(r["v4_csi"], 6) == EXPECTED, f"got {r['v4_csi']}, expected {EXPECTED}"
    assert (r["trust_signal"] == "green") == r["confident"]
    json.dumps(r, default=str)
print(f"OVERBANK CODE CHECK PASSED: v4 CSI {r['v4_csi']:.6f}, lidar {r['lidar_2m_same_pixels']['scores']['csi']:.3f}, within 5 km v4 {r['within_5km_of_gauge']['v4']['scores']['csi']}", flush=True)
