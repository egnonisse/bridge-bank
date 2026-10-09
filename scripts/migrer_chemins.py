"""Lot 0 — migre les chemins calculés à la main vers `src/paths.py`.

CE QUE FAIT CE SCRIPT
---------------------
Dans `src/`, 22 modules calculent eux-mêmes où se trouvent les données :

    DATA_DIR = Path(__file__).resolve().parent.parent / "data"

Ce calcul dépend de la PROFONDEUR du fichier. Déplacer un module d'un niveau (ce que la
réorganisation en domaines exige) change le sens de `parent.parent`, les chargements
échouent **en silence**, et le programme continue avec des données vides.

Après migration, chaque module écrit `from .paths import DATA_DIR` — vrai quelle que soit
sa profondeur. **C'est ce qui rend les déplacements sûrs.**

CE QU'IL NE TOUCHE PAS — délibérément
-------------------------------------
- **`sys.path.insert(0, str(Path(__file__)...parent.parent))`** dans `scripts/` et `tests/` :
  c'est un bootstrap d'import, pas un chemin de données. Les scripts restent dans
  `scripts/`, donc le calcul reste juste. Les migrer maintenant serait du bruit.
- **`src/spec_veille.py`** : son `sys.path.insert` sert à s'importer lui-même comme script.
- Les `# commentaires` citant le motif.

DÉDOUBLONNAGE DES NOMS
----------------------
Chaque module nommait sa constante à sa façon. La table ci-dessous ramène à DEUX noms
canoniques (`DATA_DIR`, `RACINE`) — c'est le point de la manœuvre.

    python scripts/migrer_chemins.py --dry-run    # montre, n'écrit rien
    python scripts/migrer_chemins.py              # applique
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"

# Nom local -> nom canonique dans paths.py
CANONIQUES = {
    "DATA_DIR": "DATA_DIR",
    "DATA": "DATA_DIR",
    "RACINE": "RACINE",
    "ROOT": "RACINE",
}

# Un calcul de chemin vers un dossier de données, avec le nom qu'il définit.
MOTIFS = [
    # DATA_DIR = Path(__file__).resolve().parent.parent / "data"
    re.compile(r"^(?P<nom>[A-Z_]+)\s*=\s*Path\(__file__\)[^\n]*?/\s*[\"'](?P<dossier>data)[\"']\s*$"),
    # RACINE = Path(__file__).resolve().parent.parent
    re.compile(r"^(?P<nom>[A-Z_]+)\s*=\s*Path\(__file__\)[^\n]*?\.parent\.parent\s*$"),
    # DATA = Path(__file__).resolve().parents[1] / "data"
    re.compile(r"^(?P<nom>[A-Z_]+)\s*=\s*Path\(__file__\)[^\n]*?parents\[\d\]\s*/\s*[\"'](?P<dossier>data)[\"']\s*$"),
]

MARQUEUR = "# chemins centralisés (lot 0 du plan docs/architecture.md)"


def _analyser(texte: str) -> list[tuple[int, str, str]]:
    """Retourne [(numéro de ligne, nom local, nom canonique)] pour les lignes à migrer."""
    trouves = []
    for i, ligne in enumerate(texte.splitlines(), 1):
        nue = ligne.strip()
        if nue.startswith("#"):
            continue
        for motif in MOTIFS:
            m = motif.match(nue)
            if m and m.group("nom") in CANONIQUES:
                trouves.append((i, m.group("nom"), CANONIQUES[m.group("nom")]))
                break
    return trouves


def _fin_des_imports(lignes: list[str]) -> int:
    """Numéro de la ligne APRÈS laquelle insérer un import de tête.

    Deux pièges, tous deux rencontrés :

    1. **Le docstring du module.** Il n'est ni un import ni un commentaire `#` : une
       première version s'arrêtait dessus et renvoyait 0, ce qui aurait placé l'import
       AVANT le docstring (il perd alors son statut de docstring).
    2. **Les imports parenthésés sur plusieurs lignes.** S'arrêter à la « dernière ligne
       commençant par import/from » coupe le bloc en deux → SyntaxError. On suit donc la
       profondeur de parenthèses.

    On ne s'arrête qu'après la dernière parenthèse refermée du dernier bloc d'imports.
    """
    i = 0
    # 1. Sauter le docstring du module, s'il existe.
    while i < len(lignes) and not lignes[i].strip():
        i += 1
    if i < len(lignes):
        nue = lignes[i].lstrip()
        for guillemets in ('"""', "'''"):
            if nue.startswith(guillemets):
                fin = nue.find(guillemets, len(guillemets))
                if fin != -1:            # docstring sur une seule ligne
                    i += 1
                else:                    # docstring multi-lignes
                    i += 1
                    while i < len(lignes) and guillemets not in lignes[i]:
                        i += 1
                    i += 1
                break

    # 2. Parcourir les imports jusqu'à la première instruction qui n'en est pas un.
    dernier = 0
    profondeur = 0
    while i < len(lignes):
        nue = lignes[i].strip()
        i += 1
        if not nue or nue.startswith("#"):
            continue
        if profondeur > 0 or nue.startswith(("import ", "from ")):
            profondeur += nue.count("(") - nue.count(")")
            if profondeur <= 0:
                dernier = i
                profondeur = 0
            continue
        break
    return dernier


def _inserer_import(texte: str, canonique: str, local: str) -> str:
    """Insère l'import en PRÉSERVANT le nom local du module.

    Le piège (rencontré, 4 modules cassés) : `spec_profiles.py` définit `DATA` et l'utilise
    ailleurs. Importer `DATA_DIR` sous le nom `DATA_DIR` laisse les autres usages de `DATA`
    sans définition → `NameError`.

    On garde donc le nom local en ALIAS, comme pour `regles.py` :

        from .infrastructure.paths import DATA_DIR as DATA   # conserve les usages existants

    Le nom reste, la source change. C'est ce qui rend la migration sans effet de bord.
    """
    lignes = texte.splitlines()
    dernier = _fin_des_imports(lignes)
    if canonique == local:
        bloc = f"from .infrastructure.paths import {canonique}  {MARQUEUR}"
    else:
        bloc = f"from .infrastructure.paths import {canonique} as {local}  {MARQUEUR}"
    lignes.insert(dernier, bloc)
    return "\n".join(lignes) + ("\n" if texte.endswith("\n") else "")


def migrer(dry_run: bool = False) -> int:
    fichiers = sorted(SRC.glob("*.py"))
    total = 0
    modifies = 0

    for f in fichiers:
        if f.name in ("paths.py",):
            continue
        texte = f.read_text(encoding="utf-8")
        trouves = _analyser(texte)
        if not trouves:
            continue

        nouvelles = texte.splitlines()
        # On retire de la fin vers le début pour ne pas décaler les indices.
        # On mémorise (canonique, local) : le nom LOCAL doit être préservé en alias.
        paires: list[tuple[str, str]] = []
        for numero, local, canonique in sorted(trouves, reverse=True):
            nouvelles.pop(numero - 1)
            paires.append((canonique, local))
        nouveau_texte = "\n".join(nouvelles) + ("\n" if texte.endswith("\n") else "")

        for canonique, local in dict.fromkeys(reversed(paires)):
            nouveau_texte = _inserer_import(nouveau_texte, canonique, local)

        noms = ", ".join(f"{local}->{can}" for _, local, can in trouves)
        print(f"  {f.name:32s} {len(trouves)}  {noms}")
        total += len(trouves)
        modifies += 1

        if not dry_run:
            f.write_text(nouveau_texte, encoding="utf-8")

    print()
    if dry_run:
        print(f"[dry-run] {total} ligne(s) dans {modifies} fichier(s) seraient migrees.")
    else:
        print(f"{total} ligne(s) migree(s) dans {modifies} fichier(s).")
        print("  Verification : python scripts/verifier_chemins.py")
        print("  Non-regression : pytest tests/ -q  +  scripts/auditer_constantes.py --comparer")
    return 0


if __name__ == "__main__":
    raise SystemExit(migrer(dry_run="--dry-run" in sys.argv))
