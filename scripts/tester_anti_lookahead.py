"""TEST ANTI LOOK-AHEAD des fondamentaux point-in-time.

CE QU'ON VERIFIE
----------------
1. A une date donnee, le dividende utilise est bien le DERNIER DETACHE avant
   cette date — jamais un dividende futur.
2. Le BPA utilise est celui du dernier exercice PUBLIE (decalage d'un an).
3. Les indicateurs EVOLUENT avec la date : si `per` a la meme valeur en 2023 et
   en 2026, c'est que quelque chose est fige — donc faux.

Le test 1 est le plus important : il simule exactement l'erreur qu'on corrige.
On verifie que pour toute date D, aucun dividende de date de detachement > D
n'est utilise.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.challenge_indicateurs import (  # noqa: E402
    charger_historique_fondamentaux, precalculer,
)
from src.challenge_validateur import charger_historique  # noqa: E402
from src.fondamentaux_historiques import fondamentaux_a_la_date  # noqa: E402


def main():
    hist = charger_historique()
    hf = charger_historique_fondamentaux()

    print("=" * 88)
    print("  TEST ANTI LOOK-AHEAD — FONDAMENTAUX POINT-IN-TIME")
    print("=" * 88)
    print(f"\n  Cache fondamental : {len(hf)} titres")

    utilisables = [c for c, t in hf.items()
                   if (t.dividendes or t.bpa_fiable) and c in hist]
    print(f"  Titres exploitables : {len(utilisables)}")

    # ------------------------------------------------------------------
    #  TEST 1 : aucun dividende futur ne peut etre utilise
    # ------------------------------------------------------------------
    print("\n" + "-" * 88)
    print("  TEST 1 — un dividende n'est jamais connu avant son detachement")
    print("-" * 88)

    violations = 0
    verifies = 0
    for code in utilisables:
        t = hf[code]
        if not t.dividendes:
            continue
        for d in t.dividendes:
            # Juste AVANT le detachement : ce dividende ne doit pas etre connu
            from datetime import date, timedelta
            y, m, j = (int(x) for x in d["ex_date"].split("-"))
            veille = (date(y, m, j) - timedelta(days=1)).isoformat()
            f = fondamentaux_a_la_date(t, veille, 1000.0)
            verifies += 1
            if f.get("ex_date_dividende") == d["ex_date"]:
                violations += 1
                print(f"    ❌ {code} : le dividende du {d['ex_date']} est connu "
                      f"la veille ({veille})")
            # Juste APRES : il doit l'etre
            f2 = fondamentaux_a_la_date(t, d["ex_date"], 1000.0)
            if f2.get("ex_date_dividende") != d["ex_date"]:
                violations += 1
                print(f"    ❌ {code} : le dividende du {d['ex_date']} n'est PAS "
                      f"connu le jour meme")

    print(f"\n  {verifies} transitions de dividende testees, {violations} violation(s)")
    ok1 = violations == 0

    # ------------------------------------------------------------------
    #  TEST 2 : le BPA n'est connu qu'apres publication
    # ------------------------------------------------------------------
    print("\n" + "-" * 88)
    print("  TEST 2 — un BPA d'exercice N n'est pas connu pendant l'annee N")
    print("-" * 88)

    v2 = 0
    n2 = 0
    for code in utilisables:
        t = hf[code]
        if not t.bpa_fiable or not t.bpa:
            continue
        for a_str in t.bpa:
            try:
                a = int(a_str)
            except ValueError:
                continue
            # En juin de l'annee N, le BPA de N ne doit PAS etre utilise
            f = fondamentaux_a_la_date(t, f"{a}-06-30", 1000.0)
            n2 += 1
            if f.get("annee_bpa") == a_str:
                v2 += 1
                print(f"    ❌ {code} : BPA {a_str} utilise au {a}-06-30 "
                      f"(publication posterieure)")
    print(f"\n  {n2} couples (titre, exercice) testes, {v2} violation(s)")
    ok2 = v2 == 0

    # ------------------------------------------------------------------
    #  TEST 3 : les indicateurs EVOLUENT avec le temps
    # ------------------------------------------------------------------
    print("\n" + "-" * 88)
    print("  TEST 3 — les indicateurs varient selon la date (ils ne sont pas figes)")
    print("-" * 88)

    figes = []
    for code in utilisables[:12]:
        s = precalculer(hist[code], code, None, hf[code])
        # PER a 3 dates distinctes
        per_dates = {}
        for i, d in enumerate(s.dates):
            if d.endswith("-06-30") and s.indicateurs[i].get("per"):
                per_dates[d] = s.indicateurs[i]["per"]
        if len(per_dates) >= 2 and len(set(round(v, 2) for v in per_dates.values())) == 1:
            figes.append(code)
    print(f"\n  {len(utilisables[:12])} titres verifies, {len(figes)} fige(s)")
    if figes:
        print(f"    ❌ valeurs figees : {', '.join(figes)}")
    ok3 = not figes

    # ------------------------------------------------------------------
    #  EXEMPLE CONCRET
    # ------------------------------------------------------------------
    print("\n" + "-" * 88)
    print("  EXEMPLE — SGBC a travers le temps")
    print("-" * 88)
    if "SGBC" in hf:
        t = hf["SGBC"]
        print(f"\n  {'Date':<14} {'cours':>9} {'DPS connu':>11} {'BPA connu':>11} "
              f"{'per':>8} {'net_yield':>10} {'payout':>8}")
        print("  " + "-" * 76)
        for date, cours in [("2023-03-31", 19500), ("2023-12-29", 21000),
                            ("2024-12-31", 28000), ("2026-03-31", 39000),
                            ("2026-09-30", 38990)]:
            f = fondamentaux_a_la_date(t, date, cours)
            dps = f.get("dps")
            bpa = f.get("bpa")
            per = f.get("per")
            ny = f.get("net_yield")
            po = f.get("payout")
            print(f"  {date:<14} {cours:>9,} {dps if dps else 0:>11,.0f} "
                  f"{bpa if bpa else 0:>11,.0f} {per if per else 0:>8.2f} "
                  f"{(ny*100) if ny else 0:>9.2f}% {(po*100) if po else 0:>7.0f}%")
        print(f"\n  Lecture : le DPS « connu » saute en juin quand le dividende")
        print(f"  est detache, et le BPA en janvier quand les comptes sortent.")
        print(f"  C'est exactement le comportement attendu.")

    # ------------------------------------------------------------------
    print("\n" + "=" * 88)
    n_ok = sum([ok1, ok2, ok3])
    print(f"  RESULTAT : {n_ok}/3 tests passes")
    if n_ok == 3:
        print("\n  ✅ AUCUNE FUITE DU FUTUR — les regles fondamentales peuvent")
        print("     etre jugees honnetement sur la periode 2022-2026.")
    else:
        print("\n  ❌ FUITE DETECTEE — corriger avant de relancer le challenge.")
    print("=" * 88)


if __name__ == "__main__":
    main()
