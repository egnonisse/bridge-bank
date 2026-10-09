"""Balayage de la taille de position : à partir de quand la spéculation
redevient-elle gagnante NET de frais réels (min 1 000 F/ordre Bridge) ?

Réponse à la question : « (a) si tu veux jouer, sans gagner ? »
Le min de 1 000 F écrase les ventes partielles ⅓ des petites poches ;
ce script mesure le net médian/moyen + % de trades gagnants pour
plusieurs tailles (poche actuelle 70 000 F → 375 000 F où la
commission redevient proportionnelle sur chaque vente ⅓).
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi
from src.taxation import commission

STOP, T1, T2, T3 = 0.15, 0.20, 0.35, 0.50
TRAILING = 0.10
SIZES = [70_000, 100_000, 150_000, 200_000, 300_000, 375_000]

hist_all = load_all_history(BSApi(), force=False)


def simulate_entry(bars, i: int, amount: float) -> tuple[float, str]:
    """Règle réelle (open J+1, frais réels) sur 60 séances."""
    closes = [float(b.close) for b in bars]
    entry = float(bars[i + 1].open) if i + 1 < len(bars) else closes[i]
    if entry <= 0:
        entry = closes[i + 1] if i + 1 < len(closes) else closes[i]
    qty = (amount - commission(amount)) / entry
    cash = 0.0
    stop = entry * (1 - STOP)
    sold_1 = sold_2 = False
    highest = entry
    reason = "zone morte"
    for j in range(i + 1, min(i + 61, len(closes))):
        p = closes[j]
        if p <= stop:
            cash += qty * p - commission(qty * p)
            qty = 0.0
            reason = "stop"
            break
        if p > highest:
            highest = p
        if not sold_1 and p >= entry * (1 + T1):
            third = qty / 3
            cash += third * p - commission(third * p)
            qty -= third
            sold_1 = True
            stop = entry
        if not sold_2 and p >= entry * (1 + T2):
            third = qty / 2
            cash += third * p - commission(third * p)
            qty -= third
            sold_2 = True
            stop = highest * (1 - TRAILING)
        if p >= entry * (1 + T3):
            cash += qty * p - commission(qty * p)
            qty = 0.0
            reason = "+50 clôture"
            break
    if qty > 0:
        last_p = closes[min(i + 60, len(closes) - 1)]
        cash += qty * last_p - commission(qty * last_p)
        if reason == "zone morte" and (sold_1 or sold_2):
            reason = "paliers partiels"
    return cash / amount - 1.0, reason


def collect_entries(bars) -> list[int]:
    """Breakouts 20j AVEC volume ≥ 2×, fenêtres à split exclues."""
    closes = [float(b.close) for b in bars]
    vols = [float(b.volume) for b in bars]
    out = []
    for i in range(21, len(closes) - 61):
        if closes[i] <= 0 or closes[i] <= max(closes[i - 20:i]):
            continue
        avg20 = statistics.mean(vols[i - 20:i])
        if avg20 <= 0 or vols[i] / avg20 < 2:
            continue
        split = False
        for j in range(max(1, i - 20), min(len(closes), i + 61)):
            if closes[j - 1] > 0 and closes[j] > 0:
                r = closes[j] / closes[j - 1]
                if r > 2.5 or r < 1 / 2.5:
                    split = True
                    break
        if not split:
            out.append(i)
    return out


print(f"{'Taille':>9} | {'entrée %':>7} | {'vente ⅓ %':>8} | {'2017-22 méd':>10} | "
      f"{'2017-22 moy':>10} | {'2023-26 méd':>10} | {'2023-26 moy':>10} | "
      f"{'gagnants 23-26':>13} | {'€/trade 23-26':>13}")
print("-" * 110)
for size in SIZES:
    ce = commission(size) / size * 100
    cp = commission(size / 3) / (size / 3) * 100
    by_period = {}
    for label, bounds in (("1719", (None, "2023-01-01")), ("2326", ("2023-01-01", None))):
        rets = []
        for code in hist_all:
            bars = [b for b in hist_all[code]
                    if (not bounds[0] or str(b.date)[:10] >= bounds[0])
                    and (not bounds[1] or str(b.date)[:10] < bounds[1])]
            if len(bars) < 140:
                continue
            for i in collect_entries(bars):
                r, _ = simulate_entry(bars, i, size)
                rets.append(r)
        by_period[label] = (statistics.median(rets), statistics.mean(rets),
                            sum(1 for r in rets if r > 0) / len(rets), rets)
    m1719, a1719, _, _ = by_period["1719"]
    m2326, a2326, win, rets = by_period["2326"]
    gain_eur = statistics.median(rets) * size
    print(f"{size:>9,} | {ce:>6.2f}% | {cp:>7.2f}% | {m1719*100:>+9.1f}% | "
          f"{a1719*100:>+9.1f}% | {m2326*100:>+9.1f}% | {a2326*100:>+9.1f}% | "
          f"{win*100:>11.0f}% | {gain_eur:>+11,.0f} F")
