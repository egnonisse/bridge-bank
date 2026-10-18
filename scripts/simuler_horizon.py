"""Simulation « 1 000 000 F sur 1 an » — fenêtres glissantes sur données BRVM réelles.

DEUX SIMULATIONS, deux jeux de données RÉELS du projet (aucun chiffre inventé) :

1. **28 ans** (`data/brvm_28ans_ajuste.json`, 77 dates 1998→2026, cours ajustés des
   divisions, HORS dividendes) : un panier équipondéré des titres cotés, acheté à chaque
   date, revendu ~1 an plus tard. Distribution des rendements annuels — krachs inclus.
2. **9 ans** (`data/history_clean.pkl`, cours quotidiens 2017→2026) : LE panier de LEO
   (SGBC / SLBC / SNTS / PALC), fenêtres mensuelles de 365 jours.

Les deux mesurent le PRIX. Le dividende encaissé (+≈4,6 % net/an au taux actuel du
noyau) se lit EN PLUS : sur des cours non ajustés des dividendes, la baisse du
détachement est déjà dans le prix — le versement n'est donc pas compté deux fois.

    python scripts/simuler_horizon.py [--montant 1000000]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.infrastructure.paths import chemin_data  # noqa: E402
from src.collecte.preparation import charger_historique_propre  # noqa: E402

FRAIS_ALLER = 0.014   # 1,4 %/ordre (courtage + TVA + BRVM), règle du projet
NOYAU = ("SGBC", "SLBC", "SNTS", "PALC")


def _stats(rendements: list[float]) -> dict:
    tris = sorted(rendements)
    n = len(tris)
    return {
        "n": n,
        "mediane": statistics.median(tris),
        "moyenne": statistics.fmean(tris),
        "p10": tris[max(0, int(0.10 * (n - 1)))],
        "p90": tris[int(0.90 * (n - 1))],
        "pire": tris[0],
        "meilleur": tris[-1],
        "positifs": sum(1 for r in tris if r > 0) / n,
    }


def _afficher(titre: str, r: dict, montant: float) -> None:
    print(f"\n{titre}  ({r['n']} fenêtres de ~1 an)")
    print(f"  médiane        : {r['mediane'] * 100:+6.1f} %   "
          f"→ {montant * r['mediane']:+,.0f} F")
    print(f"  moyenne        : {r['moyenne'] * 100:+6.1f} %")
    print(f"  pire cas       : {r['pire'] * 100:+6.1f} %   "
          f"→ {montant * r['pire']:+,.0f} F")
    print(f"  1 cas sur 10 ≤ {r['p10'] * 100:+.1f} % | 1 cas sur 10 ≥ {r['p90'] * 100:+.1f} %")
    print(f"  meilleur cas   : {r['meilleur'] * 100:+6.1f} %")
    print(f"  années gagnantes : {r['positifs'] * 100:.0f} %")
    print(f"  net après frais aller-retour (−2,8 pt) : médiane "
          f"{(r['mediane'] - FRAIS_ALLER * 2) * 100:+.1f} %")


def simuler_28_ans(montant: float) -> dict:
    donnees = json.loads(chemin_data("brvm_28ans_ajuste.json").read_text(encoding="utf-8"))
    dates = sorted(donnees)
    rendements, tailles = [], []
    for i, d1 in enumerate(dates):
        t1 = date(int(d1[:4]), int(d1[4:6]), int(d1[6:8]))
        cible = t1 + timedelta(days=365)
        d2 = None
        for suivant in dates[i + 1:]:
            t2 = date(int(suivant[:4]), int(suivant[4:6]), int(suivant[6:8]))
            if abs((t2 - cible).days) <= 150:
                d2 = suivant
            if t2 > cible + timedelta(days=150):
                break
        if not d2:
            continue
        cours1, cours2 = donnees[d1], donnees[d2]
        communs = [k for k in cours1 if k in cours2 and cours1[k] and cours2[k]]
        if len(communs) < 5:          # panier trop maigre = comparaison faussée
            continue
        rendements.append(sum(cours2[k] / cours1[k] for k in communs) / len(communs) - 1)
        tailles.append(len(communs))
    r = _stats(rendements)
    r["titres_median"] = statistics.median(tailles)
    return r


def simuler_noyau(montant: float) -> dict:
    hist = charger_historique_propre()
    series = {c: sorted(hist[c], key=lambda b: str(b.date)) for c in NOYAU if c in hist}

    def prix(code: str, jour: date) -> float | None:
        """Dernière cote connue ≤ jour (forward-fill : jamais d'invention de cours)."""
        bars = series.get(code, [])
        val = None
        for b in bars:
            d = date(int(str(b.date)[:4]), int(str(b.date)[5:7]), int(str(b.date)[8:10]))
            if d <= jour:
                val = float(b.close)
            else:
                break
        return val

    debuts = sorted({str(b.date)[:7] for b in hist.get("SGBC", [])})
    rendements = []
    for mois in debuts[:-12]:
        an, mo = int(mois[:4]), int(mois[5:7])
        d1 = date(an, mo, 15)
        d2 = d1 + timedelta(days=365)
        ratios = []
        for code in NOYAU:
            p1, p2 = prix(code, d1), prix(code, d2)
            if p1 and p2:
                ratios.append(p2 / p1 - 1)
        if len(ratios) >= 3:          # au moins 3 titres des 4 disponibles à la date
            rendements.append(statistics.fmean(ratios))
    return _stats(rendements)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--montant", type=float, default=1_000_000.0)
    args = ap.parse_args()
    m = args.montant

    print("=" * 78)
    print(f"  1 000 000 F sur 1 an — fenêtres glissantes, données réelles BRVM")
    print("=" * 78)

    r28 = simuler_28_ans(m)
    _afficher(f"1. Panier BRVM équipondéré, 28 ans (1998→2026, ~"
              f"{r28['titres_median']:.0f} titres/fenêtre, hors dividendes)", r28, m)

    rn = simuler_noyau(m)
    _afficher("2. Ton noyau actuel (SGBC/SLBC/SNTS/PALC), 9 ans (2017→2026, "
              "hors dividendes)", rn, m)

    print("\n" + "-" * 78)
    print("  + DIVIDENDES : le noyau paie ≈ 4,6 % net/an (5,2 % brut) au cours actuel.")
    print("  Sur des cours RÉELS (non ajustés), la baisse du détachement est déjà dans")
    print("  le prix — le dividende encaissé s'ajoute donc SANS double comptage.")
    print("  Exemple médiane ci-dessus + 4,6 % net (théorique, si dividende maintenu).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
