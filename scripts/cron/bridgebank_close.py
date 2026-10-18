"""Cron Bridge Bank : check de clôture 16h (candidats spéculation à jouer demain).

Ce fichier est la SOURCE DE VÉRITÉ (versionné) ; la copie installée dans
%LOCALAPPDATA%/hermes/scripts/ est produite par scripts/cron/installer.py.
"""

# ==== bloc commun vérifié par tests/test_wrappers_cron.py (B2-08) ====
import os
import subprocess
import sys
from pathlib import Path


def _racine():
    """Découvre le dépôt Bridge Bank ; introuvable = échec BRUYANT (exit 2, raison).

    Ordre de recherche : 1) variable BRIDGEBANK_ROOT ; 2) position du fichier (valable
    dans le dépôt : scripts/cron/...) ; 3) bridgebank_root.txt voisin (posé par
    scripts/cron/installer.py) ; 4) défaut inscrit à l'installation. La copie installée
    est AUTONOME (n'importe aucun module du projet) : elle doit pouvoir signaler sa
    panne même si le dépôt a disparu — un cron inerte doit se voir le jour où il
    tourne, pas six mois après.
    """
    voisin = Path(__file__).with_name("bridgebank_root.txt")
    candidats = [os.environ.get("BRIDGEBANK_ROOT"),
                 Path(__file__).resolve().parent.parent.parent,
                 voisin.read_text(encoding="utf-8").strip() if voisin.exists() else None,
                 r"DEFAUT_INSTALLE"]
    for c in candidats:
        if c and (Path(c) / "src" / "main.py").exists():
            return Path(c)
    print("ERREUR Bridge Bank introuvable — ce cron est INERTE. Chemins essayés : "
          + " | ".join(str(c) for c in candidats if c)
          + ". Corrige : variable BRIDGEBANK_ROOT, fichier bridgebank_root.txt, ou "
          + "lance scripts/cron/installer.py depuis le dépôt.", file=sys.stderr)
    sys.exit(2)


def _python(racine):
    """L'interpréteur du projet : le venv s'il existe, sinon celui qui exécute ce fichier."""
    venv = racine / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.exists() else sys.executable
# ==== fin du bloc commun ====


RACINE = _racine()
CIBLE = RACINE / "scripts" / "close_check.py"
if not CIBLE.exists():
    print(f"ERREUR : {CIBLE} introuvable (dépôt incomplet ?)", file=sys.stderr)
    sys.exit(2)
subprocess.run([_python(RACINE), str(CIBLE)], check=True)
