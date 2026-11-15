"""Draws points and builds blind chips for research/INDEPENDENT_AERIAL_PROTOCOL.md."""
import hashlib
import io
import json
import math
import random
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer

from hidden_floods.audit import truth_context
from hidden_floods.config import load_site
from hidden_floods.pipeline import analysis_grid
from hidden_floods.v3 import LC_TREE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/independent_aerial"
SHEETS, PRIVATE = OUT / "sheets", OUT / "private"
SHEETS.mkdir(parents=True, exist_ok=True)
PRIVATE.mkdir(parents=True, exist_ok=True)
SEED = 20261107
PER_STRATUM, PER_SHEET = 24, 3
UA = {"User-Agent": "hidden-floods-research/0.1"}
MISSIONS = [("20261012a", (-89.2, 30.112, -86.862, 30.813)), ("20261011b", (-87.388, 30.325, -86.8, 30.6)), ("20261011a", (-88.063, 29.975, -85.475, 30.488))]
NOAA = "https://stormscdn.ngs.noaa.gov/{mission}-rgb/{z}/{x}/{y}"
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


def tile(url):
    for attempt in range(2):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
            return Image.open(io.BytesIO(data)).convert("RGBA")
        except urllib.error.HTTPError:
            return None
        except (urllib.error.URLError, OSError):
            if attempt:
                return None
    return None


def chip(fmt, lon, lat, z, size):
    n = 2 ** z
    px = (lon + 180) / 360 * n * 256
    py = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * 256
    x0, y0 = int(px - size / 2), int(py - size / 2)
    jobs = [(tx, ty) for tx in range(x0 // 256, (x0 + size) // 256 + 1) for ty in range(y0 // 256, (y0 + size) // 256 + 1)]
    with ThreadPoolExecutor(6) as ex:
        tiles = list(ex.map(lambda t: tile(fmt.format(z=z, x=t[0], y=t[1])), jobs))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for (tx, ty), t in zip(jobs, tiles, strict=True):
        if t is not None:
            canvas.paste(t, (tx * 256 - x0, ty * 256 - y0))
    return canvas


def has_data(img):
    a = np.asarray(img)
    return float(((a[..., 3] > 0) & (a[..., :3].sum(axis=2) > 0)).mean()) > 0.95


def mark(img, box):
    d = ImageDraw.Draw(img)
    w, h = img.size
    a, b, c, e = (w - box) // 2, (w + box) // 2, (h - box) // 2, (h + box) // 2
    t = max(6, box // 5)
    for x, sx in ((a, 1), (b, -1)):
        for y, sy in ((c, 1), (e, -1)):
            d.line([(x, y), (x + sx * t, y)], fill=(255, 255, 0), width=2)
            d.line([(x, y), (x, y + sy * t)], fill=(255, 255, 0), width=2)
    return img


site = load_site("yellow")
grid = analysis_grid(site)
X, Y = np.meshgrid(grid.xs, grid.ys)
lon, lat = (np.asarray(v) for v in Transformer.from_crs(grid.crs, 4326, always_xy=True).transform(X, Y))
z = np.load(ROOT / "outputs/yellow/055D_oct16/frozen_v3_layers.npz")
pred, wet, dry, hand = z["pred"], z["wet"], z["dry"], z["hand"]
corridor = truth_context(site, site.pairs["055D_oct16"].wet_time).truth.corridor
flown = np.zeros(lon.shape, bool)
for _, b in MISSIONS:
    flown |= (lon > b[0]) & (lon < b[2]) & (lat > b[1]) & (lat < b[3])
base = z["region"] & z["mapped"] & (z["landcover"] == LC_TREE) & flown
masks = {"A": base & pred & wet, "E": base & ~pred & wet, "F": base & ~pred & dry, "D": base & pred & ~corridor, "G": base & ~pred & ~corridor & (hand < 6), "H": base & ~pred & ~corridor & (hand >= 10)}
print({k: int(v.sum()) for k, v in masks.items()}, flush=True)

first_round = ROOT / "outputs/independent_check/private/key.json"
earlier = [(p["lon"], p["lat"]) for p in json.loads(first_round.read_text())["points"] if p["case"] == "yellow_aerial"]
to_m = lambda lo, la: (lo * 111320 * math.cos(math.radians(la)), la * 110540)
earlier_m = [to_m(*p) for p in earlier]
rng = np.random.default_rng(SEED)
points = []
for name, mask in masks.items():
    rows, cols = np.nonzero(mask)
    accepted, used = [], []
    for k in rng.permutation(len(rows)):
        lo, la = float(lon[rows[k], cols[k]]), float(lat[rows[k], cols[k]])
        mx, my = to_m(lo, la)
        if any((mx - a) ** 2 + (my - b) ** 2 < 300 ** 2 for a, b in used + earlier_m):
            continue
        for mission, b in MISSIONS:
            if b[0] < lo < b[2] and b[1] < la < b[3]:
                img = chip(NOAA.replace("{mission}", mission), lo, la, 19, 384)
                if has_data(img):
                    accepted.append({"lon": lo, "lat": la, "stratum": name, "row": int(rows[k]), "col": int(cols[k]), "hand_m": round(float(hand[rows[k], cols[k]]), 2), "mission": mission, "_chip": img})
                    used.append((mx, my))
                    break
        if len(accepted) == PER_STRATUM:
            break
    points += accepted
    print(f"stratum {name}: pixels {len(rows)}, points {len(accepted)}", flush=True)

order = random.Random(SEED)
order.shuffle(points)
ids = order.sample(range(100000, 999999), len(points))
key = []
HEIGHT = 396
for s in range(0, len(points), PER_SHEET):
    batch = points[s:s + PER_SHEET]
    sheet = Image.new("RGB", (70 + 200 + 8 + 384 + 8 + 388, 22 + HEIGHT * len(batch)), (12, 12, 12))
    d = ImageDraw.Draw(sheet)
    for x, label in ((70, "usual, about 100 m across"), (278, "event, about 100 m across"), (670, "event, the 50 m box enlarged")):
        d.text((x, 5), label, fill=(230, 230, 230))
    for n, (p, pid) in enumerate(zip(batch, ids[s:s + PER_SHEET], strict=True)):
        y = 22 + n * HEIGHT
        d.text((6, y + 180), str(pid), fill=(255, 255, 255))
        usual = chip(ESRI, p["lon"], p["lat"], 18, 196).convert("RGB").resize((200, 200))
        event = p["_chip"].convert("RGB")
        crop = event.crop((96, 96, 288, 288)).resize((388, 388), Image.LANCZOS)
        sheet.paste(mark(usual, 100), (70, y))
        sheet.paste(mark(event.copy(), 192), (278, y))
        sheet.paste(crop, (670, y))
        key.append({k: v for k, v in p.items() if not k.startswith("_")} | {"id": pid, "sheet": f"aer2_{s // PER_SHEET + 1:03d}"})
    sheet.save(SHEETS / f"aer2_{s // PER_SHEET + 1:03d}.jpg", quality=90)
protocol = hashlib.sha256((ROOT / "research/INDEPENDENT_AERIAL_PROTOCOL.md").read_bytes()).hexdigest()
(PRIVATE / "key.json").write_text(json.dumps({"protocol_sha256": protocol, "made": datetime.now(UTC).isoformat(), "points": key}, indent=1))
print("points", len(key), "sheets", (len(key) + PER_SHEET - 1) // PER_SHEET, "protocol", protocol, flush=True)
