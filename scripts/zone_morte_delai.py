"""Délai de conservation optimal des positions spéculatives « zone morte ».

Question : un setup qui n'a touché ni +20 % ni −15 % après 60 séances — faut-il
clôturer ou garder ? On suit ces positions 60 et 120 séances de plus et on mesure
leurs chances de sortir de la zone (par le haut ou par le bas).
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi

STOP, T1 = -0.15, 0.20
FOLLOW = 180  # suivi total depuis l'entrée (séances)

hist_all = load_all_history(BSApi(), force=False)

entries = []
for code, bars in hist_all.items():
    if len(bars) < 200:
        continue
    closes = [float(b.close) for b in bars]
    vols = [float(b.volume) for b in bars]
    for i in range(21, len(closes) - FOLLOW):
        if closes[i] <= 0 or closes[i] <= max(closes[i - 20:i]):
            continue
        avg20 = statistics.mean(vols[i - 20:i])
        if avg20 <= 0 or vols[i] < 2 * avg20:
            continue
        entries.append((code, i))

print(f"Entrées simulées : {len(entries)}\n")


def track(positions, from_day, until_day):
    """Suivi de positions entre from_day et until_day (offsets depuis l'entrée)."""
    up = down = dead = 0
    returns = []
    for code, i in positions:
        closes = [float(b.close) for b in hist_all[code]]
        entry = closes[i]
        seg = closes[i + from_day + 1:i + until_day + 1]
        if not seg:
            continue
        hi = max(seg) / entry - 1
        lo = min(seg) / entry - 1
        returns.append(seg[-1] / entry - 1)
        if hi >= T1:
            up += 1
        elif lo <= STOP:
            down += 1
        else:
            dead += 1
    return up, down, dead, returns


# Zone morte à J+60 : ni +20 ni −15 sur les 60 premières séances
dead60 = []
for code, i in entries:
    closes = [float(b.close) for b in hist_all[code]]
    entry = closes[i]
    seg = closes[i + 1:i + 61]
    if max(seg) / entry - 1 < T1 and min(seg) / entry - 1 > STOP:
        dead60.append((code, i))

print(f"Zone morte à J+60 : {len(dead60)} positions ({len(dead60)/len(entries)*100:.1f} % des entrées)\n")

print("Que deviennent-elles ensuite ?")
print(f"{'Fenêtre suivante':<22s} {'% perce +20':>11s} {'% stop −15':>10s} {'% reste morte':>12s} {'Retour médian':>14s}")
for start, end, label in ((60, 120, "J+60 → J+120"), (120, 180, "J+120 → J+180")):
    if start >= FOLLOW:
        break
    # ne garder que les positions avec assez d'historique
    eligible = [(c, i) for c, i in dead60 if i + end < len(hist_all[c])]
    if not eligible:
        continue
    up, down, dead, returns = track(eligible, start, end)
    n = up + down + dead
    print(f"{label:<22s} {up/n*100:>10.1f}% {down/n*100:>9.1f}% {dead/n*100:>11.1f}% "
          f"{statistics.median(returns)*100:>+13.1f}%")

# demi-vie : au bout de combien de temps la moitié des morts sont sorties de la zone
print("\nSortie cumulée de la zone morte (demi-vie) :")
for horizon in (80, 100, 120, 140, 160, 180):
    exited = 0
    total = 0
    for code, i in dead60:
        if i + horizon >= len(hist_all[code]):
            continue
        closes = [float(b.close) for b in hist_all[code]]
        entry = closes[i]
        seg = closes[i + 61:i + horizon + 1]
        if max(seg) / entry - 1 >= T1 or min(seg) / entry - 1 <= STOP:
            exited += 1
        total += 1
    print(f"  J+{horizon}: {exited/total*100:.0f} % sont sortis (perce +20 % ou stop −15 %)")
