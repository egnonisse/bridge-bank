"""Le NOYAU (buy & hold, dividendes reinvestis) bat-il le hasard ?

PROTOCOLE
---------
Pour chaque cohorte d'entree (debut d'annee) :
  1. selection point-in-time : titres a rendement net >= 4 %, PER <= 14,
     payout <= 80 % — avec l'information CONNUE ce jour-la ;
  2. conservation jusqu'a la fin de l'historique, dividendes REINVESTIS ;
  3. comparaison a 100 paniers ALEATOIRES de meme taille et meme periode,
     qui encaissent et reinvestissent AUSSI leurs dividendes.

La troisieme etape est la seule qui compte : un panier aleatoire sur la BRVM
touche deja des dividendes. Si on ne les lui credite pas, on se donne raison
d'avance.

CE QU'ON LIT
------------
  - rendement total, dont la part venant des dividendes reinvestis ;
  - revenu annuel encaisse (le but reel du noyau) ;
  - drawdown maximal ;
  - position du noyau dans la distribution des paniers aleatoires (p-value).
"""
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtest_noyau import (  # noqa: E402
    panier_aleatoire_noyau, backtester_noyau,
)
from src.challenge_indicateurs import charger_historique_fondamentaux  # noqa: E402
from src.challenge_validateur import charger_historique  # noqa: E402

CAPITAL = 1_000_000.0
COHORTES = ["2022-01-03", "2022-07-01", "2023-01-03", "2023-07-03",
            "2024-01-02", "2024-07-01", "2025-01-02"]


def main():
    hist = charger_historique()
    hf = charger_historique_fondamentaux()
    fin = max(str(getattr(b, "date", ""))[:10] for bs in hist.values() for b in bs)

    print("=" * 96)
    print("  LE NOYAU (buy & hold + dividendes reinvestis) BAT-IL LE HASARD ?")
    print("=" * 96)
    print(f"\n  Capital de reference : {CAPITAL:,.0f} F par cohorte")
    print(f"  Fin de periode       : {fin}")
    print(f"  Duree                : 3 a 4 ans selon la cohorte\n")

    resultats = []
    for cohorte in COHORTES:
        r = backtester_noyau(hist, hf, cohorte, fin, CAPITAL)
        if not r.nb_titres:
            print(f"  {cohorte}  AUCUN TITRE ne passe les filtres a cette date")
            continue
        base = panier_aleatoire_noyau(hist, hf, r.nb_titres, cohorte, fin,
                                      CAPITAL, tirages=100)
        med = statistics.median(base) if base else 0.0
        p = (sum(1 for x in base if x >= r.rendement_total_pct) / len(base)
             if base else None)
        resultats.append((cohorte, r, med, p))

        print("-" * 96)
        print(f"  COHORTE {cohorte}   {r.nb_titres} titres selectionnes")
        print("-" * 96)
        print(f"    rendement TOTAL (dividendes reinvestis) : "
              f"{r.rendement_total_pct:>+8.2f} %")
        print(f"      dont sans reinvestir les dividendes   : "
              f"{r.rendement_vs_prix_seul_pct:>+8.2f} %")
        print(f"    dividendes encaisses                    : "
              f"{r.dividendes_totaux:>12,.0f} F  "
              f"({r.revenu_annuel_pct:.2f} % du capital par an)")
        print(f"    reinvestissements                       : "
              f"{r.nb_reinvestissements:>12}")
        print(f"    drawdown maximal du portefeuille        : "
              f"{r.drawdown_max_pct:>+8.2f} %")
        print(f"    panier ALEATOIRE (mediane, 100 tirages) : {med:>+8.2f} %")
        if p is not None:
            print(f"    avantage vs hasard                      : "
                  f"{r.rendement_total_pct - med:>+8.2f} pts   p = {p:.3f}")
        titres = sorted(r.detail_par_titre.items(),
                        key=lambda x: -x[1]["rendement_pct"])
        print(f"    composition : " + ", ".join(t for t, _ in titres[:8])
              + ("..." if len(titres) > 8 else ""))

    # ------------------------------------------------------------------
    #  SYNTHESE
    # ------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("  SYNTHESE")
    print("=" * 96)
    if resultats:
        print(f"\n  {'Cohorte':<14}{'titres':>7}{'total':>10}{'hasard':>10}"
              f"{'avantage':>10}{'p':>8}{'revenu/an':>11}{'ddmax':>9}")
        print("  " + "-" * 86)
        gagne = 0
        for cohorte, r, med, p in resultats:
            av = r.rendement_total_pct - med
            if av > 0 and p is not None and p < 0.05:
                gagne += 1
            print(f"  {cohorte:<14}{r.nb_titres:>7}{r.rendement_total_pct:>9.1f}%"
                  f"{med:>9.1f}%{av:>+9.1f}pts{(p if p else 0):>8.3f}"
                  f"{r.revenu_annuel_pct:>10.2f}%{r.drawdown_max_pct:>8.1f}%")

        n = len(resultats)
        tot_moy = statistics.mean(r.rendement_total_pct for _, r, _, _ in resultats)
        has_moy = statistics.mean(m for _, _, m, _ in resultats)
        rev_moy = statistics.mean(r.revenu_annuel_pct for _, r, _, _ in resultats)

        print(f"\n  Moyenne : noyau {tot_moy:+.1f} %  contre hasard {has_moy:+.1f} %  "
              f"→ {'AVANTAGE' if tot_moy > has_moy else 'RETARD'} de "
              f"{abs(tot_moy - has_moy):.1f} pts")
        print(f"  Revenu annuel moyen encaisse : {rev_moy:.2f} % du capital")
        print(f"  Cohortes ou le noyau bat le hasard de facon significative : "
              f"{gagne}/{n}")

        print("\n  RAPPEL DE LECTURE")
        print("  -----------------")
        print("  1. La periode (2022-2026) est HAUSSIERE : un panier aleatoire y")
        print("     performe bien. Ne pas battre le hasard ici ne condamne PAS le")
        print("     noyau — ca dit que le marche monte, pas que la selection est nulle.")
        print("  2. Le noyau vise un REVENU regulier, pas la surperformance. Le")
        print("     chiffre a regarder est 'revenu/an', pas l'ecart au hasard.")
        print("  3. 2020 (krach COVID) n'est pas couverte : la ou un noyau")
        print("     defensif se distingue vraiment, on ne peut pas la mesurer.")
    print("=" * 96)


if __name__ == "__main__":
    main()
