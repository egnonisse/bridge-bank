"""Épreuve : après une baisse de -15 % (depuis un pic récent), que se passe-t-il ?

Questions : combien de temps pour revenir au niveau d'avant ? Quel rebond
médian à +20/+60/+120 séances ? Et combien continuent de chuter (le stop
a-t-il sauvé ou est-on parti trop tôt) ?

Usage : python scripts/epreuve_apres_moins15.py
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi

hist = load_all_history(BSApi(), force=False)

eps = []  # (code, index du point -15 %, pic atteint, suite des closes)
for code, bars in hist.items():
    closes = [b.close for b in bars]
    if len(closes) < 400 or closes[0] <= 0:
        continue
    i = 0
    while i < len(closes) - 260:
        # pic local : plus haut des 60 séances précédentes
        pic_i = i
        while pic_i < len(closes) - 260:
            # descend jusqu'à -15 % sous le pic des 60 dernières séances
            ref = max(closes[max(0, pic_i - 60): pic_i + 1])
            hit = next((j for j in range(pic_i + 1, len(closes) - 252)
                        if closes[j] / ref - 1 <= -0.15), None)
            if hit is None:
                break
            eps.append((code, hit, ref, closes))
            pic_i = hit + 60  # épisode suivant au moins 60 séances plus loin
            i = hit + 1
        i += 60

print(f"{len(eps)} épisodes de -15 % détectés sur 10 ans.\n")

# 1. temps pour REVENIR au pic (référence)
retours = []
for code, hit, ref, closes in eps:
    j = next((k for k in range(hit + 1, len(closes)) if closes[k] >= ref), None)
    if j is not None:
        retours.append((j - hit) / 21)  # en mois
if retours:
    print(f"Retour au niveau d'avant : {len(retours)}/{len(eps)} cas "
          f"({len(retours)/len(eps)*100:.0f} %) — temps médian {statistics.median(retours):.1f} mois")

# 2. rebond médian après le point -15 %
for h, label in ((20, "20 séances (~1 mois)"), (60, "60 séances (~3 mois)"),
                 (120, "120 séances (~6 mois)"), (252, "252 séances (~1 an)")):
    reb = []
    for code, hit, ref, closes in eps:
        if hit + h < len(closes):
            reb.append(closes[hit + h] / closes[hit] - 1)
    if reb:
        print(f"Rebond médian à +{label:<20}: {statistics.median(reb)*100:+.1f} % "
              f"({sum(1 for r in reb if r > 0)/len(reb)*100:.0f} % positifs)")

# 3. le stop a-t-il sauvé ? après -15 %, combien continuent vers -25/-35 % ?
for seuil in (-0.25, -0.35):
    n = 0
    for code, hit, ref, closes in eps:
        fut = closes[hit: hit + 252]
        if fut and min(fut) / closes[hit] - 1 <= seuil - (-0.15):
            n += 1
    print(f"Après -15 %, {n}/{len(eps)} cas ({n/len(eps)*100:.0f} %) ont encore "
          f"chuté jusqu'à {seuil*100:.0f} % supplémentaires dans l'année")
