"""Truth-based blind-spot audit of Copernicus GFM and OPERA DSWx-S1 across the study floods.

    python scripts/audit_blind_spot.py

Writes outputs/audit/blind_spot.json and prints a summary table.
"""

import json

import numpy as np

from hidden_floods.audit import audit_date, exposure, scene_time, truth_context
from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.pipeline import analysis_grid

EVENTS = {
    "choctawhatchee": ["20261010", "20261022", "20261027"],
    "pearl": ["20260617", "20260622", "20260624", "20260628", "20260705"],
    "tangipahoa": ["20260621", "20260628"],
}


def main():
    out_dir = REPO_ROOT / "outputs" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, dates in EVENTS.items():
        site = load_site(name)
        grid = analysis_grid(site)
        dem = dem_on_grid(site.dem_path, grid)
        for date in dates:

            ctx = truth_context(site, scene_time(site.operational_dir, date), dem=dem, grid=grid)
            res, ctx, gfm = audit_date(site, date, ctx)
            # Exposure: confirmed flooding that GFM did not map (inside its coverage and the supported region).
            region = ctx.supported & gfm.covered & ~ctx.permanent_water
            unmapped = ctx.truth.wet & region & ~gfm.flood
            osm = site.operational_dir / "osm.json"
            if osm.exists():
                res["exposure_unmapped_by_gfm"] = exposure(osm, grid, unmapped)
            rows.append(res)
            g = res["gfm"]
            share = "n/a" if g.get("share_mapped") is None else f"{g['share_mapped']:.1%}"
            print(f"{name:15s} {date}  truth-wet {g['truth_wet_ha']:8,.0f} ha  GFM mapped {share:>6s}  "
                  f"inside GFM exclusion {g.get('share_inside_exclusion_mask', float('nan')):.0%}"
                  + (f"  DSWx-S1 {res['dswx_s1'].get('share_mapped') or 0:.1%}" if "dswx_s1" in res else ""))
    (out_dir / "blind_spot.json").write_text(json.dumps(rows, indent=2, default=lambda o: float(o)
                                                        if isinstance(o, np.floating) else str(o)))


if __name__ == "__main__":
    main()
