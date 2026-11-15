"""Unblinds the reviews and applies the readings fixed in research/INDEPENDENT_AERIAL_PROTOCOL.md."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "outputs/independent_aerial"
key = json.loads((D / "private/key.json").read_text())
sha = hashlib.sha256((ROOT / "research/INDEPENDENT_AERIAL_PROTOCOL.md").read_bytes()).hexdigest()
print("protocol hash unchanged:", sha == key["protocol_sha256"], sha)
r1 = json.loads((D / "ratings/r1.json").read_text())
r2 = json.loads((D / "ratings/r2.json").read_text())
print("notes:", r1.get("_note"), "||", r2.get("_note"))
CLS = ["FLOOD", "PERMANENT", "DRY", "CANOPY", "UNSURE"]
DEC = {"FLOOD", "PERMANENT", "DRY"}
points = key["points"]
for p in points:
    a, b = r1[str(p["id"])], r2[str(p["id"])]
    p["class_1"], p["class_2"], p["score_1"], p["score_2"] = a["class"], b["class"], int(a["score"]), int(b["score"])
    p["consensus"] = a["class"] if a["class"] == b["class"] else "UNSURE"
    p["water_sign"] = min(p["score_1"], p["score_2"]) >= 2


def kappa(x, y, labels):
    n = len(x)
    po = sum(a == b for a, b in zip(x, y, strict=True)) / n
    ca, cb = Counter(x), Counter(y)
    pe = sum(ca[c] * cb[c] for c in labels) / n ** 2
    return (po - pe) / (1 - pe), po


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


kc = kappa([p["class_1"] for p in points], [p["class_2"] for p in points], CLS)
ks = kappa([p["score_1"] for p in points], [p["score_2"] for p in points], [0, 1, 2, 3])
within = sum(abs(p["score_1"] - p["score_2"]) <= 1 for p in points) / len(points)
print(f"points {len(points)}; class kappa {kc[0]:.2f}, agreement {kc[1]:.2f}; score kappa {ks[0]:.2f}, exact {ks[1]:.2f}, within one step {within:.2f}")
print("scores r1", sorted(Counter(p["score_1"] for p in points).items()), "r2", sorted(Counter(p["score_2"] for p in points).items()))
per = {}
for s in "AEFDGH":
    g = [p for p in points if p["stratum"] == s]
    c = Counter(p["consensus"] for p in g)
    dec = sum(c[x] for x in DEC)
    k = sum(p["water_sign"] for p in g)
    lo, hi = wilson(k, len(g))
    each = [sum(p[f"score_{i}"] >= 2 for p in g) for i in (1, 2)]
    per[s] = {"n": len(g), **{x: c[x] for x in CLS}, "decidable": dec, "water_sign": k, "share": round(k / len(g), 3), "ci": [round(lo, 2), round(hi, 2)], "reviewer_1_2plus": each[0], "reviewer_2_2plus": each[1], "mean_score": round(sum(p["score_1"] + p["score_2"] for p in g) / (2 * len(g)), 2)}
    print(s, per[s])


def cmp(a, b):
    ga, gb = [p for p in points if p["stratum"] in a], [p for p in points if p["stratum"] in b]
    k1, k2 = sum(p["water_sign"] for p in ga), sum(p["water_sign"] for p in gb)
    d, lo, hi = newcombe(k1, len(ga), k2, len(gb))
    return {"a": [k1, len(ga)], "b": [k2, len(gb)], "difference": round(d, 3), "ci": [round(lo, 3), round(hi, 3)], "above_zero": lo > 0}


h_share = per["H"]["water_sign"] / per["H"]["n"]
interpretable = h_share < 0.20
readings = {"1 control": {"H_water_sign": [per["H"]["water_sign"], per["H"]["n"]], "share": round(h_share, 3), "interpretable": interpretable}}
readings["2 D vs G"], readings["2 D vs H"] = cmp("D", "G"), cmp("D", "H")
readings["3 A vs F"], readings["3 A vs H"] = cmp("A", "F"), cmp("A", "H")
readings["4 E vs F"], readings["5 A vs E"] = cmp("E", "F"), cmp("A", "E")
readings["main"] = "not interpretable" if not interpretable else ("supported" if readings["2 D vs G"]["above_zero"] and readings["2 D vs H"]["above_zero"] else "not supported by this check")
readings["inside corridor"] = "not interpretable" if not interpretable else ("supported" if readings["3 A vs F"]["above_zero"] else "not supported by this check")
readings["estimate alone"] = "not interpretable" if not interpretable else ("supported" if readings["4 E vs F"]["above_zero"] else "not supported by this check")
for k, v in readings.items():
    print(k, v)
print("permanent excluded sensitivity (water sign without consensus PERMANENT):", {s: [sum(p["water_sign"] and p["consensus"] != "PERMANENT" for p in points if p["stratum"] == s), sum(p["stratum"] == s for p in points)] for s in "AEFDGH"})
print("rows with water sign:", [(p["id"], p["stratum"], p["consensus"], p["score_1"], p["score_2"], p["sheet"]) for p in points if p["water_sign"]])
print("flood called by one or both:", Counter((p["stratum"], p["class_1"] == "FLOOD", p["class_2"] == "FLOOD") for p in points if "FLOOD" in (p["class_1"], p["class_2"])))
(ROOT / "research/independent_aerial_results.json").write_text(json.dumps({"protocol_sha256": sha, "class_kappa": round(kc[0], 3), "score_kappa": round(ks[0], 3), "score_within_one": round(within, 3), "strata": per, "readings": readings}, indent=1))
(ROOT / "research/independent_aerial_points.json").write_text(json.dumps([{k: p[k] for k in ("id", "stratum", "lon", "lat", "hand_m", "mission", "class_1", "class_2", "score_1", "score_2", "consensus", "water_sign")} for p in points], indent=0))
