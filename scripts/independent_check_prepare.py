"""Draws points and builds blind chips for research/INDEPENDENT_CHECK_PROTOCOL.md. Writes only into the scratchpad."""
import hashlib
import io
import json
import math
import random
import sys
import tomllib
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from pyproj import Transformer
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]   # the project folder
sys.path.insert(0, str(ROOT / "src"))
from hidden_floods.audit import truth_context
from hidden_floods.config import load_site
from hidden_floods.pipeline import analysis_grid
from hidden_floods.v3 import LC_OTHER, LC_TREE, LC_WETLAND

OUT = ROOT / "outputs/independent_check"
SHEETS, PRIVATE = OUT / "sheets", OUT / "private"
SHEETS.mkdir(parents=True, exist_ok=True); PRIVATE.mkdir(parents=True, exist_ok=True)
SEED = 20261106
UA = {"User-Agent": "hidden-floods-research/0.1"}
JSONH = {**UA, "Content-Type": "application/json"}
LC = (LC_TREE, LC_WETLAND, LC_OTHER)
STRATA = "ABCDEFG"


def post(url, body):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), JSONH), timeout=90).read())


def strata(pred, wet, dry, scored, corridor, lc, hand):
    allowed = np.isin(lc, LC)
    return {"A": pred & wet & scored, "B": pred & dry & scored, "C": pred & corridor & ~wet & ~dry & scored, "D": pred & ~corridor & scored,
            "E": ~pred & wet & scored, "F": ~pred & dry & scored, "G": ~pred & ~corridor & scored & allowed & (hand < 6)}


def s2_items(bbox, start, end):
    return post("https://earth-search.aws.element84.com/v1/search", {"collections": ["sentinel-2-l2a"], "bbox": bbox, "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 200})["features"]


class Scene:
    """One Sentinel-2 tile. Cloud classes load up front; bands are read only when a chip is built."""

    def __init__(self, item):
        self.item, self.id = item, item["id"]
        self.time = datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00"))
        self.offset = 0 if item["properties"].get("earthsearch:boa_offset_applied", True) else 1000
        with rasterio.open(item["assets"]["scl"]["href"]) as src:
            self.scl, self.crs, self.bounds, self.t20 = src.read(1), src.crs, src.bounds, src.transform
        self.to = Transformer.from_crs(4326, self.crs, always_xy=True)

    def clear_at(self, lon, lat):
        x, y = self.to.transform(lon, lat)
        if not (self.bounds.left + 500 < x < self.bounds.right - 500 and self.bounds.bottom + 500 < y < self.bounds.top - 500):
            return False
        c, r = ~self.t20 * (x, y)
        r, c = int(r), int(c)
        win = self.scl[max(r - 2, 0):r + 3, max(c - 2, 0):c + 3]
        return win.size > 0 and not np.isin(win, [0, 1, 3, 8, 9, 10]).any()

    def bands(self, lon, lat, half_px=40):
        x, y = self.to.transform(lon, lat)
        out = {}
        for key in ("blue", "green", "red", "nir", "swir16"):
            with rasterio.open(self.item["assets"][key]["href"]) as src:
                c, r = ~src.transform * (x, y)
                scale = 2 if key == "swir16" else 1
                n = half_px // scale
                data = src.read(1, window=Window(int(c) - n, int(r) - n, 2 * n, 2 * n), boundless=True, fill_value=0).astype(float)
                if scale == 2:
                    data = np.repeat(np.repeat(data, 2, 0), 2, 1)
                out[key] = np.clip((data - self.offset) / 10000.0, 0, 1)
        return out


def rgb(a, b, c, top):
    return (np.clip(np.dstack([a, b, c]) / top, 0, 1) ** 0.8 * 255).astype(np.uint8)


def mark(img, box):
    """Corner ticks around the box, so nothing covers the ground inside it."""
    d = ImageDraw.Draw(img); w, h = img.size; a, b = (w - box) // 2, (w + box) // 2; t = max(3, box // 4)
    for x, sx in ((a, 1), (b, -1)):
        for y, sy in (((h - box) // 2, 1), ((h + box) // 2, -1)):
            d.line([(x, y), (x + sx * t, y)], fill=(255, 255, 0), width=2); d.line([(x, y), (x, y + sy * t)], fill=(255, 255, 0), width=2)
    return img


def s2_chip(pt):
    before, event = pt["_before"].bands(pt["lon"], pt["lat"]), pt["_event"].bands(pt["lon"], pt["lat"])
    panels = [rgb(before["red"], before["green"], before["blue"], 0.25), rgb(event["red"], event["green"], event["blue"], 0.25),
              rgb(before["swir16"], before["nir"], before["red"], 0.45), rgb(event["swir16"], event["nir"], event["red"], 0.45)]
    row = Image.new("RGB", (4 * 160 + 3 * 4, 160), (30, 30, 30))
    for k, p in enumerate(panels):
        row.paste(mark(Image.fromarray(p).resize((160, 160), Image.NEAREST), 10), (k * 164, 0))
    mn = lambda b: (b["green"] - b["swir16"]) / np.maximum(b["green"] + b["swir16"], 1e-4)
    box = lambda m: float((m[38:43, 38:43] > 0).mean())
    return row, {"mndwi_event_share": box(mn(event)), "mndwi_before_share": box(mn(before))}


def tile_xy(lon, lat, z):
    n = 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def get_tile(url):
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None


def mosaic_chip(template, lon, lat, z=18, size=300):
    fx, fy = tile_xy(lon, lat, z)
    px, py = fx * 256, fy * 256
    x0, y0 = int(px - size / 2), int(py - size / 2)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for tx in range(x0 // 256, (x0 + size) // 256 + 1):
        for ty in range(y0 // 256, (y0 + size) // 256 + 1):
            t = get_tile(template.format(z=z, x=tx, y=ty))
            if t is not None:
                canvas.paste(t, (tx * 256 - x0, ty * 256 - y0))
    return canvas


def has_data(chip):
    """Flown or not, judged from transparency and pure black only."""
    a = np.asarray(chip)
    return float(((a[..., 3] > 0) & (a[..., :3].sum(axis=2) > 0)).mean()) > 0.9


def draw(masks, lon, lat, n, accept, spacing=300.0):
    rng = np.random.default_rng(SEED)
    out = {}
    for name in STRATA:
        r, c = np.nonzero(masks[name])
        order = rng.permutation(len(r))
        picked, xy = [], []
        for k in order:
            la, lo = lat[r[k], c[k]], lon[r[k], c[k]]
            mx, my = lo * 111320 * math.cos(math.radians(la)), la * 110540
            if any((mx - a) ** 2 + (my - b) ** 2 < spacing ** 2 for a, b in xy):
                continue
            extra = accept(float(lo), float(la))
            if extra is None:
                continue
            picked.append({"lon": float(lo), "lat": float(la), "stratum": name, "row": int(r[k]), "col": int(c[k]), **extra}); xy.append((mx, my))
            if len(picked) == n:
                break
        out[name] = picked
        print(f"  stratum {name}: pixels {len(r)}, points {len(picked)}", flush=True)
    return out


def lonlat(grid):
    X, Y = np.meshgrid(grid.xs, grid.ys)
    a, b = Transformer.from_crs(grid.crs, 4326, always_xy=True).transform(X, Y)
    return np.asarray(a), np.asarray(b)


def s2_case(river, pair, event_items, before_items):
    site = load_site(river); grid = analysis_grid(site); lon, lat = lonlat(grid)
    z = np.load(ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
    masks = strata(z["pred"], z["wet"], z["dry"], z["region"] & z["mapped"], np.isfinite(z["depth"]), z["landcover"], z["hand"])
    print(river, {k: int(v.sum()) for k, v in masks.items()}, flush=True)
    radar = datetime.fromisoformat(site.pairs[pair].wet_time.replace("Z", "+00:00"))
    events = sorted((Scene(i) for i in event_items), key=lambda s: abs((s.time - radar).total_seconds()))
    befores = sorted((Scene(i) for i in before_items), key=lambda s: s.time, reverse=True)

    def accept(lo, la):
        e = next((s for s in events if s.clear_at(lo, la)), None)
        b = next((s for s in befores if s.clear_at(lo, la)), None)
        return None if e is None or b is None else {"_event": e, "_before": b}
    pts = draw(masks, lon, lat, 25, accept)
    return [{**p, "river": river, "pair": pair, "case": river} for v in pts.values() for p in v]


# ---- Sentinel-2 cases: scene choice by the protocol's metadata rule ----
def latest_clear(items, cutoff, max_cloud=10):
    best = {}
    for f in items:
        tile = f["id"].split("_")[1]
        if f["properties"]["eo:cloud_cover"] <= max_cloud and f["properties"]["datetime"][:10] <= cutoff:
            if tile not in best or f["properties"]["datetime"] > best[tile]["properties"]["datetime"]:
                best[tile] = f
    return list(best.values())


sat_bbox = tomllib.loads((ROOT / "sites/satilla.toml").read_text())["bbox"]
sab_bbox = tomllib.loads((ROOT / "sites/lower_sabine.toml").read_text())["bbox"]
sat_event = [f for f in s2_items(sat_bbox, "2026-10-14", "2026-10-14")]
sat_before = latest_clear(s2_items(sat_bbox, "2026-08-15", "2026-09-20"), "2026-09-20")
sab_event = [f for f in s2_items(sab_bbox, "2026-07-16", "2026-07-18") if f["properties"]["datetime"][:10] in ("2026-07-16", "2026-07-18")]
sab_before = latest_clear(s2_items(sab_bbox, "2026-04-15", "2026-07-10"), "2026-07-10", 10)
print("scenes:", json.dumps({"satilla_event": [f["id"] for f in sat_event], "satilla_before": [f["id"] for f in sat_before], "sabine_event": [f["id"] for f in sab_event], "sabine_before": [f["id"] for f in sab_before]}), flush=True)
points = s2_case("satilla", "047A_oct15", sat_event, sat_before) + s2_case("lower_sabine", "134A_jul17", sab_event, sab_before)

# ---- Blind Sentinel-2 sheets ----
rng = random.Random(SEED)
rng.shuffle(points)
ids = rng.sample(range(1000, 9999), len(points))
for p, i in zip(points, ids):
    p["id"] = i
with ThreadPoolExecutor(12) as ex:
    chips = list(ex.map(s2_chip, points))
key = []
PER = 10
for s in range(0, len(points), PER):
    batch = list(zip(points[s:s + PER], chips[s:s + PER]))
    sheet = Image.new("RGB", (4 * 164 + 70, 24 + 168 * len(batch)), (12, 12, 12))
    d = ImageDraw.Draw(sheet)
    for k, label in enumerate(("before, natural", "event, natural", "before, false color", "event, false color")):
        d.text((70 + k * 164, 6), label, fill=(230, 230, 230))
    for n, (p, (row, stats)) in enumerate(batch):
        d.text((6, 24 + n * 168 + 72), str(p["id"]), fill=(255, 255, 255))
        sheet.paste(row, (70, 24 + n * 168))
        key.append({k: v for k, v in p.items() if not k.startswith("_")} | stats | {"event_scene": p["_event"].id, "before_scene": p["_before"].id, "event_time": p["_event"].time.isoformat(), "sheet": f"sat_{s // PER + 1:03d}"})
    sheet.save(SHEETS / f"sat_{s // PER + 1:03d}.jpg", quality=88)
print("satellite points", len(points), "sheets", (len(points) + PER - 1) // PER, flush=True)

# ---- Yellow aerial, frozen v3 map ----
site = load_site("yellow"); grid = analysis_grid(site); lon, lat = lonlat(grid)
z = np.load(ROOT / "outputs/yellow/055D_oct16/frozen_v3_layers.npz")
corridor = truth_context(site, site.pairs["055D_oct16"].wet_time).truth.corridor
masks = strata(z["pred"], z["wet"], z["dry"], z["region"] & z["mapped"], corridor, z["landcover"], z["hand"])
print("yellow", {k: int(v.sum()) for k, v in masks.items()}, flush=True)
MISSIONS = [("20261012a", (-89.2, 30.112, -86.862, 30.813)), ("20261011b", (-87.388, 30.325, -86.8, 30.6)), ("20261011a", (-88.063, 29.975, -85.475, 30.488))]
for name in STRATA:  # only flown bounds, to keep the tile checks small
    in_any = np.zeros(lon.shape, bool)
    for _, b in MISSIONS:
        in_any |= (lon > b[0]) & (lon < b[2]) & (lat > b[1]) & (lat < b[3])
    masks[name] = masks[name] & in_any
print("yellow inside flown bounds", {k: int(v.sum()) for k, v in masks.items()}, flush=True)


def accept_aerial(lo, la):
    for mission, b in MISSIONS:
        if b[0] < lo < b[2] and b[1] < la < b[3]:
            chip = mosaic_chip(f"https://stormscdn.ngs.noaa.gov/{mission}-rgb/{{z}}/{{x}}/{{y}}", lo, la)
            if has_data(chip):
                return {"mission": mission, "_chip": chip}
    return None


aerial = [p for v in draw(masks, lon, lat, 20, accept_aerial).values() for p in v]
rng.shuffle(aerial)
ids = rng.sample(range(1000, 9999), len(aerial))
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
akey = []
PER_A = 8
for s in range(0, len(aerial), PER_A):
    batch = aerial[s:s + PER_A]
    rows = math.ceil(len(batch) / 2)
    sheet = Image.new("RGB", (2 * (2 * 240 + 56), 22 + rows * 262), (12, 12, 12))
    d = ImageDraw.Draw(sheet)
    for n, p in enumerate(batch):
        p["id"] = rng.randrange(10000, 99999)
        x, y = (n % 2) * (2 * 240 + 56), 22 + (n // 2) * 262
        d.text((x + 4, y + 2), f"{p['id']}", fill=(255, 255, 255))
        d.text((x + 50, y + 2), "usual", fill=(200, 200, 200)); d.text((x + 50 + 240, y + 2), "event", fill=(200, 200, 200))
        usual = mosaic_chip(ESRI, p["lon"], p["lat"]).convert("RGB").resize((240, 240))
        event = p["_chip"].convert("RGB").resize((240, 240))
        box = int(240 * 50 / (300 * 0.51))
        sheet.paste(mark(usual, box), (x + 50, y + 18)); sheet.paste(mark(event, box), (x + 50 + 240, y + 18))
        akey.append({k: v for k, v in p.items() if not k.startswith("_")} | {"river": "yellow", "pair": "055D_oct16", "case": "yellow_aerial", "sheet": f"aer_{s // PER_A + 1:03d}"})
    sheet.save(SHEETS / f"aer_{s // PER_A + 1:03d}.jpg", quality=88)
print("aerial points", len(aerial), "sheets", (len(aerial) + PER_A - 1) // PER_A, flush=True)

proto = (ROOT / "research/INDEPENDENT_CHECK_PROTOCOL.md").read_bytes()
(PRIVATE / "key.json").write_text(json.dumps({"protocol_sha256": hashlib.sha256(proto).hexdigest(), "made": datetime.now(UTC).isoformat(), "scenes": {"satilla_event": [f["id"] for f in sat_event], "satilla_before": [f["id"] for f in sat_before], "sabine_event": [f["id"] for f in sab_event], "sabine_before": [f["id"] for f in sab_before]}, "points": key + akey}, indent=1))
print("done", hashlib.sha256(proto).hexdigest(), flush=True)
