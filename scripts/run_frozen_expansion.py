"""Run the expansion test once, in protocol order: ``python scripts/run_frozen_expansion.py``."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frozen_expansion import SCENES, evaluate

from hidden_floods.config import REPO_ROOT, load_site

for river, info in json.loads(SCENES.read_text()).items():
    site = load_site(river)
    for pair in info["passes"]:
        r = evaluate(site, pair)
        (REPO_ROOT / "research" / f"expansion_{river}_{pair}_frozen_metrics.json").write_text(json.dumps(r, indent=2, default=str))
        print(json.dumps({k: r[k] for k in ("site", "pair", "judgeable", "v4_csi", "trust_signal", "signal_right", "confident", "rain", "coverage", "truth_ha", "wet_share_of_labelled", "upland_warning", "low_minus_high_db", "v4_minus_lidar_csi")}
                         | {"lidar_csi": r["lidar_2m_same_pixels"]["scores"]["csi"], "ci95": r["primary_v4"]["ci95"] and r["primary_v4"]["ci95"]["csi"]}, default=str), flush=True)
print("EXPANSION RUN DONE", flush=True)
