"""Unblinds the reviews and applies the readings fixed in research/INDEPENDENT_CHECK_PROTOCOL.md."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # the project folder
D = ROOT / "outputs/independent_check"
key = json.loads((D / "private/key.json").read_text())
proto = hashlib.sha256((ROOT / "research/INDEPENDENT_CHECK_PROTOCOL.md").read_bytes()).hexdigest()
print("protocol hash unchanged:", proto == key["protocol_sha256"], proto)
CLS = ["FLOOD", "PERMANENT", "DRY", "CANOPY", "CLOUD", "UNSURE"]
DEC = {"FLOOD", "PERMANENT", "DRY"}


def load(name):
    j = json.loads((D / "ratings" / name).read_text())
    return {k: v for k, v in j.items() if k.isdigit()}, {k: v for k, v in j.items() if not k.isdigit()}


r1 = {**load("r1_sat.json")[0], **load("r1_aer.json")[0]}
r2 = {**load("r2_sat.json")[0], **load("r2_aer.json")[0]}
for n in ("r1_sat.json", "r2_sat.json", "r1_aer.json", "r2_aer.json"):
    print("note", n, load(n)[1])


def kappa(a, b):
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in CLS) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else None, po


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def newcombe(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


out = {"protocol_sha256": proto, "cases": {}}
for case in ("satilla", "lower_sabine", "yellow_aerial"):
    pts = [p for p in key["points"] if p["case"] == case]
    for p in pts:
        a, b = r1.get(str(p["id"])), r2.get(str(p["id"]))
        p["r1"], p["r2"] = a, b
        p["consensus"] = a if a == b and a is not None else "UNSURE"
    both = [p for p in pts if p["r1"] and p["r2"]]
    kp = kappa([p["r1"] for p in both], [p["r2"] for p in both])
    missing = len(pts) - len(both)
    print(f"\n===== {case}: {len(pts)} points, rated by both {len(both)}, missing {missing}, kappa {kp[0]:.2f}, raw agreement {kp[1]:.2f}")
    print("consensus:", Counter(p["consensus"] for p in pts))
    per = {}
    for s in "ABCDEFG":
        g = [p for p in pts if p["stratum"] == s]
        c = Counter(p["consensus"] for p in g)
        dec = sum(c[x] for x in DEC)
        lo, hi = wilson(c["FLOOD"], dec)
        auto = None
        if g and "mndwi_event_share" in g[0]:
            auto = sum(p["mndwi_event_share"] >= 0.5 and p["mndwi_before_share"] < 0.5 for p in g)
        per[s] = {"n": len(g), **{x: c[x] for x in CLS}, "decidable": dec, "flood_share": None if not dec else round(c["FLOOD"] / dec, 3), "ci": None if not dec else [round(lo, 2), round(hi, 2)], "auto_new_water": auto}
        print(s, per[s])

    def pool(strata):
        g = [p for p in pts if p["stratum"] in strata and p["consensus"] in DEC]
        return sum(p["consensus"] == "FLOOD" for p in g), len(g)

    readings = {}
    for name, x, y in (("1 estimate wet vs dry", "AE", "BF"), ("2 flags beyond corridor vs control", "D", "G"), ("3 within estimate wet, flagged vs not", "A", "E"), ("extra flagged vs not, labelled", "AB", "EF")):
        k1, n1 = pool(x); k2, n2 = pool(y)
        if n1 >= 10 and n2 >= 10:
            d, lo, hi = newcombe(k1, n1, k2, n2)
            readings[name] = {"a": [k1, n1], "b": [k2, n2], "difference": round(d, 3), "ci": [round(lo, 3), round(hi, 3)], "reading": "supported" if lo > 0 else "not supported"}
        else:
            readings[name] = {"a": [k1, n1], "b": [k2, n2], "reading": "imagery can't decide (fewer than 10 decidable on a side)"}
        print(name, readings[name])
    if pts and "mndwi_event_share" in pts[0]:
        for name, x, y in (("auto: estimate wet vs dry", "AE", "BF"), ("auto: beyond corridor flags vs control", "D", "G"), ("auto: flagged vs not, labelled wet", "A", "E")):
            f = lambda st: (sum(p["mndwi_event_share"] >= 0.5 and p["mndwi_before_share"] < 0.5 for p in pts if p["stratum"] in st), sum(p["stratum"] in st for p in pts))
            k1, n1 = f(x); k2, n2 = f(y)
            d, lo, hi = newcombe(k1, n1, k2, n2)
            readings[name] = {"a": [k1, n1], "b": [k2, n2], "difference": round(d, 3), "ci": [round(lo, 3), round(hi, 3)]}
            print(name, readings[name])
    if case == "lower_sabine":
        print("event scene used:", Counter(p["event_time"][:10] for p in pts))
    print("FLOOD consensus points:", [(p["id"], p["stratum"]) for p in pts if p["consensus"] == "FLOOD"][:30])
    out["cases"][case] = {"points": len(pts), "rated_by_both": len(both), "kappa": round(kp[0], 3), "agreement": round(kp[1], 3), "strata": per, "readings": readings}

(ROOT / "research/independent_check_results.json").write_text(json.dumps(out, indent=1))
slim = [{k: v for k, v in p.items() if k in ("id", "case", "stratum", "lon", "lat", "r1", "r2", "consensus", "mndwi_event_share", "mndwi_before_share", "event_scene", "before_scene", "mission")} for p in key["points"]]
(ROOT / "research/independent_check_points.json").write_text(json.dumps(slim, indent=0))
