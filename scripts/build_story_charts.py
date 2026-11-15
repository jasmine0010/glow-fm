"""Data for the story page's charts: who was watching the Satilla flood, where NISAR and the estimate agree on Oct 15, and the
answer key for "Beat the satellite".

River levels come from USGS and are cached in outputs/story_charts, because a full build clears app/data. The agreement map reads saved
frozen layers and stops if they don't reproduce the frozen score.
"""
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime

import numpy as np
from build_app import DATA, HERO_PASS, HERO_RIVER, corners, to_web, web_grid
from PIL import Image

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.pipeline import analysis_grid

WORK = REPO_ROOT / "outputs" / "story_charts"
START, END = "2026-09-28", "2026-10-26"
FT = 0.3048
SHORT = {"02226362": "GA 158", "02226500": "Near Waycross", "02228000": "Atkinson"}
# Checked with the dataviz palette validator on the panel color, across every pair.
BOTH, ESTIMATE_ONLY, NISAR_ONLY = (185, 138, 18), (21, 154, 140), (214, 58, 214)


def river_series(site_no):
    path = WORK / f"{site_no}.json"
    if not path.exists():
        q = urllib.parse.urlencode({"format": "json", "sites": site_no, "parameterCd": "00065", "startDT": f"{START}T00:00Z", "endDT": f"{END}T23:59Z", "siteStatus": "all"})
        request = urllib.request.Request(f"https://waterservices.usgs.gov/nwis/iv/?{q}", headers={"User-Agent": "hidden-floods-research/0.1"})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(request, timeout=120).read())
    series = json.loads(path.read_text())["value"]["timeSeries"][0]
    nodata = series["variable"]["noDataValue"]
    points = max((block["value"] for block in series["values"]), key=len)
    return [(datetime.fromisoformat(p["dateTime"]).astimezone(UTC), float(p["value"])) for p in points if float(p["value"]) != nodata]


def watching():
    rivers = json.loads((DATA / "dashboard" / "rivers.json").read_text())["rivers"]
    river = next(r for r in rivers if r["id"] == HERO_RIVER)
    gauges = []
    for g in river["gauges"]:
        site_no = g["id"].replace("USGS-", "")
        rows, seen = [], set()
        for when, ft in river_series(site_no):
            # One reading every three hours is plenty for a line this wide.
            slot = (when.date(), when.hour // 3)
            if slot in seen:
                continue
            seen.add(slot)
            rows.append([when.strftime("%Y-%m-%dT%H:%MZ"), round((ft - g["flood_ft"]) * FT, 3)])
        gauges.append({"id": site_no, "name": SHORT[site_no], "flood_ft": g["flood_ft"], "rows": rows})
    scenes = json.loads((REPO_ROOT / "research" / "overbank_scenes.json").read_text())[HERO_RIVER]["passes"]
    nisar = sorted({s["time"] for p in scenes.values() for s in p["scenes"] if START <= s["time"][:10] <= END})
    audit = json.loads((REPO_ROOT / "research" / "satilla_audit.json").read_text())["dates"]
    gfm = [{"date": f"{d['date'][:4]}-{d['date'][4:6]}-{d['date'][6:]}", "covered": d["corridor_coverage"]} for d in audit if START <= f"{d['date'][:4]}-{d['date'][4:6]}-{d['date'][6:]}" <= END]
    return {"start": START, "end": END, "gauges": gauges, "nisar": nisar, "gfm": gfm}


def agreement():
    """How much of the scored ground each map calls flooded, checked against the frozen run's own score."""
    site = load_site(HERO_RIVER)
    grid, wg = analysis_grid(site), web_grid(site)
    z = np.load(REPO_ROOT / "outputs" / HERO_RIVER / HERO_PASS / "frozen_v4_layers.npz")
    frozen = json.loads((REPO_ROOT / "research" / f"overbank_{HERO_RIVER}_{HERO_PASS}_frozen_metrics.json").read_text())
    scored = z["region"] & z["mapped"]
    both, estimate_only, nisar_only = z["pred"] & z["wet"] & scored, ~z["pred"] & z["wet"] & scored, z["pred"] & z["dry"] & scored
    counts = [int(a.sum()) for a in (both, estimate_only, nisar_only)]
    csi = counts[0] / sum(counts)
    if abs(csi - frozen["v4_csi"]) > 1e-9:
        raise SystemExit(f"agreement map scores {csi}, frozen {frozen['v4_csi']}")
    px_ha = grid.res ** 2 / 1e4
    return {"corners": corners(wg), "csi": round(csi, 4), "both_ha": round(counts[0] * px_ha), "estimate_only_ha": round(counts[1] * px_ha), "nisar_only_ha": round(counts[2] * px_ha),
            "colors": [f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}" for c in (BOTH, ESTIMATE_ONLY, NISAR_ONLY)], "per_100": [round(100 * c / sum(counts)) for c in counts]}


def game():
    """The answer key for "Beat the satellite": on the web grid, red marks ground the frozen run scored, green the ground the estimate
    calls flooded, and blue NISAR's map, all within the scored ground. Each channel is 0 or 255, so browser decoding can't blur it."""
    site = load_site(HERO_RIVER)
    grid, wg = analysis_grid(site), web_grid(site)
    z = np.load(REPO_ROOT / "outputs" / HERO_RIVER / HERO_PASS / "frozen_v4_layers.npz")
    frozen = json.loads((REPO_ROOT / "research" / f"overbank_{HERO_RIVER}_{HERO_PASS}_frozen_metrics.json").read_text())
    scored = z["region"] & z["mapped"] & (z["wet"] | z["dry"])
    web = lambda a: to_web(a.astype(np.uint8), grid, wg, True, 0) == 1
    s, w, n = web(scored), web(z["wet"] & scored), web(z["pred"] & scored)
    w &= s
    n &= s
    hits, miss, false = int((n & w).sum()), int((~n & w).sum()), int((n & ~w & s).sum())
    csi = hits / (hits + miss + false)
    # Resampling to the web grid moves the score slightly; more than this and the key doesn't describe the frozen run.
    if abs(csi - frozen["v4_csi"]) > 0.01:
        raise SystemExit(f"game key scores {csi}, frozen {frozen['v4_csi']}")
    img = np.zeros(wg.shape + (4,), np.uint8)
    img[..., 0], img[..., 1], img[..., 2], img[..., 3] = s * 255, w * 255, n * 255, 255
    Image.fromarray(img, "RGBA").save(DATA / HERO_RIVER / HERO_PASS / "game.png", optimize=True)
    d = frozen
    # The zoom on the story page ends on one pixel: a pixel where NISAR and the river's answer agree, at the edge of NISAR's
    # map (three or more neighbours unflagged), so flooded and dry pixels show side by side. Among those, the one in the
    # densest patch of agreement.
    both = (n & w).astype(np.int32)
    k = 21

    def box(a, size):
        c = np.pad(np.pad(a, size // 2).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return c[size:, size:] - c[:-size, size:] - c[size:, :-size] + c[:-size, :-size]

    dense, near = box(both, k), box(n.astype(np.int32), 3)
    edge_px = (both == 1) & (near <= 6)
    r, c = np.unravel_index(int(np.argmax(np.where(edge_px, dense, -1))), both.shape)
    edge = lambda col, row: list(wg.to_lonlat(wg.x0 + col * wg.res, wg.y0 - row * wg.res))
    focus = {"pixel": [edge(c, r), edge(c + 1, r + 1)], "center": edge(c + 0.5, r + 0.5), "pixel_m": round(float(wg.res), 1), "agree_in_window": int(dense[r, c])}
    return {"file": f"{HERO_RIVER}/{HERO_PASS}/game.png", "corners": corners(wg), "cols": wg.shape[1], "rows": wg.shape[0], "web_csi": round(csi, 4), "focus": focus,
            "nisar": {"csi": round(d["v4_csi"], 4), "found": round(hits / (hits + miss), 4), "on_dry": round(false / (hits + false), 4)}}


def main():
    out = DATA / "story"
    out.mkdir(parents=True, exist_ok=True)
    charts = {"watching": watching(), "agreement": agreement(), "game": game()}
    (out / "charts.json").write_text(json.dumps(charts, separators=(",", ":")))
    a = charts["agreement"]
    print({k: a[k] for k in ("csi", "both_ha", "estimate_only_ha", "nisar_only_ha", "per_100")}, "game", charts["game"]["web_csi"], charts["game"]["nisar"], "NISAR looks", charts["watching"]["nisar"], "GFM looks", charts["watching"]["gfm"])


if __name__ == "__main__":
    main()
