"""Run the overbank test once, in protocol order: ``python scripts/run_frozen_overbank.py``."""

import json

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.frozen_overbank import SCENES, evaluate

results = []
for river, info in json.loads(SCENES.read_text()).items():
    site = load_site(river)
    for pair in info["passes"]:
        r = evaluate(site, pair)
        copy = REPO_ROOT / "research" / f"overbank_{river}_{pair}_frozen_metrics.json"
        copy.write_text(json.dumps(r, indent=2, default=str))
        results.append(r)
        print(json.dumps({k: r[k] for k in ("site", "pair", "judgeable", "v4_csi", "trust_signal", "signal_right", "confident", "rain", "coverage", "truth_ha", "wet_share_of_labelled", "upland_warning", "high_ground_db", "low_minus_high_db", "v4_minus_v3_csi", "v4_minus_lidar_csi")}
                         | {"v3_csi": r["baseline_v3_same_pixels"]["scores"]["csi"], "lidar_csi": r["lidar_2m_same_pixels"]["scores"]["csi"], "ci95": r["primary_v4"]["ci95"] and r["primary_v4"]["ci95"]["csi"], "near_5km": {k: r["within_5km_of_gauge"][k]["scores"]["csi"] for k in ("v4", "lidar_2m")}}, default=str), flush=True)
print("OVERBANK RUN DONE", flush=True)
