"""B2-10 — la chaîne brut → propre : régénération, garde-fous, usage par la validation.

Le cache PROPRE (`history_clean.pkl`) est la seule base des décisions ; la collecte écrit
un BRUT transitoire que la préparation transforme (divisions ajustées + nettoyage).
Ces tests couvrent :
- la préparation écrit le clean + son empreinte, sans brut → erreur claire ;
- `charger_historique_propre` régénère quand le brut a bougé, lit sinon ;
- la validation (`run_backtest`) charge le PROPRE, jamais le brut.
"""
from __future__ import annotations

import os
import pickle
import time
from datetime import datetime, timedelta

import pytest

from src.collecte import preparation
from src.domaine.models import HistoryBar


def _bars(n=90, base=1000.0):
    d0 = datetime(2020, 1, 1)
    return [HistoryBar(date=d0 + timedelta(days=i), open=base + i, high=base + i,
                       low=base + i, close=base + i, volume=1000)
            for i in range(n)]


@pytest.fixture
def caches(tmp_path, monkeypatch):
    """Redirige les trois fichiers de la préparation vers tmp_path."""
    brut = tmp_path / "history_cache.pkl"
    clean = tmp_path / "history_clean.pkl"
    monkeypatch.setattr(preparation, "HISTORY_BRUT", brut)
    monkeypatch.setattr(preparation, "HISTORY_CACHE", clean)
    monkeypatch.setattr(preparation, "RAPPORT_FILE", tmp_path / "ajustement_rapport.json")
    return brut, clean


def test_preparer_ecrit_le_cache_propre_et_son_empreinte(caches):
    brut, clean = caches
    with open(brut, "wb") as fh:
        pickle.dump({"TST": _bars()}, fh)

    stats = preparation.preparer_historique_propre()

    assert clean.exists()
    assert clean.with_name(clean.name + ".sha256").exists()
    assert stats["titres"] == 1
    assert (preparation.RAPPORT_FILE).exists()


def test_preparer_sans_brut_leve_une_erreur_claire(caches):
    with pytest.raises(FileNotFoundError, match="history_cache.pkl"):
        preparation.preparer_historique_propre()


def test_charger_regenere_si_le_brut_est_plus_recent(caches):
    brut, clean = caches
    with open(brut, "wb") as fh:
        pickle.dump({"TST": _bars(n=95)}, fh)
    with open(clean, "wb") as fh:
        pickle.dump({"TST": _bars(n=50)}, fh)
    vieux = 1_000_000  # le clean est (très) plus vieux que le brut
    os.utime(clean, (vieux, vieux))

    data = preparation.charger_historique_propre()

    assert len(data["TST"]) == 95  # régénéré depuis le brut, pas servi périmé


def test_charger_lit_le_clean_sans_regenerer_si_a_jour(caches):
    brut, clean = caches
    with open(brut, "wb") as fh:
        pickle.dump({"TST": _bars(n=95)}, fh)
    with open(clean, "wb") as fh:
        pickle.dump({"TST": _bars(n=60)}, fh)
    futur = time.time() + 100  # le clean est plus récent que le brut
    os.utime(clean, (futur, futur))

    data = preparation.charger_historique_propre()

    assert len(data["TST"]) == 60  # tel quel — pas de régénération inutile


def test_ni_brut_ni_clean_leve_une_erreur_claire(caches):
    with pytest.raises(FileNotFoundError, match="history_cache.pkl"):
        preparation.charger_historique_propre()


def test_la_validation_lit_le_propre_pas_le_brut(monkeypatch):
    """run_backtest charge les données via charger_historique_propre (B2-10)."""
    from src.collecte import backtest

    appels = {"propre": 0, "brut": 0}
    monkeypatch.setattr(backtest, "charger_historique_propre",
                        lambda *a, **k: appels.__setitem__("propre", appels["propre"] + 1) or {})
    monkeypatch.setattr(backtest, "load_all_history",
                        lambda *a, **k: appels.__setitem__("brut", appels["brut"] + 1) or {})

    res = backtest.run_backtest(api=None, top=10, horizon=20)

    assert appels["propre"] == 1
    assert appels["brut"] == 0  # le brut n'est PAS lu par la validation
    assert res.n_titles == 0
