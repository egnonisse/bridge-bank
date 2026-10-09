"""Journal des messages sortants — append-only, une ligne = un envoi.

POURQUOI CE JOURNAL EXISTE
--------------------------
Le journal des seuils (`seuils_journal.jsonl`) dit ce qui a changé dans les DÉCISIONS. Il ne dit
pas ce qui est SORTI, ni dans quel état était le système à ce moment-là. Sans ce journal, une
alerte reçue il y a trois semaines n'est plus qu'un souvenir : impossible de savoir avec quelles
règles, quels seuils et quelle configuration elle a été produite.

CE QU'UNE LIGNE CONTIENT
------------------------
    horodatage  date et heure de l'envoi (heure locale, secondes)
    origine     module ayant demandé l'envoi (« src.main », « src.alerts. »)
    envoye      vrai/faux — un envoi qui a ÉCHOUÉ est une information, pas une ligne à perdre
    empreinte   code · regles · seuils · config (voir `infrastructure/empreinte.py`)
    message     le texte de l'alerte SANS le rappel d'empreinte éventuel — celui-ci n'est déjà
                qu'une répétition du champ `empreinte`, l'inscrire deux fois n'apprend rien

MÊMES CONVENTIONS QUE LE JOURNAL DES SEUILS : un objet JSON par ligne, clés en français,
append-only (on n'édite ni ne supprime jamais une ligne), fichier versionné.

RÈGLE DE ROBUSTESSE : `enregistrer` NE LÈVE JAMAIS. Une trace manquante est moins grave qu'une
alerte perdue : le disque plein ou un fichier verrouillé ne doit pas empêcher une notification
de partir.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..infrastructure.paths import ALERTES_JOURNAL

log = logging.getLogger(__name__)


def enregistrer(entree: dict, chemin: Path | None = None) -> bool:
    """Ajoute une entrée au journal. Retourne True si inscrite, False sinon (jamais d'exception)."""
    cible = Path(chemin) if chemin is not None else ALERTES_JOURNAL
    try:
        cible.parent.mkdir(parents=True, exist_ok=True)
        with cible.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entree, ensure_ascii=False) + "\n")
        return True
    except (OSError, TypeError, ValueError) as exc:
        log.error("Journal des alertes : écriture impossible (%s) — le message part quand même", exc)
        return False


def lire(chemin: Path | None = None, limite: int | None = None) -> list[dict]:
    """Entrées du journal, de la plus récente à la plus ancienne. Les lignes illisibles sont
    ignorées (un journal est écrit par des versions successives du code : une ligne qu'on ne
    comprend pas ne doit pas rendre tout le journal inexploitable)."""
    cible = Path(chemin) if chemin is not None else ALERTES_JOURNAL
    if not cible.exists():
        return []
    entrees: list[dict] = []
    for ligne in cible.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            entrees.append(json.loads(ligne))
        except json.JSONDecodeError:
            log.warning("Journal des alertes : ligne illisible ignorée (%s)", ligne[:80])
    entrees.reverse()
    return entrees[:limite] if limite else entrees


def derniere(chemin: Path | None = None) -> dict | None:
    """Dernière entrée inscrite, ou None si le journal est vide."""
    entrees = lire(chemin=chemin, limite=1)
    return entrees[0] if entrees else None


def compter(chemin: Path | None = None) -> int:
    cible = Path(chemin) if chemin is not None else ALERTES_JOURNAL
    if not cible.exists():
        return 0
    return sum(1 for ligne in cible.read_text(encoding="utf-8").splitlines() if ligne.strip())
