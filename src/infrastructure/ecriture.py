"""Écriture atomique et lecture stricte des fichiers d'état (correction P7-01).

POURQUOI CE MODULE EXISTE
-------------------------
Un `write_text(...)` direct sur un fichier d'état peut être interrompu (crash, kill,
coupure) en PLEIN MILIEU de l'écriture → fichier tronqué. Pour les positions de la
poche spéculative (argent réel), cette perte n'est pas reconstructible.

Le motif correct est connu du projet (appliqué en inline dans `portfolio.py` — B1-04,
`fundamentals.py` et `backtest.py`) : écrire dans un `.tmp` voisin, puis `replace()`
(atomique sur un même volume). Il est centralisé ici pour être RÉUTILISABLE.

ET SURTOUT : la lecture ne doit JAMAIS avaler une corruption en silence.
Un fichier ABSENT = premier lancement (valeur par défaut légitime).
Un fichier PRÉSENT mais illisible = incident BRUYANT (doctrine : un système qui
échoue bruyamment est sûr ; un système qui échoue en silence est dangereux).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

TENTATIVES_REPLACE = 6  # verrou Windows transitoire : 6 essais ≈ 4 s au total


class FichierEtatIllisible(RuntimeError):
    """Un fichier d'état EXISTE mais est illisible (JSON invalide, structure inattendue).

    Lever plutôt que retourner une valeur vide : repartir de zéro en silence ferait
    croire à un état vide (ex. « aucune position spé » alors qu'elles ont été perdues).
    """


def ecrire_json_atomique(chemin: Path, donnees, *, indent: int = 2,
                         tentatives: int = TENTATIVES_REPLACE) -> None:
    """Écrit `donnees` en JSON dans `chemin` de façon ATOMIQUE (.tmp + replace).

    Un crash pendant l'écriture laisse l'ancien fichier intact — jamais de troncature.

    Deux runs CONCURRENTS (cron Hermes + lancement manuel, 19/10/2026) écrivaient le MÊME
    `X.tmp` puis se disputaient le `replace` → `PermissionError: [WinError 32]` : le
    lancement du monitor radar est mort là-dessus. D'où deux protections ici :
      1. temporaire UNIQUE par processus (`.pid.tmp`) — plus de collision d'écriture ;
      2. `replace` réessayé avec un court palier — Windows refuse un remplacement tant
         qu'un autre processus a la destination ouverte (verrou transitoire, antivirus).
    Le temporaire est supprimé si tous les essais échouent (aucun `.tmp` résiduel).
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(f"{chemin.name}.{os.getpid()}.tmp")
    temporaire.write_text(
        json.dumps(donnees, indent=indent, ensure_ascii=False), encoding="utf-8"
    )
    for essai in range(tentatives):
        try:
            temporaire.replace(chemin)  # atomique sur le même volume
            return
        except PermissionError:
            if essai == tentatives - 1:
                temporaire.unlink(missing_ok=True)
                raise
            time.sleep(0.2 * (essai + 1))


def lire_json_strict(chemin: Path):
    """Lit un JSON d'état. Absent → None. Présent mais illisible → `FichierEtatIllisible`."""
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FichierEtatIllisible(
            f"{chemin.name} existe mais est illisible ({type(exc).__name__}) — "
            "le lire de force serait repartir de zéro EN SILENCE. Réparer ou restaurer "
            f"(ex. `git show HEAD:data/{chemin.name}`), puis relancer."
        ) from exc
