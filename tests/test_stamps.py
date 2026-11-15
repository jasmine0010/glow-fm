"""Run timestamps are paused by default (src/hidden_floods/stamps.py) and come back with one switch."""

from hidden_floods import stamps


def test_paused_by_default_writes_nothing(monkeypatch):
    monkeypatch.delenv("HIDDEN_FLOODS_TIMESTAMPS", raising=False)
    monkeypatch.setattr(stamps, "RECORD", False)
    assert stamps.stamp("started_utc") == {}
    assert stamps.utc_now() is None
    assert {**stamps.stamp("created_utc"), "sha256": {}} == {"sha256": {}}


def test_switch_and_environment_resume_it(monkeypatch):
    monkeypatch.delenv("HIDDEN_FLOODS_TIMESTAMPS", raising=False)
    monkeypatch.setattr(stamps, "RECORD", True)
    assert set(stamps.stamp("run")) == {"run"}
    monkeypatch.setattr(stamps, "RECORD", False)
    monkeypatch.setenv("HIDDEN_FLOODS_TIMESTAMPS", "1")
    assert stamps.stamp("run")["run"].endswith("+00:00")
