"""Stage against NWS flood level and flood timing at each overbank pass (research/overbank_gauges.json). Gauges only: no radar, flood layer or truth.

NWS lists the Alapaha and Withlacoochee flood values as elevations, so those are compared with stage plus the USGS datum.
"""

import json
from datetime import datetime

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.io.gauges import usgs_series
from hidden_floods.trust import timing_class

RESEARCH = REPO_ROOT / "research"
FT = 0.3048
ELEVATION_LISTED = {"alapaha", "withlacoochee"}
TIMING = {1: "rising", 2: "near crest", 3: "receding", 4: "late recession"}

scenes = json.loads((RESEARCH / "overbank_scenes.json").read_text())
screen = json.loads((RESEARCH / "overbank_screen.json").read_text())
out = {}
for river, info in scenes.items():
    site = load_site(river)
    meta = {g["id"]: g for g in screen[river]["gauges"]}
    for pair, v in info["passes"].items():
        t = datetime.fromisoformat(v["wet_time"].replace("Z", ""))
        rows = []
        for g in site.gauges:
            series = usgs_series(site.gauges_dir, g)
            m = meta[g.id.replace("USGS-", "")]
            level = float(series.at(t)) * FT
            if river in ELEVATION_LISTED:
                level += float(m["datum_ft"]) * FT
            rows.append({"gauge": g.name, "level_m": round(level, 2), "nws_flood_m": round(m["flood_m"], 2), "above": level > m["flood_m"], "margin_m": round(level - m["flood_m"], 2),
                         "basis": "elevation" if river in ELEVATION_LISTED else "stage", "timing": TIMING[timing_class(series, v["wet_time"])]})
            print(river, pair, rows[-1], flush=True)
        out.setdefault(river, {})[pair] = rows
(RESEARCH / "overbank_gauges.json").write_text(json.dumps(out, indent=1))
