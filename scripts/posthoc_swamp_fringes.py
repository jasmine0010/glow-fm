"""POST-HOC, exploratory: NISAR's phase over the Choctawhatchee delta swamp during Hurricane Isaias (Results, Fig. 11).

Not part of any frozen test and not scored. It redraws the feasibility check F3 (research/FEASIBILITY.md, "F3 follow-up")
from the three GUNW pairs on disk: a dry-season control (Sep 15 -> 27), the rising flood (Oct 9 -> 21) and the crest seen
from the other direction (Oct 5 -> 17).

Writes app/data/figures/fringes_{control,flood,crest}.jpg (hue: wrapped phase; brightness: coherence) and
app/data/figures/fringes.json (each pair's facts and its water-level profile along the swamp), and prints the profile
at three longitudes to compare with the table in FEASIBILITY.md.

Profile method (unchanged from the feasibility check): along the swamp band, add up the phase step from each 20 m column
to the next over pixels with coherence > 0.45 in both columns (columns with fewer than 10 such pixels add nothing),
convert phase to vertical water-level change with each pair's incidence angle, and report it relative to the Bunker
gauge. The sign convention (a negative phase step means the water rose) is unverified.
"""

import json

import h5py
import numpy as np
from PIL import Image
from pyproj import Transformer

from hidden_floods.config import REPO_ROOT, data_root
from hidden_floods.io.nisar import GUNW_WRP, IDENT, WAVELENGTH_M, gunw_incidence_deg, read_gunw_box

FOLDER = data_root() / "choctawhatchee"
PAIRS = [
    ("control", "Sep 15 to Sep 27", "dry-season control", "GUNW_030_127_D_073_031_4000_SH_20260915"),
    ("flood", "Oct 9 to Oct 21", "flood rising", "GUNW_032_127_D_073_033_4000_SH_20261009"),
    ("crest", "Oct 5 to Oct 17", "flood crest", "GUNW_032_076_A_017_033_4000_SH_20261005"),
]
VIEW = (-86.17, 30.33, -85.94, 30.47)    # the picture: west, south, east, north
BAND = (-86.16, 30.377, -85.95, 30.428)  # the profile's swamp band
BUNKER = (-86.088, 30.395)               # FDEP gauge CTBF1, Choctawhatchee River at Bunker: the profile's zero
COH_MIN, COLS_MIN = 0.45, 10
CHECK_LONS = (-86.04, -86.02, -85.99)
OUT = REPO_ROOT / "app" / "data" / "figures"


def utm_box(t, box):
    (x0, y0), (x1, y1) = t.transform(box[0], box[1]), t.transform(box[2], box[3])
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def picture(layers, name):
    """Wrapped phase as hue, coherence as brightness, averaged over 2 by 2 pixels (40 m)."""
    ifg, coh = layers.layers["wrappedInterferogram"], layers.layers["coherenceMagnitude"].astype(float)
    h, w = (ifg.shape[0] // 2) * 2, (ifg.shape[1] // 2) * 2
    z = ifg[:h, :w].reshape(h // 2, 2, w // 2, 2).mean((1, 3))
    c = np.nan_to_num(coh[:h, :w].reshape(h // 2, 2, w // 2, 2).mean((1, 3)))
    hue = ((np.angle(z) + np.pi) / (2 * np.pi) * 255).astype(np.uint8)
    val = (np.clip(c / 0.75, 0, 1) ** 0.8 * 255).astype(np.uint8)
    hsv = np.dstack([hue, np.full_like(hue, 215), val])
    Image.fromarray(hsv, "HSV").convert("RGB").save(OUT / f"fringes_{name}.jpg", quality=84, optimize=True, progressive=True)
    return w // 2, h // 2


def profile(path, t, tb):
    layers = read_gunw_box(path, utm_box(t, BAND), which="wrapped")
    ifg, coh = layers.layers["wrappedInterferogram"], layers.layers["coherenceMagnitude"]
    cx, cy = t.transform(-86.03, 30.40)
    theta = gunw_incidence_deg(path, cx, cy)
    per_rad = WAVELENGTH_M / (4 * np.pi * np.cos(np.deg2rad(theta)))
    step = ifg[:, 1:] * np.conj(ifg[:, :-1])
    ok = (coh[:, 1:] > COH_MIN) & (coh[:, :-1] > COH_MIN)
    total, count = np.where(ok, step, 0).sum(0), ok.sum(0)
    rise = np.concatenate([[0.0], np.cumsum(np.where(count >= COLS_MIN, np.angle(total), 0.0))])
    good = np.concatenate([[False], count >= COLS_MIN])
    ymid = (layers.ys[0] + layers.ys[-1]) / 2
    lons = np.array([tb.transform(x, ymid)[0] for x in layers.xs])
    dh = -(rise - rise[np.abs(lons - BUNKER[0]).argmin()]) * per_rad
    return {
        "incidence_deg": round(theta, 1), "m_per_cycle": round(2 * np.pi * per_rad, 3),
        "swamp_coherence": round(float(np.median(coh[coh > 0.2])), 2), "coherent_columns": round(float(np.mean(count >= COLS_MIN)), 2),
        "lon": [round(float(v), 4) for v in lons[::5]], "dh_m": [round(float(v), 3) for v in dh[::5]],
        "ok": [bool(good[k:k + 5].mean() >= 0.5) for k in range(0, len(good), 5)],
        "at": {f"{lon:.2f}": round(float(dh[np.abs(lons - lon).argmin()]), 2) for lon in CHECK_LONS},
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"note": "POST-HOC, exploratory; not part of any frozen test (scripts/posthoc_swamp_fringes.py)",
           "view": VIEW, "band": BAND, "bunker": BUNKER, "pairs": []}
    for name, dates, role, key in PAIRS:
        path = next(FOLDER.glob(f"NISAR_L2_PR_{key}*.h5"))
        with h5py.File(path, "r") as h:
            epsg = int(h[GUNW_WRP]["projection"][()]) if "projection" in h[GUNW_WRP] else 32616
            direction = h[IDENT]["orbitPassDirection"][()].decode()
        t = Transformer.from_crs(4326, epsg, always_xy=True)
        tb = Transformer.from_crs(epsg, 4326, always_xy=True)
        view = read_gunw_box(path, utm_box(t, VIEW), which="wrapped")
        w, h = picture(view, name)
        # where the band and the gauge fall in the picture, as fractions of its width and height
        x0, x1, y1, y0 = view.xs[0], view.xs[-1], view.ys[0], view.ys[-1]
        frac = lambda lon, lat: [round((t.transform(lon, lat)[0] - x0) / (x1 - x0), 4), round((y1 - t.transform(lon, lat)[1]) / (y1 - y0), 4)]
        p = profile(path, t, tb)
        out["pairs"].append({"name": name, "dates": dates, "role": role, "direction": direction.lower(), "track": key.split("_")[2] + key.split("_")[3],
                             "image": f"data/figures/fringes_{name}.jpg", "image_px": [w, h],
                             "band_frac": frac(BAND[0], BAND[3]) + frac(BAND[2], BAND[1]), "bunker_frac": frac(*BUNKER), **p})
        print(f"{name:8} {dates:16} {direction:10} incidence {p['incidence_deg']} deg, {100 * p['m_per_cycle']:.1f} cm per cycle, "
              f"swamp coherence {p['swamp_coherence']}, coherent columns {p['coherent_columns']:.0%}, "
              + ", ".join(f"{k}: {v:+.2f} m" for k, v in p["at"].items()))
    (OUT / "fringes.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8")
    print("wrote", OUT / "fringes.json")


if __name__ == "__main__":
    main()
