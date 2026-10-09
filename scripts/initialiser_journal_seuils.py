"""Initialise le journal des seuils avec l'état ACTUEL des seuils calibrés.

Pourquoi c'est nécessaire : le journal n'existe que depuis aujourd'hui. Sans une entrée de
départ, il est vide — donc une alerte ne peut pas dire d'où vient le seuil qu'elle applique,
et le premier calibrage futur paraîtrait sorti de nulle part.

Ce script écrit une entrée « migration » pour chaque titre du fichier calibré qui n'a pas
encore d'entrée. Il est IDEMPOTENT : le relancer ne crée pas de doublon.

    python scripts/initialiser_journal_seuils.py [--dry-run]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import seuils_vente as sv  # noqa: E402


def main(dry_run: bool = False) -> int:
    calibres = sv.charger()
    if not calibres:
        print("Aucun seuil calibré dans", sv.SEUILS_FILE)
        return 1

    deja = {e["titre"] for e in sv.lire_journal()}
    ecrits = 0

    for code, info in sorted(calibres.items()):
        if code.upper() in deja:
            print(f"  {code:6s} : déjà au journal — ignoré")
            continue

        entree = {
            "horodatage": None,      # rempli par journaliser
            "titre": code.upper(),
            "avant": None,           # inconnu : le seuil existait avant le journal
            "apres": info.get("threshold"),
            "motif": sv.MOTIF_MIGRATION,
            "origine": sv.ORIGINE_MANUELLE,
            "methode": "valeur en vigueur au moment de la creation du journal",
            "test": {k: info[k] for k in
                     ("down_prob", "borne_basse", "episodes", "significatif", "mode")
                     if k in info},
        }

        seuil = (info.get("threshold") or 0) * 100
        prob = info.get("down_prob")
        mode = info.get("mode", "?")
        print(f"  {code:6s} : seuil {seuil:.0f} % · {prob} % sur "
              f"{info.get('episodes', '?')} cas · {mode}")

        if not dry_run:
            sv.journaliser(code, entree["avant"], entree["apres"], entree["motif"],
                           entree["origine"], entree["methode"], entree["test"])
        ecrits += 1

    if dry_run:
        print(f"\n[dry-run] {ecrits} entrée(s) seraient écrites.")
    else:
        total = len(sv.lire_journal())
        print(f"\n{ecrits} entrée(s) écrite(s). Journal : {total} entrée(s) au total.")
        print(f"  {sv.JOURNAL_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
