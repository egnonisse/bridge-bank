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
    # B2-14 (13/10/2026) : `git add -A` embarquait AUSSI les livrables d'audit
    # (audit/) — des commits de backup « fourre-tout » rendaient l'historique
    # illisible (ex. 968998f : 25 fichiers mêlant audit + état + données). Les
    # livrables d'audit se committent EXPLICITEMENT dans leur lot (règle « un lot
    # = un commit », docs/architecture.md §9) ; le backup auto ne s'en occupe plus.
    # Le reste (src, scripts, tests, docs, data, fichiers racine) reste couvert.
    run("git", "add", "-A", "--", ".", ":(exclude)audit")
    staged = run("git", "diff", "--cached", "--name-only")
    if not staged:
        # Rien de nouveau : garder le silence (cron no_agent = pas de message)
        return
    count = len(staged.splitlines())
    run("git", "commit", "-m", f"chore: backup automatique — {count} fichier(s) modifié(s)")
    push = subprocess.run(
        # --no-verify DÉLIBÉRÉ : une sauvegarde ne doit JAMAIS être bloquée par un filet
        # rouge. Ce qu'on sauvegarde ici est un ÉTAT DE TRAVAIL ; le perdre serait pire que
        # de l'intégrer rouge, et la CI signalera le rouge dans la minute. Le crochet
        # `.githooks/pre-push` bloque, lui, les poussées manuelles.
        ["git", "push", "--no-verify"], cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if push.returncode != 0:
        print(f"⚠️ Backup Bridge Bank ÉCHOUÉ : {push.stderr.strip()[-300:]}")
        sys.exit(1)
    print(f"✓ Backup Bridge Bank : {count} fichier(s) commité(s) et poussé(s) sur GitHub")


if __name__ == "__main__":
    main()
