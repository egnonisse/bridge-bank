"""Tests des divisions officielles de nominal (point de défaillance silencieux).

Pourquoi ce fichier existe (priorité n°2 de la passation du 12/10/2026) : une erreur
d'ajustement ici fausse **tous** les rendements longs — sans crier. Le module était à
0 % de couverture ; ces tests portent sur la logique réelle (`charger`, `utiles`,
`appliquer`, `ajuster_barres`, `ajuster_historique`), pas sur une table.

Les barres de test sont des `HistoryBar` (datetime) comme partout dans le projet.
"""
import json
from datetime import datetime

import pytest

from src.collecte import divisions_officielles as do
from src.domaine.models import HistoryBar


def _barre(date_iso, close, volume=100):
    d = datetime.fromisoformat(date_iso)
    return HistoryBar(date=d, open=close, high=close, low=close, close=close, volume=volume)


def _fichier(tmp_path, divisions, cours_reels=None):
    chemin = tmp_path / "divisions_test.json"
    donnees = {"divisions": divisions}
    if cours_reels is not None:
        donnees["cours_reels_07_10_2026"] = cours_reels
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    return chemin


DIVS = [
    {"code": "snts", "date": "2026-01-10", "nouvelles": 10, "anciennes": 1},   # facteur déduit 10
    {"code": "SNTS", "date": "2026-01-20", "nouvelles": 1, "anciennes": 1},    # neutre : ignorée
    {"code": "X", "date": "2026-01-15", "nouvelles": 2, "anciennes": 1, "facteur": 2.0},
]


# ═════════════════════════════════ charger ══════════════════════════════════════════

def test_charger_groupes_et_tries(tmp_path):
    par_code = do.charger(_fichier(tmp_path, DIVS))
    assert set(par_code) == {"SNTS", "X"}          # codes normalisés en MAJUSCULES
    assert len(par_code["SNTS"]) == 1               # la neutre (1 pour 1) est écartée
    assert par_code["SNTS"][0].facteur == 10.0      # facteur déduit de nouvelles/anciennes
    assert par_code["X"][0].facteur == 2.0


def test_charger_trie_par_date(tmp_path):
    divs = [
        {"code": "A", "date": "2026-03-01", "nouvelles": 2, "anciennes": 1},
        {"code": "A", "date": "2026-01-01", "nouvelles": 5, "anciennes": 1},
    ]
    par_code = do.charger(_fichier(tmp_path, divs))
    assert [o.date for o in par_code["A"]] == ["2026-01-01", "2026-03-01"]


def test_charger_fichier_absent_echoue_bruyamment(tmp_path):
    """Le message doit dire POURQUOI c'est indispensable (pas un OSError nu)."""
    with pytest.raises(FileNotFoundError, match="Indispensable"):
        do.charger(tmp_path / "absent.json")


def test_sens_et_type_d_une_operation():
    division = do.Operation("A", "2026-01-01", 10.0, 10, 1)
    regroupement = do.Operation("B", "2026-01-01", 0.5, 1, 2)
    assert division.type == "division" and regroupement.type == "regroupement"
    assert division.sens == "10 nouvelles pour 1 ancienne(s)"


# ═════════════════════════════════ utiles (périmètre) ═══════════════════════════════

def test_utiles_ignore_les_operations_anterieures_au_debut():
    """Règle de périmètre : une division de 2013 n'affecte pas un historique qui
    commence en 2017 (le cours de départ est déjà post-division)."""
    ops = [do.Operation("A", "2025-06-01", 10.0, 10, 1),
           do.Operation("A", "2026-06-01", 2.0, 2, 1)]
    retenues = do.utiles(ops, "2026-01-01")
    assert [o.date for o in retenues] == ["2026-06-01"]


def test_utiles_sans_date_debut_garde_tout():
    ops = [do.Operation("A", "2025-06-01", 10.0, 10, 1)]
    assert do.utiles(ops, "") == ops


# ═════════════════════════════════ appliquer ════════════════════════════════════════

def test_appliquer_divise_le_passe_et_laisse_le_present():
    """Barres AVANT la division : cours / facteur, volume x facteur.
    Barres À PARTIR de la date (>=) : intactes."""
    barres = [_barre("2026-01-01", 1000, 50), _barre("2026-01-09", 1000, 50),
              _barre("2026-01-10", 100, 500), _barre("2026-01-12", 100, 500)]
    n = do.appliquer(barres, [do.Operation("A", "2026-01-10", 10.0, 10, 1)])
    assert n == 1
    assert [b.close for b in barres] == [100.0, 100.0, 100.0, 100.0]
    assert barres[0].volume == 500 and barres[1].volume == 500   # le passé est ré-échelonné
    assert barres[2].volume == 500                                # le présent est intact
    # OHLC ajusté aussi (pas seulement la clôture)
    assert barres[0].open == 100.0 and barres[0].high == 100.0 and barres[0].low == 100.0


def test_appliquer_cumule_deux_divisions():
    """Deux opérations sur le même titre se composent : le passé subit les deux."""
    barres = [_barre("2026-01-01", 1000), _barre("2026-06-01", 500), _barre("2026-12-01", 100)]
    do.appliquer(barres, [do.Operation("A", "2026-06-01", 5.0, 5, 1),
                          do.Operation("A", "2026-12-01", 5.0, 5, 1)])
    assert barres[0].close == pytest.approx(1000 / 25)
    assert barres[1].close == pytest.approx(500 / 5)
    assert barres[2].close == 100


def test_appliquer_sans_operations_ou_sans_barres():
    assert do.appliquer([_barre("2026-01-01", 100)], []) == 0
    assert do.appliquer([], [do.Operation("A", "2026-01-01", 2.0, 2, 1)]) == 0


# ═════════════════════════════════ ajuster_barres ═══════════════════════════════════

def test_ajuster_barres_ne_modifie_jamais_l_entree():
    """Invariant central : l'appelant garde ses barres d'origine intactes."""
    barres = [_barre("2026-01-01", 1000), _barre("2026-01-10", 100)]
    copie = do.ajuster_barres(barres, [do.Operation("A", "2026-01-10", 10.0, 10, 1)])
    assert copie[0].close == 100.0            # l'ajustement porte sur la COPIE
    assert barres[0].close == 1000.0          # l'original est intact
    assert copie[1].close == barres[1].close == 100.0


def test_ajuster_barres_perimetre_par_defaut_au_premier_jour():
    """Sans date_debut explicite, le périmètre part du premier jour de la série."""
    barres = [_barre("2026-01-05", 1000), _barre("2026-01-20", 1000)]
    ops = [do.Operation("A", "2026-01-01", 10.0, 10, 1),   # AVANT le début : ignorée
           do.Operation("A", "2026-01-10", 10.0, 10, 1)]   # active
    copie = do.ajuster_barres(barres, ops)
    assert copie[0].close == 100.0    # ajustée par la 2e opération seulement
    assert copie[1].close == 1000.0


# ═════════════════════════════════ ajuster_historique ═══════════════════════════════

def test_ajuster_historique_rapport_et_perimetre(tmp_path):
    hist = {
        "SNTS": [_barre("2026-01-05", 1000), _barre("2026-01-15", 100)],
        "AUTRE": [_barre("2026-01-05", 200)],
    }
    # La division du 10/01 a lieu APRÈS le début de l'historique SNTS -> active (×10).
    res = do.ajuster_historique(hist, _fichier(tmp_path, DIVS))
    assert res["nb_titres_ajustes"] == 1
    assert res["sans_division"] == ["AUTRE"]
    assert res["rapport"][0]["code"] == "SNTS"
    assert res["rapport"][0]["facteur_cumule"] == 10.0
    assert res["historique"]["SNTS"][0].close == 100.0
    assert hist["SNTS"][0].close == 1000.0            # l'entrée n'est pas modifiée


def test_ajuster_historique_sans_fichier_reference():
    """Fichier absent -> aucune division appliquée, pas de plantage."""
    res = do.ajuster_historique({"A": [_barre("2026-01-01", 100)]},
                                chemin=__import__("pathlib").Path("fichier_absent_xyz.json"))
    assert res["nb_titres_ajustes"] == 0
    assert res["sans_division"] == ["A"]


# ═════════════════════════════════ cours_reels ══════════════════════════════════════

def test_cours_reels_parse_les_espaces(tmp_path):
    chemin = _fichier(tmp_path, [], cours_reels={"SNTS": "42 995", "SGBC": "38 400"})
    assert do.cours_reels(chemin) == {"SNTS": 42995, "SGBC": 38400}


def test_cours_reels_valeur_illisible_ignoree(tmp_path):
    chemin = _fichier(tmp_path, [], cours_reels={"SNTS": "n/a", "SGBC": "38 400"})
    assert do.cours_reels(chemin) == {"SGBC": 38400}
