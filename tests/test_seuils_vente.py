"""Tests des seuils de vente sur plus-value — mode informatif et significativité.

Couvre les points de contrôle IMPÉRATIFS fixés le 08/10/2026 :
  1. les quatre seuils restent visibles en mode informatif ;
  2. le test de Wilson bloque les seuils insuffisamment significatifs SANS effacer les
     seuils historiques ;
  3. l'auto-calibrage respecte le mode ;
  4. les sorties fondamentales restent inchangées.
"""
import json
from pathlib import Path

import pytest

from src.portfolio import DividendPosition, check_dividend_position, status_level
from src.calibration.seuils_vente import (MODE_DECLENCHEUR, MODE_INFORMATIF, est_declencheur,
                              evaluer, intervalle_wilson, mode_pour)

RACINE = Path(__file__).resolve().parent.parent
FICHIER_SEUILS = RACINE / "data" / "profit_thresholds.json"
TITRES_HISTORIQUES = {"SNTS", "SGBC", "SLBC", "PALC"}


# --------------------------------------------------------------------------
#  Le test statistique lui-même
# --------------------------------------------------------------------------
def test_wilson_reste_dans_bornes():
    """Sur 7 cas à 86 %, l'intervalle normal sortirait de [0,1] ; Wilson non."""
    p, bas, haut = intervalle_wilson(6, 7)
    assert 0.0 <= bas < p < haut <= 1.0
    assert round(bas * 100) == 49        # borne basse mesurée sur SNTS


def test_wilson_cas_degenere():
    assert intervalle_wilson(0, 0) == (0.0, 0.0, 1.0)


def test_petit_echantillon_non_significatif():
    """86 % sur 7 cas ne suffit PAS : borne basse 49 % < 50 %."""
    r = evaluer(6, 7)
    assert r["down_prob"] == 86
    assert r["borne_basse"] == 49
    assert r["significatif"] is False
    assert r["mode"] == MODE_INFORMATIF


def test_grand_echantillon_large_devient_significatif():
    """Un vrai signal (grand n, probabilité élevée) doit passer."""
    r = evaluer(400, 500)                # 80 % sur 500 cas
    assert r["significatif"] is True
    assert r["mode"] == MODE_DECLENCHEUR


def test_echantillon_insuffisant_bloque_meme_avec_100_pourcent():
    """100 % sur 3 cas ne prouve rien — le garde-fou du nombre de cas tient."""
    r = evaluer(3, 3)
    assert r["significatif"] is False
    assert r["mode"] == MODE_INFORMATIF


# --------------------------------------------------------------------------
#  Contrôle 1 & 2 — les seuils historiques survivent et passent en informatif
# --------------------------------------------------------------------------
@pytest.mark.skipif(not FICHIER_SEUILS.exists(), reason="fichier de seuils absent")
def test_les_quatre_seuils_historiques_sont_conserves():
    """AUCUN seuil ne doit avoir été supprimé par la migration."""
    data = json.loads(FICHIER_SEUILS.read_text(encoding="utf-8"))
    assert TITRES_HISTORIQUES.issubset(set(data)), \
        f"seuils manquants : {TITRES_HISTORIQUES - set(data)}"
    for code in TITRES_HISTORIQUES:
        assert "threshold" in data[code], f"{code} a perdu son seuil"
        assert float(data[code]["threshold"]) > 0


@pytest.mark.skipif(not FICHIER_SEUILS.exists(), reason="fichier de seuils absent")
def test_les_quatre_seuils_sont_informatifs():
    """Mesure du 08/10 : aucune borne basse n'atteint 50 % -> aucun déclencheur."""
    data = json.loads(FICHIER_SEUILS.read_text(encoding="utf-8"))
    for code in TITRES_HISTORIQUES:
        assert data[code]["mode"] == MODE_INFORMATIF, f"{code} déclenche encore"
        assert est_declencheur(data[code]) is False


@pytest.mark.skipif(not FICHIER_SEUILS.exists(), reason="fichier de seuils absent")
def test_champs_de_significativite_presents():
    data = json.loads(FICHIER_SEUILS.read_text(encoding="utf-8"))
    for code, info in data.items():
        for champ in ("borne_basse", "episodes", "significatif", "mode"):
            assert champ in info, f"{code} : champ {champ} absent"


def test_seuil_ancien_sans_mode_est_informatif():
    """Un seuil hérité (sans champ mode) ne doit jamais déclencher une vente."""
    ancien = {"code": "XXXX", "threshold": 0.10, "down_prob": 90, "episodes": 30}
    assert mode_pour(ancien) == MODE_INFORMATIF
    assert est_declencheur(ancien) is False


def test_mode_explicite_est_respecte():
    """Le mode écrit est souverain : c'est ce qui empêche l'auto-calibrage de revenir."""
    assert mode_pour({"mode": MODE_DECLENCHEUR}) == MODE_DECLENCHEUR
    assert mode_pour({"mode": MODE_INFORMATIF}) == MODE_INFORMATIF
    assert mode_pour(None) == MODE_INFORMATIF


# --------------------------------------------------------------------------
#  Contrôle 3 — l'alerte de plus-value n'ordonne plus la vente
# --------------------------------------------------------------------------
def _position(code="PALC", entry=8000.0):
    return DividendPosition(code=code, name="PALM CI", entry_price=entry,
                            quantity=10, dps=430.0, per_open=11.0)


def test_alerte_pv_ne_propose_pas_de_vente_si_informatif():
    pos = _position()
    prix = pos.entry_price * 1.20            # +20 %, largement au-dessus du seuil
    alertes = check_dividend_position(pos, prix, current_dps=pos.dps, current_per=11.0)
    texte = "\n".join(a.message for a in alertes)
    assert "INFO" in texte
    assert "VENDS 1/3" not in texte
    assert "RIEN À FAIRE" in texte


def test_alerte_pv_explique_en_langage_courant():
    """Règle de style néophyte : dire POURQUOI, sans jargon statistique."""
    pos = _position()
    prix = pos.entry_price * 1.20
    texte = "\n".join(a.message for a in check_dividend_position(pos, prix))
    assert "pile ou face" in texte, "le repère du hasard doit être explicite"
    assert "rebaissé" in texte, "la raison doit être dite en clair"
    # Aucun terme technique ne doit rester nu dans le message.
    for jargon in ("borne basse", "NON significatif", "indiscernable"):
        assert jargon not in texte, f"jargon non traduit : {jargon}"


def test_console_distingue_info_et_declenchement():
    pos = _position()
    niveau, libelle = status_level(pos, pos.entry_price * 1.20)
    assert "info" in libelle.lower()
    assert "VENDS" not in libelle


# --------------------------------------------------------------------------
#  Contrôle 4 — les sorties FONDAMENTALES sont intactes
# --------------------------------------------------------------------------
def test_dividende_coupe_declenche_toujours_la_vente_totale():
    pos = _position()
    alertes = check_dividend_position(pos, pos.entry_price, current_dps=0.0)
    assert pos.closed is True
    assert any("VENDS TOUT" in a.message for a in alertes)


def test_per_explose_declenche_toujours_la_vente_totale():
    pos = _position()
    alertes = check_dividend_position(pos, pos.entry_price, current_dps=pos.dps,
                                      current_per=99.0)
    assert pos.closed is True
    assert any("VENDS TOUT" in a.message for a in alertes)


def test_prix_de_sortie_declenche_toujours_la_vente_totale():
    pos = _position()
    alertes = check_dividend_position(pos, pos.exit_price * 1.05,
                                      current_dps=pos.dps, current_per=11.0)
    assert pos.closed is True
    assert any("VENDS TOUT" in a.message for a in alertes)
