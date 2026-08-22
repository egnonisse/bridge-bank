"""Seuil d'alerte +X % optimal PAR TITRE selon son historique (9 ans).

Critère : le seuil le plus bas où le signal est fiable, c.-à-d.
- % de cas en baisse à J+20 >= 65 %
- médiane du retour à J+20 <= -2 %
- au moins 8 épisodes indépendants (robustesse statistique)
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history
from src.bsapi import BSApi

hist_all = load_all_history(BSApi(), force=False)

CODES = ["SNTS", "SGBC", "SLBC", "PALC", "BOAS", "SOGC", "STBC", "SPHC", "CIEC", "ORGT"]
CANDIDATE_THRESHOLDS = [0.05, 0.08, 0.10, 0.12, 0.13, 0.15, 0.18, 0.20, 0.25]


def independent_episodes(closes, lo):
    raw = []
    for i in range(20, len(closes) - 20):
        ret = closes[i] / closes[i - 20] - 1
        if lo <= ret <= 0.65:
            raw.append(i)
    out = []
    for i in raw:
        if not out or i - out[-1] >= 10:
            out.append(i)
    return out


print(f"{'Code':>6s} {'Seuil reco':>10s} {'Épisodes':>9s} {'% baisse J+20':>13s} {'Médiane J+20':>13s}  (testés)")
print("-" * 80)
for code in CODES:
    bars = hist_all.get(code, [])
    if len(bars) < 120:
        print(f"{code:>6s}   (historique insuffisant)")
        continue
    closes = [float(b.close) for b in bars]
    chosen = None
    detail = []
    for lo in CANDIDATE_THRESHOLDS:
        idx = independent_episodes(closes, lo)
        if len(idx) < 8:
            continue
        fwds = [closes[i + 20] / closes[i] - 1 for i in idx]
        pct_down = sum(1 for f in fwds if f < 0) / len(fwds) * 100
        med = statistics.median(fwds) * 100
        detail.append((lo, len(idx), pct_down, med))
        if chosen is None and pct_down >= 65 and med <= -2:
            chosen = (lo, len(idx), pct_down, med)
    if chosen:
        lo, n, pd, md = chosen
        print(f"{code:>6s} {lo*100:>9.0f}% {n:>9d} {pd:>12.0f}% {md:>+12.1f}%  ", end="")
        print(" | ".join(f"{l*100:.0f}%→{d:.0f}%↓/{m:+.0f}%" for l, _, d, m in detail))
    else:
        print(f"{code:>6s} {'aucun':>10s}  (aucun seuil fiable dans 5-25 %)")
