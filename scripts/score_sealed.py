"""Score the sealed passes as they reach NASA's catalog (research/SEALED_TEST_PROTOCOL.md §3 and §4).

    python scripts/score_sealed.py

Refuses to run if anything in research/freeze_receipt_sealed.json has changed. Each found pass is run once, with the
frozen live code, and its result is kept in outputs/sealed/<id>.json; it is never run again. Every sealed pass stays
in the results: waiting, missing, not run, not judgeable, or judged.

Writes research/SEALED_TEST_RESULTS.md and app/data/live/sealed.json (the Results page reads it). NISAR scenes and
IMERG rainfall are read with your Earthdata sign-in through curl and ~/.netrc; this code never reads the sign-in.
"""

import json
import sys
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hidden_floods import live
from hidden_floods.config import REPO_ROOT
from hidden_floods.frozen_v3 import RECEIPT_V3, settings_from
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.sealed import BASELINE_DAYS, MATCH, MISSING_AFTER, digest, hit, judgeable, light, rainy, reading

RECEIPT = REPO_ROOT / "research" / "freeze_receipt_sealed.json"
CACHE = REPO_ROOT / "outputs" / "sealed"
RESULTS_MD = REPO_ROOT / "research" / "SEALED_TEST_RESULTS.md"
SITE_JSON = REPO_ROOT / "app" / "data" / "live" / "sealed.json"


def parse(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def check_receipt() -> dict:
    if not RECEIPT.exists():
        raise SystemExit("not sealed yet: run scripts/seal_next_passes.py first")
    receipt = json.loads(RECEIPT.read_text())
    changed = [f for f, h in receipt["sha256"].items() if digest(REPO_ROOT / f) != h]
    if changed:
        raise SystemExit(f"changed since sealing, not scoring: {changed}")
    return receipt


def imerg_rain(bounds: tuple[float, float, float, float], when: datetime) -> tuple[float | None, float | None]:
    """IMERG V07 Late Run mean over the box, 24 h and 72 h before the pass (RAINFALL.md), with the project's reader."""
    import rain_imerg as ri   # the same reader as RAINFALL.md's check
    w, s, e, n = bounds
    i0, j0 = ri.cell(w, s)
    i1, j1 = ri.cell(e, n)
    t = when.astimezone(UTC).replace(tzinfo=None)
    names = ri.list_granules(t - timedelta(hours=72, minutes=30), t)
    want = {k: v for k, v in names.items() if t - timedelta(hours=72) <= k < t}
    ri.check_axes(next(iter(want.values())))
    series = {}
    for k, name in want.items():
        series[k] = float(np.mean(ri.read_box(name, i0, i1, j0, j1)))   # mm per hour, mean over the box's cells
    return ri.totals(series, t, 24), ri.totals(series, t, 72)


class Retry(Exception):
    """A temporary failure (catalog, rainfall or download): nothing is recorded, and the pass is tried again next time."""


def run_pass(e: dict, scene, rule, cfg, now: datetime) -> dict:
    """The frozen live run of one sealed pass, as scripts/live_cases.py runs a US case."""
    start = parse(e["flood_from"])
    before = [s for s in live.scenes_over(e["lon"], e["lat"], start - timedelta(days=BASELINE_DAYS), start) if s.stack_key == e["stack"]]
    base = [s for s in before if s.scene.name in set(e["baseline"])]
    if len(base) != len(e["baseline"]):
        return {"status": "not run", "reason": "The sealed earlier passes are no longer all in NASA's catalog."}
    case = {"id": f"sealed_{e['id']}", "kind": "us", "lon": e["lon"], "lat": e["lat"], "usgs": e["usgs"]}
    p = live.prepare(case, {"wet": scene, "baseline": base}, score_it=True)
    res = live.run_rule(p, rule)
    if p.truth is None:
        return {"status": "not run", "reason": "No usable USGS gauge with a known height reference in the box, so there's nothing to score against."}
    sc = live.score_case(p, res, cfg.block_m, cfg.n_boot, cfg.seed)
    wet_region = p.truth["wet"] & p.truth["region"]
    coverage = float((wet_region & res["mapped"]).sum() / wet_region.sum()) if wet_region.any() else None
    lon, lat = zip(*live.corners_lonlat(p.grid), strict=True)
    try:
        h24, h72 = imerg_rain((min(lon), min(lat), max(lon), max(lat)), scene.time)
    except Exception as ex:  # noqa: BLE001
        if now < scene.time + MISSING_AFTER:
            raise Retry(f"IMERG rainfall couldn't be read yet ({type(ex).__name__})") from ex
        h24 = h72 = None   # still unreadable 30 days on: rain unknown, so not judged
    is_rainy = rainy(h24, h72)
    lamp = light(bool(res["confident"]), is_rainy)
    csi = sc["scores"]["csi"]
    out = {"scene": scene.scene.name, "scene_utc": live._iso(scene.time), "confident": bool(res["confident"]), "rain_24h_mm": h24, "rain_72h_mm": h72,
           "rainy": is_rainy, "light": lamp, "csi": csi, "csi_ci95": sc["ci95"]["csi"] if sc["ci95"] else None, "estimate_wet_ha": sc["estimate_wet_ha"],
           "coverage": coverage, "flagged_ha": float((res["pred"] & ~p.water).sum() * p.grid.pixel_area_ha), "gauges": len(p.info.get("gauges", []))}
    if lamp is None:
        return out | {"status": "not judged", "reason": "IMERG rainfall couldn't be read, so the trust light is unknown."}
    if csi is None or not judgeable(sc["estimate_wet_ha"], coverage):
        return out | {"status": "not judgeable", "reason": "Under 500 ha of estimated flooding, or the radar mapped under 60% of it."}
    return out | {"status": "judged", "hit": hit(lamp, csi)}


def overbank_passes() -> list[dict]:
    rows = []
    for f in sorted((REPO_ROOT / "research").glob("overbank_*_frozen_metrics.json")):
        m = json.loads(f.read_text())
        if m.get("judgeable"):
            rows.append({"id": f"{m['site']} {m['pair']}", "light": m["trust_signal"], "csi": m["v4_csi"]})
    return rows


def main() -> None:
    receipt = check_receipt()
    sealed = json.loads((REPO_ROOT / receipt["list"]).read_text())
    rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    cfg = settings_from(json.loads(RECEIPT_V3.read_text()))
    now = datetime.now(UTC)
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for e in sealed["passes"]:
        row = {k: e[k] for k in ("id", "lid", "name", "state", "stack", "predicted_utc")}
        cached = CACHE / f"{e['id']}.json"
        if cached.exists():   # run once, never again
            rows.append(row | json.loads(cached.read_text()))
            continue
        pred = parse(e["predicted_utc"])
        if now < pred - MATCH:
            rows.append(row | {"status": "waiting", "reason": "Not flown yet."})
            continue
        try:
            found = [s for s in live.scenes_over(e["lon"], e["lat"], pred - 2 * MATCH, pred + 2 * MATCH) if s.stack_key == e["stack"] and abs(s.time - pred) <= MATCH]
        except Exception as ex:  # noqa: BLE001
            rows.append(row | {"status": "waiting", "reason": f"NASA's catalog didn't answer ({type(ex).__name__})."})
            continue
        if not found:
            gone = now > pred + MISSING_AFTER
            rows.append(row | {"status": "missing" if gone else "waiting", "reason": "No scene in NASA's catalog within an hour of the predicted time" + (" 30 days on." if gone else " yet.")})
            continue
        print(f"{e['id']}: running", flush=True)
        scene = min(found, key=lambda s: abs(s.time - pred))
        try:
            result = run_pass(e, scene, rule, cfg, now)
        except (Retry, OSError, TimeoutError, RuntimeError) as ex:   # temporary: nothing recorded, tried again next run
            rows.append(row | {"status": "waiting", "reason": f"Found, but couldn't be run this time ({ex}); tried again next check."})
            continue
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            result = {"status": "not run", "reason": f"The method couldn't run here: {ex}"}
        if result["status"] != "waiting":
            cached.write_text(json.dumps(result, indent=1, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
        rows.append(row | result)
    assert len(rows) == len(sealed["passes"]), "a sealed pass went missing from the results"
    judged = [{"id": r["id"], "light": r["light"], "csi": r["csi"]} for r in rows if r["status"] == "judged"]
    ob = overbank_passes()
    out = {"sealed_utc": sealed["sealed_utc"], "checked_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "protocol": sealed["protocol"],
           "counts": {s: sum(r["status"] == s for r in rows) for s in ("waiting", "missing", "not run", "not judged", "not judgeable", "judged")},
           "combined": reading(ob + judged), "sealed_only": reading(judged), "overbank_judgeable": len(ob), "passes": rows}
    SITE_JSON.write_text(json.dumps(out, separators=(",", ":"), default=str))
    lines = ["# Sealed test: results so far", "", f"Sealed {sealed['sealed_utc']} under `research/SEALED_TEST_PROTOCOL.md`. Checked {out['checked_utc']}.", "",
             f"**Combined with the overbank test's {len(ob)} judgeable passes:** {out['combined']['hits']} hits of {out['combined']['judgeable']} judgeable, **{out['combined']['verdict']}**.",
             f"**Sealed passes alone:** {out['sealed_only']['hits']} of {out['sealed_only']['judgeable']}, {out['sealed_only']['verdict']}.", "",
             "| Pass | River | Predicted (UTC) | Status | Light | CSI | Hit | Note |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['id']} | {r['name']}, {r['state']} | {r['predicted_utc']} | {r['status']} | {r.get('light') or '—'} | "
                     f"{'—' if r.get('csi') is None else f'{r['csi']:.2f}'} | {'—' if r.get('hit') is None else ('yes' if r['hit'] else 'no')} | {r.get('reason', '')} |")
    RESULTS_MD.write_text("\n".join(lines) + "\n", encoding="utf8")
    print(json.dumps(out["counts"]), out["combined"]["verdict"])


if __name__ == "__main__":
    main()
