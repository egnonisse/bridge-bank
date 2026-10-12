"""Point d'entrée du check quotidien Bridge Bank (Planificateur de tâches Windows).

Exécute la commande `daily` et journalise la sortie dans logs/daily.log.
Le répertoire du projet est résolu en absolu, donc le répertoire de travail
de la tâche planifiée importe peu.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "daily.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

_stdout, _stderr = sys.stdout, sys.stderr


def main() -> None:
    import argparse
    from datetime import datetime

    echec = False
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"\n{'=' * 62}\n")
        fh.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Démarrage\n")
        sys.stdout = sys.stderr = fh
        try:
            from src.main import cmd_daily, load_dotenv
            load_dotenv()  # version locale de src.main : charge ROOT/.env en absolu, indépendant du cwd
            cmd_daily(argparse.Namespace())
        except Exception:
            import traceback
            traceback.print_exc()
            echec = True
        finally:
            sys.stdout, sys.stderr = _stdout, _stderr
        fh.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Terminé{' (ÉCHEC)' if echec else ''}\n")
    if echec:
        sys.exit(1)  # B2-04 : le planificateur doit VOIR l'échec — fini le faux-vert


if __name__ == "__main__":
    main()
