"""Envoie un message sur Telegram via le NOTIFIER INTERNE du projet (jobs cron agents).

POURQUOI CE SCRIPT
------------------
Les jobs cron AGENTS du projet (veille radar 09h45, analyse value 09h30) ne peuvent PAS
livrer par le gateway Hermes : `deliver=telegram` y répond `blocked_config` — « platform
'telegram' has no gateway credentials configured » — et la livraison est SUPPRIMÉE en
silence (constat du 13/10/2026 : job value en échec depuis ≥ le 07/10, radar en
`delivery: suppressed` sur tous ses runs). La règle du projet depuis le 18/09 : TOUT part
par le notifier interne (`src/notify.py`, token du projet, journalisé avec empreinte).

Les jobs no_agent le font déjà (le script envoie lui-même). Pour un job AGENT, le pont
est ce script : l'agent écrit son rapport dans un fichier, puis l'envoie ici.

USAGE (depuis un job cron agent)
--------------------------------
    cd "/c/Users/LEO/projects/Bridge Bank"
    ./.venv/Scripts/python.exe scripts/notifier_envoyer.py --fichier <chemin.txt>
    ./.venv/Scripts/python.exe scripts/notifier_envoyer.py --texte "message"
    echo "message" | ./.venv/Scripts/python.exe scripts/notifier_envoyer.py --stdin

Sortie : « envoyé » (code 0) ou la raison de l'échec (code 1) — jamais un silence.
Le journal des envois (`data/alertes_journal.jsonl`) porte la trace de chaque message.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


def main() -> int:
    ap = argparse.ArgumentParser(description="Envoi Telegram via le notifier interne du projet.")
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--fichier", type=Path, help="fichier contenant le message")
    source.add_argument("--texte", help="message en argument")
    source.add_argument("--stdin", action="store_true", help="message sur l'entrée standard")
    args = ap.parse_args()

    if args.fichier:
        if not args.fichier.exists():
            print(f"ÉCHEC : fichier introuvable — {args.fichier}")
            return 1
        texte = args.fichier.read_text(encoding="utf-8")
    elif args.texte:
        texte = args.texte
    else:
        texte = sys.stdin.read()

    if not texte.strip():
        print("ÉCHEC : message vide")
        return 1

    from src.main import get_notifier, load_config, load_dotenv

    load_dotenv()
    notifier = get_notifier(load_config())
    if not notifier.enabled:
        print("ÉCHEC : Telegram non configuré (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return 1
    if notifier.send(texte):
        print(f"envoyé ({len(texte)} caractères)")
        return 0
    print("ÉCHEC : l'API Telegram a refusé le message (voir logs)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
