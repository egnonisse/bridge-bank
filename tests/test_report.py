"""Tests du rapport mensuel de santé du portefeuille."""
import pytest

from src.report import (
    _format,
    _record_snapshot,
    load_state,
    save_state,
    set_cash,
)


def test_set_cash_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr("src.report.STATE_FILE", tmp_path / "state.json")
    set_cash(118261.29)
    assert load_state()["cash"] == 118261.29


def test_record_snapshot_dedup_per_day(monkeypatch, tmp_path):
    monkeypatch.setattr("src.report.STATE_FILE", tmp_path / "state.json")
    state = load_state()
    _record_snapshot(state, 1000.0, 800.0, 0.0, 0.0, 200.0)
    _record_snapshot(state, 1050.0, 830.0, 0.0, 0.0, 220.0)  # même jour → remplace
    assert len(state["history"]) == 1
    assert state["history"][0]["total"] == 1050.0


def test_save_load_state_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr("src.report.STATE_FILE", tmp_path / "state.json")
    state = {"cash": 5000.0, "obligations": [{"name": "EOS.O15", "amount": 30000.0}], "history": []}
    save_state(state)
    loaded = load_state()
    assert loaded["cash"] == 5000.0
    assert loaded["obligations"][0]["name"] == "EOS.O15"


def test_format_reports_concentration_warning():
    data = {
        "state": {"history": []},
        "total": 675261.0,
        "stocks": 557000.0,
        "spec": 0.0,
        "bonds": 0.0,
        "cash": 118261.0,
        "pnl": -5658.0,
        "div_earned": 0.0,
        "pos_rows": [
            {
                "code": "SNTS", "name": "SONATEL SN", "qty": 9,
                "entry": 32436.0, "last": 31900.0, "pnl": -4820.0,
                "ret_pct": -1.7, "net_cost": 4.56, "net_now": 4.65,
                "payout": 48, "sustain": "✅ sain", "value": 287100.0,
            }
        ],
        "spec_rows": [],
        "max_name": "SONATEL SN",
        "max_pct": 42.5,
    }
    msg = _format(data)
    assert "SONATEL SN" in msg
    assert "Concentration" in msg
    assert "42.5%" in msg
    assert "1er rapport" in msg


def test_format_evolution_uses_previous_snapshot():
    data = {
        "state": {"history": [{"date": "2026-08-18", "total": 650000.0}]},
        "total": 675261.0,
        "stocks": 557000.0, "spec": 0.0, "bonds": 0.0, "cash": 118261.0,
        "pnl": -5658.0, "div_earned": 0.0,
        "pos_rows": [], "spec_rows": [],
        "max_name": "", "max_pct": 0.0,
    }
    msg = _format(data)
    assert "vs 2026-08-18" in msg
