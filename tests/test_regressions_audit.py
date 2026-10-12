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
# CORRIGÉ le 12/10/2026 (lot 1) — test gelé : fichier illisible ⇒ bruyant, jamais « vide ».
def test_portfolio_corrompu_ne_redevient_pas_vide(monkeypatch, tmp_path):
    from src import portfolio as pf

    bad = tmp_path / "portfolio.json"
    bad.write_text("{ceci n'est pas du json", encoding="utf-8")
    monkeypatch.setattr(pf, "PORTFOLIO_FILE", bad)
    with pytest.raises(pf.PortfolioInvalide):
        pf.load_portfolio()  # un fichier illisible doit être BRUYANT, pas « vide »


def test_portfolio_ecriture_atomique(monkeypatch, tmp_path):
    """B1-04 (CORRIGÉ 12/10) — écriture via temporaire puis `replace` (jamais tronqué)."""
    from src import portfolio as pf

    cible = tmp_path / "portfolio.json"
    monkeypatch.setattr(pf, "PORTFOLIO_FILE", cible)
    monkeypatch.setattr(pf, "DATA_DIR", tmp_path)
    pos = pf.DividendPosition(code="X", name="X", entry_price=1000.0, quantity=1,
                              dps=10.0, per_open=5.0, opened_at="2026-01-01T00:00:00")
    pf.save_portfolio([pos])
    assert cible.exists()
    assert not (tmp_path / "portfolio.json.tmp").exists(), "le temporaire doit avoir été remplacé"


# ------------------------------------------ B1-02 : format FR dans les fiches
# CORRIGÉ le 12/10/2026 (lot 1) — test gelé.
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
# CORRIGÉ le 12/10/2026 (lot 1) — test gelé : le stop est horodaté (champ closed_at).
def test_close_reason_porte_la_date_du_stop():
    from src.strategie.speculation import SpecPosition, check_position

    pos = SpecPosition(code="X", name="X", entry_price=10000.0, quantity=1)
    check_position(pos, 8000.0)  # stop −15 % → clôture
    assert pos.closed
    assert re.search(r"\d{4}-\d{2}-\d{2}", pos.close_reason), (
        "la date du stop doit figurer dans close_reason — sans elle, le cooldown "
        "« 30 j après stop-out » de la veille est inopérant"
    )
    assert pos.closed_at[:10] == datetime.now().strftime("%Y-%m-%d"), (
        "closed_at doit être horodaté au moment de la clôture"
    )


# ───────────────────── B1-01 : la sortie ne se perd plus (CORRIGÉ 12/10) ─────

def _pos_snts():
    from src.portfolio import DividendPosition

    return DividendPosition(code="SNTS", name="Sonatel", entry_price=32000.0, quantity=3,
                            dps=1977.0, per_open=7.0, opened_at="2026-01-01T00:00:00")


def _cmd_portf_check(monkeypatch, pos, send_ok: bool):
    """Exécute cmd_portf check : sortie déclenchée (prix > prix de sortie), Telegram simulé.
    Retourne (position, notifier, saves)."""
    import argparse

    import src.collecte.fundamentals as fund_mod
    import src.main as main_mod
    import src.portfolio as pf

    class FakeApi:
        def market_snapshot(self):
            return Snapshot(stocks=[Quote(code="SNTS", name="Sonatel",
                                          last=pos.exit_price + 100, is_index=False)])

    class FakeNotifier:
        enabled = True

        def __init__(self):
            self.messages = []

        def send(self, msg):
            self.messages.append(msg)
            return send_ok

    notif = FakeNotifier()
    saves = []
    monkeypatch.setattr(main_mod, "BSApi", FakeApi)
    monkeypatch.setattr(pf, "load_portfolio", lambda: [pos])
    monkeypatch.setattr(pf, "save_portfolio", lambda positions: saves.append(True))
    monkeypatch.setattr(pf, "load_alert_state", lambda: {})
    monkeypatch.setattr(pf, "save_alert_state", lambda s: None)
    monkeypatch.setattr(fund_mod, "get_fundamentals", lambda code: {"dps": 1977.0, "per": 8.0})
    monkeypatch.setattr(main_mod, "get_notifier", lambda cfg: notif)
    monkeypatch.setattr(main_mod, "load_config", lambda: {})

    args = argparse.Namespace(action="check", code=None, amount=100000,
                              dps=None, per=None, _actions=None)
    main_mod.cmd_portf(args)
    return pos, notif, saves


def test_sortie_non_delivree_annule_la_cloture(monkeypatch):
    """B1-01 (CORRIGÉ) — envoi Telegram en échec ⇒ la clôture est ANNULÉE : la position
    redevient surveillée et la sortie sera re-tentée au prochain run (jamais perdue)."""
    pos = _pos_snts()
    pos, notif, saves = _cmd_portf_check(monkeypatch, pos, send_ok=False)
    assert notif.messages, "la sortie devait être tentée via Telegram"
    assert pos.closed is False, "position clôturée alors que l'alerte est perdue !"
    assert saves, "sauvegarde attendue (sans la fausse clôture)"


def test_sortie_delivree_est_persistee(monkeypatch):
    """B1-01 (CORRIGÉ) — envoi réussi ⇒ la clôture est conservée."""
    pos = _pos_snts()
    pos, notif, saves = _cmd_portf_check(monkeypatch, pos, send_ok=True)
    assert notif.messages
    assert pos.closed is True
