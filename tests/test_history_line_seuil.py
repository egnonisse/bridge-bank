"""Tests de la ligne « 📜 LES AUTRES FOIS » — elle doit dire sur QUOI elle porte.

POURQUOI CE FICHIER EXISTE
--------------------------
La ligne affichait « après une hausse de 13 % » **écrit en dur**, alors que le seuil du
titre vaut 13 % (SNTS), 10 % (SGBC) ou 5 % (SLBC, PALC). Trois titres sur quatre recevaient
donc l'affirmation d'un seuil qui n'était pas le leur — et pour SLBC, la statistique
affichée (39 %, mesurée à +13 %) disait même l'**inverse** de la sienne (51 % à 5 %).

Ces tests empêchent le retour du littéral : ils vérifient que la phrase parle bien du titre
concerné, et qu'elle avoue sa référence quand elle en diffère.
"""
import json

import pytest

from src import portfolio as pf


def _profil(episodes=10, pct_down=90, median_20=-3.3, delay=44, depth=-14.2,
            seuil=13, fiable=False, borne=60):
    return {"seuil_pct": seuil, "significatif": fiable, "borne_basse": borne,
            "episodes": episodes, "pct_down_20j": pct_down, "median_5j": -1.0,
            "median_20j": median_20, "median_60j": -8.4, "trough_delay_median": delay,
            "trough_depth_median": depth, "trough_depth_worst": -22.8}


@pytest.fixture
def profil_snts(tmp_path, monkeypatch):
    """Profil de référence + seuils : SNTS à 13 %, SGBC à 10 %."""
    prof = tmp_path / "reversal.json"
    prof.write_text(json.dumps({
        "_meta": {"min_episodes": 8},
        "SNTS": _profil(episodes=10, pct_down=90, seuil=13),
        "SGBC": _profil(episodes=26, pct_down=62, median_20=-1.8, delay=38,
                        depth=-8.4, seuil=10),
    }), encoding="utf-8")

    seuils = tmp_path / "seuils.json"
    seuils.write_text(json.dumps({
        "SNTS": {"threshold": 0.13, "down_prob": 86, "episodes": 7},
        "SGBC": {"threshold": 0.10, "down_prob": 63, "episodes": 30},
    }), encoding="utf-8")

    monkeypatch.setattr(pf, "REVERSAL_FILE", prof)
    from src.calibration import seuils_vente as sv
    monkeypatch.setattr(sv, "SEUILS_FILE", seuils)
    return prof


def _pos(code):
    return pf.DividendPosition(code=code, name=code, entry_price=1000.0, quantity=3,
                               dps=200.0, per_open=10.0)


def test_le_seuil_affiche_est_celui_du_titre(tmp_path, monkeypatch):
    """Un profil PÉRIMÉ (mesuré à un autre seuil que celui du titre) doit le DIRE.

    Depuis l'unification, les profils sont générés au seuil de leur titre : ce cas ne
    devrait plus arriver. Il reste testé parce qu'un profil peut être régénéré à un autre
    seuil, ou survivre à un changement de seuil — et laisser croire qu'il porte le seuil du
    titre serait alors une affirmation fausse.
    """
    prof = tmp_path / "reversal.json"
    prof.write_text(json.dumps({
        "_meta": {"min_episodes": 8},
        "SNTS": _profil(seuil=10, episodes=26),   # profil mesuré à +10 %
    }), encoding="utf-8")
    monkeypatch.setattr(pf, "REVERSAL_FILE", prof)

    ligne = pf._history_line(_pos("SNTS"))
    assert "repère mesuré à +10 %" in ligne, (
        "le seuil du PROFIL doit être nommé comme tel")
    assert "ton seuil est 13 %" in ligne, (
        "le message doit dire à l'utilisateur quel est SON seuil")


def test_quand_les_seuils_correspondent_la_phrase_est_naturelle(profil_snts):
    """SNTS est à 13 %, le profil aussi : pas besoin d'avertissement."""
    ligne = pf._history_line(_pos("SNTS"))
    assert "après une hausse de 13 %" in ligne
    assert "ton seuil est" not in ligne, (
        "aucun avertissement quand le seuil du titre EST celui du profil")


def test_le_seuil_du_profil_est_lu_dans_sa_source(tmp_path, monkeypatch):
    """Le seuil du profil est PORTÉ PAR LE PROFIL, jamais un littéral dans le code.

    Si un profil est régénéré à un autre seuil que celui du titre (par exemple après un
    calibrage), le message suit SANS modification du code — et si le profil est périmé, il
    le dit au lieu de laisser croire qu'il s'agit du seuil du titre.
    """
    prof = tmp_path / "reversal.json"
    prof.write_text(json.dumps({
        "_meta": {"min_episodes": 8},
        "SNTS": _profil(seuil=10),          # profil mesuré à +10 %
    }), encoding="utf-8")
    monkeypatch.setattr(pf, "REVERSAL_FILE", prof)

    ligne = pf._history_line(_pos("SNTS"))
    assert "repère mesuré à +10 %" in ligne, (
        "le seuil du profil doit être lu depuis la donnée, pas écrit dans le code")
    assert "ton seuil est 13 %" in ligne, "SNTS garde son seuil de 13 %"


def test_le_nombre_de_cas_est_affiche(profil_snts):
    """Le compte évite la fausse contradiction avec le seuil de vente.

    SNRTS : le seuil annonce « 86 % sur 7 cas », le profil « 90 % sur 10 cas ». Sans le
    nombre de cas, le lecteur croit à une incohérence ; avec lui, il voit deux mesures.
    """
    ligne = pf._history_line(_pos("SNTS"))
    assert "10 cas" in ligne, "le nombre de cas du profil doit être affiché"


def test_pas_de_jargon_dans_la_ligne(profil_snts):
    """Règle de style (03/09/2026) : le lecteur n'a jamais touché à la bourse."""
    ligne = pf._history_line(_pos("SGBC")).lower()
    for mot in ("borne", "significatif", "indiscernable", "médiane", "séance",
                "percentile", "écart-type"):
        assert mot not in ligne, f"jargon dans une alerte utilisateur : {mot}"


def test_le_seuil_nest_pas_ecrit_en_dur_dans_le_code():
    """Garde-fou statique : le motif fautif ne doit pas revenir dans la source.

    Le test est volontairement textuel : il cherche l'ancienne formulation littérale.
    """
    source = (pf.__file__)
    from pathlib import Path

    texte = Path(source).read_text(encoding="utf-8")
    assert "après une hausse de 13 % en" not in texte, (
        "le seuil 13 % est réapparu ÉCRIT EN DUR dans le message (au lieu d'être lu)")


def test_titre_absent_du_profil_ne_plante_pas(profil_snts):
    assert pf._history_line(_pos("INCONNU")) == ""
