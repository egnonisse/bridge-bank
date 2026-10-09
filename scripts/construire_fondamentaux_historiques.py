"""Construit le cache des fondamentaux HISTORIQUES (etape 1 de l'option A).

Ce que fait le script
---------------------
Pour les 48 titres : recupere les dividendes dates et le BPA par exercice,
puis VERIFIE le BPA par controle croise (PER recalcule contre PER de reference).
Seuls les BPA verifies seront utilises par le juge.

Sortie : `data/fondamentaux_historiques.json`

Pourquoi le controle est indispensable
--------------------------------------
Mesure sur 16 titres : 10 coherents, 2 franchement faux (NTLC 20,7x trop grand,
BICC 2,3x trop petit), 4 sans donnee. Sans ce filtre, des regles fondamentales
seraient jugees sur des chiffres inventes — pire que le look-ahead qu'on corrige.
"""
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.analyse.fondamentaux_historiques import (  # noqa: E402
    collecter_titre, sauver_cache, valider_bpa,
)


def main():
    ds_path = RACINE / "data" / "challenge_dataset.json"
    if not ds_path.exists():
        raise SystemExit("challenge_dataset.json absent — le lancer d'abord")
    ds = json.loads(ds_path.read_text(encoding="utf-8"))
    refs = {t["code"]: {"cours": t.get("cours_final"), "per": t.get("per")}
            for t in ds["titres"]}
    codes = sorted(refs.keys())

    print("=" * 92)
    print("  CONSTRUCTION DU CACHE FONDAMENTAL HISTORIQUE")
    print("=" * 92)
    print(f"\n  {len(codes)} titres a collecter\n")

    titres = {}
    for i, code in enumerate(codes, 1):
        r = refs[code]
        t = collecter_titre(code, r["cours"], r["per"])
        titres[code] = t
        etat = "OK " if t.bpa_fiable else ("--" if not t.bpa else "ECARTE")
        ec = f"{t.ecart_per_pct:+.0f}%" if t.ecart_per_pct is not None else "   -"
        print(f"  [{i:>2}/{len(codes)}] {code:<8} {len(t.dividendes):>2} dividende(s)  "
              f"BPA {len(t.bpa)} an(s)  [{etat} {ec:>5}]")

    chemin = sauver_cache(titres)
    print(f"\n  Ecrit : {chemin.name}")

    # --- Bilan -----------------------------------------------------------
    print("\n" + "=" * 92)
    print("  BILAN")
    print("=" * 92)

    avec_div = [c for c, t in titres.items() if t.dividendes]
    bpa_ok = [c for c, t in titres.items() if t.bpa_fiable]
    bpa_ko = [c for c, t in titres.items() if t.bpa and not t.bpa_fiable]
    sans_bpa = [c for c, t in titres.items() if not t.bpa]

    print(f"\n  Titres avec au moins 1 dividende daté : {len(avec_div)}/{len(codes)}")
    print(f"  BPA VERIFIE (utilisable)             : {len(bpa_ok)}/{len(codes)}")
    print(f"  BPA ecarte (controle croise negatif) : {len(bpa_ko)}")
    print(f"  BPA absent                           : {len(sans_bpa)}")

    if bpa_ok:
        print(f"\n  ✅ BPA utilisables ({len(bpa_ok)}) :")
        print("     " + ", ".join(sorted(bpa_ok)))
    if bpa_ko:
        print(f"\n  ⚠️  BPA ecartes ({len(bpa_ko)}) — regles fondamentales desactivees :")
        for c in sorted(bpa_ko)[:15]:
            print(f"     {c:<8} {titres[c].notes[-1][:70]}")

    # Periode couverte par les dividendes
    from collections import Counter
    annees = Counter(d["ex_date"][:4] for t in titres.values() for d in t.dividendes)
    print(f"\n  Dividendes par annee (nombre de titres concernes) :")
    for a in sorted(annees):
        print(f"    {a}  {annees[a]:>3}  {'#' * min(annees[a], 40)}")

    exploitables = [a for a, n in annees.items() if n >= 20]
    if exploitables:
        print(f"\n  >>> FENETRE POINT-IN-TIME : {min(exploitables)} → {max(exploitables)}")

    print("\n" + "=" * 92)
    print("  ETAPE 1 TERMINEE. Prochaine etape : brancher ces donnees dans")
    print("  le calcul des indicateurs (per / net_yield / payout par date).")
    print("=" * 92)


if __name__ == "__main__":
    main()
