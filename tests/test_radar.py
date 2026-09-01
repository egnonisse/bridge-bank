"""Tests du radar de veille « sortie de fond » (détection, zéro trading)."""
from datetime import datetime, timedelta

from src.models import HistoryBar
from src.radar import ath_status, scan


def _bars(closes: list[float], start: str = "2020-01-01") -> list[HistoryBar]:
    d = datetime.strptime(start, "%Y-%m-%d")
    return [
        HistoryBar(date=d + timedelta(days=i), open=c, high=c, low=c,
                   close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


def test_ath_status():
    closes = [200.0] * 50 + [10.0] * 200 + [25.0] * 100
    ath, pct = ath_status(closes)
    assert ath == 200.0
    assert abs(pct - (-87.5)) < 0.01  # 25/200 - 1


def test_scan_detects_sortie_de_fond():
    # ATH 200 -> fond 10 -> rebond jusqu'à 25 sur les 120 dernières barres
    rise = [10 + 15 * i / 119 for i in range(120)]
    series = [200.0] * 40 + [10.0] * 160 + rise
    bars = _bars(series)
    hist = {"TEST1": bars}

    # titre tranquille : rien ne bouge
    flat = [50.0 + (0.1 if i % 2 else -0.1) for i in range(300)]
    hist["FLAT1"] = _bars(flat)

    hits = scan(hist)
    codes = [h["code"] for h in hits]
    assert "TEST1" in codes
    assert "FLAT1" not in codes

    hit = next(h for h in hits if h["code"] == "TEST1")
    assert hit["level"] == 1
    assert hit["r60"] > 15 and hit["r120"] > 30
    assert hit["pct_ath"] <= -80


def test_scan_level2_accumulation():
    # ATH 200 -> fond 55 -> rebond à 80 (soit -60 % de l'ATH, entre -50 et -80)
    rise = [55 + 25 * i / 119 for i in range(120)]
    series = [200.0] * 40 + [55.0] * 160 + rise
    hist = {"TEST2": _bars(series)}
    hits = scan(hist)
    hit = next(h for h in hits if h["code"] == "TEST2")
    assert hit["level"] == 2


def test_scan_ignores_short_series():
    hist = {"SHORT": _bars([10.0] * 100)}
    assert scan(hist) == []
