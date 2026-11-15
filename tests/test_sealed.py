"""The sealed test's fixed rules (src/hidden_floods/sealed.py) and its guards (scripts/score_sealed.py)."""

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hidden_floods import sealed
from hidden_floods.config import REPO_ROOT

T0 = datetime(2026, 10, 27, 4, 10, tzinfo=UTC)


def test_next_passes_repeat_every_twelve_days_within_the_horizon():
    now = datetime(2026, 11, 14, 22, 0, tzinfo=UTC)
    got = sealed.predicted_times(T0, now)
    assert got == [T0 + timedelta(days=24), T0 + timedelta(days=36)]
    assert all(now < t <= now + sealed.HORIZON for t in got)
    # a pass exactly at the sealing time has happened, so it isn't predicted
    assert sealed.predicted_times(T0, T0 + timedelta(days=12))[0] == T0 + timedelta(days=24)
    # a long-quiet track still lands on its own 12-day grid
    assert all((t - T0) % sealed.REPEAT == timedelta(0) for t in sealed.predicted_times(T0, T0 + timedelta(days=100)))


def test_trust_light_and_judgeable_follow_the_overbank_rules():
    assert sealed.rainy(4.9, 24.9) is False and sealed.rainy(5.0, 0.0) is True and sealed.rainy(0.0, 25.0) is True
    assert sealed.rainy(None, 3.0) is None
    assert sealed.light(True, False) == "green" and sealed.light(True, True) == "red" and sealed.light(False, False) == "red"
    assert sealed.light(True, None) is None
    assert sealed.judgeable(500.0, 0.6) and not sealed.judgeable(499.9, 0.9) and not sealed.judgeable(800.0, 0.59) and not sealed.judgeable(800.0, None)
    assert sealed.hit("green", 0.60) and not sealed.hit("green", 0.59) and sealed.hit("red", 0.2) and not sealed.hit("red", 0.7)


def test_reading_uses_the_fixed_bars_and_trivial_rules():
    few = [{"light": "green", "csi": 0.7}] * 4
    assert sealed.reading(few)["verdict"] == "too few"
    good = [{"light": "green", "csi": 0.7}] * 3 + [{"light": "red", "csi": 0.3}] * 2
    r = sealed.reading(good)
    assert r["hits"] == 5 and r["verdict"] == "held up" and r["always_green_hits"] == 3 and r["always_red_hits"] == 2
    # all green and all scoring well: 100% hits, but no better than "always green", so not "held up"
    assert sealed.reading([{"light": "green", "csi": 0.7}] * 5)["verdict"] == "mixed"
    bad = [{"light": "green", "csi": 0.2}] * 3 + [{"light": "red", "csi": 0.8}] * 2
    assert sealed.reading(bad)["verdict"] == "did not hold up"


def test_overbank_record_is_three_of_four():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("score_sealed", REPO_ROOT / "scripts" / "score_sealed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ob = mod.overbank_passes()
    r = sealed.reading(ob)
    assert (r["judgeable"], r["hits"], r["verdict"]) == (4, 3, "too few")


def test_scorer_refuses_after_a_sealed_file_changes(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("score_sealed", REPO_ROOT / "scripts" / "score_sealed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = tmp_path / "x.txt"
    f.write_text("sealed")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"list": "x.txt", "sha256": {str(f): sealed.digest(f)}}))
    monkeypatch.setattr(mod, "RECEIPT", receipt)
    monkeypatch.setattr(mod, "REPO_ROOT", Path("/"))
    mod.check_receipt()                      # unchanged: fine
    f.write_text("edited")
    with pytest.raises(SystemExit, match="changed since sealing"):
        mod.check_receipt()


def test_every_sealed_pass_stays_in_the_results():
    site = REPO_ROOT / "app" / "data" / "live" / "sealed.json"
    receipt = REPO_ROOT / "research" / "freeze_receipt_sealed.json"
    if not (site.exists() and receipt.exists()):
        pytest.skip("not scored yet")
    listed = json.loads((REPO_ROOT / json.loads(receipt.read_text())["list"]).read_text())["passes"]
    shown = json.loads(site.read_text())["passes"]
    assert [p["id"] for p in shown] == [p["id"] for p in listed]
