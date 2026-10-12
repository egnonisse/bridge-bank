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


# ------------------------------------------- B1-03 : DRIP net d'IRVM
# CORRIGÉ le 12/10/2026 (lot 2) — test gelé : le cash comptabilisé est le NET (IRVM retenue).
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
# CORRIGÉ le 12/10/2026 (lot 3) — test gelé : le test est désormais symétrique.
def test_nettoyeur_detecte_les_artefacts_bas(make_bars):
    from src.collecte.nettoyage_aberrantes import reperer_aberrantes

    closes = [100.0] * 20 + [10.0] + [100.0] * 20  # artefact vers le BAS (0,1×)
    idx = reperer_aberrantes(make_bars(closes))
    assert 20 in idx


def test_nettoyeur_ne_touche_pas_une_vraie_baisse(make_bars):
    """Anti sur-nettoyage : une chute RÉELLE (÷2,5) reste dans la fourchette [÷5, ×5]
    et n'est PAS corrigée — seul un artefact isolé hors fourchette l'est."""
    from src.collecte.nettoyage_aberrantes import reperer_aberrantes

    closes = [100.0] * 10 + [40.0] * 3 + [100.0] * 10  # creux durable à 40 (ratio 0,4)
    idx = reperer_aberrantes(make_bars(closes))
    assert idx == [], f"une vraie baisse ne doit pas être nettoyée : {idx}"


# ═══════════════════════════ CORRECTIONS APPLIQUÉES — LOT 2 (12/10/2026)

# ------------------------------------------- B1-05 : sortie au dps COURANT

def test_sortie_rapprochee_par_un_dividende_reduit():
    """B1-05 (CORRIGÉ) — dividende réduit (sans coupe > 50 %) ⇒ le prix de sortie (net 2 %)
    est recalculé au dps courant et RAPPROCHÉ : le rendement tombe sous 2 % ⇒ VENDS TOUT."""
    from src.portfolio import LEVEL_EXIT, DividendPosition, check_dividend_position

    p = DividendPosition(code="X", name="X", entry_price=30000.0, quantity=1,
                         dps=2000.0, per_open=10.0)
    # exit figé (dps 2000) = 62 857 ; dps courant 1000 -> exit recalculé ≈ 31 429 < 33 000
    alerts = check_dividend_position(p, 33000, current_dps=1000, current_per=10)
    assert p.closed and "sortie" in p.close_reason
    assert any(a.level == LEVEL_EXIT for a in alerts)


def test_sortie_eloignee_par_un_dividende_en_hausse():
    """B1-05 (CORRIGÉ) — dividende en HAUSSE ⇒ le prix de sortie s'ÉLOIGNE : un cours qui
    déclenchait la sortie avec l'ancien dps ne la déclenche plus (on garde le loyer)."""
    from src.portfolio import LEVEL_EXIT, DividendPosition, check_dividend_position

    p = DividendPosition(code="X", name="X", entry_price=30000.0, quantity=1,
                         dps=1000.0, per_open=10.0)
    # exit figé (dps 1000) = 31 429 ; dps courant 2000 -> exit recalculé = 62 857 > 33 000
    alerts = check_dividend_position(p, 33000, current_dps=2000, current_per=10)
    assert not p.closed
    assert not any(a.level == LEVEL_EXIT for a in alerts)


# --------------------------------------- B1-09 : stop-outs CONSÉCUTIFS

def test_stopouts_espaces_ne_suspendent_pas():
    """B1-09 (CORRIGÉ) — deux stop-outs espacés de 2 ans = cooldown simple (30 j) ;
    seuls des stop-outs RAPPROCHÉS (échecs répétés) déclenchent la suspension (60 j)."""
    from src.strategie.spec_veille import (STOPOUT_COOLDOWN_DAYS, STOPOUT_SUSPEND_DAYS,
                                           stopout_cooldowns)
    from src.strategie.speculation import SpecPosition

    def stop(quand: str):
        return SpecPosition(code="X", name="X", entry_price=100.0, quantity=1,
                            closed=True, close_reason="STOP déclenché", closed_at=quand)

    _last, days = stopout_cooldowns([stop("2024-06-01T10:00:00"), stop("2026-10-01T10:00:00")])
    assert days["X"] == STOPOUT_COOLDOWN_DAYS, "2 ans d'écart ≠ échecs répétés"

    _last, days = stopout_cooldowns([stop("2026-09-20T10:00:00"), stop("2026-10-01T10:00:00")])
    assert days["X"] == STOPOUT_SUSPEND_DAYS, "11 jours d'écart = échecs répétés → suspension"


# ------------------------------- B1-13 : anti-spam consommé à la LIVRAISON

def _cmd_specveille_avec(monkeypatch, send_ok: bool):
    """Exécute cmd_specveille avec UNE fiche OUI en attente et un envoi simulé."""
    import types

    import src.main as main_mod
    from src.strategie import spec_veille as sv

    fiche = types.SimpleNamespace(code="X", verdict="OUI", blocks={"main": "CASSURE"})
    monkeypatch.setattr(sv, "scan", lambda all_=False: [(fiche, "msg", "X:CASSURE")])
    marquees: list[str] = []
    monkeypatch.setattr(sv, "mark_delivered", lambda keys: marquees.extend(keys))

    class FakeNotifier:
        enabled = True

        def send(self, msg):
            return send_ok

    monkeypatch.setattr(main_mod, "load_config", lambda: {})
    monkeypatch.setattr(main_mod, "get_notifier", lambda cfg: FakeNotifier())
    main_mod.cmd_specveille(types.SimpleNamespace())
    return marquees


def test_fiche_non_livree_reste_disponible(monkeypatch):
    """B1-13 (CORRIGÉ) — envoi Telegram en échec ⇒ la fiche n'est PAS marquée « vue 7 j » :
    elle sera reproposée demain (l'anti-spam se consomme à la LIVRAISON, plus à la génération)."""
    marquees = _cmd_specveille_avec(monkeypatch, send_ok=False)
    assert "X:CASSURE" not in marquees, "fiche marquée alors que l'envoi a échoué !"


def test_fiche_livree_est_marquee(monkeypatch):
    """B1-13 (CORRIGÉ) — envoi réussi ⇒ la fiche est marquée (anti-spam 7 j normal)."""
    marquees = _cmd_specveille_avec(monkeypatch, send_ok=True)
    assert "X:CASSURE" in marquees


# --------------------------------- B2-01/B2-03 : cache PER (valeurs + fraîcheur)

def test_per_cache_rejette_les_valeurs_invalides(monkeypatch, tmp_path):
    """B2-01 (CORRIGÉ) — un PER ≤ 0 (« 0.00 » affiché par brvm.org = non calculable) est
    ÉCARTÉ ; l'ancien format plat (float) reste lu (rétro-compatibilité)."""
    from src.collecte import fundamentals as fu

    fichier = tmp_path / "per_cache.json"
    fichier.write_text(
        '{"STAC": 0.0, "SICC": {"per": 0.0, "date": "2026-10-12"}, "SNTS": 10.88}',
        encoding="utf-8",
    )
    monkeypatch.setattr(fu, "PER_CACHE_FILE", fichier)
    lu = fu._load_per_cache()
    assert "STAC" not in lu and "SICC" not in lu, "un PER ≤ 0 ne doit jamais être servi"
    assert lu["SNTS"]["per"] == 10.88  # rétro-compat ancien schéma
    assert lu["SNTS"]["date"] == ""     # date inconnue pour l'ancien format (honnête)


def test_per_cache_schema_date_et_pas_de_residu(monkeypatch, tmp_path):
    """B2-03 (CORRIGÉ) — le cache porte sa DATE de collecte ; l'écriture est atomique
    (aucun .tmp résiduel, aucun verrou qui traîne)."""
    from src.collecte import fundamentals as fu

    monkeypatch.setattr(fu, "PER_CACHE_FILE", tmp_path / "per_cache.json")
    monkeypatch.setattr(fu, "LOCK_FILE", tmp_path / "per_cache.lock")
    fu._save_per_cache({"SNTS": {"per": 10.88, "date": "2026-10-12"}})
    assert fu._load_per_cache()["SNTS"]["date"] == "2026-10-12"
    assert not (tmp_path / "per_cache.json.tmp").exists()
    assert not (tmp_path / "per_cache.lock").exists()


def test_verrou_cache_libere_et_orphelin_purge(monkeypatch, tmp_path):
    """Incident du 12/10 (course multi-threads) — le verrou du cache se libère après usage
    et un verrou orphelin (process tué) est purgé plutôt que de bloquer 15 s chaque run."""
    import os
    import time

    from src.collecte import fundamentals as fu

    verrou = tmp_path / "per_cache.lock"
    monkeypatch.setattr(fu, "LOCK_FILE", verrou)

    with fu._cache_lock() as ok:
        assert ok is True
        assert verrou.exists()
    assert not verrou.exists(), "verrou non libéré après usage"

    fd = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # verrou orphelin simulé
    os.close(fd)
    vieux = time.time() - 120
    os.utime(verrou, (vieux, vieux))  # > LOCK_STALE_SECONDS (60 s)
    with fu._cache_lock(timeout=2.0) as ok:
        assert ok is True, "un verrou orphelin doit être purgé, pas attendu"
    assert not verrou.exists()


# -------------------------------------- B1-07 : cooldown watchlist (clé fixe)
# CORRIGÉ le 12/10/2026 (lot 2) — test gelé : la clé du cooldown ne contient plus le prix.
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
