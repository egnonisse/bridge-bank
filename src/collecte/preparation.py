"""Préparation de l'historique PROPRE — le maillon brut → propre du pipeline (B2-10).

Le pipeline historique a deux étages :
  1. COLLECTE — `backtest.load_all_history()` télécharge les cours et écrit
     `history_cache.pkl` (BRUT) : une donnée d'entrée transitoire, jamais utilisée
     pour décider.
  2. PRÉPARATION — ce module ajuste les divisions de nominal et nettoie les valeurs
     aberrantes, puis écrit le cache CANONIQUE `history_clean.pkl` via
     `history_io.ecrire_cache()` (atomique + empreinte .sha256).

B2-10 (13/10/2026) : avant, seule une partie de la production lisait le propre — le
backtest de validation, le radar et le noyau-check consommaient le BRUT, non ajusté
des divisions (les cassures de split y biaisent les rendements mesurés). Désormais
tous passent par `charger_historique_propre()`, et `cmd_integrity` (chaîne du matin)
régénère le propre dès que le brut a bougé — le maillon manuel est fermé.
"""
from __future__ import annotations

import json
import logging
import pickle

from ..infrastructure.paths import DATA_DIR, HISTORY_BRUT, HISTORY_CACHE
from . import divisions_officielles as dv
from . import nettoyage_aberrantes as na
from .history_io import charger_cache, ecrire_cache
from src.infrastructure.paths import chemin_data  # noqa: E402  (B2-09)

log = logging.getLogger(__name__)

RAPPORT_FILE = chemin_data("ajustement_rapport.json")


def preparer_historique_propre() -> dict:
    """Régénère le cache propre depuis le brut. Retourne les statistiques.

    Lève FileNotFoundError si le brut est absent — jamais de cache propre vide.
    """
    if not HISTORY_BRUT.exists():
        raise FileNotFoundError(
            f"Historique brut introuvable : {HISTORY_BRUT.name} — lancer d'abord une "
            "collecte (check quotidien, ou scripts/refresh_history.py)")
    with open(HISTORY_BRUT, "rb") as fh:
        brut = pickle.load(fh)

    res = dv.ajuster_historique(brut)
    net = na.nettoyer_historique(res["historique"])
    propre = net["historique"]
    sha = ecrire_cache(HISTORY_CACHE, propre)

    # Rapport des opérations (même format que l'ancien script — lu par le rapport mensuel).
    with open(RAPPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump({
            "titres_ajustes": res["nb_titres_ajustes"],
            "sans_operation": res["sans_division"],
            "operations": res["rapport"],
            "aberrantes_corrigees": net["total_corrections"],
        }, fh, ensure_ascii=False, indent=1)

    return {
        "titres": len(propre),
        "titres_ajustes": res["nb_titres_ajustes"],
        "sans_division": len(res["sans_division"]),
        "aberrantes_corrigees": net["total_corrections"],
        "sha": sha,
    }


def charger_historique_propre(preparer_si_necessaire: bool = True) -> dict:
    """Charge le cache PROPRE (celui des décisions) ; le régénère si le brut a bougé.

    - brut plus récent que le propre (ou propre absent) → préparation automatique —
      le daily le fait chaque matin ; ceci couvre les commandes lancées entre deux matins ;
    - propre absent après préparation → FileNotFoundError avec la marche à suivre ;
    - empreinte divergente → `CacheHistoriqueAltere` (bruyant, via history_io).
    """
    if preparer_si_necessaire:
        brut_mtime = HISTORY_BRUT.stat().st_mtime if HISTORY_BRUT.exists() else None
        propre_mtime = HISTORY_CACHE.stat().st_mtime if HISTORY_CACHE.exists() else None
        if brut_mtime is not None and (propre_mtime is None or brut_mtime > propre_mtime):
            stats = preparer_historique_propre()
            log.info("Historique propre régénéré depuis le brut : %d titres, %d barres nettoyées.",
                     stats["titres"], stats["aberrantes_corrigees"])
    if not HISTORY_CACHE.exists():
        if not HISTORY_BRUT.exists():
            raise FileNotFoundError(
                f"Ni {HISTORY_BRUT.name} (brut) ni {HISTORY_CACHE.name} (propre) : lancer "
                "d'abord une collecte (check quotidien, ou scripts/refresh_history.py).")
        raise FileNotFoundError(
            f"{HISTORY_CACHE.name} absent — lancer : python scripts/preparer_historique_propre.py")
    return charger_cache(HISTORY_CACHE)
