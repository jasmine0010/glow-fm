"""Dry run of the no-lidar code on Yellow River Oct 16, a used river that isn't in the test. Layers go to a temporary folder."""

import json
import tempfile
from pathlib import Path

from fetch_stacks import scenes_for

from hidden_floods.config import load_site
from hidden_floods.frozen_no_lidar import score_pass
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import evaluate_v4, rule_from

EXPECTED = 0.890845
site = load_site("yellow")
pair = "055D_oct16"
with tempfile.TemporaryDirectory() as out:
    evaluate_v4(site, pair, scenes_for(site, site.pairs[pair]), rule_from(json.loads(RECEIPT_V4.read_text())), out_dir=Path(out), regression_check=True)
    r = score_pass(site, pair, Path(out))
    print(json.dumps(r, indent=1, default=str), flush=True)
    assert round(r["maps"]["nisar_with_lidar"]["csi"], 6) == EXPECTED, r["maps"]["nisar_with_lidar"]["csi"]
    assert r["replay_agreement"] > 0.999, r["replay_agreement"]
print("NO LIDAR CODE CHECK PASSED", flush=True)
