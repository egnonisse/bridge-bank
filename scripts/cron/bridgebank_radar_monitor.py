"""Cron Bridge Bank : monitor de la veille radar (codes niveau 1 non traités).

Transmet la sortie du monitor ; en cas d'échec du sous-processus, imprime ERREUR +
détail : l'agent du cron se réveille alors et diagnostique au lieu d'ignorer
silencieusement.

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
CIBLE = RACINE / "scripts" / "radar_new_codes.py"
if not CIBLE.exists():
    print(f"ERREUR : {CIBLE} introuvable (dépôt incomplet ?)", file=sys.stderr)
    sys.exit(2)
try:
    out = subprocess.run([_python(RACINE), str(CIBLE)], capture_output=True,
                         text=True, timeout=600)
except subprocess.TimeoutExpired:
    print("ERREUR monitor radar : timeout (> 600 s)")
    sys.exit(0)
if out.returncode != 0:
    print(f"ERREUR monitor radar (exit {out.returncode}) : {out.stderr.strip()[-400:]}")
    sys.exit(0)
print(out.stdout.strip() or "")
