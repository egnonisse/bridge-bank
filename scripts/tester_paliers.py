"""Les PALIERS de sortie battent-ils une sortie simple ?

LA REGLE REELLE, APPLIQUEE EN PRODUCTION ET JAMAIS MESUREE
----------------------------------------------------------
  +20 %  -> vendre 1/3 puis stop au break-even
  +35 %  -> vendre 1/3 puis stop suiveur
  +50 %  -> clore
  garde-fou : stop a -15 % sur la position entiere.

QUATRE MODES COMPARES, SUR LES MEMES SIGNAUX D'ACHAT
----------------------------------------------------
  duree   : on garde N seances, rien d'autre (reference neutre)
  paliers : la regle ci-dessus
  stop    : stop -15 %, sinon duree N
  suiveur : stop au break-even apres +20 %, stop suiveur apres +35 %,
            SANS jamais vendre par tiers — isole l'effet des ventes partielles

CE QUE LA COMPARAISON REVELE
----------------------------
Vendre par tiers protege (on encaisse une partie du gain) mais plafonne (on
coupe les trajectoires qui font x2). Le stop au break-even evite de rendre un
gain acquis mais sort parfois trop tot. Lequel l'emporte est une question
EMPIRIQUE — c'est pourquoi on mesure au lieu de supposer.

PIEGE EVITE
-----------
Les ventes partielles supportent leur part de frais : vendre en trois fois,
c'est trois ordres, donc un cout superieur a une sortie unique. Ne pas le
compter flatterait artificiellement les paliers.
"""
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.challenge_indicateurs import (  # noqa: E402
    charger_historique_fondamentaux, precalculer_historique,
)
from src.challenge_schema import compiler, evaluer_compilee  # noqa: E402
from src.challenge_validateur import charger_historique  # noqa: E402
from src.paliers_sortie import bilan, simuler_paliers  # noqa: E402

# Regles d'achat a tester : les mieux etayees du systeme
REGLES = [
    ("R1 rebond confirme", "pos5a < 0.25 et prix_vs_mm200 > 0", 250),
    ("R2 tendance confirmee", "r120 > 0.10 et prix_vs_mm200 > 0.05 et vol60 < 0.80", 120),
    ("R5 capitulation+volume", "dd_atl < -0.80 et vol_ratio > 1.00 et r5 > 0.01", 120),
]


def main():
    hist = charger_historique()
    hf = charger_historique_fondamentaux()
    series = precalculer_historique(hist, None, hf)

    print("=" * 104)
    print("  LES PALIERS DE SORTIE BATTENT-ILS UNE SORTIE SIMPLE ?")
    print("=" * 104)
    print(f"\n  {len(series)} titres, historique 2017-2026")
    print(f"  Frais : 2,8 % par aller-retour, appliques AU PRORATA de chaque vente\n")

    synthese: dict[str, list] = {"duree": [], "paliers": [], "stop": [], "suiveur": []}

    for nom, achat, duree_max in REGLES:
        ach = compiler(achat)
        signaux = []
        for code, s in series.items():
            for i, ind in enumerate(s.indicateurs):
                if ind and evaluer_compilee(ach, ind):
                    signaux.append((code, i))
        if not signaux:
            print(f"  {nom} : aucun signal, ignore")
            continue

        print("-" * 104)
        print(f"  {nom}   ({len(signaux)} entrees)")
        print("-" * 104)
        print(f"    {'mode':<10}{'trades':>8}{'moyen':>10}{'median':>10}"
              f"{'reussite':>10}{'pire':>10}{'meilleur':>10}{'duree':>8}{'ecart-type':>12}")
        print("    " + "-" * 94)

        for mode in ("duree", "paliers", "stop", "suiveur"):
            trades = []
            for code, i in signaux:
                barres = hist.get(code)
                if barres is None:
                    continue
                t = simuler_paliers(barres, i, duree_max, mode)
                if t is not None:
                    t.code = code
                    trades.append(t)
            b = bilan(trades)
            if not b.get("n"):
                continue
            synthese[mode].extend(t.rendement_net for t in trades)
            print(f"    {mode:<10}{b['n']:>8}{b['rendement_moyen_pct']:>9.2f}%"
                  f"{b['rendement_median_pct']:>9.2f}%{b['taux_reussite']*100:>9.1f}%"
                  f"{b['pire_pct']:>9.1f}%{b['meilleur_pct']:>9.1f}%"
                  f"{b['duree_mediane']:>8.0f}{b['ecart_type_pct']:>11.1f}%")
        print()

    # --- Synthese ------------------------------------------------------
    print("=" * 104)
    print("  SYNTHESE — tous signaux confondus")
    print("=" * 104)
    print(f"\n  {'mode':<10}{'trades':>9}{'moyen':>10}{'median':>10}"
          f"{'reussite':>10}{'pire':>10}{'ecart-type':>12}")
    print("  " + "-" * 72)
    ref = None
    for mode in ("duree", "paliers", "stop", "suiveur"):
        r = synthese[mode]
        if not r:
            continue
        moy = statistics.mean(r) * 100
        if mode == "duree":
            ref = moy
        print(f"  {mode:<10}{len(r):>9}{moy:>9.2f}%"
              f"{statistics.median(r)*100:>9.2f}%"
              f"{sum(1 for x in r if x > 0)/len(r)*100:>9.1f}%"
              f"{min(r)*100:>9.1f}%{(statistics.pstdev(r)*100 if len(r)>1 else 0):>11.1f}%")

    if ref is not None:
        print(f"\n  Ecart au mode « duree » (reference neutre) :")
        for mode in ("paliers", "stop", "suiveur"):
            r = synthese[mode]
            if not r:
                continue
            moy = statistics.mean(r) * 100
            verdict = ("MEILLEUR" if moy > ref else "MOINS BON")
            print(f"    {mode:<10} {moy - ref:>+7.2f} pts   ({verdict})")

    print("\n  COMMENT LIRE")
    print("  ------------")
    print("  1. Un mode avec un ecart-type plus faible mais un rendement moindre")
    print("     n'est pas « pire » : il prend moins de risque par trade.")
    print("  2. Le taux de reussite eleve des paliers est ATTENDU (on encaisse tot)")
    print("     et ne suffit pas : le rendement moyen compte autant.")
    print("  3. La question utile n'est pas « quel mode gagne le plus » mais")
    print("     « le gain de confort vaut-il le rendement abandonne ? ».")
    print("=" * 104)


if __name__ == "__main__":
    main()
