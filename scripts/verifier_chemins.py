"""Vérifie que l'arborescence de `data/` a UN SEUL point de vérité : `src/infrastructure/paths.py`.

DEUX CONTRÔLES
--------------
1. **Chemins recalculés à la main** — `Path(__file__).resolve().parent.parent / "data"` est
   **implicite** : il dépend de la profondeur du fichier. Tant que tout vit dans `src/`, il tombe
   juste. Dès qu'un module descend d'un niveau, il désigne le mauvais dossier — et la panne est
   **silencieuse** : un chargement qui échoue renvoie une valeur par défaut, le programme
   continue avec des données vides, et rien ne le signale.
2. **Noms de fichiers recopiés** (P6-01/P6-05, ajouté le 13/10) — écrire `DATA_DIR / "x.json"`
   dans un module au lieu d'importer la constante de `paths.py` recrée une copie du nom : le jour
   où le fichier est renommé ou déplacé, la copie ne suit pas — panne silencieuse encore.
   La liste des noms surveillés est **dérivée de `paths.py`** : ajouter une constante y étend
   automatiquement le contrôle. Périmètre : `src/` — les `scripts/` d'enquête ponctuelle gardent
   leurs chemins directs (décision documentée dans `docs/architecture.md` §6).
3. **Formes résiduelles de chemins data/** (B2-09, 13/10/2026) — l'idiome historique
   `RACINE / "data" / "x"`, un alias local (`DATA = RACINE / "data"` puis `DATA / "x"`), ou la
   chaîne relative `"data/x"` (dépendante du dossier courant) recréent un chemin qui ne suit
   PAS un déplacement des données. Interdits : l'idiome et le relatif **partout** ; l'alias
   dans `scripts/` et `tests/` seulement (dans `src/`, `DATA_DIR` importé de `paths.py` est le
   style accepté, ses noms restant surveillés par le contrôle 2).

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

# Contrôle 3 (B2-09, 13/10/2026) : formes résiduelles de chemins data/.
# Idiome historique `RACINE / "data"` (définition d'alias comprise).
MOTIF_IDIOME = re.compile(
    r"\b(RACINE|RACINE_PROJET|PROJECT_ROOT|DATA|DATA_DIR)\s*/\s*[\"']data[\"']")
# Alias local recréé dans le fichier : `DATA / "x"` ou `DATA_DIR / "x"`.
MOTIF_ALIAS = re.compile(r"\b(DATA|DATA_DIR)\s*/\s*[\"']")
# Chaîne relative dépendante du dossier courant.
MOTIF_RELATIF = re.compile(r"[\"']data/")
# Exemption EXPLICITE, ligne à ligne et visible dans le code concerné : un contrôle de
# données qui vérifie le FORMAT « data/... » d'une sortie publiée n'est pas un chemin.
# (Le faux positif se voit ; il se déclare, il ne se devine pas.)
_EXEMPTION = "noqa: chemin-relatif"
# Seuls fichiers autorisés à écrire l'idiome : paths.py (source) et le migrateur (outil).
_FICHIERS_EXCLUS = {"paths.py", "migrer_chemins.py"}


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


def _noms_centraux() -> set[str]:
    """Noms de fichiers dont la constante vit dans `src/infrastructure/paths.py`.

    La source de vérité du contrôle est `paths.py` lui-même : toute constante `DATA_DIR / "x"`
    ajoutée là-bas devient surveillée ici, sans rien à mettre à jour dans ce script.
    """
    sys.path.insert(0, str(RACINE))
    try:
        import src.infrastructure.paths as p
    finally:
        sys.path.pop(0)
    return {
        c.name for c in vars(p).values()
        if isinstance(c, Path) and c.parent == p.DATA_DIR
    }


def _scanner_noms(dossier: Path) -> list[dict]:
    """Littéraux de noms de fichiers recopiés dans du code (hors `paths.py`)."""
    noms = _noms_centraux()
    trouves = []
    for f in sorted(dossier.rglob("*.py")):
        if any(p.startswith(".") for p in f.parts) or "__pycache__" in f.parts:
            continue
        if f.parent.name == "infrastructure" and f.name == "paths.py":
            continue
        try:
            texte = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        texte_ignore = _lignes_de_texte(texte)
        for i, ligne in enumerate(texte.splitlines(), 1):
            if i in texte_ignore:
                continue
            if "/" not in ligne and "joinpath" not in ligne:
                continue
            for nom in noms:
                if f'"{nom}"' in ligne or f"'{nom}'" in ligne:
                    trouves.append({
                        "fichier": f.relative_to(RACINE).as_posix(),
                        "ligne": i,
                        "nom": nom,
                        "code": ligne.strip()[:78],
                    })
                    break
    return trouves


def _scanner_formes(dossier: Path, alias_locaux: bool = False) -> list[dict]:
    """Formes résiduelles de chemins data/ (contrôle 3, B2-09).

    `RACINE / "data"` (idiome) et `"data/…"` (relatif au dossier courant) sont interdits
    PARTOUT ; l'alias local `DATA / "x"` l'est dans scripts/ et tests/ seulement — dans
    src/, `DATA_DIR` importé de paths.py est le style accepté (contrôle 2 pour les noms).
    """
    trouves = []
    for f in sorted(dossier.rglob("*.py")):
        if any(p.startswith(".") for p in f.parts) or "__pycache__" in f.parts:
            continue
        if f.name in _FICHIERS_EXCLUS:
            continue
        try:
            texte = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        texte_ignore = _lignes_de_texte(texte)
        for i, ligne in enumerate(texte.splitlines(), 1):
            if i in texte_ignore or _EXEMPTION in ligne:
                continue
            m = MOTIF_IDIOME.search(ligne)
            if not m and alias_locaux:
                m = MOTIF_ALIAS.search(ligne)
            if not m:
                m = MOTIF_RELATIF.search(ligne)
            if m:
                trouves.append({
                    "fichier": f.relative_to(RACINE).as_posix(),
                    "ligne": i,
                    "forme": m.group(0)[:40],
                    "code": ligne.strip()[:78],
                })
    return trouves


def main(strict: bool = False) -> int:
    src = _scanner(RACINE / "src")
    scripts = _scanner(RACINE / "scripts")
    tests = _scanner(RACINE / "tests")
    total = src + scripts + tests
    noms = _scanner_noms(RACINE / "src")
    f_src = _scanner_formes(RACINE / "src")
    f_scripts = _scanner_formes(RACINE / "scripts", alias_locaux=True)
    f_tests = _scanner_formes(RACINE / "tests", alias_locaux=True)
    formes = f_src + f_scripts + f_tests

    print("=" * 78)
    print("  ARBORESCENCE DE DONNEES — un seul point de verite : src/infrastructure/paths.py")
    print("=" * 78)
    print()
    print("  1. CHEMINS CALCULES A LA MAIN")
    print(f"     src/     : {len(src):>3d} occurrence(s)")
    print(f"     scripts/ : {len(scripts):>3d} occurrence(s)")
    print(f"     tests/   : {len(tests):>3d} occurrence(s)")
    print(f"     TOTAL    : {len(total):>3d}")
    print()
    print("  2. NOMS DE FICHIERS RECOPIES (perimetre : src/ seulement)")
    print(f"     TOTAL    : {len(noms):>3d}")
    print()
    print("  3. FORMES RESIDUELLES  (RACINE / \"data\", alias local, chemin relatif)")
    print(f"     src/     : {len(f_src):>3d} occurrence(s)")
    print(f"     scripts/ : {len(f_scripts):>3d} occurrence(s)")
    print(f"     tests/   : {len(f_tests):>3d} occurrence(s)")
    print(f"     TOTAL    : {len(formes):>3d}")
    print()

    if not total and not noms and not formes:
        print("  Rien a signaler : l'arborescence peut changer sans casser les")
        print("  chargements de donnees (un seul point de verite).")
        return 0

    if total:
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
        print("    from .infrastructure.paths import DATA_DIR       (dans src/)")
        print("    from src.infrastructure.paths import DATA_DIR    (dans scripts/ et tests/)")
        print()
        print("  Cette migration est un PREREQUIS a tout deplacement de fichier :")
        print("  sans elle, descendre un module d'un niveau change le sens de")
        print("  `parent.parent` et casse les chargements SANS erreur visible.")

    if noms:
        print("  Noms recopies — importer la constante de paths.py a la place :")
        for t in sorted(noms, key=lambda x: (x["fichier"], x["ligne"])):
            print(f"    {t['fichier']}:{t['ligne']}  ({t['nom']})  {t['code']}")

    if formes:
        print("  Formes residuelles — utiliser paths.py (constante ou chemin_data) :")
        for t in sorted(formes, key=lambda x: (x["fichier"], x["ligne"])):
            print(f"    {t['fichier']}:{t['ligne']}  ({t['forme']})  {t['code']}")

    if strict:
        print()
        print("  [--strict] Des chemins ou des noms subsistent : migration incomplete.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(strict="--strict" in sys.argv))
