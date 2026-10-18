"""Tests du régime de marché et de l'alerte de trésorerie.

Couvre les points de contrôle IMPÉRATIFS du 08/10/2026 :
  3. le renforcement dépend d'un indicateur EXPLICITEMENT défini, calculé sur des
     données disponibles ;
  4. l'alerte de trésorerie est informative et ne déclenche aucun investissement ;
  5. le renforcement n'est jamais bloqué (règle LEO « ne bloque pas »).
"""
import json
from pathlib import Path

import pytest

from src.portfolio import DividendPosition, reinforcement_messages
from src.calibration.regime_marche import (BAISSIER, FENETRE, HAUSSIER, construire_indice,
                              etat_marche)
from src.report import TARGET_CASH, alerte_tresorerie
from src.infrastructure.paths import HISTORY_CACHE  # noqa: E402  (B2-09)

RACINE = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
#  Contrôle 3 — l'indicateur est défini, calculé, et cohérent
# --------------------------------------------------------------------------
def _series_simple():
    """Trois titres qui montent, pour un cas entièrement contrôlable."""
    return {
        "AAA": {"2026-01-01": 100.0, "2026-01-02": 110.0, "2026-01-03": 120.0},
        "BBB": {"2026-01-01": 50.0, "2026-01-02": 55.0, "2026-01-03": 60.0},
        "CCC": {"2026-01-01": 10.0, "2026-01-02": 11.0, "2026-01-03": 12.0},
        "DDD": {"2026-01-01": 200.0, "2026-01-02": 220.0, "2026-01-03": 240.0},
        "EEE": {"2026-01-01": 30.0, "2026-01-02": 33.0, "2026-01-03": 36.0},
    }


def test_indice_median_est_en_buy_and_hold():
    """Méthode buy & hold : si TOUT monte de 20 %, l'indice monte de 20 %."""
    idx = construire_indice(_series_simple())
    assert idx[0][1] == pytest.approx(100.0)
    assert idx[-1][1] == pytest.approx(120.0)


def test_indice_ignore_les_valeurs_extremes():
    """Un titre qui bondit x100 ne déplace pas la médiane (contrairement à la moyenne)."""
    series = _series_simple()
    series["ZZZ"] = {"2026-01-01": 1.0, "2026-01-02": 50.0, "2026-01-03": 100.0}
    idx = construire_indice(series)
    assert idx[-1][1] == pytest.approx(120.0)      # inchangé par l'aberration


def test_etat_marche_est_traçable():
    """Le régime n'est pas un booléen nu : il porte ses chiffres."""
    etat = etat_marche(_series_simple())
    assert etat["etat"] in (HAUSSIER, BAISSIER)
    assert "valeur" in etat and "moyenne" in etat and "ecart_pct" in etat


def test_historique_insuffisant_ne_plante_pas():
    etat = etat_marche({"AAA": {"2026-01-01": 100.0}})
    assert etat["etat"] in (HAUSSIER, BAISSIER)


def _cache_historique_minimal(tmp_path):
    """Faux cache historique (propre, avec sidecar) pour les tests du régime du jour."""
    from types import SimpleNamespace

    from src.collecte.history_io import ecrire_cache

    hist = tmp_path / "h.pkl"
    ecrire_cache(hist, {"AAA": [SimpleNamespace(date="2026-01-01", close=100.0)]})
    return hist


def test_regime_du_jour_recalcule_si_le_cache_historique_change(tmp_path):
    """P6-04 : un « régime du jour » calculé sur un AUTRE cache n'est PAS réutilisé.

    Le cas réel : le cache de cours est corrigé/régénéré dans la journée — le régime
    calculé le matin porte l'empreinte de l'ancien cache et doit être recalculé.
    """
    from datetime import date

    from src.calibration.regime_marche import regime_du_jour
    from src.collecte.history_io import lire_sha

    hist = _cache_historique_minimal(tmp_path)
    cache = tmp_path / "r.json"
    cache.write_text(json.dumps({
        "calcule_le": date.today().isoformat(), "raison": "POISON", "_cache_sha": "périmé",
    }), encoding="utf-8")

    etat = regime_du_jour(chemin_hist=hist, chemin_cache=cache)

    assert etat.get("raison") != "POISON"          # recalculé, pas servi du cache
    assert json.loads(cache.read_text(encoding="utf-8")).get("_cache_sha") == lire_sha(hist)


def test_regime_du_jour_reutilise_un_cache_du_meme_cache(tmp_path):
    """Voie nominale : même jour + même empreinte → le cache disque est servi tel quel."""
    from datetime import date

    from src.calibration.regime_marche import regime_du_jour
    from src.collecte.history_io import lire_sha

    hist = _cache_historique_minimal(tmp_path)
    cache = tmp_path / "r.json"
    cache.write_text(json.dumps({
        "calcule_le": date.today().isoformat(), "raison": "SENTINELLE",
        "_cache_sha": lire_sha(hist),
    }), encoding="utf-8")

    etat = regime_du_jour(chemin_hist=hist, chemin_cache=cache)

    assert etat.get("raison") == "SENTINELLE"      # servi sans recalcul


@pytest.mark.skipif(not (HISTORY_CACHE).exists(),
                    reason="cache quotidien absent")
def test_indice_reel_monte_et_creuse_en_2020():
    """Contrôle de vraisemblance sur les vraies données.

    Si l'indice baissait sur 2017-2026 (ce que faisait la version à rebalancement
    quotidien, via le volatility drag), il serait inutilisable pour décider.
    """
    from src.calibration.regime_marche import charger_series_quotidiennes

    series = charger_series_quotidiennes(HISTORY_CACHE)
    idx = construire_indice(series)
    assert idx[-1][1] > idx[0][1], "l'indice doit monter sur la période"
    creux = min(v for _, v in idx)
    assert creux < 60, "un creux profond doit apparaître (2018-2020)"
    assert FENETRE > 0


# --------------------------------------------------------------------------
#  Contrôle 5 — le renforcement n'est JAMAIS bloqué (il est documenté)
# --------------------------------------------------------------------------
def _pos(code="SNTS", entry=32435.0, qty=6):
    return DividendPosition(code=code, name="SONATEL", entry_price=entry,
                            quantity=qty, dps=1977.0, per_open=9.0)


def _prix_factory(portefeuille, prix):
    return lambda code: prix


def test_renforcement_part_toujours_regime_absent():
    pos = _pos()
    prix = pos.dps / 0.054545 / 1.014 * 0.95          # sous le seuil d'entrée
    hits, blocked = reinforcement_messages([pos], _prix_factory(None, prix),
                                           lambda c: 9.0, 500000.0, regime=None)
    assert hits, "le renforcement doit partir même sans indicateur de marché"
    assert blocked == []


def test_renforcement_part_toujours_en_marche_haussier():
    """Règle LEO : informer, jamais bloquer — même dans le régime défavorable."""
    pos = _pos()
    prix = pos.dps / 0.054545 / 1.014 * 0.95
    regime = {"etat": HAUSSIER, "ecart_pct": 12.7, "points": 200}
    hits, blocked = reinforcement_messages([pos], _prix_factory(None, prix),
                                           lambda c: 9.0, 500000.0, regime=regime)
    assert hits, "l'alerte ne doit PAS être supprimée en marché haussier"
    assert blocked == []
    assert "MONTE" in hits[0][1]
    assert "4 fois sur 10" in hits[0][1]              # traduit, pas « 42-49 % »


def test_renforcement_marche_baissier_affiche_lavantage():
    pos = _pos()
    prix = pos.dps / 0.054545 / 1.014 * 0.95
    regime = {"etat": BAISSIER, "ecart_pct": -8.0, "points": 200}
    hits, _ = reinforcement_messages([pos], _prix_factory(None, prix),
                                     lambda c: 9.0, 500000.0, regime=regime)
    assert hits and "BAISSE" in hits[0][1]
    assert "7 fois sur 10" in hits[0][1]


def test_messages_du_regime_sans_jargon():
    """Règle de style LEO : aucun terme technique nu dans les alertes."""
    pos = _pos()
    prix = pos.dps / 0.054545 / 1.014 * 0.95
    for etat in (HAUSSIER, BAISSIER):
        hits, _ = reinforcement_messages([pos], _prix_factory(None, prix),
                                         lambda c: 9.0, 500000.0,
                                         regime={"etat": etat, "ecart_pct": 5.0})
        texte = hits[0][1]
        for jargon in ("indice", "moyenne", "capital égal", "régime", "séances"):
            assert jargon not in texte.lower(), f"jargon non traduit : {jargon}"


def test_indicateur_indisponible_nempeche_pas_lalerte():
    """Un régime `None` ou vide doit dégrader proprement, pas casser."""
    pos = _pos()
    prix = pos.dps / 0.054545 / 1.014 * 0.95
    for regime in (None, {}, {"etat": None}):
        hits, _ = reinforcement_messages([pos], _prix_factory(None, prix),
                                         lambda c: 9.0, 500000.0, regime=regime)
        assert hits


# --------------------------------------------------------------------------
#  Contrôle 4 — trésorerie : information, aucun ordre
# --------------------------------------------------------------------------
def test_alerte_tresorerie_silencieuse_sous_le_seuil():
    assert alerte_tresorerie(TARGET_CASH) == ""
    assert alerte_tresorerie(TARGET_CASH + 1.0) == ""


def test_alerte_tresorerie_est_informative():
    """Déclenchement avec un historique injecté (3 relevés au-dessus du seuil)."""
    hist = [{"date": f"2026-10-0{i}", "cash": 700000.0, "total": 1500000.0}
            for i in (1, 2, 3)]
    msg = alerte_tresorerie(46.0, history=hist, montant=700000.0)
    assert msg, "l'alerte doit se déclencher après 3 relevés"
    assert "Aucun ordre n'est passé" in msg
    # Le montant concret doit apparaître AVANT le pourcentage, et au format français
    # (espace, pas de virgule : « 700 000 F » se lit sans ambiguïté).
    assert "\u202f" in msg, "le séparateur de milliers doit etre une espace, pas une virgule"
    assert "700\u202f000 F" in msg
    # Aucune consigne d'achat ne doit apparaître.
    for interdit in ("ACHÈTE", "ACHETE", "ordre d'achat à", "RENFORCE"):
        assert interdit not in msg


def test_alerte_tresorerie_ne_declenche_pas_sous_le_nombre_de_jours():
    """Deux relevés ne suffisent pas : évite l'alerte après une simple vente."""
    hist = [{"date": f"2026-10-0{i}", "cash": 700000.0, "total": 1500000.0}
            for i in (1, 2)]
    assert alerte_tresorerie(46.0, history=hist) == ""


def test_alerte_tresorerie_sarrete_au_premier_releve_sous_le_seuil():
    """La série doit être CONSÉCUTIVE, pas cumulée."""
    hist = [
        {"date": "2026-09-30", "cash": 100000.0, "total": 1500000.0},   # 6,7 %
        {"date": "2026-10-01", "cash": 700000.0, "total": 1500000.0},   # 46 %
        {"date": "2026-10-02", "cash": 700000.0, "total": 1500000.0},   # 46 %
    ]
    assert alerte_tresorerie(46.0, history=hist) == ""


def test_alerte_tresorerie_nappelle_aucune_fonction_dinvestissement():
    """Garde-fou structurel : la fonction ne fait que composer du texte."""
    import inspect

    from src import report

    source = inspect.getsource(report.alerte_tresorerie)
    for interdit in ("buy", "spec_open", "reinforce", "place_order", "open_position"):
        assert interdit not in source, f"alerte_tresorerie appelle {interdit}"
