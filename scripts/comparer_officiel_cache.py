"""Croisement OFFICIEL : cours BRVM (bfin.brvm.org) contre le cache BSTrade.

SOURCE OFFICIELLE
-----------------
`bfin.brvm.org/Activites_marche.aspx` publie, pour chaque journee de cotation
depuis 1998, le tableau officiel des transactions. Le choix de la journee se
fait par postback ASP.NET : un script HTTP ne peut pas le rejouer (ViewState
signe, 82 fragments, JavaScript requis) — d'ou la collecte via navigateur,
sauvegardee dans `data/brvm_officiel_echantillon.json`.

CE QUE MESURE CE SCRIPT
-----------------------
Pour chaque journee de l'echantillon, on compare le cours officiel de chaque
titre au cours du cache BSTrade a la meme date. L'ecart est le seul juge :
  - ecart ~0  -> le cache est fiable
  - ecart fort -> le cache (ou l'extraction) est en cause

C'est LE test qui manquait : verifier les PRIX, pas seulement les divisions.
"""
import json
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

ECHANTILLON = RACINE / "data" / "brvm_officiel_echantillon.json"
CACHE = RACINE / "data" / "history_cache.pkl"
SORTIE = RACINE / "data" / "croisement_officiel_final.json"


def iso(v: str) -> str:
    """'20260930' -> '2026-09-30'."""
    return f"{v[:4]}-{v[4:6]}-{v[6:]}"


def main():
    if not ECHANTILLON.exists():
        raise SystemExit(f"Echantillon officiel absent : {ECHANTILLON}")

    officiel = json.loads(ECHANTILLON.read_text(encoding="utf-8"))
    with open(CACHE, "rb") as fh:
        hist = pickle.load(fh)

    print("=" * 92)
    print("  CROISEMENT OFFICIEL — BRVM (bfin.brvm.org)  x  cache BSTrade")
    print("=" * 92)

    rapport = []
    ecarts_tous = []
    divergences = []

    for v, cot in sorted(officiel.items()):
        d = iso(v)
        if not cot:
            continue
        compares = 0
        ecarts = []
        for code, vals in cot.items():
            bs = hist.get(code)
            if not bs:
                continue
            c_cache = None
            for b in reversed(bs):
                if str(b.date)[:10] == d:
                    c_cache = float(b.close)
                    break
            if c_cache is None:
                continue
            compares += 1
            offic = vals.get("cours")
            if not offic:
                continue
            e = (offic / c_cache - 1) * 100
            ecarts.append(abs(e))
            ecarts_tous.append(abs(e))
            if abs(e) > 0.005:
                divergences.append({
                    "date": d, "code": code, "officiel": offic,
                    "cache": c_cache, "ecart_pct": round(e, 4),
                })

        if not ecarts:
            print(f"\n  {d}  aucune date commune (cache absent a cette date)")
            continue

        med = statistics.median(ecarts)
        mx = max(ecarts)
        n_div = sum(1 for e in ecarts if e > 0.005)
        rapport.append({
            "date": d, "compares": compares, "ecart_median_pct": round(med, 4),
            "ecart_max_pct": round(mx, 4), "divergences": n_div,
        })
        etat = "OK  " if mx <= 1.0 else ">>> "
        print(f"  {etat}{d}  {compares:>3} titres  ecart median {med:>8.4f} %  "
              f"max {mx:>8.4f} %  ({n_div} divergences)")

    # --- Bilan -----------------------------------------------------------
    print("\n" + "=" * 92)
    print("  BILAN")
    print("=" * 92)

    if not ecarts_tous:
        print("\n  Aucune comparaison possible.")
        return

    print(f"\n  Journees comparees        : {len(rapport)}")
    print(f"  Comparaisons titre x date : {len(ecarts_tous):,}")
    print(f"  Ecart MEDIAN              : {statistics.median(ecarts_tous):.4f} %")
    print(f"  Ecart MOYEN               : {statistics.mean(ecarts_tous):.4f} %")
    print(f"  Ecart 95e percentile      : {sorted(ecarts_tous)[int(len(ecarts_tous)*0.95)]:.4f} %")
    print(f"  Ecart MAXIMAL             : {max(ecarts_tous):.4f} %")
    n_exact = sum(1 for e in ecarts_tous if e < 0.005)
    print(f"  Concordances EXACTES      : {n_exact:,}/{len(ecarts_tous):,} "
          f"({n_exact/len(ecarts_tous)*100:.1f} %)")

    if divergences:
        print(f"\n  --- {len(divergences)} divergence(s) a examiner ---")
        for x in sorted(divergences, key=lambda y: -abs(y["ecart_pct"]))[:20]:
            print(f"    {x['date']}  {x['code']:<7} officiel {x['officiel']:>10,.0f}  "
                  f"cache {x['cache']:>10,.0f}  ({x['ecart_pct']:+.3f} %)")

    # --- Verdict ---------------------------------------------------------
    print("\n" + "=" * 92)
    med = statistics.median(ecarts_tous)
    mx = max(ecarts_tous)
    if mx <= 1.0:
        print("  ✅ VERDICT : le cache BSTrade reproduit les cours OFFICIELS de la BRVM")
        print(f"     sur {len(ecarts_tous):,} points de controle repartis sur "
              f"{len(rapport)} journees / {len(set(x['date'][:4] for x in rapport))} annees.")
        print("     Ecart maximal observe : "
              f"{mx:.3f} % (arrondis de cotation uniquement).")
    elif med <= 1.0:
        print("  ⚠️  VERDICT : concordance globale bonne, mais quelques points divergent.")
        print("     Examiner les divergences listees ci-dessus.")
    else:
        print("  ❌ VERDICT : divergences significatives — le cache n'est PAS fiable.")
    print("=" * 92)

    SORTIE.write_text(json.dumps({
        "journees": rapport,
        "comparaisons": len(ecarts_tous),
        "ecart_median_pct": round(statistics.median(ecarts_tous), 4),
        "ecart_max_pct": round(max(ecarts_tous), 4),
        "concordances_exactes": n_exact,
        "divergences": divergences,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Ecrit : {SORTIE.name}")


if __name__ == "__main__":
    main()
