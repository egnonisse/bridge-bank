"""Tests de non-régression de l'audit (phase 4) — cibles des corrections (phases 9-11).

Ces tests DÉCRIVENT LE COMPORTEMENT CIBLE des findings confirmés pendant la phase 3
(voir `audit/registre_desaccords.md` et `audit/matrice_tests_phase4.md`).

Convention : tant que le bug est actif, le test est marqué `xfail` (échec attendu,
non bloquant). Quand la correction sera appliquée, un test passera en **XPASS** —
c'est le signal pour retirer le marqueur `xfail` et geler la correction.
"""
import re
from datetime import datetime

import pytest

from src.domaine.models import Quote, Snapshot


# ------------------------------------------------- B1-03 : DRIP net d'IRVM
@pytest.mark.xfail(
    reason="B1-03 (P2) — record_dividend comptabilise le BRUT ; "
           "correction : cash = dps × (1−IRVM) × quantité",
    strict=False,
)
def test_drip_comptabilise_le_net_apres_irvm():
    from src.portfolio import DividendPosition, record_dividend

    pos = DividendPosition(
        code="SNTS", name="Sonatel", entry_price=32000.0, quantity=3,
        dps=1740.0, per_open=7.0, opened_at=datetime.now().isoformat(),
    )
    cash, _shares, _residual = record_dividend(pos, 1000.0)
    attendu = 1740.0 * (1 - 0.12) * 3  # 4 593,60 F nets (IRVM retenue à la source)
    assert cash == pytest.approx(attendu, abs=0.01)


# -------------------------------------------- B1-04 : portefeuille corrompu
@pytest.mark.xfail(
    reason="B1-04 (P2) — load_portfolio retourne [] en silence si le fichier est illisible, "
           "puis le cron écrase ; correction : distinguer absent/illisible, ne jamais écraser",
    strict=False,
)
def test_portfolio_corrompu_ne_redevient_pas_vide(monkeypatch, tmp_path):
    from src import portfolio as pf

    bad = tmp_path / "portfolio.json"
    bad.write_text("{ceci n'est pas du json", encoding="utf-8")
    monkeypatch.setattr(pf, "PORTFOLIO_FILE", bad)
    with pytest.raises(Exception):
        pf.load_portfolio()  # un fichier illisible doit être BRUYANT, pas « vide »


# ------------------------------------------ B1-02 : format FR dans les fiches
@pytest.mark.xfail(
    reason="B1-02 (P2) — les fiches spé (et messages live) formatent les francs avec une "
           "virgule de milliers ; correction : format_fr.fcfa()",
    strict=False,
)
def test_fiche_spec_sans_virgule_de_milliers():
    from src.strategie.spec_fiche import build_fiche

    closes = [10000.0] * 300 + [15000.0]  # cassure, montants à 5 chiffres
    f = build_fiche("TEST", "Test", closes)
    msg = f.message()
    assert not re.search(r"\d,\d{3}", msg), "montant à virgule anglaise dans la fiche"


# ------------------------------------- B2-11 : nettoyeur symétrique (bas)
@pytest.mark.xfail(
    reason="B2-11 (P3) — reperer_aberrantes ne détecte que les outliers HAUTS ; "
           "correction : test symétrique (c/med < 1/seuil, comme cache_integrity)",
    strict=False,
)
def test_nettoyeur_detecte_les_artefacts_bas(make_bars):
    from src.collecte.nettoyage_aberrantes import reperer_aberrantes

    closes = [100.0] * 20 + [10.0] + [100.0] * 20  # artefact vers le BAS (0,1×)
    idx = reperer_aberrantes(make_bars(closes))
    assert 20 in idx


# -------------------------------------- B1-07 : cooldown watchlist (clé fixe)
@pytest.mark.xfail(
    reason="B1-07 (P2) — la clé de cooldown contient le prix → re-notification à chaque "
           "tick ; correction : clé sans le prix (code:type:seuil)",
    strict=False,
)
def test_cooldown_watchlist_ne_repete_pas(monkeypatch, tmp_path):
    from src import alerts as al

    class FakeApi:
        def __init__(self, price: float):
            self.price = price

        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code="X", name="X", last=self.price, is_index=False)])

    monkeypatch.setattr(al, "STATE_FILE", tmp_path / "alerts_state.json")
    engine = al.AlertEngine(
        api=FakeApi(105.0), notifier=None,
        watchlist={"X": {"max": 100}}, cooldown_minutes=30, session_only=False,
    )
    first = engine.check_once()
    assert len(first) == 1
    engine.api = FakeApi(110.0)  # même seuil franchi, prix différent
    second = engine.check_once()
    assert second == [], "le cooldown de 30 min doit rendre muet, quel que soit le prix"


# --------------------------------------- B0-01 : date de stop structurée
@pytest.mark.xfail(
    reason="B0-01 (P1) — close_reason ne contient aucune date ; le cooldown stop-out de la "
           "veille retombe sur la date d'ouverture ; correction : horodater le stop",
    strict=False,
)
def test_close_reason_porte_la_date_du_stop():
    from src.strategie.speculation import SpecPosition, check_position

    pos = SpecPosition(code="X", name="X", entry_price=10000.0, quantity=1)
    check_position(pos, 8000.0)  # stop −15 % → clôture
    assert pos.closed
    assert re.search(r"\d{4}-\d{2}-\d{2}", pos.close_reason), (
        "la date du stop doit figurer dans close_reason (ou un champ dédié `closed_at`) — "
        "sans elle, le cooldown de la veille est inopérant"
    )
