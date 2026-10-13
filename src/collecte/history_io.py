"""Lecture et écriture du cache historique — UN SEUL chemin (P6-04, P7-03).

Le cache `history_clean.pkl` est produit par le pipeline local
(`scripts/preparer_historique_propre.py`) et consommé par le régime de marché, le
challenge et les outils d'analyse. Deux garanties, portées par ce module :

- **Une seule lecture (P6-04)** : `charger_cache()` — contexte `with`, message clair,
  et la même vérification pour TOUS les lecteurs (fin des lectures dispersées).
- **Provenance vérifiée (P7-03)** : le cache porte un sidecar `<cache>.sha256`, écrit
  avec lui par `ecrire_cache()`. Si le sidecar existe et que l'empreinte du fichier
  DIVERGE, le chargement échoue **bruyamment** (`CacheHistoriqueAltere`) : un cache
  modifié hors du pipeline ne doit JAMAIS alimenter des décisions. Le sidecar se
  régénère avec le cache — jamais à la main.

Périmètre : le cache CANONIQUE (celui des décisions) seulement. Le cache brut
(`history_cache.pkl`, produit par `backtest.load_all_history`) est une donnée
d'entrée transitoire, retéléchargée par le pipeline — hors contrat.
"""
from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

from ..infrastructure.paths import HISTORY_CACHE  # chemin central (P6-01)


class CacheHistoriqueAltere(RuntimeError):
    """Le cache ne correspond plus à son empreinte de référence (sidecar .sha256)."""


def sha_fichier(chemin: Path) -> str:
    """Empreinte SHA-256 du fichier, lue par blocs (le cache pèse ~7 Mo)."""
    h = hashlib.sha256()
    with open(chemin, "rb") as fh:
        for bloc in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def lire_sha(chemin: Path) -> str | None:
    """Empreinte de référence écrite à côté du cache ; None si le sidecar est absent."""
    try:
        return chemin.with_name(chemin.name + ".sha256").read_text(encoding="utf-8").split()[0]
    except (OSError, IndexError):
        return None


def ecrire_cache(chemin: Path, donnees: dict) -> str:
    """Écrit le cache (atomique) puis son empreinte de référence ; retourne l'empreinte.

    `.tmp` + `replace()` : un crash en pleine écriture ne peut pas laisser un cache
    tronqué. Le sidecar est écrit APRÈS le remplacement, sur le fichier final.
    """
    tmp = chemin.with_name(chemin.name + ".tmp")
    with open(tmp, "wb") as fh:
        pickle.dump(donnees, fh)
    tmp.replace(chemin)
    sha = sha_fichier(chemin)
    sidecar = chemin.with_name(chemin.name + ".sha256")
    sidecar_tmp = sidecar.with_name(sidecar.name + ".tmp")
    sidecar_tmp.write_text(sha + "\n", encoding="utf-8")
    sidecar_tmp.replace(sidecar)
    return sha


def charger_cache(chemin: Path | None = None) -> dict:
    """Charge le cache canonique — empreinte vérifiée si le sidecar existe.

    - sidecar absent → chargement (le prochain passage du pipeline le créera) ;
    - empreinte divergente → `CacheHistoriqueAltere`, avec la marche à suivre.
    """
    chemin = chemin or HISTORY_CACHE
    attendu = lire_sha(chemin)
    if attendu is not None:
        reel = sha_fichier(chemin)
        if reel != attendu:
            raise CacheHistoriqueAltere(
                f"{chemin.name} ne correspond pas à son empreinte ({reel[:12]}… vs "
                f"{attendu[:12]}…) : le cache a été modifié hors du pipeline. "
                "Régénérer : python scripts/preparer_historique_propre.py"
            )
    with open(chemin, "rb") as fh:
        return pickle.load(fh)
