"""Point d'entrée du rapport mensuel Bridge Bank (cron Hermes, 1er du mois).

Exécute la commande `report` (qui envoie le bilan à Telegram) et journalise
la sortie dans logs/report.log. Le répertoire du projet est résolu en absolu.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "report.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

_stdout, _stderr = sys.stdout, sys.stderr


def main() -> None:
    import argparse
    from datetime import datetime

    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"\n{'=' * 62}\n")
        fh.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Rapport mensuel\n")
        sys.stdout = sys.stderr = fh
        try:
            from src.main import cmd_report, load_dotenv
            load_dotenv()  # version locale de src.main : charge ROOT/.env en absolu, indépendant du cwd
            cmd_report(argparse.Namespace(action="show", amount=None))
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            sys.stdout, sys.stderr = _stdout, _stderr
        fh.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Terminé\n")


if __name__ == "__main__":
    main()
