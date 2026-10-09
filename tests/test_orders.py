"""Tests des ordres limites du noyau dividende (payout + value trap)."""
from src.domaine.models import Quote, Snapshot
from src.strategie.orders import build_limit_orders


def _fake_api(stocks):
    class FakeAPI:
        def __init__(self):
            self.snap = Snapshot(stocks=stocks)

        def market_snapshot(self):
            return self.snap

    return FakeAPI()


def test_build_limit_orders_acheter_vs_limite(monkeypatch):
    stocks = [
        Quote(code="SNTS", name="Sonatel", last=32000, is_index=False),  # entry 35745 -> ACHETER
        Quote(code="CHER", name="Cher", last=12000, is_index=False),  # entry 9040 -> LIMITE
    ]
    monkeypatch.setattr("src.strategie.orders.get_dps", lambda code: {"SNTS": 1977, "CHER": 500}.get(code))
    monkeypatch.setattr("src.strategie.orders.get_per_brvm", lambda code: None)
    orders = build_limit_orders(_fake_api(stocks), ["SNTS", "CHER"])
    by_code = {o["code"]: o for o in orders}

    assert by_code["SNTS"]["action"] == "ACHETER"
    assert abs(by_code["SNTS"]["entry_price"] - 35745.4) < 1.0
    assert by_code["CHER"]["action"] == "LIMITE"

    # ACHETER d'abord
    assert orders[0]["code"] == "SNTS"


def test_build_limit_orders_net_yield_reported(monkeypatch):
    stocks = [Quote(code="SNTS", name="Sonatel", last=32000, is_index=False)]
    monkeypatch.setattr("src.strategie.orders.get_dps", lambda code: 1977)
    monkeypatch.setattr("src.strategie.orders.get_per_brvm", lambda code: None)
    orders = build_limit_orders(_fake_api(stocks), ["SNTS"])
    # brut 6,18 % -> net 4,64 %
    assert abs(orders[0]["net_yield"] - 4.64) < 0.05


def test_build_limit_orders_missing_dps(monkeypatch):
    stocks = [Quote(code="PALC", name="PalmCI", last=8980, is_index=False)]
    monkeypatch.setattr("src.strategie.orders.get_dps", lambda code: None)
    orders = build_limit_orders(_fake_api(stocks), ["PALC"])
    assert orders[0]["error"] == "dividende indisponible"


def test_build_limit_orders_unknown_code(monkeypatch):
    stocks = [Quote(code="SNTS", name="Sonatel", last=32000, is_index=False)]
    monkeypatch.setattr("src.strategie.orders.get_dps", lambda code: 1977)
    orders = build_limit_orders(_fake_api(stocks), ["XXXX"])
    assert orders[0]["error"] == "introuvable ou sans cotation"


def test_build_limit_orders_value_trap(monkeypatch):
    stocks = [Quote(code="SOGC", name="SOGB", last=7315, is_index=False)]
    monkeypatch.setattr("src.strategie.orders.get_dps", lambda code: 570)
    monkeypatch.setattr("src.strategie.orders.get_per_brvm", lambda code: 13.49)  # payout ~105 %
    orders = build_limit_orders(_fake_api(stocks), ["SOGC"])
    assert orders[0]["action"] == "⚠️ VALUE TRAP"
    assert orders[0]["payout"] == 105
    assert "NON COUVERT" in orders[0]["sustainability"]


def test_build_limit_orders_payout_sain(monkeypatch):
    stocks = [Quote(code="SNTS", name="Sonatel", last=32000, is_index=False)]
    monkeypatch.setattr("src.strategie.orders.get_dps", lambda code: 1977)
    monkeypatch.setattr("src.strategie.orders.get_per_brvm", lambda code: 7.74)  # payout ~48 %
    orders = build_limit_orders(_fake_api(stocks), ["SNTS"])
    assert orders[0]["payout"] == 48
    assert "sain" in orders[0]["sustainability"]
