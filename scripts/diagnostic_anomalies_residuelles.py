"""Diagnostic des anomalies RESTANTES apres ajustement des divisions.

Deux questions :
  1. Pourquoi 3 titres (BOAB, PALC, SIBC) ne sont-ils pas ajustes ?
  2. Pourquoi le drawdown median reste-t-il a -89 % ?

Le drawdown est calcule sur une base AJUSTEE. S'il reste anormal, c'est qu'il
existe une AUTRE famille d'anomalies : valeurs aberrantes isolees, jours a
cours nul, ou barres dupliquees.
"""
import pickle
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.collecte.cache_integrity import _is_probable_split  # noqa: E402
from src.ajustement import ajuster_historique, ratio_rond  # noqa: E402

DATA = RACINE / "data"
with open(DATA / "history_cache.pkl", "rb") as fh:
    hist = pickle.load(fh)

print("=" * 86)
print("  QUESTION 1 — POURQUOI CES 3 TITRES NE SONT PAS AJUSTES ?")
print("=" * 86)

for code in ("BOAB", "PALC", "SIBC"):
    if code not in hist:
        continue
    barres = hist[code]
    closes = [float(b.close) for b in barres]
    dates = [str(b.date)[:10] for b in barres]
    print(f"\n  {code}")
    for i in range(1, len(closes)):
        if not closes[i - 1] or not closes[i]:
            continue
        rapport = closes[i - 1] / closes[i]
        if rapport < 1.8:
            continue
        rond = ratio_rond(rapport)
        confirm = _is_probable_split(closes, i)
        print(f"    {dates[i]}  {closes[i-1]:>10,.0f} -> {closes[i]:>9,.0f} F")
        print(f"      ratio mesure  : x{rapport:.2f}")
        print(f"      ratio rond    : {'1:' + str(rond) if rond else 'AUCUN (ecart > 5 %)'}")
        print(f"      _is_probable_split (seuil 2.5) : {confirm}")
        if rond and not confirm:
            print("      >>> REJETE : la fonction du projet exige un ratio >= 2.5")

print("\n" + "=" * 86)
print("  QUESTION 2 — DRAWDOWNS RESTANTS ANORMAUX")
print("=" * 86)

res = ajuster_historique(hist)
hist2 = res["historique"]

anomalies = []
for code, barres in hist2.items():
    cl = [float(b.close) for b in barres if getattr(b, "close", None)]
    if len(cl) < 30:
        continue
    pic, dd, pic_idx = cl[0] or 1, 0.0, 0
    pire_i = 0
    for idx, c in enumerate(cl):
        if c > pic:
            pic, pic_idx = c, idx
        if pic:
            v = (c - pic) / pic
            if v < dd:
                dd, pire_i = v, idx
    if dd < -0.85:
        dates = [str(b.date)[:10] for b in barres]
        anomalies.append({
            "code": code,
            "dd": dd * 100,
            "sommet": (cl[pic_idx], dates[pic_idx]),
            "creux": (cl[pire_i], dates[pire_i]),
            "n": len(cl),
        })

print(f"\n  {len(anomalies)} titres avec un drawdown < -85 % apres ajustement\n")
for a in sorted(anomalies, key=lambda x: x["dd"])[:12]:
    print(f"  {a['code']:8} dd={a['dd']:>7.1f} %   "
          f"sommet {a['sommet'][0]:>9,.0f} F ({a['sommet'][1]})  ->  "
          f"creux {a['creux'][0]:>9,.0f} F ({a['creux'][1]})")

# --- Recherche de la cause : sauts isoles non confirmes -------------------
print("\n" + "=" * 86)
print("  CAUSE PROBABLE : SAUTS ISOLEES NON CONFIRMES (retour au niveau)")
print("=" * 86)

sauts_isoles = []
for code, barres in hist.items():
    cl = [float(b.close) for b in barres]
    dates = [str(b.date)[:10] for b in barres]
    for i in range(2, len(cl) - 2):
        c0, c1, c2 = cl[i - 1], cl[i], cl[i + 1]
        if not c0 or not c1 or not c2:
            continue
        bas = c1 / c0 if c0 else 1
        retour = c2 / c1 if c1 else 1
        # Chute brutale PUIS retour immediat = donnee douteuse
        if bas < 0.6 and retour > 1.4:
            sauts_isoles.append({
                "code": code, "date": dates[i],
                "avant": c0, "pendant": c1, "apres": c2,
            })

print(f"\n  {len(sauts_isoles)} sauts isoles (chute puis retour) detectes")
for s in sauts_isoles[:10]:
    print(f"  {s['code']:8} {s['date']}  {s['avant']:>9,.0f} -> {s['pendant']:>8,.0f} "
          f"-> {s['apres']:>9,.0f} F")

# --- Jours a cours nul ou aberrant --------------------------------------
print("\n" + "=" * 86)
print("  AUTRES ANOMALIES")
print("=" * 86)
nuls = sum(1 for bs in hist.values() for b in bs if not getattr(b, "close", None))
print(f"  barres avec close nul : {nuls}")

doublons = 0
for code, barres in hist.items():
    dates = [str(b.date)[:10] for b in barres]
    c = Counter(dates)
    doublons += sum(v - 1 for v in c.values() if v > 1)
print(f"  barres dupliquees     : {doublons}")

print("\n" + "=" * 86)
