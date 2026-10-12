"""Tests du simulateur de paliers de sortie (la règle la plus coûteuse du système).

Pourquoi ce fichier existe (priorité n°1 de la passation du 12/10/2026) : `simuler_paliers`
et `comparer_modes` produisent l'attribution « paliers = −45,4 pt » qui fonde la décision
du 08/10 ; le module était à 0 % de couverture.

Ce qui est vérifié ici, ce sont les RÈGLES telles qu'écrites dans le module (pas une
réécriture) : les 4 modes, le marqueur de palier, le break-even, le stop suiveur,
la pondération des frais par fraction vendue.
"""
from datetime import datetime, timedelta

import pytest

from src.domaine.models import HistoryBar
from src.regles import FRAIS_ALLER_RETOUR as FRAIS
from src.strategie.paliers_sortie import (
    SortiePartielle, TradePartiel, bilan, collecter_signaux, comparer_modes,
    simuler_paliers,
)


def _bars(closes):
    """Barres quotidiennes consécutives (dates lisibles) à partir des clôtures."""
    debut = datetime(2026, 1, 1)
    return [HistoryBar(date=debut + timedelta(days=i), open=c, high=c, low=c,
                       close=c, volume=100) for i, c in enumerate(closes)]


# ═════════════════════════════ mode « duree » (référence neutre) ═════════════════════

def test_duree_sort_au_bout_de_n_seances():
    barres = _bars([100, 101, 102, 103, 104, 105, 106, 107])
    t = simuler_paliers(barres, 0, duree_max=5, mode="duree")
    assert t.seances == 5 and t.motif_final == "duree"
    assert t.date_sortie == str(barres[5].date)[:10]
    assert len(t.sorties) == 1 and t.sorties[0].fraction == 1.0
    assert t.fraction_restante == 0.0
    # Rendement net = cours final / cours d'entrée, frais aller-retour une seule fois.
    attendu = (105 / 100) * (1 - FRAIS) - 1
    assert t.rendement_net == pytest.approx(attendu)


def test_duree_coincee_par_la_fin_de_serie():
    barres = _bars([100, 110, 120])
    t = simuler_paliers(barres, 0, duree_max=50, mode="duree")
    assert t.seances == 2                       # min(i+duree, n-1)
    assert t.date_sortie == str(barres[-1].date)[:10]


def test_cours_d_entree_nul_retourne_none():
    assert simuler_paliers(_bars([0, 100]), 0, 60, "duree") is None


def test_liste_vide_leve_index_error_comportement_actuel():
    """CONSTAT (pas un contrat souhaitable) : une liste de barres VIDE lève IndexError —
    le module n'a pas de garde d'entrée. Les appelants (comparer_modes, scripts de mesure)
    ne passent jamais de série vide ; si un nouvel appelant en passe une, il faut d'abord
    décider si le module doit retourner None. Verrouillé ici pour que le jour où ça change,
    ça se voie."""
    with pytest.raises(IndexError):
        simuler_paliers([], 0, 60, "paliers")


# ═════════════════════════════ mode « paliers » (règle de LEO) ═══════════════════════

def test_paliers_vente_par_tiers_a_20_et_35_puis_cloture_a_50():
    """La règle réelle : +20 % -> 1/3, +35 % -> 1/3, +50 % -> clôture du reste.

    NOTE de lecture : chaque palier se joue sur une barre DISTINCTE (le compteur
    `palier` n'avance que d'un cran par barre) — c'est pourquoi la série descend
    un seuil par séance ici."""
    barres = _bars([100, 121, 136, 151])
    t = simuler_paliers(barres, 0, duree_max=250, mode="paliers")
    assert [round(s.seuil, 2) for s in t.sorties] == [0.20, 0.35, 0.50]
    assert [s.fraction for s in t.sorties] == [pytest.approx(1 / 3),
                                               pytest.approx(1 / 3),
                                               pytest.approx(1 / 3)]
    assert t.motif_final == "+50 % atteint"
    assert t.seances == 3 and t.fraction_restante == 0.0


def test_paliers_un_seul_palier_par_seance_meme_si_le_cours_saute():
    """Comportement réel (découvert en écrivant ces tests) : un cours qui saute
    directement à +36 % ne déclenche QUE le palier +20 % à cette séance ; le +35 %
    attend la séance suivante AU-DESSUS du seuil. Si la série retombe entre-temps,
    le 2e palier ne se joue jamais."""
    barres = _bars([100, 136, 84])
    t = simuler_paliers(barres, 0, duree_max=250, mode="paliers")
    assert [round(s.seuil, 2) for s in t.sorties] == [0.20, 0.67]  # jamais +35 %
    assert t.motif_final == "stop"


def test_paliers_stop_initial_moins_15_pct_sort_toute_la_position():
    barres = _bars([100, 84])          # -16 % : sous le garde-fou -15 %
    t = simuler_paliers(barres, 0, duree_max=250, mode="paliers")
    assert t.motif_final == "stop" and t.seances == 1
    assert len(t.sorties) == 1 and t.sorties[0].fraction == 1.0
    assert t.sorties[0].cours == 84


def test_paliers_stop_au_break_even_apres_le_premier_palier():
    """Après +20 %, le stop monte à l'entrée : un retour à l'entrée solde le reste.
    C'est le cœur de la protection : on ne rend jamais un gain acquis.

    NB : une sortie « stop »/« durée » enregistre `seuil = fraction restante` (le
    champ `seuil` ne porte pas un palier dans ce cas) — comportement réel du module."""
    barres = _bars([100, 121, 100])
    t = simuler_paliers(barres, 0, duree_max=250, mode="paliers")
    assert [round(s.seuil, 2) for s in t.sorties] == [0.20, pytest.approx(0.67, abs=0.01)]
    assert t.motif_final == "stop"
    assert t.sorties[-1].fraction == pytest.approx(2 / 3)   # le reste non vendu
    assert t.sorties[-1].cours == 100                        # sorti au break-even


def test_paliers_stop_suiveur_apres_le_deuxieme_palier():
    """Après +35 %, le stop suit le sommet à -10 % : la hausse est conservée."""
    barres = _bars([100, 121, 136, 125])   # paliers joués sur 2 séances, puis recul
    t = simuler_paliers(barres, 0, duree_max=250, mode="paliers")
    assert [round(s.seuil, 2) for s in t.sorties[:2]] == [0.20, 0.35]
    assert t.motif_final == "stop"
    assert t.sorties[-1].cours == 125      # sommet +36 % -> stop à +26 % -> touché à 125


def test_paliers_chaque_seuil_ne_se_joue_qu_une_fois():
    """LE piège documenté du module : sans le marqueur, la règle revendrait 1/3 à CHAQUE
    séance au-dessus du seuil (mesure d'époque : 1 013 ventes au lieu de 4)."""
    barres = _bars([100] + [121] * 12)     # +21 % maintenu 12 séances
    t = simuler_paliers(barres, 0, duree_max=250, mode="paliers")
    ventes_20 = [s for s in t.sorties if abs(s.seuil - 0.20) < 1e-9]
    assert len(ventes_20) == 1
    assert len(t.sorties) == 2 and t.motif_final == "duree"   # 1/3 vendu, le reste court


def test_paliers_sans_palier_atteint_sort_a_la_duree():
    barres = _bars([100, 110] + [110] * 60)     # jamais +20 %
    t = simuler_paliers(barres, 0, duree_max=40, mode="paliers")
    assert t.motif_final == "duree" and t.seances == 40
    assert len(t.sorties) == 1 and t.sorties[0].fraction == 1.0


# ═════════════════════════════ mode « stop » (—15 % seul) ════════════════════════════

def test_stop_simple_coupe_a_moins_15():
    barres = _bars([100, 90, 84])
    t = simuler_paliers(barres, 0, duree_max=250, mode="stop")
    assert t.motif_final == "stop" and t.seances == 2
    assert t.sorties[0].cours == 84


def test_stop_simple_laisse_courir_sans_palier():
    """Mode stop : jamais de vente partielle — +100 % ne déclenche rien avant la durée."""
    barres = _bars([100, 150, 200] + [200] * 30)
    t = simuler_paliers(barres, 0, duree_max=20, mode="stop")
    assert t.motif_final == "duree" and len(t.sorties) == 1
    assert t.sorties[0].fraction == 1.0


# ═════════════════════════════ mode « suiveur » (paliers sans vente partielle) ═══════

def test_suiveur_ne_vend_jamais_par_tiers():
    """Le mode suiveur isole l'effet d'échelle : mêmes stops, AUCUNE vente partielle."""
    barres = _bars([100, 121, 136, 125])       # paliers franchis puis recul sous le suiveur
    t = simuler_paliers(barres, 0, duree_max=250, mode="suiveur")
    assert len(t.sorties) == 1                  # une seule sortie, de toute la position
    assert t.sorties[0].fraction == 1.0
    assert t.motif_final == "stop" and t.sorties[0].cours == 125


def test_suiveur_stop_break_even_apres_20_pct():
    barres = _bars([100, 121, 100])
    t = simuler_paliers(barres, 0, duree_max=250, mode="suiveur")
    assert t.motif_final == "stop" and t.sorties[0].cours == 100
    assert len(t.sorties) == 1


# ═════════════════════════════ pondération des frais (le piège évité) ════════════════

def test_rendement_net_pondere_les_frais_par_fraction_vendue():
    """Vendre en trois fois, c'est trois ordres : chaque fraction supporte SA part de
    frais. Ne pas le compter flatterait artificiellement les paliers."""
    t = TradePartiel(code="X", date_entree="2026-01-01", date_sortie="2026-01-04",
                     cours_entree=100, seances=3)
    t.sorties = [
        SortiePartielle(0.20, 1 / 3, "2026-01-02", 120, 0.20),
        SortiePartielle(0.35, 1 / 3, "2026-01-03", 135, 0.35),
        SortiePartielle(0.50, 1 / 3, "2026-01-04", 150, 0.50),
    ]
    attendu = sum(
        ((cours / 100) * (1 - FRAIS / 3) - 1) / 3 for cours in (120, 135, 150))
    assert t.rendement_net == pytest.approx(attendu)
    assert t.a_vendu_avant_fin is True


def test_a_vendu_avant_fin_faux_pour_une_sortie_unique():
    t = TradePartiel(code="X", date_entree="a", date_sortie="b", cours_entree=100, seances=1)
    t.sorties = [SortiePartielle(1.0, 1.0, "b", 90, 0.0)]
    assert t.a_vendu_avant_fin is False


def test_rendement_net_sans_cours_d_entree_vaut_zero():
    t = TradePartiel(code="X", date_entree="a", date_sortie="b", cours_entree=0, seances=1)
    assert t.rendement_net == 0.0


# ═════════════════════════════ comparer_modes / bilan ════════════════════════════════

def test_comparer_modes_meme_ensemble_de_signaux_pour_les_4_modes():
    series = {"A": _bars([100, 121, 136, 151]), "B": _bars([100, 84, 80])}
    signaux = [("A", 0), ("B", 0)]
    res = comparer_modes(series, signaux, duree_max=10)
    assert set(res) == {"duree", "paliers", "stop", "suiveur"}
    for mode, trades in res.items():
        assert len(trades) == 2, mode          # mêmes signaux pour tous les modes
        assert {t.code for t in trades} == {"A", "B"}
    # Le mode paliers a vendu le titre A en 3 fois, le mode duree en 1 fois.
    assert len(res["paliers"][0].sorties) == 3
    assert len(res["duree"][0].sorties) == 1


def test_comparer_modes_ignore_les_signaux_sans_historique():
    res = comparer_modes({"A": _bars([100, 110, 120])}, [("ZZ", 0), ("A", 0)], duree_max=2)
    assert all(len(trades) == 1 for trades in res.values())


def test_bilan_agrege_et_bilan_vide():
    assert bilan([]) == {"n": 0}
    trades = [
        simuler_paliers(_bars([100, 121, 136, 151]), 0, 10, "paliers"),
        simuler_paliers(_bars([100, 84]), 0, 10, "paliers"),
    ]
    b = bilan(trades)
    assert b["n"] == 2
    assert 0 <= b["taux_reussite"] <= 1
    assert b["pire_pct"] <= b["rendement_moyen_pct"] <= b["meilleur_pct"]


def test_collecter_signaux_suit_le_predicat():
    """collecter_signaux retient (code, index) partout où l'indicateur passe le prédicat."""

    class Serie:
        def __init__(self, indicateurs):
            self.indicateurs = indicateurs

    series = {"A": Serie([{"x": 1}, {"x": 5}, None]), "B": Serie([{"x": 9}])}
    signaux = collecter_signaux(series, lambda ind: ind["x"] > 4)
    assert signaux == [("A", 1), ("B", 0)]
