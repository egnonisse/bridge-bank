"""Validation du parseur de fondamentaux — AVANT toute reconstitution massive.

But : verifier que le BPA et les dividendes extraits sont JUSTES. Un parseur
qui se trompe d'une colonne produit des PER aberrants (NTLC a donne 0,93, ce
qui est impossible) et ruinerait tout le chantier.

Methode : on compare le PER recalcule (cours actuel / BPA du dernier exercice)
au PER de reference du dataset, lui-meme issu de la source officielle. Un ecart
superieur a 40 % signale un probleme d'extraction.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.fondamentaux_historiques import bpa_connu, collecter_titre  # noqa: E402

CODES = ["SGBC", "NTLC", "SNTS", "BOAC", "BICC", "ECOC", "ONTBF", "SLBC",
         "BOAB", "PALC", "CIEC", "CFAC", "SIVC", "UNXC", "SMBC", "BOAN"]


def main():
    ds = json.loads((RACINE / "data" / "challenge_dataset.json").read_text(encoding="utf-8"))
    per_ref = {t["code"]: t.get("per") for t in ds["titres"]}
    cours = {t["code"]: t.get("cours_final") for t in ds["titres"]}

    print("=" * 84)
    print("  VALIDATION DU PARSEUR — PER recalcule vs PER de reference")
    print("=" * 84)
    print(f"\n  {'Code':<8} {'cours':>9} {'BPA':>11} {'PER calc':>9} "
          f"{'PER ref':>9} {'ecart':>8}  verdict")
    print("  " + "-" * 74)

    bons, mauvais, sans = [], [], []
    for code in CODES:
        t = collecter_titre(code)
        b = bpa_connu(t, "2026-12-31")
        c = cours.get(code)
        ref = per_ref.get(code)
        if not b or not c or not ref:
            sans.append(code)
            print(f"  {code:<8} {c or 0:>9,.0f} {'-':>11} {'-':>9} {ref or 0:>9.2f} "
                  f"{'-':>8}  donnee manquante")
            continue
        bpa = b[1]
        per_calc = c / bpa if bpa else 0
        ecart = (per_calc / ref - 1) * 100
        ok = abs(ecart) < 40
        (bons if ok else mauvais).append(code)
        print(f"  {code:<8} {c:>9,.0f} {bpa:>11,.0f} {per_calc:>9.2f} {ref:>9.2f} "
              f"{ecart:>7.0f}%  {'OK' if ok else 'FAUX'}")

    print("\n" + "=" * 84)
    print(f"  coherents : {len(bons)}/{len(CODES)}   faux : {len(mauvais)}   "
          f"donnees manquantes : {len(sans)}")
    if mauvais:
        print(f"\n  ❌ Titres FAUX (parseur a corriger) : {', '.join(mauvais)}")
        print("     Le BPA extrait ne correspond pas a la realite : soit la ligne")
        print("     lue n'est pas l'EPS, soit le decalage de colonne est faux.")
    else:
        print("\n  ✅ Parseur fiable sur l'echantillon.")
    print("=" * 84)


if __name__ == "__main__":
    main()
