"""Fetch corridor-only windows of every same-track scene within 60 days of each development pass. Resumable."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from explore_model_ideas import PASSES, get_site

from hidden_floods.config import data_root
from hidden_floods.pipeline import analysis_grid
from hidden_floods.stack import cache_path, parse, read_scene, track_scenes

LOCAL = tuple(data_root() / d for d in ("choctawhatchee", "pearl", "yellow", "edouard"))
WINDOW_DAYS = 60


def scenes_for(site, pair):
    meta = parse(Path(site.gcov[pair.wet]).name)
    t = datetime.fromisoformat(pair.wet_time.replace("Z", ""))
    start, end = (t - timedelta(days=WINDOW_DAYS)).isoformat() + "Z", (t + timedelta(days=WINDOW_DAYS)).isoformat() + "Z"
    return track_scenes(site.bbox, meta["track"], meta["frame"], start, end)


def main():
    seen, total, failed = set(), 0, []
    for _, name, pair_name in [*PASSES, ("isaias", "yellow", "055D_oct04")]:
        site = get_site(name)
        grid = analysis_grid(site)
        pair = site.pairs[pair_name]
        scenes = scenes_for(site, pair)
        print(f"{name} {pair_name}: {len(scenes)} scenes {[s.time[:10] for s in scenes]}", flush=True)
        for s in scenes:
            key = (name, s.name)
            if key in seen:
                continue
            seen.add(key)
            if cache_path(site, s.name).exists():
                continue
            try:
                read_scene(site, grid, s, LOCAL)
                total += 1
            except (OSError, ValueError, KeyError, RuntimeError) as e:  # a missing date only thins a baseline, and is listed
                failed.append((name, s.name, repr(e)[:80]))
                print("  FAILED", s.time[:10], repr(e)[:100], flush=True)
        print(f"  fetched so far {total}", flush=True)
    print("failed:", failed, flush=True)
    print("STACKS DONE", flush=True)


if __name__ == "__main__":
    main()
