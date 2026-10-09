"""Tests du module live (cours temps réel brvm.org + horaires de séance)."""
from datetime import datetime

from src.collecte.live import live_quotes, session_open


def test_session_open_during_hours():
    assert session_open(datetime(2026, 8, 19, 10, 0)) is True   # mercredi 10h
    assert session_open(datetime(2026, 8, 19, 9, 0)) is True    # à l'ouverture
    assert session_open(datetime(2026, 8, 19, 15, 0)) is True   # à la clôture


def test_session_closed_outside_hours():
    assert session_open(datetime(2026, 8, 19, 8, 59)) is False  # avant 09h
    assert session_open(datetime(2026, 8, 19, 15, 1)) is False  # après 15h


def test_session_closed_weekend():
    assert session_open(datetime(2026, 8, 22, 10, 0)) is False  # samedi
    assert session_open(datetime(2026, 8, 23, 10, 0)) is False  # dimanche


def test_live_quotes_parses_prices(monkeypatch):
    class FakeResp:
        text = (
            "<tr><td>SNTS</td><td>SONATEL SN</td><td>34 400</td></tr>"
            "<tr><td>SPHC</td><td>SAPH CI</td><td>9 660</td></tr>"
            "<tr><td>ORAC</td><td>ORANGE CI</td><td>20 000</td></tr>"
        )

        def raise_for_status(self):
            pass

    monkeypatch.setattr("src.collecte.live.requests.get", lambda *a, **k: FakeResp())
    quotes = live_quotes(["SNTS", "SPHC", "ORAC", "XXXX"])
    assert quotes["SNTS"] == 34400.0
    assert quotes["SPHC"] == 9660.0
    assert quotes["ORAC"] == 20000.0
    assert "XXXX" not in quotes
