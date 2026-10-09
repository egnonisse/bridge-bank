"""Rafraîchit les STATISTIQUES des seuils de vente — sans jamais toucher aux seuils.

POURQUOI CE SCRIPT
------------------
Le seuil de vente stocke, à côté de sa valeur, les statistiques qui l'ont justifié
(`down_prob`, `borne_basse`, `episodes`). L'unification au 09/10/2026 a montré que ces
statistiques peuvent être PÉRIMÉES : SLBC annonçait 51 % alors que le recalcul donne 54 %
(41 cas dans les deux cas — un cas de baisse de différence, sur une série qui a évolué).

CE QU'IL MODIFIE — ET CE QU'IL NE MODIFIE PAS
---------------------------------------------
    MODIFIE     : down_prob, borne_basse, episodes, significatif  (des STATISTIQUES)
    NE TOUCHE À : threshold, mode                                 (des DÉCISIONS)

C'est la distinction de la condition n° 4 : « conserver les seuils de vente [...] Le
changement doit concerner les statistiques affichées ». Un seuil est une décision ; la
probabilité qui l'accompagne est une mesure, et une mesure se remesure.

Le `mode` n'est PAS recalculé : un `declencheur` posé volontairement doit survivre
(invariant B3 — une décision humaine ne s'efface pas lors d'un recalcul).

Tout changement réel est ÉCRIT AU JOURNAL, avec l'ancienne et la nouvelle valeur.

    python scripts/rafraichir_stats_seuils.py [--dry-run]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history  # noqa: E402
from src.bsapi import BSApi  # noqa: E402
from src import seuils_vente as sv  # noqa: E402


def main(dry_run: bool = False) -> int:
    hist = load_all_history(BSApi(), force=False)
    seuils = sv.charger()
    changements = 0

    print(f"{'titre':7s}{'seuil':>7s}  {'cas':>12s}  {'baisse':>14s}  {'borne basse':>15s}")
    print("-" * 66)

    for code, info in sorted(seuils.items()):
        bars = hist.get(code)
        if not bars:
            print(f"{code:7s}{info.get('threshold', 0)*100:6.0f}%  (pas d'historique)")
            continue

        closes = [float(b.close) for b in bars]
        seuil = float(info.get("threshold", 0.13))
        ep = sv.episodes(closes, seuil)
        if not ep:
            continue
        n = len(ep)
        k = sum(1 for r in ep if r < 0)
        recalcule = sv.evaluer(k, n)

        anciens = {c: info.get(c) for c in ("down_prob", "borne_basse", "episodes",
                                            "significatif")}
        nouveaux = {c: recalcule.get(c) for c in ("down_prob", "borne_basse", "episodes",
                                                  "significatif")}
        bouge = anciens != nouveaux

        marque = "  <-- mise a jour" if bouge else ""
        print(f"{code:7s}{seuil*100:6.0f}%  "
              f"{str(anciens['episodes']):>5s} -> {n:<4d}  "
              f"{str(anciens['down_prob']):>5s}% -> {k/n*100:<4.0f}%  "
              f"{str(anciens['borne_basse']):>5s}% -> {recalcule['borne_basse']:<3d}%{marque}")

        if bouge:
            changements += 1
            if not dry_run:
                # On ne touche NI threshold NI mode : ce sont des décisions.
                for champ, valeur in nouveaux.items():
                    info[champ] = valeur
                sv.journaliser(
                    code, avant=anciens["down_prob"], apres=recalcule["down_prob"],
                    motif="unification de la definition d'episode "
                          "(fenetres disjointes de 20 seances, sans borne haute)",
                    origine=sv.ORIGINE_AUTO,
                    methode="recalcul sur l'historique au seuil inchange du titre",
                    test={**recalcule, "mode": info.get("mode", "?")})

    if dry_run:
        print(f"\n[dry-run] {changements} seuil(s) auraient leurs statistiques mises a jour.")
        return 0

    if changements:
        try:
            sv.enregistrer(seuils, origine=sv.ORIGINE_AUTO)
        except (sv.SeuilsInvalides, sv.SeuilProtege) as exc:
            # Une mesure rafraîchie peut rendre une entrée incohérente (un `declencheur` dont
            # la preuve s'affaiblit) : l'écriture est refusée et la décision doit être REVUE
            # À LA MAIN. On le dit — on ne contourne pas.
            print(f"\nStatistiques NON ecrites : {exc}")
            print("  -> reglage a revoir a la main (aucun ecrit sur disque, journal inchange).")
            return 1
        print(f"\n{changements} seuil(s) mis a jour (seuils INCHANGES).")
        print(f"  Journal : {sv.JOURNAL_FILE}")
    else:
        print("\nAucun changement : les statistiques etaient deja a jour.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
