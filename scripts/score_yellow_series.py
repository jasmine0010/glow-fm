"""Score frozen v3, unchanged, on every usable Yellow River pass. Writes research/v3_yellow_series.json.

Follow-up scores: only Oct 16 is the pre-registered test, and it must match the frozen number exactly.
"""

import json
from dataclasses import asdict

from hidden_floods.config import REPO_ROOT
from hidden_floods.frozen_v3 import RECEIPT_V3, settings_from
from hidden_floods.series import FROZEN_FRAME, SERIES_PAIRS, score_frame, yellow_series_site

rule = settings_from(json.loads(RECEIPT_V3.read_text())).rule
frozen = json.loads((REPO_ROOT / "research" / "v3_yellow_055D_frozen_metrics.json").read_text())
site = yellow_series_site()
frames = []
for pair in SERIES_PAIRS:
    fr = score_frame(site, pair, rule)
    frames.append(asdict(fr))
    if pair.name == FROZEN_FRAME and abs(fr.csi - frozen["primary_v3_mapped_area"]["scores"]["csi"]) > 1e-9:
        raise SystemExit(f"Oct 16 CSI {fr.csi} differs from the frozen result")
    print(f"{fr.pair} {fr.time[:10]} timing {fr.timing} rise {fr.stage_rise_m} thr {fr.threshold_db:.2f} flagged {fr.flagged_ha:,.0f} "
          f"confirmed {fr.confirmed_ha:,.0f} on-dry {fr.flagged_on_dry_ha:,.0f} csi {fr.csi} ci {fr.csi_ci95} "
          f"recall {fr.recall} precision {fr.precision} coverage {fr.coverage}", flush=True)
(REPO_ROOT / "research" / "v3_yellow_series.json").write_text(json.dumps(frames, indent=1, allow_nan=False))
print("SERIES DONE", flush=True)
