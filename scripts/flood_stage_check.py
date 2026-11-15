"""River stage against NWS flood stage at each gauge on each pass. Writes research/flood_stage_by_pass.json.

NWS and USGS stage may not share a datum, so a gauge is marked "datum?" if its lowest stage in the saved record is above
the NWS flood stage or its highest is under half of it. Those gauges are excluded from the pass's reading.
"""

import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from explore_model_ideas import get_site

from hidden_floods.config import REPO_ROOT
from hidden_floods.io.gauges import usgs_series

NWS = "https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv"
PASSES = (("choctawhatchee", "076A_oct17"), ("choctawhatchee", "127D_oct21"), ("pearl", "105A_jul03"), ("pearl", "156D_jun25"), ("tangipahoa", "105A_jun21"), ("tangipahoa", "156D_jun25"),
          ("yellow", "055D_oct04"), ("yellow", "076A_oct05"), ("yellow", "127D_oct09"), ("yellow", "055D_oct16"), ("yellow", "076A_oct17"), ("yellow", "127D_oct21"),
          ("village_creek", "134A_sep03"), ("village_creek", "012D_sep07"), ("pine_island", "012D_sep07"), ("pine_island", "134A_sep03"),
          ("pee_dee", "098D_jul27"), ("neuse", "090A_jul26"), ("lower_sabine", "134A_jul17"))


def flood_stages():
    req = urllib.request.Request(NWS, headers={"User-Agent": "hidden-floods research"})
    text = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        uid = (r.get("usgs id") or "").strip()
        try:
            stage = float(r.get("flood stage") or "nan")
        except ValueError:
            stage = float("nan")
        if uid and np.isfinite(stage) and stage > 0:
            out[uid] = stage
    return out


def main():
    stages, rows = flood_stages(), []
    for river, pair_name in PASSES:
        site = get_site(river)
        pair = site.pairs[pair_name]
        gauges = []
        for g in site.gauges:
            s = usgs_series(site.gauges_dir, g)
            uid = g.id.removeprefix("USGS-")
            fs = stages.get(uid)
            try:
                wet = float(s.at(pair.wet_time))
            except ValueError:
                wet = None
            state = "no NWS flood stage" if fs is None or wet is None else "above" if wet >= fs else "below"
            if fs is not None and (float(np.min(s.stage_ft)) > fs or float(np.max(s.stage_ft)) < fs / 2):
                state = "datum?"
            gauges.append({"name": g.name, "id": uid, "stage_ft": wet, "flood_stage_ft": fs, "state": state})
        known = [g["state"] for g in gauges if g["state"] in ("above", "below")]
        reading = "not known" if not known else "above" if all(x == "above" for x in known) else "below" if all(x == "below" for x in known) else "mixed"
        rows.append({"river": river, "pair": pair_name, "stage": reading, "gauges_read": len(known), "gauges": gauges})
        print(river, pair_name, reading, [(g["id"], g["stage_ft"] and round(g["stage_ft"], 1), g["flood_stage_ft"], g["state"]) for g in gauges], flush=True)
    (REPO_ROOT / "research" / "flood_stage_by_pass.json").write_text(json.dumps(rows, indent=1))
    print("FLOOD STAGE DONE", flush=True)


if __name__ == "__main__":
    main()
