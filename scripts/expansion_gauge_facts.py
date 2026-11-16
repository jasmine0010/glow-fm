"""Stage against NWS flood level and flood timing at each expansion pass (research/expansion_gauges.json). Gauges only: no radar, flood layer or truth.

NWS gives some flood levels as elevations, not stages (Suwannee and Altamaha gauges, for example, list 22.7 m). A level is
read as an elevation when it is more than 3 m above the highest stage the gauge recorded in the site window; it is then
compared with stage plus the USGS datum. NWS doesn't state the datum of those levels, so their margins are approximate by
tens of centimetres, as in the overbank test.
"""

import json
from datetime import datetime

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.io.gauges import usgs_series
from hidden_floods.trust import timing_class

RESEARCH = REPO_ROOT / "research"
FT = 0.3048
TIMING = {1: "rising", 2: "near crest", 3: "receding", 4: "late recession"}

scenes = json.loads((RESEARCH / "expansion_scenes.json").read_text())
screen = json.loads((RESEARCH / "expansion_screen.json").read_text())["basins"]
out = {}
for river, info in scenes.items():
    site = load_site(river)
    meta = {g["id"]: g for g in screen[river]["gauges"]}
    for pair, v in info["passes"].items():
        t = datetime.fromisoformat(v["wet_time"].replace("Z", ""))
        rows = []
        for g in site.gauges:
            gid = g.id.replace("USGS-", "")
            series = usgs_series(site.gauges_dir, g)
            flood_m = meta.get(gid, {}).get("flood_m")
            try:
                level = float(series.at(t)) * FT
            except ValueError:
                rows.append({"gauge": g.name, "level_m": None, "note": "no reading at the pass"})
                continue
            if flood_m is None:
                rows.append({"gauge": g.name, "level_m": round(level, 2), "nws_flood_m": None, "timing": TIMING[timing_class(series, v["wet_time"])]})
                continue
            elevation = flood_m > float(series.stage_ft.max()) * FT + 3.0
            if elevation:
                level += float(g.datum_ft) * FT
            rows.append({"gauge": g.name, "level_m": round(level, 2), "nws_flood_m": round(flood_m, 2), "above": level > flood_m, "margin_m": round(level - flood_m, 2),
                         "basis": "elevation" if elevation else "stage", "timing": TIMING[timing_class(series, v["wet_time"])]})
            print(river, pair, rows[-1], flush=True)
        out.setdefault(river, {})[pair] = rows
(RESEARCH / "expansion_gauges.json").write_text(json.dumps(out, indent=1))
print("GAUGE FACTS DONE", flush=True)
