"""Profil temporel du retournement SNTS après +13 % en 20 séances (épisodes indépendants)."""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history
from src.bsapi import BSApi

hist_all = load_all_history(BSApi(), force=False)

for code in ("SNTS", "SGBC", "SLBC"):
    bars = hist_all[code]
    closes = [float(b.close) for b in bars]
    dates = [str(b.date)[:10] for b in bars]
    n = len(closes)

    raw = []
    for i in range(20, n - 60):
        ret = closes[i] / closes[i - 20] - 1
        if 0.13 <= ret <= 0.65:
            raw.append(i)
    # dédoublonner : 1 épisode par vague (>=10 séances d'écart)
    idx = []
    for i in raw:
        if not idx or i - idx[-1] >= 10:
            idx.append(i)

    print(f"=== {code} : {len(idx)} épisodes indépendants (+13 % à +65 % en 20 séances) ===")
    print(f"{'Date':>12s} {'ret20':>7s} {'J+5':>7s} {'J+20':>7s} {'J+60':>7s} {'Creux à':>9s} {'Prof.':>7s}")
    for i in idx:
        fut = closes[i + 1:i + 61]
        jmin = min(range(len(fut)), key=lambda j: fut[j])
        f5 = closes[i + 5] / closes[i] - 1
        f20 = closes[i + 20] / closes[i] - 1
        f60 = closes[i + 60] / closes[i] - 1
        print(
            f"{dates[i]:>12s} {closes[i]/closes[i-20]-1:>+6.0%} {f5:>+6.1%} {f20:>+6.1%} "
            f"{f60:>+6.1%} {'J+' + str(jmin+1):>9s} {fut[jmin]/closes[i]-1:>+6.1%}"
        )
    delais = []
    creux = []
    for i in idx:
        fut = closes[i + 1:i + 61]
        jmin = min(range(len(fut)), key=lambda j: fut[j])
        delais.append(jmin + 1)
        creux.append(fut[jmin] / closes[i] - 1)
    print(
        f"→ Délai médian du creux : {statistics.median(delais):.0f} séances | "
        f"profondeur médiane : {statistics.median(creux):+.1%} | pire : {min(creux):+.1%}"
    )
    print()
