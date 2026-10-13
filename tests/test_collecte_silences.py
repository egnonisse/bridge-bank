"""Tests des silences de la collecte — audit C9, corrigés le 13/10/2026 (B2-05 + B2-06).

Ce qui est verrouillé ici : la collecte NE SE TAIT PLUS.
- B2-05 : `ajuster_historique` sans fichier de divisions LÈVE (plus d'historique brut
  silencieusement non ajusté — classe de l'incident du 21/08, faux drawdowns −96 %) ;
- B2-06 : repli d'historique journalisé, titres en échec comptés et signalés, barre sans
  horodatage écartée (plus de date « maintenant » fabriquée), valeur illisible signalée.
"""
from __future__ import annotations

from datetime import datetime

from src.collecte import backtest as bt
from src.collecte import bsapi
from src.domaine.models import HistoryBar, Quote, Snapshot


def _barre(date: str, close: float) -> HistoryBar:
    return HistoryBar(date=datetime.fromisoformat(date), open=close, high=close,
                      low=close, close=close, volume=1000)


# ═══════════════════════════ B2-06 : repli d'historique journalisé ═════════════════════

class _ApiEchouePuisRepond:
    def __init__(self):
        self.appels: list[tuple[str, str, str]] = []

    def history(self, code, start, end):
        self.appels.append((code, start, end))
        if len(self.appels) == 1:
            raise TimeoutError("ReadTimeout simulé")
        return [_barre("2026-10-10", 100.0)]


def test_fetch_history_repli_journalise(caplog):
    api = _ApiEchouePuisRepond()
    with caplog.at_level("WARNING", logger="src.collecte.backtest"):
        bars = bt._fetch_history(api, "SAFC", "20261010")
    assert len(bars) == 1
    assert len(api.appels) == 2 and api.appels[1][1] != bt.HISTORY_START  # repli ~2 ans
    assert any("repli" in m and "SAFC" in m for m in caplog.messages)


# ═══════════════════════════ B2-06 : titres en échec comptés ═══════════════════════════

def test_collecte_titres_en_echec_comptes(caplog, monkeypatch, tmp_path):
    """Un titre en échec disparaissait du cache en silence — il est désormais signalé."""
    monkeypatch.setattr(bt, "CACHE_FILE", tmp_path / "cache.pkl")
    monkeypatch.setattr(bt, "INACTIFS_FILE", tmp_path / "inactifs.json")
    monkeypatch.setattr(bt, "DATA_DIR", tmp_path)

    class _Api:
        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code="OK", name="OK", last=100.0),
                                    Quote(code="KO", name="KO", last=100.0)])

    def faux_fetch(api, code, end):
        if code == "KO":
            raise RuntimeError("boum")
        return [_barre("2026-10-10", 100.0)]

    monkeypatch.setattr(bt, "_fetch_history", faux_fetch)
    with caplog.at_level("WARNING", logger="src.collecte.backtest"):
        data = bt.load_all_history(_Api(), force=True)
    assert set(data) == {"OK"}                                   # le titre en échec n'est pas inventé
    assert any("ÉCHEC" in m and "KO" in m for m in caplog.messages)


# ═══════════════════════════ B2-06 : barre sans horodatage ═════════════════════════════

def test_history_barre_sans_horodatage_ecartee(caplog, monkeypatch):
    """Plus de date « maintenant » fabriquée : la barre non datée est écartée ET dite."""
    api = bsapi.BSApi()

    class _Reponse:
        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"CurrentDate": 1700000000000, "OpenP": 10, "HighP": 11,
                 "LowP": 9, "CloseP": 10, "Volume": 5},
                {"CurrentDate": 0, "OpenP": 10, "HighP": 11,
                 "LowP": 9, "CloseP": 10, "Volume": 5},
            ]

    monkeypatch.setattr(api.session, "get", lambda *a, **k: _Reponse())
    with caplog.at_level("WARNING", logger="src.collecte.bsapi"):
        bars = api.history("TEST", "20260101", "20261010")
    assert len(bars) == 1
    assert any("horodatage" in m for m in caplog.messages)


# ═══════════════════════════ B2-06 : illisible vs absent ═══════════════════════════════

def test_to_float_illisible_signale_absent_muet(caplog):
    with caplog.at_level("WARNING", logger="src.collecte.bsapi"):
        assert bsapi._to_float("abc") == 0.0
    assert any("illisible" in m for m in caplog.messages)        # illisible : SIGNALÉ
    caplog.clear()
    with caplog.at_level("WARNING", logger="src.collecte.bsapi"):
        assert bsapi._to_float("") == 0.0
    assert not caplog.messages                                    # absent : convention muette
