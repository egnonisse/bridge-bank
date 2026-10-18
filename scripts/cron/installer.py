"""Installe ou vérifie les lanceurs de cron Bridge Bank (B2-08, 13/10/2026).

POURQUOI
--------
Les crons Hermes exécutent des lanceurs dans %LOCALAPPDATA%/hermes/scripts/, HORS du
dépôt. Un lanceur qui contient un chemin en dur meurt en silence quand le dépôt est
déplacé ou cloné ailleurs. Ici, les lanceurs versionnés (scripts/cron/bridgebank_*.py)
sont la SOURCE DE VÉRITÉ ; la copie installée est un ARTEFACT produit par ce script :
à l'installation, la racine du dépôt courant remplace le placeholder `DEFAUT_INSTALLE`
(dernier recours du bloc de découverte) et un `bridgebank_root.txt` est déposé à côté.

    python scripts/cron/installer.py             # installe / met à jour
    python scripts/cron/installer.py --verifier  # compare, exit 1 si divergence

Après un déplacement ou un clone du dépôt : relancer l'installation, puis `--verifier`.
"""
import argparse
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
SOURCE_DIR = RACINE / "scripts" / "cron"
DEFAUT_DEST = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "hermes" / "scripts"
TACHES = ("backup", "close", "daily", "radar_monitor", "report", "specveille")
PLACEHOLDER = 'r"DEFAUT_INSTALLE"'
RACINE_TXT = "bridgebank_root.txt"


def rendre(tache: str, racine: Path) -> str:
    """Contenu de la copie installée : source versionnée + racine inscrite en défaut."""
    source = (SOURCE_DIR / f"bridgebank_{tache}.py").read_text(encoding="utf-8")
    if PLACEHOLDER not in source:
        raise SystemExit(f"ERREUR : {SOURCE_DIR}/bridgebank_{tache}.py ne contient pas "
                         f"le placeholder {PLACEHOLDER} — source corrompue ?")
    return source.replace(PLACEHOLDER, f'r"{racine}"')


def installer(dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    ecrits = []
    for tache in TACHES:
        attendu = rendre(tache, RACINE)
        cible = dest / f"bridgebank_{tache}.py"
        actuel = cible.read_text(encoding="utf-8") if cible.exists() else None
        if actuel == attendu:
            continue
        cible.write_text(attendu, encoding="utf-8")
        ecrits.append(cible.name)
    racine_txt = dest / RACINE_TXT
    if racine_txt.read_text(encoding="utf-8").strip() if racine_txt.exists() else None \
            != str(RACINE):
        racine_txt.write_text(str(RACINE) + "\n", encoding="utf-8")
        ecrits.append(RACINE_TXT)
    if ecrits:
        print(f"Installé dans {dest} : " + ", ".join(ecrits))
    else:
        print(f"Déjà à jour dans {dest} (rien à faire).")
    return 0


def verifier(dest: Path) -> int:
    divergences = []
    for tache in TACHES:
        cible = dest / f"bridgebank_{tache}.py"
        if not cible.exists():
            divergences.append(f"{cible.name} : ABSENT")
            continue
        if cible.read_text(encoding="utf-8") != rendre(tache, RACINE):
            divergences.append(f"{cible.name} : DIVERGE du dépôt")
    racine_txt = dest / RACINE_TXT
    if not racine_txt.exists():
        divergences.append(f"{RACINE_TXT} : ABSENT")
    elif racine_txt.read_text(encoding="utf-8").strip() != str(RACINE):
        divergences.append(f"{RACINE_TXT} : pointe ailleurs que {RACINE}")
    if divergences:
        print(f"DIVERGENCES dans {dest} :")
        for d in divergences:
            print(f"  - {d}")
        print("Corrige avec : python scripts/cron/installer.py")
        return 1
    print(f"OK — les {len(TACHES)} lanceurs et {RACINE_TXT} correspondent au dépôt.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verifier", action="store_true",
                    help="compare l'installation aux sources, exit 1 si divergence")
    ap.add_argument("--destination", type=Path, default=DEFAUT_DEST,
                    help=f"dossier des lanceurs installés (défaut : {DEFAUT_DEST})")
    args = ap.parse_args()
    return verifier(args.destination) if args.verifier else installer(args.destination)


if __name__ == "__main__":
    sys.exit(main())
