"""Tests de la règle IPS : les poches sont étanches (blocage des doublons)."""
from types import SimpleNamespace

import pytest

from src import portfolio as pm
from src import speculation as sp
from src.models import Quote, Snapshot


def _api(code: str, last: float):
    class FakeAPI:
        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code=code, name=code, last=last, is_index=False)])

    return FakeAPI()


def test_spec_open_blocked_when_in_noyau(monkeypatch):
    monkeypatch.setattr("src.portfolio.load_portfolio",
                        lambda: [SimpleNamespace(code="SNTS", closed=False)])
    with pytest.raises(ValueError, match="poches étanches"):
        sp.open_position(_api("SNTS", 32000), "SNTS", 100000)


def test_spec_open_allowed_when_noyau_closed(monkeypatch):
    monkeypatch.setattr("src.portfolio.load_portfolio",
                        lambda: [SimpleNamespace(code="SNTS", closed=True)])
    pos = sp.open_position(_api("SNTS", 32000), "SNTS", 100000)
    assert pos.code == "SNTS"
    assert pos.quantity == 3


def test_noyau_open_blocked_when_in_spec(monkeypatch):
    monkeypatch.setattr("src.speculation.load_positions",
                        lambda: [SimpleNamespace(code="NSBC", closed=False)])
    with pytest.raises(ValueError, match="poches étanches"):
        pm.open_dividend_position(_api("NSBC", 10000), "NSBC", 100000, dps=500, per_open=10)


def test_noyau_open_allowed_when_spec_closed(monkeypatch):
    """Scénario légitime : ligne spéculative déjà vendue → rachat noyau autorisé."""
    monkeypatch.setattr("src.speculation.load_positions",
                        lambda: [SimpleNamespace(code="NSBC", closed=True)])
    pos = pm.open_dividend_position(_api("NSBC", 10000), "NSBC", 100000, dps=500, per_open=10)
    assert pos.code == "NSBC"
    assert pos.quantity == 10
