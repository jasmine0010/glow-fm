"""Set up the expansion test (research/EXPANSION_PROTOCOL.md) without reading any radar backscatter, flood layer or truth.

A replication of the overbank test (research/OVERBANK_PROTOCOL.md) on the forested rivers that no frozen test or live run has
read, chosen from research/expansion_screen.json. It uses the overbank setup's own functions unchanged: gauges, lidar,
WorldCover, GFM's static reference water, each scene's projection and valid-sample mask, and IMERG rainfall.

Differences from the overbank setup, all fixed before any radar is read:
- the rivers, and the gauges on each (one free-flowing reach with a known datum; tidal gauges and gauges across a dam or
  reservoir from the rest are left out);
- the window, Jun 21 - Oct 21, 2026: every PROVISIONAL pass, the catalogue the frozen reader reads;
- one pass per orbit: where a track has two frames over the river, the frame with the larger mean rise;
- a river is kept only if forest and wetland make up at least half of its gauge-supported corridor.
Writes research/expansion_scenes.json, expansion_rain.json and expansion_dropped.json (rivers left out, and why).
"""

import json
import math
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rain_imerg
import setup_overbank as ob
from setup_edouard import fetch_reference_water

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.sitegen import create_site
from hidden_floods.stack import parse, track_scenes

RIVERS = {
    "ogeechee": {"gauges": ["02200120", "02201230", "02202040", "02202190", "02202500"], "tracks": [("119A", "018"), ("026D", "072"), ("098D", "072"), ("047A", "018")],
                 "left_out": "Ellabell and Richmond Hill (tidal reach)"},
    "suwannee": {"gauges": ["02314500", "02315500", "02315550", "02319500", "02319800", "02320000", "02320500", "02323000", "02323500"],
                 "tracks": [("098D", "073"), ("098D", "074"), ("047A", "017"), ("026D", "073"), ("148A", "017")], "left_out": "above Fargo (a second gauge at the same place)"},
    "altamaha": {"gauges": ["02224940", "02225000", "02226000", "02226160"], "tracks": [("026D", "072"), ("047A", "017"), ("047A", "018"), ("098D", "072"), ("098D", "073")], "left_out": "none"},
    "apalachicola": {"gauges": ["02358000", "02358700", "02359170"], "tracks": [("127D", "073"), ("148A", "017"), ("026D", "073"), ("076A", "017")],
                     "left_out": "below Woodruff Dam (no datum, at the same place as Chattahoochee)"},
    "escambia": {"gauges": ["02375500", "02376033"], "tracks": [("004A", "017"), ("055D", "073"), ("076A", "017")], "left_out": "none"},
    "tar": {"gauges": ["02082585", "02083500", "02084000"], "tracks": [("090A", "020")], "left_out": "Spring Hope (above the Tar River Reservoir) and below the dam near Langley Crossroads"},
    "trinity_lower": {"gauges": ["08066250", "08066500", "08067000", "08067100"], "tracks": [("012D", "073"), ("134A", "017")], "left_out": "Wallisville, both gauges (tidal, at Trinity Bay)"},
    "ef_san_jacinto": {"gauges": ["08069800", "08070000", "08070200"], "tracks": [("113D", "073"), ("134A", "017")], "left_out": "none"},
}
DROPPED = {"blackwater": "Its second gauge (near Harold) has no stated datum, so the river has one usable gauge (rule 2(a) needs two).",
           "perdido": "One gauge.", "test and live rivers": "Every river with a frozen test or a prepared Run it yourself case."}
START, END = "2026-06-21T00:00:00Z", "2026-10-21T17:07:00Z"
SITE_START, SITE_END = "2026-04-15T00:00:00Z", "2026-11-15T00:00:00Z"
GFM_DATES = ("20260626", "20260623", "20260701", "20260716", "20260726", "20261015", "20261014", "20260906", "20260815")
MONTHS = {6: "jun", 7: "jul", 8: "aug", 9: "sep", 10: "oct"}
MIN_FOREST = 0.5
OUT, RAIN = REPO_ROOT / "research" / "expansion_scenes.json", REPO_ROOT / "research" / "expansion_rain.json"
LEFT = REPO_ROOT / "research" / "expansion_dropped.json"


def tiles(bbox):
    """WorldCover's 3-degree tiles that cover a box."""
    out = set()
    for lat in range(math.floor(bbox[1] / 3) * 3, math.floor(bbox[3] / 3) * 3 + 1, 3):
        for lon in range(math.floor(bbox[0] / 3) * 3, math.floor(bbox[2] / 3) * 3 + 1, 3):
            out.add(f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}")
    return sorted(out)


def select_track(site, track, frame):
    """Rule 2(b) over this test's window, exactly as setup_overbank.select_track applies it over the overbank window."""
    scenes = track_scenes(site.bbox, track, frame, START, END)
    st = {s.time: ob.stages(site, s.time) for s in scenes}
    best = None
    for s in scenes:
        ids = list(st[s.time])
        pool = [x for x in scenes if x.time != s.time and abs(ob.when(x.time) - ob.when(s.time)) <= timedelta(days=60) and all(i in st[x.time] for i in ids)]
        if len(ids) < 2 or not pool:
            continue
        dry = min(pool, key=lambda x: sum(st[x.time][i] for i in ids) / len(ids))
        rises = {i: round(st[s.time][i] - st[dry.time][i], 2) for i in ids}
        mean = sum(rises.values()) / len(rises)
        if max(rises.values()) > 1.0 and (best is None or mean > best["mean_rise_m"]):
            best = {"wet": s, "dry": dry, "rises_m": rises, "mean_rise_m": round(mean, 2)}
    return best


def main():
    listing = {}
    for name, spec in RIVERS.items():
        path = ob.SITES_DIR / f"{name}.toml"
        for attempt in range(8):     # USGS's API limits requests per hour; a limited attempt leaves a half-made site, so start again
            if path.exists():
                break
            try:
                create_site(name, spec["gauges"], SITE_START, SITE_END, f"Unread river, {name}. Held-out expansion test.", fetch_dem=False)
            except urllib.error.HTTPError as err:
                if err.code != 429 or attempt == 7:
                    raise
                path.unlink(missing_ok=True)
                print(f"{name}: USGS rate limit, waiting 10 minutes", flush=True)
                time.sleep(600)
        site = load_site(name)
        for tile in tiles(site.bbox):
            ob.fetch_tile(tile)
        picks = {}
        for track, frame in spec["tracks"]:
            b = select_track(site, track, frame)
            if b is None:
                print(f"{name} {track}/{frame}: no qualifying pass", flush=True)
            elif track not in picks or b["mean_rise_m"] > picks[track]["mean_rise_m"]:   # one pass per orbit
                picks[track] = {"track": track, "frame": frame, **b}
        crs, passes = None, {}
        for p in sorted(picks.values(), key=lambda p: -p["mean_rise_m"]):
            wet, dry = p["wet"], p["dry"]
            epsg, terms, valid_w = ob.scene_meta(site, wet)
            if crs and f"EPSG:{epsg}" != crs:      # the site's projection comes from its first pass that qualifies
                print(f"{name} {p['track']}: projection EPSG:{epsg} differs from the primary {crs}, so the frozen reader can't use it", flush=True)
                continue
            _, terms_d, valid_d = ob.scene_meta(site, dry)
            t = ob.when(wet.time)
            pair = f"{p['track']}_{MONTHS[t.month]}{t.day:02d}"
            ok = terms and terms_d and min(valid_w, valid_d) >= 0.6
            print(f"{name} {pair}: EPSG:{epsg} wet {wet.time} dry {dry.time} rises {p['rises_m']} mean {p['mean_rise_m']} valid {valid_w:.2f}/{valid_d:.2f} {'PASS' if ok else 'FAIL'}", flush=True)
            if ok:
                crs = crs or f"EPSG:{epsg}"
                passes[pair] = {"track": p["track"], "frame": p["frame"], "wet": wet.name, "dry": dry.name, "wet_time": wet.time, "dry_time": dry.time,
                                "rises_m": p["rises_m"], "mean_rise_m": p["mean_rise_m"], "valid_share": [round(valid_w, 3), round(valid_d, 3)]}
        if not passes:
            print(f"{name}: dropped, no qualifying pass", flush=True)
            continue
        text = path.read_text()
        if "[pairs." not in text:
            keys = {}
            for v in passes.values():
                for role in ("wet", "dry"):
                    keys[v[role]] = f"{role}_{v['track']}_{parse(v[role])['time'][:10].replace('-', '')}"
            gcov = "[gcov]\n" + "".join(f'"{k}" = "{n}"\n' for n, k in keys.items())
            pairs = "".join(f'[pairs."{pn}"]\nwet = "{keys[v["wet"]]}"\ndry = "{keys[v["dry"]]}"\nwet_time = "{v["wet_time"]}"\ndry_time = "{v["dry_time"]}"\n\n' for pn, v in passes.items())
            lines = text.replace("[gcov]\n", gcov, 1).replace("[pairs]\n", pairs, 1).split("\n")
            path.write_text("\n".join(f'crs = "{crs}"' if ln.startswith("crs = ") else ln for ln in lines))
        listing[name] = {"left_out_gauges": spec["left_out"], "crs": crs, "passes": passes}
    print("sites written; fetching lidar", flush=True)
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(ob.fetch_dem, listing))
    rain, kept = {}, {}
    rain_imerg.CACHE.mkdir(parents=True, exist_ok=True)
    first_time = ob.when(next(iter(next(iter(listing.values()))["passes"].values()))["wet_time"])
    rain_imerg.curl(rain_imerg.OPENDAP + next(iter(rain_imerg.list_granules(first_time - timedelta(hours=1), first_time).values())) + ".dmr", seed=True)
    try:
        for name, info in listing.items():
            site = load_site(name)
            got = 0
            for d in GFM_DATES:
                got = fetch_reference_water(site, d)
                if got:
                    print(f"{name}: reference water from {d}, {got} files", flush=True)
                    break
            info["reference_water_files"] = got
            info["static"] = ob.static_shares(site) if got else None
            print(f"{name}: {info['static']}", flush=True)
            if not info["static"] or info["static"]["forest_share"] < MIN_FOREST:
                DROPPED[name] = f"Forest and wetland are {info['static'] and info['static']['forest_share']} of the corridor, under {MIN_FOREST}." if info["static"] else "No reference water."
                print(f"{name}: dropped. {DROPPED[name]}", flush=True)
                continue
            for pair, v in info["passes"].items():
                tw = ob.when(v["wet_time"])
                lo, hi = (tw - timedelta(days=60)).isoformat() + "Z", (tw + timedelta(days=60)).isoformat() + "Z"
                scenes = track_scenes(site.bbox, v["track"], v["frame"], max(lo, START), min(hi, END))
                v["scenes"] = [{"name": s.name, "track": s.track, "frame": s.frame, "time": s.time, "url": s.url} for s in scenes]
                rain.setdefault(name, {})[pair] = ob.imerg_rain(site, v["wet_time"])
                print(f"{name} {pair}: {len(scenes)} baseline-window scenes; rain {rain[name][pair]}", flush=True)
            kept[name] = info
    finally:
        rain_imerg.JAR.unlink(missing_ok=True)
    OUT.write_text(json.dumps(kept, indent=1))
    LEFT.write_text(json.dumps(DROPPED, indent=1))
    RAIN.write_text(json.dumps(rain, indent=1))
    print("EXPANSION SETUP DONE", flush=True)


if __name__ == "__main__":
    main()
