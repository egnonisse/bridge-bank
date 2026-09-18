"""Épreuve : « acheter bas » paie-t-il vraiment ? (calibration du prix d'entrée spé)

Pour chaque titre, le prix d'entrée est classé en percentile de sa fourchette
des 5 dernières années (tranches de 20 %). On mesure le rendement forward à
12 mois NET de frais pour CHAQUE tranche : les entrées « basses » donnent-elles
plus de gagnants et de meilleurs gains que les entrées « hautes » ?

Usage : python scripts/epreuve_acheter_bas.py
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.backtest import load_all_history
from src.bsapi import BSApi

FRAIS = 0.028
HORIZON = 252
TRANCHES = [(0, 0.20), (0.20, 0.40), (0.40, 0.60), (0.60, 0.80), (0.80, 1.01)]

hist = load_all_history(BSApi(), force=False)

res = {t: [] for t in TRANCHES}
wins = {t: 0 for t in TRANCHES}
n_by_t = {t: 0 for t in TRANCHES}
last_entry = -10**9

for code, bars in hist.items():
    closes = [b.close for b in bars]
    if len(closes) < 500 or closes[0] <= 0:
        continue
    for i in range(260, len(closes) - HORIZON):
        if i - last_entry < 60:
            continue
        window = closes[i - 260 : i]
        lo, hi = min(window), max(window)
        if hi <= lo:
            continue
        pct = (closes[i] - lo) / (hi - lo)
        for (a, b) in TRANCHES:
            if a <= pct < b:
                break
        r = closes[i + HORIZON] / closes[i] - 1 - FRAIS
        res[(a, b)].append(r)
        if r > 0:
            wins[(a, b)] += 1
        n_by_t[(a, b)] += 1
        last_entry = i

print("« Acheter bas » — 12 mois net de frais, entrées réparties (spacing 60 séances) :\n")
print(f'{"Tranche du prix (5 ans)":<28}{"n":>5}{"Gagnants":>10}{"Médiane nette":>15}{"Moyenne":>9}')
for (a, b) in TRANCHES:
    rs = res[(a, b)]
    if not rs:
        continue
    label = f"{int(a*100)}-{int(b*100)} %"
    print(f"{label:<28}{len(rs):>5}{wins[(a,b)]/len(rs)*100:>9.0f} %"
          f"{statistics.median(rs)*100:>+14.1f} %{statistics.mean(rs)*100:>+8.1f} %")
