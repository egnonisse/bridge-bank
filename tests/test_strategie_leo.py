"""Tests du moteur de simulation de la stratégie réelle de LEO (MoteurLeo).

Pourquoi ce fichier existe (priorité n°1 de la passation du 12/10/2026) : ce moteur a
produit les chiffres d'attribution qui fondent des décisions, et il était à 0 % de couverture.
Re-mesurés le 13/10 après le lot 9 (A3-08 plafond équitable + A3-10 J+1) : −42,9 / −16,1 pt ;
après le lot 4 : −49,0 / +26,7 pt ; avant : −45,4 / +26,2 pt.

Ce qui est vérifié : le coût d'un ordre (minimum inclus), le CMP frais inclus, le
marqueur de palier (sans lui : 1 013 ventes au lieu de 4, mesuré à l'époque), la réserve
de cash, l'entrée en tranches, le renfort sur faiblesse et ses conditions, les dividendes
nets d'IRVM, la cohérence du résultat final, et depuis le lot 9 (13/10/2026) : le plafond
de ligne DYNAMIQUE (A3-08), l'exécution à J+1 (A3-10), les titres achetés publiés.

CONSTATS de lecture (à connaître, verrouillés par les tests) :
  - le plafond de ligne par défaut est DYNAMIQUE : capital × (1 − cash) / n_titres
    (A3-08 : chaque variante ouvre le même univers de titres) ; `budget_max_ligne`
    explicite le remplace et sert aux tests de non-régression ;
  - une décision prise sur le close de la séance `d` s'exécute à la séance SUIVANTE
    du titre (A3-10) : le premier achat arrive au rang 1, pas au rang 0 ;
  - avec un plafond explicite, les `nb_tranches` achats d'entrée consomment exactement
    ce plafond (tranche = plafond / nb_tranches) ; le renfort n'a de marge que si les
    tranches ont été rabotées par le cash disponible.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.domaine.models import HistoryBar
from src.regles import FRAIS_MINIMUM, FRAIS_PAR_SENS
from src.strategie.strategie_leo import (
    MoteurLeo, Parametres, Position, _cout_ordre,
    variante_complete, variante_noyau_passif, variante_paliers_seuls,
    variante_renforcement_seul,
)
from src.taxation import IRVM_DIVIDEND_TAX

DEBUT = datetime(2026, 1, 1)


def _serie(closes):
    return [HistoryBar(date=DEBUT + timedelta(days=i), open=c, high=c, low=c,
                       close=c, volume=100) for i, c in enumerate(closes)]


def _params(**kw):
    """Paramètres neutres pour les scénarios : 1 tranche, pas de renfort ni paliers.

    `budget_max_ligne` est fixé EXPLICITEMENT (non-régression : plafond connu) ;
    les tests du plafond DYNAMIQUE (A3-08) passent `budget_max_ligne=None`.
    """
    base = dict(nb_tranches=1, espacement_jours=0, renforcement_actif=False,
                paliers_actifs=False, cash_cible=0.0,
                budget_max_ligne=100_000.0)
    base.update(kw)
    return Parametres(**base)


# ═════════════════════════════════ _cout_ordre ══════════════════════════════════════

def test_cout_ordre_minimum_et_proportionnel():
    assert _cout_ordre(50_000) == pytest.approx(FRAIS_MINIMUM)        # sous le seuil du minimum
    assert _cout_ordre(10_000) == pytest.approx(FRAIS_MINIMUM)
    assert _cout_ordre(100_000) == pytest.approx(100_000 * FRAIS_PAR_SENS)
    assert _cout_ordre(1_000_000) == pytest.approx(1_000_000 * FRAIS_PAR_SENS)


# ═════════════════════════════════ _acheter / _vendre (unités) ══════════════════════

def test_acheter_inclut_les_frais_dans_le_cmp():
    m = MoteurLeo({}, {}, _params(), capital=100_000)
    ok = m._acheter("X", "2026-01-01", 1_000.0, 100_000.0, "test")
    assert ok
    pos = m.positions["X"]
    assert pos.actions == pytest.approx((100_000 - 1_400) / 1_000)   # net de frais
    assert pos.cout_total == pytest.approx(100_000.0)                # frais INCLUS dans le coût
    assert pos.cmp == pytest.approx(100_000 / 98.6)
    assert pos.cmp > 1_000                                            # le CMP dépasse le cours
    assert m.cash == pytest.approx(0.0) and m.frais_payes == pytest.approx(1_400.0)
    assert m.journal[-1][1] == "ACHAT" and m.nb_achats == 1


def test_acheter_refuse_montant_trop_petit_ou_cours_nul():
    m = MoteurLeo({}, {}, _params(), capital=100_000)
    assert m._acheter("X", "2026-01-01", 1_000.0, 1_500.0, "trop petit") is False   # < 2 × 1 000
    assert m._acheter("X", "2026-01-01", 0.0, 50_000.0, "cours nul") is False
    assert m.positions == {} and m.nb_achats == 0


def test_vendre_net_de_frais_et_prorata_du_cmp():
    m = MoteurLeo({}, {}, _params(), capital=100_000)
    m._acheter("X", "2026-01-01", 1_000.0, 100_000.0, "test")
    pos = m.positions["X"]
    actions_avant, cout_avant = pos.actions, pos.cout_total
    produit = m._vendre("X", "2026-02-01", 1_200.0, actions_avant / 2, "test", marqueur=0.0)
    assert produit == pytest.approx((actions_avant / 2) * 1_200 - _cout_ordre((actions_avant / 2) * 1_200))
    assert pos.actions == pytest.approx(actions_avant / 2)
    # Le coût sort AU PRORATA du CMP : la moitié des actions emporte la moitié du coût.
    assert pos.cout_total == pytest.approx(cout_avant / 2)
    assert pos.cmp == pytest.approx(100_000 / 98.6)   # le CMP ne bouge pas sur une vente


def test_vendre_tout_ferme_la_position():
    m = MoteurLeo({}, {}, _params(), capital=100_000)
    m._acheter("X", "2026-01-01", 1_000.0, 100_000.0, "test")
    m._vendre("X", "2026-02-01", 1_100.0, 1_000.0, "tout")
    assert "X" not in m.positions
    assert m.nb_ventes == 1


# ═════════════════════════════════ les paliers dans executer ════════════════════════

def test_le_meme_palier_ne_se_rejoue_pas_chaque_seance():
    """LE piège documenté du moteur : sans le marqueur de palier, la règle vend 1/3
    à CHAQUE séance au-dessus du seuil (1 013 ventes au lieu de 4, mesuré)."""
    closes = [1_000.0, 1_000.0, 1_000.0] + [1_200.0] * 37   # +18 % sur le CMP (frais inclus)
    m = MoteurLeo({"X": _serie(closes)}, {}, _params(paliers_actifs=True), capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_ventes == 1                       # une seule vente, malgré 37 séances au-dessus
    assert m.positions["X"].ventes[0][3] == pytest.approx(0.15)


def test_les_deux_paliers_peuvent_tomber_le_meme_jour():
    """Gain de +23 % : la boucle des seuils joue +15 % ET +20 % dans la même séance."""
    closes = [1_000.0, 1_000.0, 1_000.0] + [1_250.0] * 37
    m = MoteurLeo({"X": _serie(closes)}, {}, _params(paliers_actifs=True), capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_ventes == 2
    seuils = sorted(v[3] for v in m.positions["X"].ventes)
    assert seuils == [pytest.approx(0.15), pytest.approx(0.20)]


def test_un_palier_jamais_atteint_ne_vend_rien():
    closes = [1_000.0] * 3 + [1_100.0] * 37      # +8,5 % sur le CMP : sous le seuil 15 %
    m = MoteurLeo({"X": _serie(closes)}, {}, _params(paliers_actifs=True), capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_ventes == 0


# ═════════════════════════════════ réserve de cash ══════════════════════════════════

def test_cash_cible_bloque_une_tranche_surdimensionnee():
    """Réserve de 90 % (10 k disponibles) face à un PLAFOND EXPLICITE de 100 k : la
    tranche (100 k) dépasse le disponible, aucune entrée n'a lieu."""
    m = MoteurLeo({"X": _serie([1_000.0] * 40)}, {},
                  _params(cash_cible=0.9, budget_max_ligne=100_000.0), capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_achats == 0 and m.cash == pytest.approx(100_000.0)


def test_plafond_auto_ne_franchit_jamais_la_reserve():
    """A3-08 : avec le plafond AUTO, la part investissable par titre s'adapte à la
    réserve — l'entrée est possible (10 k > moitié de tranche auto) et la réserve
    de 90 % reste intacte au franc près. Le plafond auto ne DÉPASSE jamais le
    disponible par construction."""
    m = MoteurLeo({"X": _serie([1_000.0] * 40)}, {},
                  _params(cash_cible=0.9, budget_max_ligne=None), capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.positions["X"].cout_total == pytest.approx(10_000.0)
    assert m.cash == pytest.approx(90_000.0)


# ═════════════════════════════════ entrée progressive ═══════════════════════════════

def test_entree_progressive_trois_tranches_espacees():
    m = MoteurLeo({"X": _serie([1_000.0] * 60)}, {},
                  _params(nb_tranches=3, espacement_jours=12,
                          budget_max_ligne=300_000.0), capital=1_000_000)
    m.executer("2026-01-01", "2026-03-01", univers=["X"])
    pos = m.positions["X"]
    assert pos.tranches_achetees == 3 and m.nb_achats == 3
    motifs = [j[4] for j in m.journal if j[1] == "ACHAT"]
    assert motifs == ["entree 1/3", "entree 2/3", "entree 3/3"]
    # Espacement (A3-10 : exécution à J+1) : décision au rang 0 → achat au rang 1,
    # puis 12 séances d'espacement entre exécutions : rangs 1, 14, 27.
    rangs = [j[0] for j in m.journal if j[1] == "ACHAT"]
    assert rangs == ["2026-01-02", "2026-01-15", "2026-01-28"]


def test_pas_de_quatrieme_tranche_ni_de_renfort_sans_baisse():
    m = MoteurLeo({"X": _serie([1_000.0] * 60)}, {},
                  _params(nb_tranches=3, espacement_jours=12, renforcement_actif=True,
                          budget_max_ligne=300_000.0), capital=1_000_000)
    m.executer("2026-01-01", "2026-03-01", univers=["X"])
    assert m.nb_achats == 3                       # cours plat : jamais de renfort
    assert m.positions["X"].tranches_achetees == 3


# ═════════════════════════════════ renfort sur faiblesse ═════════════════════════════

def _moteur_avec_position_pleine(cash, closes):
    """Prépare un moteur « à la main » : 3 tranches déjà passées, plafond non consommé.

    C'est le cas réel où le renfort a de la marge : les tranches ont été rabotées par
    le cash disponible (le cours et les montants vivent dans le journal du moteur)."""
    m = MoteurLeo({"X": _serie(closes)}, {},
                  _params(nb_tranches=3, espacement_jours=12, renforcement_actif=True,
                          budget_max_ligne=300_000.0), capital=300_000)
    m.cash = cash
    pos = m.positions.setdefault("X", Position(code="X"))
    # A3-12(d) : le plafond se mesure sur le cumul investi — le helper le renseigne
    # comme le ferait une vraie séquence d'achats (200 k déjà investis).
    pos.actions, pos.cout_total, pos.investi_total, pos.tranches_achetees = \
        200.0, 200_000.0, 200_000.0, 3
    pos.cours_dernier_achat, pos.date_dernier_achat = 1_000.0, "2026-01-01"
    return m


def test_renfort_sur_faiblesse_se_declenche_dans_les_conditions():
    """Baisse de −5 % (≥ seuil 4,5 %), plafond non consommé (reste 100 k > tranche/2)
    et cash disponible (100 k > tranche/2) : le renfort passe, motif chiffré."""
    closes = [1_000.0] * 10 + [950.0] * 30
    m = _moteur_avec_position_pleine(cash=100_000.0, closes=closes)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_achats == 1
    motif = [j[4] for j in m.journal if j[1] == "ACHAT"][-1]
    assert motif == "renfort (-5.0 %)"
    assert m.positions["X"].tranches_achetees == 4
    assert m.positions["X"].cout_total == pytest.approx(300_000.0)


def test_renfort_bloque_si_baisse_insuffisante():
    closes = [1_000.0] * 10 + [960.0] * 30       # −4 % : sous le seuil de 4,5 %
    m = _moteur_avec_position_pleine(cash=100_000.0, closes=closes)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_achats == 0


def test_renfort_bloque_si_plafond_ou_cash_insuffisant():
    closes = [1_000.0] * 10 + [950.0] * 30
    # Cash sous tranche/2 : la réserve interdit le renfort.
    m = _moteur_avec_position_pleine(cash=40_000.0, closes=closes)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_achats == 0
    # Plafond déjà consommé : plus de marge (reste 0). Le plafond se mesure sur le cumul
    # investi (A3-12(d)) — on simule donc un titre ayant déjà investi ses 300 k.
    m2 = _moteur_avec_position_pleine(cash=100_000.0, closes=closes)
    m2.positions["X"].investi_total = 300_000.0   # plafond atteint
    m2.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m2.nb_achats == 0


# ═════════════════════════════════ dividendes ═══════════════════════════════════════

def test_dividendes_credites_nets_d_irvm():
    closes = [1_000.0] * 40
    hf = {"X": SimpleNamespace(dividendes=[{"ex_date": "2026-01-10", "montant": 50.0}])}
    m = MoteurLeo({"X": _serie(closes)}, hf, _params(), capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    actions = m.positions["X"].actions               # 98,6 actions achetées le 01/01
    attendu = actions * 50.0 * (1 - IRVM_DIVIDEND_TAX)
    assert m.positions["X"].dividendes == pytest.approx(attendu)
    dividendes_journal = [j for j in m.journal if j[1] == "DIVIDENDE"]
    assert len(dividendes_journal) == 1 and dividendes_journal[0][0] == "2026-01-10"


def test_dividende_hors_periode_ignore():
    hf = {"X": SimpleNamespace(dividendes=[{"ex_date": "2025-06-01", "montant": 50.0}])}
    m = MoteurLeo({"X": _serie([1_000.0] * 40)}, hf, _params(), capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.positions["X"].dividendes == 0.0


# ═════════════════════════════════ _jours_ecoules ═══════════════════════════════════

def test_jours_ecoules_entre_deux_dates():
    dates = [str(b.date)[:10] for b in _serie([1_000.0] * 40)]
    assert MoteurLeo._jours_ecoules("2026-01-01", "2026-01-13", dates) == 12
    assert MoteurLeo._jours_ecoules("2026-01-05", "2026-01-05", dates) == 0


def test_jours_ecoules_hors_serie_retourne_999():
    dates = [str(b.date)[:10] for b in _serie([1_000.0] * 40)]
    assert MoteurLeo._jours_ecoules("2027-01-01", "2027-02-01", dates) == 999   # après la série
    assert MoteurLeo._jours_ecoules("2019-01-01", "2019-06-01", dates) == 999   # avant la série


# ═════════════════════════════════ résultat final ═══════════════════════════════════

def test_resultat_final_coherent_et_calculable_a_la_main():
    """Cours 1 000 jusqu'au rang 20 puis 1 100 : tout est vérifiable analytiquement."""
    closes = [1_000.0] * 20 + [1_100.0] * 20
    m = MoteurLeo({"X": _serie(closes)}, {}, _params(), capital=100_000)
    r = m.executer("2026-01-01", "2026-02-09", univers=["X"])
    actions = (100_000 - 1_400) / 1_000
    assert r.valeur_finale == pytest.approx(actions * 1_100)      # cash = 0
    assert r.rendement_pct == pytest.approx((actions * 1_100 / 100_000 - 1) * 100)
    assert r.nb_achats == 1 and r.nb_ventes == 0 and r.nb_lignes == 1
    assert r.frais_payes == pytest.approx(1_400.0)
    assert r.capital_deploye == pytest.approx(100_000.0)
    # L'exposition est mesurée AVANT les ordres de chaque séance (ordre du code :
    # valeur → exécution) et le premier achat n'arrive qu'au rang 1 (A3-10) :
    # 38 séances sur 40 à 100 % = 95 %.
    assert r.exposition_moyenne_pct == pytest.approx(95.0, abs=0.1)
    assert r.drawdown_max_pct == pytest.approx(-1.4, abs=0.05)
    # Le drawdown part de la valeur TOTALE : les frais d'entrée (1,4 %) créent à eux
    # seuls ce plancher, avant toute baisse de cours. Comportement réel du moteur.
    assert r.detail["X"]["cmp"] == pytest.approx(100_000 / 98.6, abs=0.01)


def test_executer_sans_serie_assez_longue_retourne_un_resultat_vide():
    """Moins de 30 séances dans la fenêtre : aucun titre éligible, résultat neutre."""
    m = MoteurLeo({"X": _serie([1_000.0] * 20)}, {}, _params(), capital=100_000)
    r = m.executer("2026-01-01", "2026-01-20", univers=["X"])
    assert r.nb_lignes == 0 and r.valeur_finale == 0.0 and r.capital_initial == 100_000


# ═════════════════════════════════ variantes (l'attribution) ═════════════════════════

def test_variantes_de_l_attribution():
    passif = variante_noyau_passif()
    assert passif.nb_tranches == 1 and not passif.renforcement_actif
    assert not passif.paliers_actifs and passif.cash_cible == 0.0

    complete = variante_complete()
    assert complete.nb_tranches == 3 and complete.renforcement_actif
    assert complete.paliers_actifs and complete.cash_cible == 0.15
    assert complete.seuils_vente == ((0.15, 1 / 3), (0.20, 1 / 3))

    renfort = variante_renforcement_seul()
    assert renfort.renforcement_actif and not renfort.paliers_actifs

    paliers = variante_paliers_seuls()
    assert paliers.paliers_actifs and not paliers.renforcement_actif
    assert paliers.nb_tranches == 1


# ═══════════════════════════ A3-12 — moteur honnête (4 corrections) ═══════════════════
# Audit du 12/10 : (a) dividendes d'une position soldée perdus du compte-rendu ;
# (b) réserve de cash franchie d'une demi-tranche ; (c) dividende crédité après les ordres
# du jour (achat à l'ex-date rémunéré à tort) ; (d) plafond de ligne contournable en
# réinvestissant le produit d'une vente. Corrigés le 13/10.

def test_a3_12a_dividendes_conserves_apres_vente_totale():
    """Une position soldée disparaît de `positions` (pop) mais son dividende reste dans le
    compte-rendu — c'est un revenu réellement encaissé (avant : perdu du total).

    La vente est placée au DERNIER jour pour isoler le compte-rendu : le ré-achat après une
    ligne soldée est un comportement séparé du moteur (jamais atteint avec les paliers réels
    ⅓ + ⅓ — c'est pourquoi une vente totale est ici forcée)."""
    closes = [1_000.0] * 29 + [1_300.0] * 2   # +30 % sur les 2 derniers jours : le palier
    # est DÉCIDÉ au rang 29 et EXÉCUTÉ au rang 30 (A3-10) — la ligne est soldée.
    hf = {"X": SimpleNamespace(dividendes=[{"ex_date": "2026-01-03", "montant": 50.0}])}
    m = MoteurLeo({"X": _serie(closes)}, hf,
                  _params(paliers_actifs=True, seuils_vente=((0.20, 1.0),)),
                  capital=100_000)
    r = m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert "X" not in m.positions                          # la ligne est soldée…
    actions = (100_000 - _cout_ordre(100_000)) / 1_000     # …mais le dividende compte
    attendu = actions * 50.0 * (1 - IRVM_DIVIDEND_TAX)
    assert r.dividendes == pytest.approx(attendu)
    assert r.dividendes > 0


def test_a3_12b_reserve_de_cash_jamais_franchie_par_la_tranche():
    """dispo (55 k) > tranche/2 mais < tranche (100 k) : l'achat se cale sur le disponible —
    la réserve cash_cible (45 %) n'est jamais entamée (avant : achat de 100 k, cash à 0)."""
    closes = [1_000.0] * 30
    m = MoteurLeo({"X": _serie(closes)}, {}, _params(cash_cible=0.45), capital=100_000)
    r = m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.positions["X"].cout_total == pytest.approx(55_000.0)
    assert r.cash_final == pytest.approx(45_000.0)      # réserve intacte au franc près


def test_a3_12c_achat_le_jour_de_l_ex_date_ne_touche_pas_le_dividende():
    """Le droit au dividende va aux détenteurs d'AVANT l'ex-date : la tranche 1 est
    décidée au rang 0 et EXÉCUTÉE au rang 1 (02/01, A3-10) — elle est rémunérée ;
    la tranche 2, décidée au rang 1, s'exécute LE JOUR de l'ex-date (03/01) et
    n'est PAS rémunérée (le crédit se fait sur les positions d'entrée de séance)."""
    closes = [1_000.0] * 30
    hf = {"X": SimpleNamespace(dividendes=[{"ex_date": "2026-01-03", "montant": 50.0}])}
    m = MoteurLeo({"X": _serie(closes)}, hf,
                  _params(nb_tranches=2, espacement_jours=0,
                          budget_max_ligne=100_000.0),
                  capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    dates_achats = [j[0] for j in m.journal if j[1] == "ACHAT"]
    assert dates_achats == ["2026-01-02", "2026-01-03"]   # exécutions décalées d'une séance
    actions_tranche1 = (50_000 - _cout_ordre(50_000)) / 1_000
    attendu = actions_tranche1 * 50.0 * (1 - IRVM_DIVIDEND_TAX)
    assert m.positions["X"].dividendes == pytest.approx(attendu)


def test_a3_12d_plafond_non_contournable_en_reinvestissant_une_vente():
    """Après une vente, le plafond se mesure sur le cumul INVESTI : le produit de la vente
    ne peut plus être réinvesti au-delà du plafond (avant : `cout_total` baissait au
    prorata, rouvrant 33 k de marge et le renfort passait)."""
    closes = [1_000.0] * 4 + [1_250.0] * 2 + [820.0] * 24   # palier +25 %, puis −18 %
    m = MoteurLeo({"X": _serie(closes)}, {},
                  _params(nb_tranches=2, espacement_jours=0, renforcement_actif=True,
                          seuil_renforcement=0.045, paliers_actifs=True,
                          seuils_vente=((0.20, 1 / 3),), budget_max_ligne=100_000.0),
                  capital=1_000_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    motifs = [j[4] for j in m.journal if j[1] == "ACHAT"]
    assert not any("renfort" in motif for motif in motifs)
    # Contrôle : la vente du palier a bien eu lieu (sinon le test ne prouverait rien).
    assert any(j[1] == "VENTE" for j in m.journal)
    assert m.positions["X"].investi_total == pytest.approx(100_000.0)   # plafond atteint


# ═══════════════════ A3-08 / A3-10 — moteur honnête (lot 9, 13/10/2026) ══════════════
# Audit du 13/10 : (A3-08) le plafond fixe de 300 k faisait acheter un univers DIFFÉRENT
# selon la variante — la passive épuisait le cash au 3e titre, le résultat dépendait de
# l'ordre du dict `univers`, et 5 paramètres déclarés n'étaient JAMAIS lus. (A3-10) les
# ordres s'exécutaient au close du signal — irréalisable sur une place cotée au fixing.

def test_a3_08_plafond_auto_ouvre_les_memes_5_titres_et_ignore_l_ordre_de_l_univers():
    """LE test du fix : avec le plafond dynamique, la variante passive (1 tranche,
    cash 0 %) achète LES 5 TITRES — avant, elle épuisait son cash au 3e et la
    composition dépendait de l'ordre de l'univers. L'univers INVERSE donne le même
    résultat final : le biais d'ordre a disparu."""
    closes = [1_000.0] * 60
    hist = {f"T{i}": _serie(closes) for i in range(5)}
    univers = [f"T{i}" for i in range(5)]
    p = variante_noyau_passif()
    assert p.budget_max_ligne is None                # plafond auto (défaut de production)
    m = MoteurLeo(hist, {}, p, capital=1_000_000)
    r = m.executer("2026-01-01", "2026-03-01", univers=univers)
    assert r.titres_achetes == univers               # les 5, dans l'ordre
    assert r.nb_achats == 5

    m2 = MoteurLeo(hist, {}, variante_noyau_passif(), capital=1_000_000)
    r2 = m2.executer("2026-01-01", "2026-03-01", univers=list(reversed(univers)))
    assert r2.titres_achetes == univers              # mêmes titres (triés)
    assert r2.valeur_finale == pytest.approx(r.valeur_finale)   # même résultat


def test_a3_08_parametres_morts_retires():
    """Un paramètre qu'on peut régler SANS EFFET est un mensonge de l'API."""
    p = Parametres()
    for fantome in ("budget_ligne", "max_tranches_renforcement", "duree_max_seances",
                    "rebalancement_actif", "seuil_rebalancement"):
        assert not hasattr(p, fantome), fantome


def test_a3_08_plafond_explicite_respecte():
    """Non-régression : un plafond explicite reste prioritaire et borne le cumul
    investi par titre (5 titres × 100 k = 500 k investis, 500 k de cash restant)."""
    closes = [1_000.0] * 60
    hist = {f"T{i}": _serie(closes) for i in range(5)}
    m = MoteurLeo(hist, {}, variante_noyau_passif(), capital=1_000_000)
    m.p.budget_max_ligne = 100_000.0
    r = m.executer("2026-01-01", "2026-03-01", univers=[f"T{i}" for i in range(5)])
    assert r.titres_achetes == [f"T{i}" for i in range(5)]
    assert r.capital_deploye == pytest.approx(500_000.0)
    assert r.cash_final == pytest.approx(500_000.0)


def test_a3_10_execution_au_cours_de_la_seance_suivante():
    """Le signal est lu au close du rang 0 ; l'achat s'exécute au rang 1, AU COURS
    DU RANG 1 (2 000 F) — jamais au cours du signal (1 000 F)."""
    closes = [1_000.0, 2_000.0] + [2_000.0] * 58
    m = MoteurLeo({"X": _serie(closes)}, {}, _params(), capital=100_000)
    m.executer("2026-01-01", "2026-03-01", univers=["X"])
    achats = [j for j in m.journal if j[1] == "ACHAT"]
    assert achats[0][0] == "2026-01-02"                      # exécuté à J+1
    assert m.positions["X"].cours_dernier_achat == 2_000.0   # au cours de J+1
    assert m.positions["X"].cmp == pytest.approx(
        2_000.0 * 100_000 / (100_000 - _cout_ordre(100_000)), abs=0.01)


def test_a3_10_ordre_non_execute_a_la_fin_n_est_pas_applique():
    """Un palier franchi au DERNIER jour de la fenêtre est décidé mais jamais
    exécuté (la séance suivante sort de la fenêtre) : la vente n'a PAS lieu — on
    n'applique jamais une exécution qui n'a pas eu lieu."""
    closes = [1_000.0] * 29 + [1_300.0]
    m = MoteurLeo({"X": _serie(closes)}, {},
                  _params(paliers_actifs=True, seuils_vente=((0.20, 1.0),)),
                  capital=100_000)
    m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert m.nb_ventes == 0
    assert "X" in m.positions                    # toujours détenue


def test_a3_08_titres_achetes_meme_revendus_en_totalite():
    """`titres_achetes` liste les titres MÊME si la ligne a été entièrement revendue :
    on vérifie l'univers visité, pas l'inventaire final."""
    closes = [1_000.0] * 29 + [1_300.0] * 2
    m = MoteurLeo({"X": _serie(closes)}, {},
                  _params(paliers_actifs=True, seuils_vente=((0.20, 1.0),)),
                  capital=100_000)
    r = m.executer("2026-01-01", "2026-02-09", univers=["X"])
    assert "X" not in m.positions          # ligne soldée…
    assert r.titres_achetes == ["X"]       # …mais l'univers visité la liste
