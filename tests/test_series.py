import json

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.frozen_v3 import FROZEN_PAIRS, RECEIPT_V3
from hidden_floods.series import FROZEN_FRAME, SERIES_PAIRS, yellow_series_site


def test_series_keeps_the_protocol_dry_reference_for_each_track():
    pairs = {p.name: p for p in SERIES_PAIRS}
    base = load_site("yellow").pairs[FROZEN_FRAME]
    assert (pairs[FROZEN_FRAME].wet, pairs[FROZEN_FRAME].dry, pairs[FROZEN_FRAME].wet_time) == (base.wet, base.dry, base.wet_time)
    for p in SERIES_PAIRS:
        assert p.wet.startswith(p.name[:4]) and p.dry.startswith(p.name[:4])
        assert p.dry_time < p.wet_time
    assert [p.wet_time for p in SERIES_PAIRS] == sorted(p.wet_time for p in SERIES_PAIRS)


def test_series_site_resolves_every_scene_without_changing_the_frozen_site():
    site = yellow_series_site()
    for p in SERIES_PAIRS:
        assert site.gcov_path(p.wet).name.endswith(".h5") and site.gcov_path(p.dry).name.endswith(".h5")
    assert set(load_site("yellow").pairs) == set(FROZEN_PAIRS["yellow"])
    assert "sites/yellow.toml" in json.loads(RECEIPT_V3.read_text())["sha256"]


def test_saved_series_reproduces_the_frozen_score():
    frames = json.loads((REPO_ROOT / "research" / "v3_yellow_series.json").read_text())
    frozen = json.loads((REPO_ROOT / "research" / "v3_yellow_055D_frozen_metrics.json").read_text())
    assert [f["pair"] for f in frames] == [p.name for p in SERIES_PAIRS]
    only = [f for f in frames if f["frozen"]]
    assert len(only) == 1 and abs(only[0]["csi"] - frozen["primary_v3_mapped_area"]["scores"]["csi"]) < 1e-9
