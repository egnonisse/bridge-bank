"""Tests de la détection de nouvelles opportunités value+dividende."""
from src.analyse import screener


class _FakeAPI:
    pass


def test_detect_new_value_opportunities(monkeypatch, tmp_path):
    monkeypatch.setattr(screener, "VALUE_STATE_FILE", tmp_path / "value_state.json")

    # run 1 : deux titres value → tous « nouveaux » (baseline)
    monkeypatch.setattr(
        screener,
        "screen_value_dividend",
        lambda api, force=False: [
            {"code": "SGBC", "name": "SGB", "last": 39000, "per": 12.0, "dps": 2606, "yield": 6.68, "net_yield": 5.08},
            {"code": "SNTS", "name": "Sonatel", "last": 32000, "per": 7.74, "dps": 1977, "yield": 6.18, "net_yield": 4.64},
        ],
    )
    new1 = screener.detect_new_value_opportunities(_FakeAPI())
    assert len(new1) == 2

    # run 2 : SGBC reste, BOAS entre (SNTS sort) → seul BOAS est nouveau
    monkeypatch.setattr(
        screener,
        "screen_value_dividend",
        lambda api, force=False: [
            {"code": "SGBC", "name": "SGB", "last": 39000, "per": 12.0, "dps": 2606, "yield": 6.68, "net_yield": 5.08},
            {"code": "BOAS", "name": "BOA SN", "last": 2500, "per": 8.0, "dps": 180, "yield": 7.2, "net_yield": 5.5},
        ],
    )
    new2 = screener.detect_new_value_opportunities(_FakeAPI())
    assert len(new2) == 1
    assert new2[0]["code"] == "BOAS"


def test_load_value_state_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(screener, "VALUE_STATE_FILE", tmp_path / "absent.json")
    assert screener.load_value_state() == set()
