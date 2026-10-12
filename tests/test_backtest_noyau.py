"""Tests du backtest du NOYAU (achat + conservation + dividendes réinvestis).

Pourquoi ce fichier existe (priorité n°1 de la passation du 12/10/2026) : ce module
produit les chiffres de sélection et de revenu du noyau ; il était à 28 % de couverture.
Ce qui est vérifié : les filtres point-in-time, le réinvestissement des dividendes nets,
le forward-fill du drawdown (le piège qui avait fabriqué un −73 % inexistant), la
reproductibilité du panier aléatoire (graine).
"""
from datetime import datetime, timedelta

import pytest

from src.analyse.fondamentaux_historiques import TitreFondamentaux
from src.backtesting.backtest_noyau import (
    Position, _drawdown_portefeuille, _index_dates, backtester_noyau,
    panier_aleatoire_noyau, simuler_position,
)
from src.domaine.models import HistoryBar
from src.regles import IRVM

DEBUT = datetime(2026, 1, 1)


def _serie(closes, debut=DEBUT, pas_jours=1):
    return [HistoryBar(date=debut + timedelta(days=i * pas_jours), open=c, high=c,
                       low=c, close=c, volume=100) for i, c in enumerate(closes)]


def _dates(barres):
    return [str(b.date)[:10] for b in barres]


# ═════════════════════════════════ _index_dates ═════════════════════════════════════

def test_index_dates_cas_exacts():
    dates = ["2026-01-01", "2026-01-05", "2026-01-10"]
    assert _index_dates(dates, "2025-12-31") == 0      # avant le début -> premier indice
    assert _index_dates(dates, "2026-01-01") == 0
    assert _index_dates(dates, "2026-01-05") == 1
    assert _index_dates(dates, "2026-01-06") == 2      # premier >= cible
    assert _index_dates(dates, "2026-01-10") == 2
    assert _index_dates(dates, "2026-02-01") is None   # après la fin
    assert _index_dates([], "2026-01-01") is None


# ═════════════════════════════════ simuler_position ═════════════════════════════════

def test_simuler_position_achete_conserve_et_reinvestit():
    """Dividende net (IRVM 12 %), réinvesti AU COURS DE LA SÉANCE DE DÉTACHEMENT."""
    barres = _serie([100, 102, 104, 106, 108, 110, 112, 114, 116, 118])
    divs = [{"ex_date": "2026-01-05", "montant": 10.0}]
    p = simuler_position(barres, divs, "2026-01-01", "2026-01-10", capital=10_000)
    assert p is not None
    net_attendu = 100.0 * 10.0 * (1 - IRVM)               # 880 (100 actions achetées à 100)
    assert p.dividendes_encaisses == pytest.approx(net_attendu)
    assert p.actions_rachetees == pytest.approx(net_attendu / 108)  # réinvesti au cours du 05/01
    assert p.actions == pytest.approx(100 + net_attendu / 108)
    assert p.reinvestissements == 1


def test_simuler_position_ignore_les_dividendes_hors_periode():
    barres = _serie([100] * 5 + [110] * 5)
    divs = [{"ex_date": "2025-12-31", "montant": 10.0},   # avant l'entrée
            {"ex_date": "2026-02-01", "montant": 10.0}]   # après la sortie
    p = simuler_position(barres, divs, _dates(barres)[0], _dates(barres)[-1], capital=1_000)
    assert p is not None
    assert p.dividendes_encaisses == 0.0 and p.reinvestissements == 0


def test_simuler_position_entree_apres_la_fin_ou_sans_cours_retourne_none():
    barres = _serie([100, 110, 120])
    assert simuler_position(barres, [], "2027-01-01", "2027-12-31", 1_000) is None
    assert simuler_position(_serie([0, 0, 0]), [], _dates(barres)[0], "2026-01-03", 1_000) is None


def test_simuler_position_fenetre_trop_courte_retourne_none():
    """i1 <= i0 : aucune séance de détention -> pas de position."""
    barres = _serie([100, 100, 100])
    assert simuler_position(barres, [], "2026-01-01", "2026-01-01", 1_000) is None


# ═════════════════════════════════ _drawdown_portefeuille ════════════════════════════

def test_drawdown_reporte_la_derniere_cote_connue():
    """LE piège documenté : un titre qui ne cote pas tous les jours ne doit PAS faire
    chuter la valeur du portefeuille. Sans forward-fill, la valeur doublerait/moitié
    à chaque jour sans cote (mesure d'époque : −73 % là où le marché perdait −2,3 %).

    Ici les deux titres sont PLATS : le drawdown vrai est 0. Un calcul naïf (sans
    report) verrait une baisse de −50 % les jours impairs où B ne cote pas."""
    jours = 40
    A = _serie([100.0] * jours)
    B = _serie([200.0] * ((jours + 1) // 2), pas_jours=2)   # cote un jour sur deux
    positions = [
        Position(code="A", date_entree="2026-01-01", cours_entree=100.0,
                 actions=10.0, capital_initial=1_000.0),
        Position(code="B", date_entree="2026-01-01", cours_entree=200.0,
                 actions=5.0, capital_initial=1_000.0),
    ]
    dd = _drawdown_portefeuille({"A": A, "B": B}, positions, "2026-01-01", _dates(A)[-1])
    assert dd == pytest.approx(0.0, abs=1e-12)


def test_drawdown_mesure_une_vraie_baisse():
    closes = [100.0] * 20 + [80.0] * 20
    A = _serie(closes)
    positions = [Position(code="A", date_entree="2026-01-01", cours_entree=100.0,
                          actions=10.0, capital_initial=1_000.0)]
    dd = _drawdown_portefeuille({"A": A}, positions, "2026-01-01", _dates(A)[-1])
    assert dd == pytest.approx(-0.20)          # −20 % depuis le sommet 100


def test_drawdown_serie_trop_courte_vaut_zero():
    A = _serie([100.0] * 10)                   # < 30 dates dans la fenêtre
    positions = [Position(code="A", date_entree="2026-01-01", cours_entree=100.0,
                          actions=1.0, capital_initial=100.0)]
    assert _drawdown_portefeuille({"A": A}, positions, "2026-01-01", _dates(A)[-1]) == 0.0


# ═════════════════════════════════ backtester_noyau (filtres point-in-time) ══════════

def _hf_retenu(code="A", dividende=60.0):
    return TitreFondamentaux(code=code, dividendes=[
        {"ex_date": "2025-12-01", "montant": dividende},
        {"ex_date": "2026-03-01", "montant": dividende},
    ])


def test_backtester_noyau_applique_les_trois_filtres():
    """A passe (net 4,48 %) ; B est exclu par le RENDEMENT (< 4 % net) ; C par le PER
    (> 14) ; D par le PAYOUT (> 80 %). Tous les fondamentaux sont CONNUS à l'entrée."""
    hist = {
        "A": _serie([1000.0] * 181),
        "B": _serie([1000.0] * 181),
        "C": _serie([1000.0] * 181),
        "D": _serie([1000.0] * 181),
    }
    hf = {
        "A": _hf_retenu("A", 60.0),                       # net 4,48 % ✓
        "B": _hf_retenu("B", 30.0),                       # net 1,84 % ✗ rendement
        "C": TitreFondamentaux(code="C", bpa={"2024": 3.0}, bpa_fiable=True,
                               dividendes=[{"ex_date": "2025-12-01", "montant": 60.0}]),
        "D": TitreFondamentaux(code="D", bpa={"2024": 60.0}, bpa_fiable=True,
                               dividendes=[{"ex_date": "2025-12-01", "montant": 60.0}]),
    }
    res = backtester_noyau(hist, hf, "2026-01-01", "2026-06-30", capital=1_000_000)
    assert res.nb_titres == 1 and res.positions[0].code == "A"
    # PER de C : 1000/3 = 333 > 14 → exclu. Payout de D : 60/60 = 1,0 > 0,80 → exclu.


def test_backtester_noyau_valeurs_de_bout_en_bout():
    """Cours constant 1000, dividende 60 détaché le 01/03 (connu dès 2025 via un
    dividende antérieur) : tout est calculable à la main, donc vérifiable."""
    hist = {"A": _serie([1000.0] * 181)}
    hf = {"A": _hf_retenu("A", 60.0)}
    res = backtester_noyau(hist, hf, "2026-01-01", "2026-06-30", capital=1_000_000)
    # 1000 actions ; dividende net 1000 × 60 × 0,88 = 52 800 réinvesti à 1000 → +52,8 actions
    assert res.dividendes_totaux == pytest.approx(52_800.0)
    assert res.nb_reinvestissements == 1
    assert res.valeur_finale == pytest.approx(1_052_800.0)
    assert res.rendement_total_pct == pytest.approx(5.28, abs=0.01)
    assert res.drawdown_max_pct == pytest.approx(0.0, abs=1e-9)
    # Sans réinvestissement : 1000×1000 + 52 800 = 1 052 800 → même valeur ici PCQ cours
    # constant ≠ dividende ; la ligne "prix seul" doit rester ≤ la ligne réinvestie.
    assert res.rendement_vs_prix_seul_pct <= res.rendement_total_pct
    # Revenu annuel : 52 800 / 1 000 000 / 0,5 an = 10,56 %
    assert res.revenu_annuel_pct == pytest.approx(10.56, abs=0.02)


def test_backtester_noyau_sans_candidat_retourne_vide():
    hist = {"B": _serie([1000.0] * 181)}
    res = backtester_noyau(hist, {"B": _hf_retenu("B", 30.0)}, "2026-01-01", "2026-06-30")
    assert res.nb_titres == 0 and res.positions == []


def test_backtester_noyau_ignore_un_titre_sans_assez_d_historique():
    """Un titre dont l'entrée tombe dans les 30 dernières barres est écarté."""
    hist = {"A": _serie([1000.0] * 40),                  # 40 séances
            "B": _serie([1000.0] * 181)}
    hf = {"A": _hf_retenu("A"), "B": _hf_retenu("B")}
    res = backtester_noyau(hist, hf, "2026-02-15", "2026-06-30")
    # A : entrée au 15/02 = indice 45 >= 40-30=10 → écarté. B : retenu.
    assert [p.code for p in res.positions] == ["B"]


# ═════════════════════════════════ panier_aleatoire_noyau ═══════════════════════════

def test_panier_aleatoire_reproductible_a_graine_fixe():
    """La graine est le contrat de reproductibilité : deux exécutions identiques."""
    hist = {code: _serie([100.0 + 10 * i for i in range(250)])
            for i, code in enumerate(("A", "B", "C"))}
    r1 = panier_aleatoire_noyau(hist, {}, 2, _dates(hist["A"])[0], _dates(hist["A"])[-1],
                                1_000_000, tirages=5, graine=7)
    r2 = panier_aleatoire_noyau(hist, {}, 2, _dates(hist["A"])[0], _dates(hist["A"])[-1],
                                1_000_000, tirages=5, graine=7)
    assert r1 == r2 and len(r1) == 5


def test_panier_aleatoire_univers_insuffisant_retourne_vide():
    hist = {"A": _serie([100.0] * 250)}
    assert panier_aleatoire_noyau(hist, {}, 2, _dates(hist["A"])[0],
                                  _dates(hist["A"])[-1], 1_000_000) == []


# ═════════════════════════════════ Position (modèle) ════════════════════════════════

def test_position_rendement_total():
    p = Position(code="A", date_entree="2026-01-01", cours_entree=100.0,
                 actions=10.0, capital_initial=1_000.0)
    assert p.valeur(120.0) == pytest.approx(1_200.0)
    assert p.rendement_total(120.0) == pytest.approx(0.20)
    p.capital_initial = 0.0
    assert p.rendement_total(120.0) == 0.0
