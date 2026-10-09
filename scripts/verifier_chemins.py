"""Vérifie qu'aucun module ne recalcule son propre chemin de données.

POURQUOI CE CONTRÔLE
--------------------
Le chemin `Path(__file__).resolve().parent.parent / "data"` est **implicite** : il dépend de
la profondeur du fichier. Tant que tout vit dans `src/`, il tombe juste. Dès qu'un module
descend d'un niveau, il désigne le mauvais dossier — et la panne est **silencieuse** : un
chargement qui échoue renvoie une valeur par défaut, le programme continue avec des données
vides, et rien ne le signale.

Aucun test de valeur ne détecte ça. Ce contrôle, oui.

Il sert **avant et après** une réorganisation : avant, il donne la liste de ce qu'il faut
migrer vers `src/paths.py` ; après, il prouve qu'il ne reste rien.

    python scripts/verifier_chemins.py            # rapport
    python scripts/verifier_chemins.py --strict   # code de sortie 1 si un chemin subsiste

Le TEXTE est ignoré : un idiome cité dans une docstring, un commentaire ou un message d'aide
n'est pas un chemin recalculé. Sans ce filtre le contrôle serait insatisfiable — `paths.py`
et `migrer_chemins.py` documentent tous deux l'idiome à remplacer.
"""
from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Un chemin recalculé à la main : `Path(__file__)...parent` suivi d'un dossier de données.
MOTIF = re.compile(
    r"Path\(__file__\)[^\n]*?parent\s*/\s*[\"'](data|scripts|docs|tests)[\"']")
# Variante sans Path() (os.path.dirname(__file__) + join).
MOTIF_OS = re.compile(r"dirname\(__file__\)[^\n]*?[\"'](data|scripts|docs|tests)[\"']")


def _lignes_de_texte(source: str) -> set[int]:
    """Numéros des lignes occupées par un commentaire ou une chaîne (docstring, message).

    Seul `tokenize` distingue de façon fiable un chemin recalculé de sa citation. Un littéral
    qui **ouvre** la ligne est du texte ; au milieu d'une expression, c'est du code et il
    reste compté. En cas de fichier illisible on retourne l'ensemble vide : on scanne tout,
    jamais l'inverse — un faux positif se voit, un faux négatif se cache.
    """
    lignes = source.splitlines()
    ignorees: set[int] = set()
    try:
        for jeton in tokenize.generate_tokens(io.StringIO(source).readline):
            if jeton.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            debut, fin = jeton.start[0], jeton.end[0]
            if lignes[debut - 1][:jeton.start[1]].strip():
                continue
            ignorees.update(range(debut, fin + 1))
    except (tokenize.TokenError, IndentationError, SyntaxError, IndexError):
        return set()
    return ignorees


def _scanner(dossier: Path, etendue: str = "*.py") -> list[dict]:
    trouves = []
    for f in sorted(dossier.rglob(etendue)):
        # Les dossiers cachés (.hermes-tmp*, .venv) ne contiennent pas de code du projet.
        if any(p.startswith(".") for p in f.parts) or "__pycache__" in f.parts:
            continue
        try:
            texte = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        texte_ignore = _lignes_de_texte(texte)
        for i, ligne in enumerate(texte.splitlines(), 1):
            if i in texte_ignore:
                continue
            m = MOTIF.search(ligne) or MOTIF_OS.search(ligne)
            if m:
                trouves.append({
                    "fichier": f.relative_to(RACINE).as_posix(),
                    "ligne": i,
                    "dossier": m.group(1),
                    "code": ligne.strip()[:78],
                })
    return trouves


def main(strict: bool = False) -> int:
    src = _scanner(RACINE / "src")
    scripts = _scanner(RACINE / "scripts")
    tests = _scanner(RACINE / "tests")
    total = src + scripts + tests

    print("=" * 78)
    print("  CHEMINS CALCULES A LA MAIN — cible : src/paths.py")
    print("=" * 78)
    print()
    print(f"  src/     : {len(src):>3d} occurrence(s)")
    print(f"  scripts/ : {len(scripts):>3d} occurrence(s)")
    print(f"  tests/   : {len(tests):>3d} occurrence(s)")
    print(f"  TOTAL    : {len(total):>3d}")
    print()

    if not total:
        print("  Aucun chemin recalculé a la main : l'arborescence peut changer")
        print("  sans casser les chargements de donnees.")
        return 0

    # Regroupe par fichier : c'est l'unite de travail d'une migration.
    par_fichier: dict[str, list[dict]] = {}
    for t in total:
        par_fichier.setdefault(t["fichier"], []).append(t)

    print(f"  {len(par_fichier)} fichier(s) a migrer :")
    for fichier, occurrences in sorted(par_fichier.items(),
                                       key=lambda kv: -len(kv[1])):
        lignes = ", ".join(str(o["ligne"]) for o in occurrences[:6])
        suite = f" (+{len(occurrences)-6})" if len(occurrences) > 6 else ""
        print(f"    {fichier:38s} {len(occurrences):>3d}  l.{lignes}{suite}")

    print()
    print("  MIGRATION : remplacer par")
    print("    from .paths import DATA_DIR          (dans src/)")
    print("    from src.paths import DATA_DIR       (dans scripts/ et tests/)")
    print()
    print("  Cette migration est un PREREQUIS a tout deplacement de fichier :")
    print("  sans elle, descendre un module d'un niveau change le sens de")
    print("  `parent.parent` et casse les chargements SANS erreur visible.")

    if strict:
        print()
        print("  [--strict] Des chemins subsistent : migration incomplete.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(strict="--strict" in sys.argv))
