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


def _decline(frm: float, to: float, n: int) -> list[float]:
    """Descente GRADUELLE (pas de cassure > 2,5× d'une séance à l'autre)."""
    return [frm * (to / frm) ** (i / max(1, n - 1)) for i in range(n)]


def test_ath_status():
    # ATH 200, descente GRADUELLE au fond 10, remontée graduelle à 25
    # (aucune cassure : l'ATH comparable reste 200)
    closes = [200.0] * 50 + _decline(200, 10, 60) + [10.0] * 60 + \
        [10 + 15 * i / 39 for i in range(40)]
    ath, pct = ath_status(closes)
    assert ath == 200.0
    assert abs(pct - (-87.5)) < 0.01  # 25/200 - 1


def test_ath_status_ignore_niveaux_pre_division():
    # CIEC-like : 75 000 début 2017 → division x0.05 (niveau permanent ~3 115)
    # → le vrai sommet comparable est 7 000, pas 75 000
    series = [75000.0] * 12 + [58000.0] * 10 + [3115.0] * 200 + [7000.0] * 50
    ath, pct = ath_status(series)
    assert ath == 7000.0
    assert abs(pct - 0.0) < 0.01


def test_scan_detects_sortie_de_fond():
    # ATH 200 (sans division) → descente graduelle au fond 10 → rebond à 25
    series = [200.0] * 40 + _decline(200, 10, 60) + [10.0] * 40 + \
        [10 + 15 * i / 119 for i in range(120)]
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


def test_scan_detecte_eveil_rebond_depuis_le_creux():
    """Niveau ÉVEIL (idée LEO « début de hausse ») : rebond +10 % depuis un creux
    récent, titre encore sous 50 % de son ATH — sans atteindre l'accumulation."""
    # ATH 100, descente à ~40 (pct_ath ≈ −60 %), creux 35 récent (~5 séances),
    # rebond à 38,5 (+10 %) — r60/r120 restent négatifs → éveil, pas accumulation
    # (min_bars=260 : la série doit atteindre 260 barres)
    series = ([100.0] * 110 + _decline(100, 40, 80) + [40.0] * 50
              + _decline(40, 35, 5) + [35.0] * 5
              + [35 * (1 + 0.10 * i / 9) for i in range(10)])
    bars = _bars(series)
    hits = scan({"EVEIL1": bars})
    hit = next((h for h in hits if h["code"] == "EVEIL1"), None)
    assert hit is not None, "l'éveil doit être détecté"
    assert hit["level"] == 2
    assert hit["eveil"] is True
    assert hit["rebond"] >= 10.0
    assert hit["pct_ath"] <= -50


def test_scan_level2_accumulation():
    # ATH 200 → descente graduelle à 55 → rebond à 80 (soit -60 % de l'ATH)
    series = [200.0] * 40 + _decline(200, 55, 60) + [55.0] * 40 + \
        [55 + 25 * i / 119 for i in range(120)]
    hist = {"TEST2": _bars(series)}
    hits = scan(hist)
    hit = next(h for h in hits if h["code"] == "TEST2")
    assert hit["level"] == 2


def test_scan_ignores_short_series():
    hist = {"SHORT": _bars([10.0] * 100)}
    assert scan(hist) == []


def test_filter_new_level1_anti_spam(tmp_path, monkeypatch):
    from src import radar as radar_mod

    monkeypatch.setattr(radar_mod, "ALERT_STATE_FILE", tmp_path / "state.json")
    hits = [
        {"code": "AAA", "level": 1, "date": "2026-09-01"},
        {"code": "BBB", "level": 2, "date": "2026-09-01"},
    ]
    new = radar_mod.filter_new_level1(hits)
    assert [h["code"] for h in new] == ["AAA"]

    # second passage : plus rien de nouveau (anti-spam permanent)
    assert radar_mod.filter_new_level1(hits) == []


def test_monitor_output_permanent_par_cycle():
    from src.radar import monitor_output

    alerted = {"AAA": "2026-01-10", "BBB": "2026-01-10", "CCC": "2026-01-10"}

    # 1. premier tick (aucun historique de présence) : les marqués présents ne ressortent pas
    out, seen = monitor_output(["AAA", "BBB"], alerted, {}, "2026-09-01")
    assert out == []
    assert seen == {"AAA": "2026-09-01", "BBB": "2026-09-01"}

    # 2. tick suivant, mêmes titres présents : silence
    out, seen = monitor_output(["AAA", "BBB"], alerted, seen, "2026-09-02")
    assert out == []

    # 3. titre jamais traité qui apparaît : signalé
    out, seen = monitor_output(["AAA", "DDD"], alerted, seen, "2026-09-03")
    assert out == ["DDD"]

    # 4. vacillement court (absence 4 jours) : PAS re-signalé
    out, seen = monitor_output(["AAA"], alerted, seen, "2026-09-04")
    assert out == []
    out, seen = monitor_output(["AAA", "BBB"], alerted, seen, "2026-09-06")
    assert out == []  # BBB absent du 09-03 au 09-05 : gap 4 j < 5

    # 5. vrai retour après >= 5 jours d'absence : RÉ-SIGNALÉ (veille permanente)
    out, seen = monitor_output(["AAA"], alerted, seen, "2026-09-09")  # BBB ressort
    assert out == []
    for j in range(10, 16):  # ticks quotidiens réels : AAA présent chaque jour
        out, seen = monitor_output(["AAA"], alerted, seen, f"2026-09-{j:02d}")
        assert out == []
    out, seen = monitor_output(["AAA", "BBB"], alerted, seen, "2026-09-16")
    assert out == ["BBB"]  # BBB absent du 09-09 au 09-15 : gap >= 5 ; AAA continu -> silence
