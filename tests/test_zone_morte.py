"""Tests de la zone morte spéculative : revue à ~J+120, jamais de clôture auto."""
from datetime import datetime, timedelta

from src.domaine.models import HistoryBar, Quote, Snapshot
from src.speculation import (
    ZONE_DEAD_REVIEW_DAYS,
    SpecPosition,
    check_all,
    zone_morte_status,
)


def make_bars(n: int = 200, close: float = 105.0) -> list[HistoryBar]:
    """n barres journalières plates (ni +20 % ni −15 % pour une entrée à 100)."""
    today = datetime.now().replace(hour=12)
    return [
        HistoryBar(
            date=today - timedelta(days=n - 1 - i),
            open=close, high=close, low=close, close=close, volume=1000,
        )
        for i in range(n)
    ]


def make_pos(days_ago: int = 130, entry: float = 100.0) -> SpecPosition:
    return SpecPosition(
        code="XXX", name="Test", entry_price=entry, quantity=30,
        opened_at=(datetime.now() - timedelta(days=days_ago)).isoformat(),
    )


class FakeApi:
    def market_snapshot(self) -> Snapshot:
        return Snapshot(stocks=[Quote(code="XXX", name="Test", last=105.0)])


def test_zone_morte_flat(monkeypatch):
    monkeypatch.setattr("src.speculation.load_all_history", lambda api: {"XXX": make_bars()})
    sessions, dead = zone_morte_status(make_pos(days_ago=130), FakeApi())
    assert dead is True
    assert sessions >= ZONE_DEAD_REVIEW_DAYS


def test_zone_morte_hit_up(monkeypatch):
    bars = make_bars()
    bars[-5].close = 125.0  # +25 % touché → pas zone morte
    monkeypatch.setattr("src.speculation.load_all_history", lambda api: {"XXX": bars})
    _, dead = zone_morte_status(make_pos(), FakeApi())
    assert dead is False


def test_zone_morte_hit_down(monkeypatch):
    bars = make_bars()
    bars[-5].close = 80.0  # −20 % → stop touché → pas zone morte
    monkeypatch.setattr("src.speculation.load_all_history", lambda api: {"XXX": bars})
    _, dead = zone_morte_status(make_pos(), FakeApi())
    assert dead is False


def test_zone_morte_skip_when_palier_sold():
    pos = make_pos()
    pos.sold_1 = True
    assert zone_morte_status(pos, FakeApi()) is None


def test_zone_morte_skip_when_closed():
    pos = make_pos()
    pos.closed = True
    assert zone_morte_status(pos, FakeApi()) is None


def test_check_all_review_once(monkeypatch):
    pos = make_pos(days_ago=130)
    monkeypatch.setattr("src.speculation.load_positions", lambda: [pos])
    monkeypatch.setattr("src.speculation.load_all_history", lambda api: {"XXX": make_bars()})
    monkeypatch.setattr("src.speculation.save_positions", lambda positions: None)

    events = check_all(FakeApi())
    assert any("REVUE" in e for e in events)
    assert pos.review_alerted is True

    events2 = check_all(FakeApi())  # pas de double alerte
    assert not any("REVUE" in e for e in events2)


def test_check_all_no_review_before_threshold(monkeypatch):
    pos = make_pos(days_ago=90)  # ~90 séances < 120
    monkeypatch.setattr("src.speculation.load_positions", lambda: [pos])
    monkeypatch.setattr("src.speculation.load_all_history", lambda api: {"XXX": make_bars()})
    monkeypatch.setattr("src.speculation.save_positions", lambda positions: None)

    events = check_all(FakeApi())
    assert not any("REVUE" in e for e in events)
    assert pos.review_alerted is False
