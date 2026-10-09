"""Empreinte de version — de quoi expliquer une alerte passée.

POURQUOI CE MODULE EXISTE
-------------------------
Le journal des seuils dit CE QUI a changé ; il ne dit pas dans quel ÉTAT était le système
quand une alerte est partie. Deux alertes différentes à trois semaines d'intervalle peuvent
l'être pour quatre raisons distinctes, et sans empreinte rien ne les distingue :

  1. le CODE a changé (règle réécrite, correction)         -> empreinte du commit ;
  2. les RÈGLES ont changé (PER max, payout, fiscalité)    -> `regles.py` + `taxation.py` ;
  3. les SEUILS calibrés ont changé (une décision)         -> `profit_thresholds.json` ;
  4. la CONFIGURATION a changé (watchlist, noyau, cadence)  -> `config.yaml`.

CE QUE COUVRE LE DRAPEAU `*`
----------------------------
Un paramètre peut être modifié SUR LE DISQUE entre deux exécutions sans qu'aucun commit
n'apparaisse : c'est le cas que le SHA du commit seul ne verrait jamais. Quand l'arbre de
travail est modifié, l'empreinte du code porte un `*` — l'alerte dit alors « le code n'était
pas exactement celui du commit ».

CE QU'ELLE NE COUVRE PAS (limite assumée)
-----------------------------------------
L'empreinte est lue AU MOMENT DE L'ENVOI. Un changement survenu PENDANT le calcul de l'alerte
n'est pas distinguable d'un changement antérieur ; le distinguer exigerait de transporter
l'état dans tout le pipeline, ce qui est disproportionné au regard du risque (une exécution
dure quelques minutes).

Aucune fonction de ce module ne lève : une empreinte manquante ne doit pas empêcher une
alerte de partir.
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Iterable

from .paths import MODULE_REGLES, MODULE_TAXATION, PROFIT_THRESHOLDS, RACINE

log = logging.getLogger(__name__)

# Fichiers dont le CONTENU définit une famille de décisions (voir l'en-tête du module).
FICHIERS_REGLES = (MODULE_REGLES, MODULE_TAXATION)
FICHIERS_SEUILS = (PROFIT_THRESHOLDS,)
FICHIERS_CONFIG = (RACINE / "config.yaml",)

# Fichiers modifiés par le fonctionnement normal (journaux append-only) : les compter comme
# « arbre modifié » ferait porter un `*` à chaque alerte, pour toujours. Ils sont donc exclus
# du calcul du drapeau : un journal qui s'allonge n'est pas un changement de règles.
EXCLUS_DU_DRAPEAU = (
    ":(exclude)data/*.jsonl",
)
LONGUEUR = 12


def _sha256_fichiers(chemins: Iterable[Path]) -> str:
    """Empreinte du CONTENU d'un ensemble de fichiers, nom inclus (renommer change la clé)."""
    h = hashlib.sha256()
    for chemin in chemins:
        try:
            contenu = chemin.read_bytes()
        except OSError as exc:                      # fichier absent ou illisible : on le DIT
            log.warning("Empreinte : %s illisible (%s)", chemin, exc)
            contenu = b"<illisible>"
        h.update(chemin.name.encode("utf-8"))
        h.update(b"\0")
        h.update(contenu)
        h.update(b"\0")
    return h.hexdigest()[:LONGUEUR]


def _git(*arguments: str) -> str | None:
    """Sortie d'une commande git, ou None (dépôt absent, git absent, commande en échec)."""
    try:
        r = subprocess.run(
            ["git", *arguments], cwd=str(RACINE), capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("git %s indisponible : %s", " ".join(arguments), exc)
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def commit() -> str | None:
    """SHA court du commit courant, ou None hors dépôt git."""
    return _git("rev-parse", "--short", "HEAD") or None


def arbre_modifie() -> bool:
    """Vrai si des fichiers suivis diffèrent du commit (hors journaux append-only)."""
    sortie = _git("status", "--porcelain", "--", ".", *EXCLUS_DU_DRAPEAU)
    return bool(sortie)


def empreinte_code() -> str:
    """`<sha court>` — suffixé d'un `*` si l'arbre de travail est modifié. `inconnu` sans git."""
    sha = commit()
    if sha is None:
        return "inconnu"
    return f"{sha}*" if arbre_modifie() else sha


def empreinte_regles() -> str:
    return _sha256_fichiers(FICHIERS_REGLES)


def empreinte_seuils() -> str:
    return _sha256_fichiers(FICHIERS_SEUILS)


def empreinte_config() -> str:
    return _sha256_fichiers(FICHIERS_CONFIG)


def carte() -> dict[str, str]:
    """Les quatre empreintes ensemble — ce qu'on inscrit au journal des envois.

    `regles` et `seuils` sont séparés volontairement : une alerte qui change parce qu'on a
    modifié un seuil (décision calibrée) et une alerte qui change parce qu'une règle métier a
    été réécrite (code) n'ont pas la même explication, et il faut pouvoir les distinguer.
    """
    return {
        "code": empreinte_code(),
        "regles": empreinte_regles(),
        "seuils": empreinte_seuils(),
        "config": empreinte_config(),
    }
