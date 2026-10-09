"""Validation historique des paliers spéculation (−15 % stop, +20/+35/+50 %).

Simule la règle d'entrée réelle : breakout 20 séances + volume >= 2x moyenne 20j.
Puis suit la trajectoire 60 séances : quels paliers sont atteints, dans quel ordre,
et si le stop −15 % sauve ou coupe à tort.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi

STOP, T1, T2, T3 = -0.15, 0.20, 0.35, 0.50

hist_all = load_all_history(BSApi(), force=False)

entries = []  # (code, i) entrées simulées
for code, bars in hist_all.items():
    if len(bars) < 200:
        continue
    closes = [float(b.close) for b in bars]
    vols = [float(b.volume) for b in bars]
    for i in range(21, len(closes) - 60):
        if closes[i] <= 0:
            continue
        # breakout 20j : close > max des 20 séances précédentes
        if closes[i] <= max(closes[i - 20:i]):
            continue
        avg20 = statistics.mean(vols[i - 20:i])
        if avg20 <= 0 or vols[i] < 2 * avg20:
            continue
        entries.append((code, i))

print(f"Entrées simulées (breakout 20j + volume ≥ 2×, 9 ans, 47 titres) : {len(entries)}\n")

# trajectoire 60 séances
reached_t1 = reached_t2 = reached_t3 = 0
stopped_first = 0
both_none = 0
summits = []
for code, i in entries:
    closes = [float(b.close) for b in hist_all[code]]
    entry = closes[i]
    fut = closes[i + 1:i + 61]
    lo = min(fut) / entry - 1
    hi = max(fut) / entry - 1
    summits.append(hi)
    # ordre : premier palier touché (le plus haut avant le stop)
    if lo <= STOP and hi < T1:
        stopped_first += 1
    elif hi >= T1:
        reached_t1 += 1
        if hi >= T2:
            reached_t2 += 1
        if hi >= T3:
            reached_t3 += 1
    else:
        both_none += 1

n = len(entries)
print(f"{'Résultat 60 séances':<32s} {'N':>5s} {'%':>6s}")
print("-" * 46)
print(f"{'Atteint +20 % (1er palier)':<32s} {reached_t1:>5d} {reached_t1/n*100:>5.1f}%")
print(f"{'Atteint +35 % (2e palier)':<32s} {reached_t2:>5d} {reached_t2/n*100:>5.1f}%")
print(f"{'Atteint +50 % (clôture)':<32s} {reached_t3:>5d} {reached_t3/n*100:>5.1f}%")
print(f"{'Stop −15 % avant tout palier':<32s} {stopped_first:>5d} {stopped_first/n*100:>5.1f}%")
print(f"{'Ni +20 ni −15 (zone morte)':<32s} {both_none:>5d} {both_none/n*100:>5.1f}%")
print()
if reached_t1:
    print(f"Probabilités conditionnelles : P(+35 % | +20 %) = {reached_t2/reached_t1*100:.0f} %  |  "
          f"P(+50 % | +35 %) = {reached_t3/reached_t2*100:.0f} %" if reached_t2 else
          f"P(+35 % | +20 %) = {reached_t2/reached_t1*100:.0f} %")
print(f"Sommets des winners : médiane {statistics.median(summits)*100:+.1f} %, "
      f"pire {min(summits)*100:+.1f} %")

# le stop sauve-t-il ? trajectoire APRÈS avoir touché −15 %
after_stop = []
for code, i in entries:
    closes = [float(b.close) for b in hist_all[code]]
    entry = closes[i]
    for j in range(1, 61):
        if closes[i + j] / entry - 1 <= STOP:
            fut_after = closes[i + j + 1:i + j + 21]
            if len(fut_after) == 20:
                after_stop.append(min(fut_after) / closes[i + j] - 1)
            break
if after_stop:
    print(f"\nAprès le stop −15 % : le titre continue de baisser de "
          f"{statistics.median(after_stop)*100:+.1f} % (médiane des 20 séances suivantes) — "
          f"le stop sauve {'plus' if statistics.median(after_stop) < 0 else 'moins'} que 15 %")
    print(f"  {sum(1 for x in after_stop if x < -0.10)/len(after_stop)*100:.0f} % des cas retombent "
          f"encore de −10 % ou plus après le stop")
