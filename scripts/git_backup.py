"""Backup hebdomadaire Bridge Bank : commit + push vers le dépôt privé GitHub.

Silencieux (stdout vide) si rien à sauvegarder ; sinon un court message récap.
Appelé par le cron Hermes via le wrapper bridgebank_backup.py.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str) -> str:
    return subprocess.run(
        list(args), cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout.strip()


def main() -> None:
    run("git", "add", "-A")
    staged = run("git", "diff", "--cached", "--name-only")
    if not staged:
        # Rien de nouveau : garder le silence (cron no_agent = pas de message)
        return
    count = len(staged.splitlines())
    run("git", "commit", "-m", f"chore: backup automatique — {count} fichier(s) modifié(s)")
    push = subprocess.run(
        ["git", "push"], cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if push.returncode != 0:
        print(f"⚠️ Backup Bridge Bank ÉCHOUÉ : {push.stderr.strip()[-300:]}")
        sys.exit(1)
    print(f"✓ Backup Bridge Bank : {count} fichier(s) commité(s) et poussé(s) sur GitHub")


if __name__ == "__main__":
    main()
