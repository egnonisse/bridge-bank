"""Point d'entrée : la position du prix dans l'historique (30/10/2026).

Constat fondateur : PALC acheté au 78e percentile d'un titre PLAT (+1,3 %/an, −44 % sous
son ATH) alors que les 8 filtres du noyau ne regardaient que le dividende. Coût mesuré :
avec le même capital, 36 actions au prix médian au lieu de 26 (+39 % de loyer).

Ce qui est verrouillé ici :
- un titre PLAT acheté haut est SIGNALÉ (« prude » / « cher ») ;
- un titre en CROISSANCE reste « normal même à 99e percentile (SGBC 98e à +11,2 %/an) —
  sans ce garde-fou, l'indicateur ferait vendre ses meilleurs titres ;
- un historique trop court ne produit AUCUN verdict (jamais d'extrapolation) ;
- le bloc affiche l'ÉCART À LA MÉDIANE, jamais un « loyer au prix médian » qui
  appliquerait le dps d'aujourd'hui à un prix d'il y a huit ans.
"""
from datetime import datetime, timedelta

from src.domaine.models import HistoryBar
from src.strategie.noyau_check import bloc_point_entree, point_entree
from src.taxation import net_yield


def _barres(closes):
    """HistoryBar quotidiennes consécutives (dates réalistes, 1 séance/jour)."""
    base = datetime(2018, 1, 2)
    return [HistoryBar(date=base + timedelta(days=i), open=c, high=c, low=c, close=c,
                       volume=100) for i, c in enumerate(closes)]


def _hist(closes, code="TEST"):
    return {code: _barres(closes)}


# Un titre PLAT : premier et dernier cours IDENTIQUES (tendance nulle), avec un palier
# haut au milieu — sinon la tendance calculée premier→dernier ne serait pas « plate ».
PLAT = [100.0] * 150 + [120.0] * 75 + [100.0] * 75
# Un titre en CROISSANCE : de 10 à 100, tendance franche.
CROISSANCE = [10.0 + i * (90.0 / 299) for i in range(300)]


def test_titre_plat_achete_haut_est_signale():
    """PALC-like : plat, prix au-dessus de TOUTE la distribution -> « cher »."""
    pe = point_entree("TEST", 130.0, _hist(PLAT))
    assert pe is not None
    assert pe["percentile"] >= 85
    assert pe["verdict"] == "cher"
    assert "ACHAT TARDIF" in pe["phrase"]


def test_titre_plat_point_entree_moyen_haut():
    """Zone 70-85 : « prude » — le cas exact du PALC acheté à 8 641 F (78e)."""
    pe = point_entree("TEST", 120.0, _hist(PLAT))   # 225/300 séances sous 120 = 75e
    assert pe is not None and 70 <= pe["percentile"] < 85
    assert pe["verdict"] == "prude"


def test_titre_en_croissance_reste_normal_malgre_un_percentile_eleve():
    """Le garde-fou qui évite de condamner ses meilleurs titres (SGBC 98e, +11 %/an)."""
    pe = point_entree("TEST", 100.0, _hist(CROISSANCE))
    assert pe is not None
    assert pe["percentile"] >= 95          # prix au sommet de sa distribution…
    assert pe["tendance"] > 6.0
    assert pe["verdict"] == "normal"       # …et pourtant normal : il monte
    assert "croissance" in pe["phrase"]


def test_historique_trop_court_ne_produit_aucun_verdict():
    """Moins de 250 séances : None (jamais d'extrapolation sur un historique court)."""
    assert point_entree("TEST", 100.0, _hist([100.0] * 200)) is None
    assert point_entree("INCONNU", 100.0, _hist(PLAT)) is None   # titre absent du cache
    assert point_entree("TEST", 100.0, None) is None             # hist non fourni
    assert bloc_point_entree(None, 500.0, 100.0) == ""


def test_bloc_affiche_l_ecart_a_la_mediane_pas_un_loyer_fictif():
    """SGBC affichait « au prix médian 16,2 % » — faux (dps d'aujourd'hui sur un prix de
    2018). Le bloc doit donner l'écart au prix médian, pas un rendement rétro-calculé."""
    pe = point_entree("TEST", 115.0, _hist(PLAT))
    bloc = bloc_point_entree(pe, 10.0, 115.0)
    assert "vs la médiane historique" in bloc
    assert "au prix médian" not in bloc
    # le seul rendement affiché est celui du prix courant, calculé avec la vraie formule
    assert f"{net_yield(10.0 / 115.0) * 100:.1f} % net" in bloc
