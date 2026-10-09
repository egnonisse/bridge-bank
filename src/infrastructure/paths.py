"""Chemins du projet — une seule source, pour que l'arborescence puisse évoluer.

POURQUOI CE MODULE EXISTE
-------------------------
41 modules et 86 scripts calculaient chacun leur chemin de données :

    DATA_DIR = Path(__file__).resolve().parent.parent / "data"

Ce calcul est **implicite** : il dépend de la PROFONDEUR du fichier dans l'arborescence.
Tant que tout est dans `src/`, `parent.parent` tombe sur la racine du projet. Mais dès qu'un
module descend d'un niveau — `src/portfolio/positions.py` — le même code désigne `src/` au
lieu de la racine, et **tous les fichiers de données deviennent introuvables**.

Pire : la panne n'est pas bruyante. Un `load()` qui ne trouve pas son fichier renvoie une
valeur par défaut, et le programme continue avec des données vides. C'est le type de cas
qu'aucun test de valeur ne détecte (le snapshot des constantes lit des valeurs, pas des
chemins).

CE MODULE EST LE PRÉREQUIS À TOUT DÉPLACEMENT
---------------------------------------------
Il permet de réorganiser `src/` en domaines **sans toucher aux chemins** : chaque module
écrit désormais `from .infrastructure.paths import DATA_DIR`, ce qui reste vrai quelle que soit
sa profondeur. Le jour où l'arborescence change, il n'y a **qu'un fichier** à corriger.

Un contrôle automatique vérifie qu'aucun module ne recalcule son chemin à la main :

    python scripts/verifier_chemins.py
"""
from __future__ import annotations

from pathlib import Path

# Racine du projet : trois niveaux au-dessus de CE fichier (src/infrastructure/paths.py).
# C'est LE seul endroit du projet où un chemin se calcule à la main — et c'est précisément le
# but de ce module : le jour où un fichier descend d'un niveau, il n'y a qu'ici à corriger.
# (Au lot 2, ce fichier est passé de `src/paths.py` à `src/infrastructure/paths.py` : un
# `parent.parent` y désignait la racine, il désignait `src/` après le déplacement.)
RACINE = Path(__file__).resolve().parents[2]

# ── Données ───────────────────────────────────────────────────────────────────
DATA_DIR = RACINE / "data"
MARKET_DIR = DATA_DIR / "market"          # cours archivés (historique, collectes)
PORTFOLIO_DIR = DATA_DIR / "portfolio"    # positions, snapshots, relevés

# Fichiers de données — le nom vit ici, jamais recopié dans un module.
HISTORY_CACHE = DATA_DIR / "history_clean.pkl"
PROFIT_THRESHOLDS = DATA_DIR / "profit_thresholds.json"
SEUILS_JOURNAL = DATA_DIR / "seuils_journal.jsonl"
ALERTES_JOURNAL = DATA_DIR / "alertes_journal.jsonl"
REVERSAL_PROFILES = DATA_DIR / "reversal_profiles.json"
PORTFOLIO_STATE = DATA_DIR / "portfolio_state.json"
FUNDAMENTALS_HISTORIQUES = DATA_DIR / "fondamentaux_historiques.json"
DIVISIONS_OFFICIELLES = DATA_DIR / "divisions_officielles.json"

# ── Code et documentation ────────────────────────────────────────────────────
SRC_DIR = RACINE / "src"
SCRIPTS_DIR = RACINE / "scripts"
TESTS_DIR = RACINE / "tests"
DOCS_DIR = RACINE / "docs"
DECISIONS_DIR = DOCS_DIR / "decisions"

# ── Modules porteurs de RÈGLES (empreinte jointe aux alertes) ────────────────
# Leur CONTENU définit les décisions d'investissement : c'est ce que l'empreinte des règles
# mesure. Quand le plan (§5, lot 5) déplacera ces modules vers `domaine/`, ces deux lignes sont
# à corriger — et `tests/test_empreinte.py` échoue immédiatement si elles pointent dans le vide.
# Un chemin de fichier qui ne désigne plus rien ne doit pas se traduire par une empreinte
# constante, silencieusement identique à elle-même alors que les règles changent.
MODULE_REGLES = SRC_DIR / "regles.py"
MODULE_TAXATION = SRC_DIR / "taxation.py"


def chemin_data(nom: str) -> Path:
    """Chemin d'un fichier de `data/` — pour les noms qui ne méritent pas une constante.

    À utiliser plutôt que de reconstruire le chemin : si `data/` change de place ou de nom,
    une seule fonction est à corriger.
    """
    return DATA_DIR / nom


def verifier() -> list[str]:
    """Contrôle de cohérence : signale les chemins attendus qui manquent.

    Retourne la liste des problèmes (vide = tout est en place). Ne lève jamais : un appel
    depuis un test doit pouvoir rapporter sans interrompre.
    """
    problemes: list[str] = []
    for nom, p in (("DATA_DIR", DATA_DIR), ("SRC_DIR", SRC_DIR),
                   ("SCRIPTS_DIR", SCRIPTS_DIR), ("TESTS_DIR", TESTS_DIR)):
        if not p.exists():
            problemes.append(f"{nom} introuvable : {p}")
    return problemes
