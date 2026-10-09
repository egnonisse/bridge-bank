"""Le noyau apporte-t-il VRAIMENT plus de revenu que le hasard ?

LA QUESTION QUE JE N'AVAIS PAS POSEE
------------------------------------
J'avais mesure le rendement TOTAL du noyau (dividendes reinvestis) et compare a
des paniers aleatoires. Verdict : le noyau ne bat pas le hasard.

Mais j'ai avance que le noyau a un « cahier des charges different » : produire du
REVENU. Or les paniers aleatoires encaissent EUX AUSSI des dividendes — sur la
BRVM, la plupart des titres en versent.

Donc la vraie question est :
    le noyau encaisse-t-il PLUS de revenu qu'un panier aleatoire de meme taille ?

Si oui, le noyau a bien une fonction propre (le revenu), meme sans surperformer.
Si non, mon argument ne tient pas et il faut le dire.

CE QU'ON MESURE
---------------
  - dividendes encaisses (F) et en % du capital par an, pour le noyau ;
  - les memes chiffres pour 100 paniers aleatoires de meme taille ;
  - la position du noyau dans cette distribution.
"""
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtest_noyau import _index_dates, simuler_position  # noqa: E402
from src.challenge_indicateurs import charger_historique_fondamentaux  # noqa: E402
from src.challenge_validateur import charger_historique  # noqa: E402
import random  # noqa: E402

CAPITAL = 1_000_000.0
COHORTES = ["2022-01-03", "2023-01-03", "2024-01-02", "2025-01-02"]


def revenu_panier(hist, hf, codes, date_debut, date_fin, capital):
    """Dividendes encaisses par un panier donne, en % du capital par an."""
    part = capital / len(codes)
    total = 0.0
    for code in codes:
        t = hf.get(code)
        p = simuler_position(hist[code], t.dividendes if t else [],
                             date_debut, date_fin, part)
        if p is not None:
            total += p.dividendes_encaisses
    try:
        a0, a1 = int(date_debut[:4]), int(date_fin[:4])
        annees = (a1 - a0) + (int(date_fin[5:7]) - int(date_debut[5:7])) / 12
        annees = max(annees, 0.5)
    except Exception:
        annees = 1.0
    return (total / capital / annees) * 100, total


def main():
    from src.backtest_noyau import backtester_noyau

    hist = charger_historique()
    hf = charger_historique_fondamentaux()
    fin = max(str(getattr(b, "date", ""))[:10] for bs in hist.values() for b in bs)

    print("=" * 100)
    print("  LE NOYAU APPORTE-T-IL PLUS DE REVENU QU'UN PANIER ALEATOIRE ?")
    print("=" * 100)
    print(f"\n  Capital : {CAPITAL:,.0f} F · periode jusqu'au {fin}")
    print(f"  Mesure : dividendes encaisses en % du capital initial PAR AN\n")

    univers = []
    for code, barres in hist.items():
        dates = [str(getattr(b, "date", ""))[:10] for b in barres]
        i0 = _index_dates(dates, "2022-01-03")
        if i0 is None or i0 >= len(barres) - 30:
            continue
        univers.append(code)

    rng = random.Random(11)
    lignes = []
    for cohorte in COHORTES:
        r = backtester_noyau(hist, hf, cohorte, fin, CAPITAL)
        if not r.nb_titres:
            continue
        codes_noyau = [p.code for p in r.positions]

        # 100 paniers aleatoires de MEME taille
        tirages = []
        tot_tirages = []
        for _ in range(100):
            tir = rng.sample(univers, len(codes_noyau))
            rev, tot = revenu_panier(hist, hf, tir, cohorte, fin, CAPITAL)
            tirages.append(rev)
            tot_tirages.append(tot)
        med = statistics.median(tirages)
        p_mieux = sum(1 for x in tirages if x >= r.revenu_annuel_pct) / len(tirages)

        lignes.append((cohorte, r, med, p_mieux))

        print("-" * 100)
        print(f"  COHORTE {cohorte}   ({r.nb_titres} titres)")
        print("-" * 100)
        print(f"    noyau              : {r.revenu_annuel_pct:>7.2f} %/an   "
              f"({r.dividendes_totaux:>12,.0f} F encaisses)")
        print(f"    panier aleatoire   : {med:>7.2f} %/an   (mediane de 100 tirages)")
        print(f"    avantage           : {r.revenu_annuel_pct - med:>+7.2f} pts")
        print(f"    p (part des tirages faisant aussi bien ou mieux) : {p_mieux:.3f}")

    # --- Synthese -----------------------------------------------------
    print("\n" + "=" * 100)
    print("  SYNTHESE")
    print("=" * 100)
    if lignes:
        print(f"\n  {'Cohorte':<14}{'noyau %/an':>13}{'hasard %/an':>14}"
              f"{'avantage':>11}{'p':>9}")
        print("  " + "-" * 62)
        for cohorte, r, med, p in lignes:
            print(f"  {cohorte:<14}{r.revenu_annuel_pct:>12.2f}%{med:>13.2f}%"
                  f"{r.revenu_annuel_pct - med:>+10.2f}pt{p:>9.3f}")

        moy_n = statistics.mean(r.revenu_annuel_pct for _, r, _, _ in lignes)
        moy_h = statistics.mean(m for _, _, m, _ in lignes)
        gagne = sum(1 for _, _, _, p in lignes if p < 0.05)
        print(f"\n  Moyenne noyau  : {moy_n:.2f} %/an")
        print(f"  Moyenne hasard : {moy_h:.2f} %/an")
        print(f"  Ecart          : {moy_n - moy_h:+.2f} pts")
        print(f"  Cohortes ou l'avantage est significatif (p<0,05) : {gagne}/{len(lignes)}")

        print("\n" + "=" * 100)
        if moy_n > moy_h + 0.5 and gagne >= len(lignes) // 2:
            print("  ✅ LE NOYAU APPORTE PLUS DE REVENU que le hasard.")
            print("     Son role est donc reel et distinct : il produit du cash")
            print("     plus regulierement, independamment de la performance totale.")
        elif abs(moy_n - moy_h) <= 0.5:
            print("  ⚠️  PAS DE DIFFERENCE NOTABLE de revenu avec le hasard.")
            print("     Mon argument « cahier des charges different » NE TIENT PAS :")
            print("     sur la BRVM, la plupart des titres paient des dividendes, donc")
            print("     un tirage aleatoire en touche autant. Il faut le dire.")
        else:
            print("  ❌ le hasard apporte plus de revenu.")
        print("=" * 100)


if __name__ == "__main__":
    main()
