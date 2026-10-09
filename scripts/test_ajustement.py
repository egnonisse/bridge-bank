"""Test de l'ajustement des divisions de nominal.

Compare les statistiques AVANT / APRES correction sur les titres les plus
touches, et verifie que les valeurs redeviennent plausibles.
"""
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.ajustement import ajuster_historique, detecter_divisions  # noqa: E402

DATA = RACINE / "data"
with open(DATA / "history_cache.pkl", "rb") as fh:
    hist = pickle.load(fh)

print("=" * 84)
print("  TEST DE L'AJUSTEMENT — AVANT / APRES")
print("=" * 84)


def stats(barres):
    cl = [float(b.close) for b in barres if getattr(b, "close", None)]
    if len(cl) < 30:
        return None
    perf = (cl[-1] / cl[0] - 1) * 100 if cl[0] else 0
    pic, dd = cl[0] or 1, 0.0
    for c in cl:
        pic = max(pic, c)
        if pic:
            dd = min(dd, (c - pic) / pic)
    rets = [(cl[i] - cl[i - 1]) / cl[i - 1] for i in range(1, len(cl)) if cl[i - 1]]
    vol = statistics.pstdev(rets) * (252 ** 0.5) * 100 if len(rets) > 2 else None
    return {"perf": perf, "dd": dd * 100, "vol": vol}


# Titres les plus touches
CIBLES = ["BOAC", "SGBC", "STBC", "STAC", "SIVC", "BOAN", "BOAS", "CBIBF"]

print("\n  --- TITRES LES PLUS TOUCHES ---")
for code in CIBLES:
    if code not in hist:
        continue
    barres = hist[code]
    dates = [str(getattr(b, "date", ""))[:10] for b in barres]
    closes = [float(getattr(b, "close", 0) or 0) for b in barres]
    divs = detecter_divisions(closes, dates)

    from dataclasses import replace
    copies = list(barres)
    from src.ajustement import ajuster_barres
    n = ajuster_barres(copies, dates, closes)

    a, b = stats(barres), stats(copies)
    if not a or not b:
        continue
    print(f"\n  {code}  ({n} division(s) — {', '.join(f'1:{d.ratio}' for d in divs)})")
    print(f"    performance  : {a['perf']:+9.1f} %  ->  {b['perf']:+9.1f} %")
    print(f"    drawdown max : {a['dd']:+9.1f} %  ->  {b['dd']:+9.1f} %")
    if a["vol"] and b["vol"]:
        print(f"    volatilite   : {a['vol']:+9.1f} %  ->  {b['vol']:+9.1f} %")

# --- Ajustement global ---------------------------------------------------
print("\n" + "=" * 84)
print("  AJUSTEMENT GLOBAL")
print("=" * 84)
res = ajuster_historique(hist)
hist2 = res["historique"]
print(f"  {len(res['divisions'])} titres ajustes")
for code, n in sorted(res["divisions"]):
    print(f"    {code:8} {n} division(s)")

# --- Statistiques de marche comparees ------------------------------------
def marche(h):
    perfs, dds, vols = [], [], []
    for code, barres in h.items():
        s = stats(barres)
        if s:
            perfs.append(s["perf"])
            dds.append(s["dd"])
            if s["vol"]:
                vols.append(s["vol"])
    return {
        "n": len(perfs),
        "perf_med": statistics.median(perfs),
        "dd_med": statistics.median(dds),
        "dd_pire": min(dds),
        "vol_med": statistics.median(vols) if vols else 0,
    }

m1, m2 = marche(hist), marche(hist2)
print("\n" + "=" * 84)
print("  STATISTIQUES DU MARCHE")
print("=" * 84)
print(f"  {'INDICATEUR':28} {'AVANT':>14} {'APRES':>14}")
print("  " + "-" * 58)
print(f"  {'titres':28} {m1['n']:>14} {m2['n']:>14}")
print(f"  {'drawdown median':28} {m1['dd_med']:>13.1f}% {m2['dd_med']:>13.1f}%")
print(f"  {'drawdown pire':28} {m1['dd_pire']:>13.1f}% {m2['dd_pire']:>13.1f}%")
print(f"  {'volatilite mediane (ann.)':28} {m1['vol_med']:>13.1f}% {m2['vol_med']:>13.1f}%")

print("\n" + "=" * 84)
if m2["dd_med"] > -95:
    print("  >>> LES STATISTIQUES SONT MAINTENANT PLAUSIBLES <<<")
else:
    print("  >>> ATTENTION : drawdowns encore anormaux <<<")
print("=" * 84)

# --- Sauvegarde de l'historique ajuste -----------------------------------
sortie = DATA / "history_cache_ajuste.pkl"
with open(sortie, "wb") as fh:
    pickle.dump(hist2, fh)
print(f"\n  Historique ajuste enregistre : {sortie.name} "
      f"({sortie.stat().st_size / 1024 / 1024:.1f} Mo)")
print("  (l'original history_cache.pkl est INCHANGE)")
