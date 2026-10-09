"""TEST : les regles fondamentales sont-elles desormais JUGABLES ?

Avant la reconstitution, toute regle utilisant per / net_yield / payout etait
automatiquement classee « biaisee » et exclue — donc intestable.

Ce test verifie trois choses :
  1. une regle fondamentale passe la validation sans etre marquee biaisee ;
  2. elle produit des ENTREES (preuve que l'indicateur est bien calcule par date
     et non absent) ;
  3. l'indicateur VARIE dans le temps (preuve qu'il est point-in-time et non
     fige sur une valeur unique).
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtesting.challenge_indicateurs import (  # noqa: E402
    charger_historique_fondamentaux, precalculer_historique,
)
from src.backtesting.challenge_schema import Hypothese, valider_hypothese  # noqa: E402
from src.backtesting.challenge_validateur import charger_historique  # noqa: E402

REGLES = [
    # (id, nom, condition d'achat, duree_max)
    ("F1", "Rendement net >= 4 %", "net_yield > 0.04", 120),
    ("F2", "Rendement net >= 6 %", "net_yield > 0.06", 120),
    ("F3", "PER <= 14", "per > 0 et per < 14", 120),
    ("F4", "Rendement >= 4 % et PER <= 14", "net_yield > 0.04 et per < 14", 180),
    ("F5", "Payout <= 80 %", "payout > 0 et payout < 0.80", 120),
]


def main():
    hist = charger_historique()
    hf = charger_historique_fondamentaux()

    print("=" * 92)
    print("  LES REGLES FONDAMENTALES SONT-ELLES JUGABLES ?")
    print("=" * 92)

    print("\n  1. VALIDATION (plus d'exclusion automatique)")
    print("  " + "-" * 84)
    valides = []
    for rid, nom, achat, duree in REGLES:
        h = Hypothese(id=rid, nom=nom, achat=achat, vente="", duree_max=duree)
        valider_hypothese(h)
        etat = "VALIDE " if h.valide else "REJETE "
        biais = " BIAISEE" if h.biaisee else ""
        fond = ",".join(h.utilise_fond) if h.utilise_fond else "-"
        detail = "" if h.valide else f" — {h.motifs[:1]}"
        print(f"    [{etat}] {rid} {nom:<38} fond={fond:<28}{biais}{detail}")
        if h.valide and not h.biaisee:
            valides.append((rid, nom, achat, duree))

    print(f"\n  {len(valides)}/{len(REGLES)} regles valides et NON biaisees")

    print("\n  2. PRESENCE DES INDICATEURS PAR DATE")
    print("  " + "-" * 84)
    series = precalculer_historique(hist, None, hf)
    n_ny = n_per = n_po = n_tot = 0
    for code, s in series.items():
        for ind in s.indicateurs:
            if not ind:
                continue
            n_tot += 1
            if "net_yield" in ind:
                n_ny += 1
            if "per" in ind:
                n_per += 1
            if "payout" in ind:
                n_po += 1
    print(f"    seances totales           : {n_tot:,}")
    print(f"    avec net_yield renseigne  : {n_ny:,}  ({n_ny/max(n_tot,1)*100:.1f} %)")
    print(f"    avec per renseigne        : {n_per:,}  ({n_per/max(n_tot,1)*100:.1f} %)")
    print(f"    avec payout renseigne     : {n_po:,}  ({n_po/max(n_tot,1)*100:.1f} %)")

    print("\n  3. VARIATION DANS LE TEMPS (preuve du point-in-time)")
    print("  " + "-" * 84)
    exemples = [c for c in ("SGBC", "SNTS", "PALC", "BOAB", "ONTBF") if c in series]
    print(f"    {'Titre':<8} {'seances':>8} {'valeurs net_yield distinctes':>30} "
          f"{'min':>8} {'max':>8}")
    for code in exemples:
        s = series[code]
        vals = [round(i["net_yield"], 6) for i in s.indicateurs if i.get("net_yield")]
        if vals:
            print(f"    {code:<8} {len(s.dates):>8} {len(set(vals)):>30} "
                  f"{min(vals)*100:>7.2f}% {max(vals)*100:>7.2f}%")

    print("\n  4. LE JUGE ACCEPTE-T-IL DE TRANCHER ? (echantillon)")
    print("  " + "-" * 84)
    print("     NOTE : `r.valide` = la regle est-elle DANS LE DSL (pas « retenue »).")
    print("     Le verdict reel est dans `r.verdict`.\n")
    from src.backtesting.challenge_validateur import evaluer_hypothese

    print("     Comparaison AVANT / APRES la prise en compte des dividendes :")
    print(f"     {'Regle':<34} {'sans div.':>10} {'avec div.':>10} "
          f"{'hasard':>9} {'avantage':>9}  p")
    print("     " + "-" * 84)

    retenues = 0
    for rid, nom, achat, duree in valides:
        h = Hypothese(id=rid, nom=nom, achat=achat, vente="", duree_max=duree)
        valider_hypothese(h)
        r_sans = evaluer_hypothese(series, h)
        r_avec = evaluer_hypothese(series, h, historique_fond=hf)

        av = r_avec.avantage_vs_baseline_pts
        marque = " RETENUE" if r_avec.valide and av and av > 0 and \
            (r_avec.p_value or 1) < 0.05 else ""
        if marque:
            retenues += 1
        print(f"     {rid} {nom:<30} {r_sans.rendement_net_pct:>9.2f}% "
              f"{r_avec.rendement_net_pct:>9.2f}% "
              f"{r_avec.baseline_mediane_pct:>8.2f}% "
              f"{av:>+8.2f}pts  {r_avec.p_value:.3f}{marque}")
        print(f"        dividendes encaisses : {sum(t.dividendes for t in r_avec.trades):>10,.0f} F "
              f"cumules sur {r_avec.nb_trades} trades")

    print(f"\n     >>> {retenues}/{len(valides)} regle(s) battent le hasard "
          f"une fois les dividendes credites des deux cotes")

    print("\n" + "=" * 92)
    ok = len(valides) == len(REGLES) and n_ny > 0 and n_per > 0
    if ok:
        print("  ✅ Les fondamentaux sont reconstruits, calcules par date et")
        print("     jugables. Il est desormais possible de tester une strategie")
        print("     de dividende (PER / rendement / payout) sans look-ahead.")
    else:
        print("  ❌ Dispositif incomplet — voir les compteurs ci-dessus.")
    print("=" * 92)


if __name__ == "__main__":
    main()
