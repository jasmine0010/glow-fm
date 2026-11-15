"""Repeat the rainfall check with IMERG satellite rainfall, under the rules in research/RAINFALL.md. Exploratory, on spent rivers.

Reads research/rainfall_by_pass.json for the radar columns, so no radar is reloaded. Writes research/rainfall_imerg.json.
Reads only a small box from each half-hourly file. Earthdata sign-in is handled by curl from ~/.netrc; this code never reads it.
A re-run resumes from the cached half-hours. Changes no method.
"""

import json
import re
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from explore_model_ideas import get_site
from rain_check import ANTECEDENT_MM, CACHE, RECENT_MM, summarize, when

from hidden_floods.config import REPO_ROOT
from hidden_floods.fetch import get_json

COLLECTION = "C2723754845-GES_DISC"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
OPENDAP = f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION}/granules/GPM_3IMERGHHL.07%3A"
WORKERS = 6
WEEK = timedelta(hours=168)
LOG = CACHE / "imerg_progress.log"
JAR = CACHE / "imerg_jar.txt"


def log(msg):
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def curl(url, seed=False):
    jar = ["-c", str(JAR), "-b", str(JAR)] if seed else ["-b", str(JAR)]
    out = subprocess.run(["curl", "-n", "-L", "-s", "--fail", "--retry", "4", "--retry-delay", "3", "--max-time", "120", *jar, url],
                         check=False, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if out.returncode:
        raise RuntimeError(f"curl exit {out.returncode}")
    return out.stdout


def list_granules(start, end):
    """Half-hour start time to file name, from NASA's public catalogue."""
    names, page = {}, 1
    while True:
        q = f"{CMR}?collection_concept_id={COLLECTION}&temporal={start:%Y-%m-%dT%H:%M:%SZ},{end:%Y-%m-%dT%H:%M:%SZ}&page_size=2000&page_num={page}"
        entries = get_json(q, timeout=120)["feed"]["entry"]
        for e in entries:
            name = e["title"].split(":")[-1]
            m = re.search(r"\.(\d{8})-S(\d{6})-", name)
            names[datetime.strptime(m[1] + m[2], "%Y%m%d%H%M%S")] = name
        if len(entries) < 2000:
            return names
        page += 1


def cell(lon, lat):
    return int(np.floor((lon + 180) * 10)), int(np.floor((lat + 90) * 10))


def read_box(name, i0, i1, j0, j1):
    text = curl(f"{OPENDAP}{name}.dap.csv?dap4.ce=/Grid/precipitation%5B0%5D%5B{i0}:{i1}%5D%5B{j0}:{j1}%5D")
    rows = [[float(v) for v in ln.split(",")[1:]] for ln in text.splitlines() if ln.startswith("/Grid/precipitation")]
    if len(rows) != i1 - i0 + 1 or any(len(r) != j1 - j0 + 1 for r in rows):
        raise ValueError(f"unexpected shape from {name}")
    return rows


def check_axes(name):
    """Stop unless the file's array order and units are what this script assumes."""
    dmr = curl(f"{OPENDAP}{name}.dmr", seed=True)
    block = re.search(r'<Float32 name="precipitation">.*?</Float32>', dmr, re.DOTALL)[0]
    dims = re.findall(r'<Dim name="([^"]+)"', block)
    assert [d.split("/")[-1] for d in dims] == ["time", "lon", "lat"], dims
    units = re.search(r'name="[Uu]nits"[^>]*>\s*<Value>([^<]+)', block) or re.search(r'name="[Uu]nits"[^>]*value="([^"]+)', block)
    assert units and units[1].strip() == "mm/hr", units and units[1]
    text = curl(f"{OPENDAP}{name}.dap.csv?dap4.ce=/Grid/lon%5B1000:1000%5D;/Grid/lat%5B1200:1200%5D")
    log(f"axes ok: {dims}, units {units[1].strip()}; centres {[ln for ln in text.splitlines() if ln.startswith('/Grid')]}")


def fetch_river(river, passes):
    """Every half-hour in the week before each of this river's passes. Returns (cells by time, window)."""
    site = get_site(river)
    lons, lats = [site.bbox[0], site.bbox[2], *[g.lon for g in site.gauges]], [site.bbox[1], site.bbox[3], *[g.lat for g in site.gauges]]
    i0, j0 = cell(min(lons), min(lats))
    i1, j1 = cell(max(lons), max(lats))
    times = [when(p["time"]) for p in passes]
    names = list_granules(min(times) - WEEK - timedelta(minutes=30), max(times))
    want = {s: n for s, n in names.items() if any(t - WEEK <= s < t for t in times)}
    path = CACHE / f"imerg_{river}.jsonl"
    cached = {}
    if path.exists():
        for ln in path.read_text().splitlines():
            r = json.loads(ln)
            cached[datetime.fromisoformat(r["t"])] = r["grid"]
    todo = [s for s in want if s not in cached]
    log(f"{river}: box {i1 - i0 + 1}x{j1 - j0 + 1} cells, {len(want)} half-hours, {len(todo)} to read")
    failed = 0
    with ThreadPoolExecutor(WORKERS) as pool, path.open("a") as out:
        jobs = {pool.submit(read_box, want[s], i0, i1, j0, j1): s for s in todo}
        for n, job in enumerate(as_completed(jobs), 1):
            s = jobs[job]
            try:
                grid = job.result()
            except (RuntimeError, ValueError, OSError) as e:
                failed += 1
                log(f"  failed {s}: {e}")
                continue
            cached[s] = grid
            out.write(json.dumps({"t": s.isoformat(), "grid": grid}) + "\n")
            out.flush()
            if n % 200 == 0:
                log(f"  {river}: {n}/{len(todo)}")
    log(f"{river}: done, {failed} failed")
    return {s: cached[s] for s in want if s in cached}, (i0, j0)


def totals(series, end, hours):
    """Sum half-hours in the window, in mm. series holds mm per hour by half-hour start."""
    vals = [v for t, v in series.items() if end - timedelta(hours=hours) <= t < end]
    return round(float(sum(vals)) * 0.5, 1) if len(vals) >= hours * 2 * 0.9 else None


def rainy(h24, h72):
    return bool((h24 or 0) >= RECENT_MM or (h72 or 0) >= ANTECEDENT_MM)


def log_err(x, gauge):
    return abs(float(np.log10((x + 1) / (gauge + 1))))


def main():
    old = json.loads((REPO_ROOT / "research" / "rainfall_by_pass.json").read_text())
    assert summarize(old["passes"]) == old["summary"], "summarize() no longer reproduces the saved rainfall summary"
    CACHE.mkdir(parents=True, exist_ok=True)
    rivers = list(dict.fromkeys(p["river"] for p in old["passes"]))
    first = when(old["passes"][0]["time"])
    check_axes(next(iter(list_granules(first - timedelta(hours=1), first).values())))
    rows, compare = [], []
    for river in rivers:
        passes = [p for p in old["passes"] if p["river"] == river]
        data, (i0, j0) = fetch_river(river, passes)
        site = get_site(river)
        arr = {t: np.where(np.array(g, float) < -9000, np.nan, np.array(g, float)) for t, g in data.items()}
        shape = next(iter(arr.values())).shape
        clon = -180 + 0.05 + 0.1 * (i0 + np.arange(shape[0]))
        clat = -90 + 0.05 + 0.1 * (j0 + np.arange(shape[1]))
        mask = np.outer((clon >= site.bbox[0]) & (clon <= site.bbox[2]), (clat >= site.bbox[1]) & (clat <= site.bbox[3]))
        assert mask.any(), river
        box = {t: float(np.nanmean(a[mask])) for t, a in arr.items() if np.isfinite(a[mask]).any()}
        gauges_by_id = {g.id: g for g in site.gauges}
        for p in passes:
            t = when(p["time"])
            row = {k: p[k] for k in ("river", "pair", "time", "high_ground_db", "low_minus_high_db", "auc_hh", "auc_hh_minus_hv", "estimated_ha", "dry_ha", "v4_csi", "brightened")}
            row.update(rain_24h_mm=totals(box, t, 24), rain_72h_mm=totals(box, t, 72), rain_7d_mm=totals(box, t, 168), half_hours_in_72h=sum(t - timedelta(hours=72) <= s < t for s in box))
            row.update(model_24h_mm=p["rain_24h_mm"], model_72h_mm=p["rain_72h_mm"], model_7d_mm=p["rain_7d_mm"], model_status=p["status"])
            row["rainy"] = rainy(row["rain_24h_mm"], row["rain_72h_mm"])
            row["status"] = "Likely contributor" if row["rainy"] and row["brightened"] else "Possible" if row["rainy"] or row["brightened"] else "Little sign"
            row["usgs_gauges"] = []
            for g in p["usgs_gauges"]:
                info = gauges_by_id[g["id"]]
                gi, gj = cell(info.lon, info.lat)
                series = {s: float(a[gi - i0, gj - j0]) for s, a in arr.items() if np.isfinite(a[gi - i0, gj - j0])}
                g2 = {**g, "imerg_cell_24h_mm": totals(series, t, 24), "imerg_cell_72h_mm": totals(series, t, 72)}
                row["usgs_gauges"].append(g2)
                if g2["imerg_cell_72h_mm"] is not None:
                    gauge_rainy = rainy(g["rain_24h_mm"], g["rain_72h_mm"])
                    compare.append({"river": river, "pair": p["pair"], "gauge": g["name"], "gauge_72h_mm": g["rain_72h_mm"], "imerg_72h_mm": g2["imerg_cell_72h_mm"], "model_72h_mm": p["rain_72h_mm"],
                                    "imerg_err": log_err(g2["imerg_cell_72h_mm"], g["rain_72h_mm"]), "model_err": log_err(p["rain_72h_mm"], g["rain_72h_mm"]),
                                    "imerg_label_agrees": rainy(g2["imerg_cell_24h_mm"], g2["imerg_cell_72h_mm"]) == gauge_rainy, "model_label_agrees": rainy(p["rain_24h_mm"], p["rain_72h_mm"]) == gauge_rainy})
            rows.append(row)
            log(json.dumps({k: row[k] for k in ("river", "pair", "rain_24h_mm", "rain_72h_mm", "rain_7d_mm", "model_72h_mm", "high_ground_db", "status", "model_status")}))
    complete = [r for r in rows if r["rain_72h_mm"] is not None and r["rain_24h_mm"] is not None]
    summary = summarize(complete)
    imerg_err, model_err = float(np.median([c["imerg_err"] for c in compare])), float(np.median([c["model_err"] for c in compare]))
    summary["passes_missing_totals"] = len(rows) - len(complete)
    summary["gauge_comparisons"] = len(compare)
    summary["median_log_error_imerg"], summary["median_log_error_model"] = imerg_err, model_err
    summary["label_agrees_imerg"] = sum(c["imerg_label_agrees"] for c in compare)
    summary["label_agrees_model"] = sum(c["model_label_agrees"] for c in compare)
    summary["app_source"] = "IMERG" if imerg_err <= model_err else "MERRA-2"
    (REPO_ROOT / "research" / "rainfall_imerg.json").write_text(json.dumps({"summary": summary, "gauge_comparison": compare, "passes": rows}, indent=1))
    log(json.dumps(summary, indent=1))
    log("IMERG DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("IMERG FAILED\n" + traceback.format_exc())
        raise
    finally:
        JAR.unlink(missing_ok=True)
