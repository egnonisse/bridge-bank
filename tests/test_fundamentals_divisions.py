"""Tests de l'ajustement du dividende par action (dps) après une division de nominal.

Incident mesuré le 02/11/2026 (cas SNTS) : le dps 1 977 F (déclaré le 23/04/2026, donc en
base ANCIENNE) était comparé à un cours passé en base nouvelle (4 350 F après la division
10 pour 1 du 26/10/2026). Payout calculé = 1977 × 10.4 / 4350 = 473 % — fausse alerte
« risque de coupe du dividende » sur le titre le plus performant du portefeuille.
Le vrai payout est 47 % (dps 197.70).

AUCUN accès réseau : tout est pur ou monkeypatché (leçon du 30/10/2026 : un test qui touche
le réseau bloque des dizaines de secondes par appel quand le site ne répond pas).
"""
import json

import pytest

from src.collecte import divisions_officielles as do
from src.collecte import fundamentals as fm


# ═════════════════════ ajuster_dps_division (contrôle de vraisemblance) ═════════════════

def test_nominal_snts_1977_et_facteur_10_donne_197_70():
    """Cas SNTS : 1977 F (45 % brut sur un cours de 4 350 F) × facteur 10 -> 197.70."""
    assert fm.ajuster_dps_division(1977.0, 4350.0, 10.0) == pytest.approx(197.70)


def test_sans_division_valeur_inchangee():
    """Facteur 1.0 (ou None) : aucune division postérieure, on ne touche à rien."""
    assert fm.ajuster_dps_division(1977.0, 4350.0, 1.0) == 1977.0
    assert fm.ajuster_dps_division(1977.0, 4350.0, None) == 1977.0
    assert fm.ajuster_dps_division(500.0, 4000.0, 0.5) == 500.0  # regroupement : pas un split


def test_gros_payeur_12pct_sans_division_pas_divise():
    """12 % brut SANS division : rendement plausible, jamais divisé."""
    assert fm.ajuster_dps_division(600.0, 5000.0, 1.0) == 600.0


def test_gros_payeur_12pct_avec_division_pas_divise():
    """12 % brut AVEC division : le rendement est plausible -> le dps est déjà en base
    nouvelle (dividende déclaré après la division, ou source déjà ajustée). Ne PAS diviser :
    c'est le garde-fou contre la correction à tort d'un titre qui paie vraiment."""
    assert fm.ajuster_dps_division(600.0, 5000.0, 10.0) == 600.0


def test_40pct_avec_division_ajuste():
    """40 % brut AVEC division : incohérence de base (pas une aubaine) -> divisé."""
    assert fm.ajuster_dps_division(2000.0, 5000.0, 10.0) == pytest.approx(200.0)


def test_donnees_absentes_ou_nulles_inchangees():
    assert fm.ajuster_dps_division(None, 5000.0, 10.0) is None
    assert fm.ajuster_dps_division(0.0, 5000.0, 10.0) == 0.0
    assert fm.ajuster_dps_division(1977.0, None, 10.0) == 1977.0
    assert fm.ajuster_dps_division(1977.0, 0.0, 10.0) == 1977.0
    assert fm.ajuster_dps_division(1977.0, -100.0, 10.0) == 1977.0


def test_seuil_exact_15pct_est_plausible():
    """À exactement 15 % brut : le rendement est encore plausible, on ne touche pas."""
    assert fm.ajuster_dps_division(150.0, 1000.0, 10.0) == 150.0


# ═════════════════════ facteur_division_posterieure (lecture des divisions) ═══════════

def _fichier(tmp_path, divisions):
    chemin = tmp_path / "divisions_test.json"
    chemin.write_text(json.dumps({"divisions": divisions}), encoding="utf-8")
    return chemin


def test_facteur_posterieur_au_dividende(tmp_path):
    chemin = _fichier(tmp_path, [
        {"code": "SNTS", "date": "2026-10-26", "nouvelles": 10, "anciennes": 1},
        {"code": "SNTS", "date": "2017-01-05", "nouvelles": 10, "anciennes": 1},  # antérieure
    ])
    # dividende 2026-04-23 : seule la division du 26/10 est postérieure -> ×10
    assert fm.facteur_division_posterieure("SNTS", "2026-04-23", chemin) == 10.0


def test_facteur_aucune_division_posterieure(tmp_path):
    chemin = _fichier(tmp_path, [
        {"code": "BOAS", "date": "2017-10-30", "nouvelles": 10, "anciennes": 1},
    ])
    # dividende 2026-05-08 : la division de 2017 est ANTÉRIEURE -> facteur 1 (inchangé)
    assert fm.facteur_division_posterieure("BOAS", "2026-05-08", chemin) == 1.0


def test_facteur_sans_date_dividende():
    assert fm.facteur_division_posterieure("XXX", None) == 1.0
    assert fm.facteur_division_posterieure("XXX", "") == 1.0


def test_facteur_cumule_deux_divisions(tmp_path):
    chemin = _fichier(tmp_path, [
        {"code": "A", "date": "2026-06-01", "nouvelles": 5, "anciennes": 1},
        {"code": "A", "date": "2026-09-01", "nouvelles": 2, "anciennes": 1},
    ])
    assert fm.facteur_division_posterieure("A", "2026-01-01", chemin) == 10.0


def test_facteur_fiche_mal_formee_leve(tmp_path):
    """Garde-fou B2-16 : une fiche au mauvais schéma (n/m) doit LEVER, jamais être avalée."""
    chemin = _fichier(tmp_path, [{"code": "SNTS", "date": "2026-10-26", "n": 10, "m": 1}])
    with pytest.raises(ValueError):
        fm.facteur_division_posterieure("SNTS", "2026-04-23", chemin)


def test_facteur_fichier_absent_leve(tmp_path):
    """Doctrine B2-05 : fichier des divisions introuvable -> échec bruyant, pas de repli."""
    with pytest.raises(FileNotFoundError, match="Indispensable"):
        fm.facteur_division_posterieure("SNTS", "2026-04-23", tmp_path / "absent.json")


# ═════════════════════ get_fundamentals : le dps exposé est ajusté ═════════════════════

def test_get_fundamentals_snts_expose_dps_ajuste(monkeypatch):
    """Aucun réseau : PER et facteur injectés. get_dps sert OFFICIAL_DPS (1977.0 brut)
    et get_fundamentals le ré-exprime en base nouvelle."""
    monkeypatch.setattr(fm, "get_per_brvm", lambda code: 10.4)
    monkeypatch.setattr(fm, "facteur_division_posterieure",
                        lambda code, date, chemin=None: 10.0)
    res = fm.get_fundamentals("SNTS")
    assert res["code"] == "SNTS"
    assert res["dps"] == pytest.approx(197.70)
    assert res["per"] == 10.4


def test_get_fundamentals_snts_avec_fichier_reel(monkeypatch):
    """Preuve bout-en-bout sur les données réelles : OFFICIAL_DPS 1977.0 + division
    2026-10-26 (×10) lue dans data/divisions_officielles.json -> dps 197.70.
    Lecture locale uniquement, aucun réseau."""
    monkeypatch.setattr(fm, "get_per_brvm", lambda code: 10.4)
    res = fm.get_fundamentals("SNTS")
    assert res["dps"] == pytest.approx(197.70)


def test_get_fundamentals_titre_sans_division_inchange(monkeypatch):
    """Un titre officiel dont la division est ANTÉRIEURE au dividende reste brut."""
    monkeypatch.setattr(fm, "get_per_brvm", lambda code: None)
    # BOAS : avis 2026-05-08, division 2017-10-30 (antérieure) -> facteur 1, dps 511 brut.
    res = fm.get_fundamentals("BOAS")
    assert res["dps"] == 511.0
