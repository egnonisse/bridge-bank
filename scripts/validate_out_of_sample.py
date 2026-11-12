"""Validation out-of-sample des seuils + simulation AVEC frais (1,4 %/transaction).

Protocole :
- IN-SAMPLE   : 2017-2022 (calibrage des seuils)
- OUT-OF-SAMPLE : 2023-2026 (validation — les seuils n'ont jamais vu ces données)
- Frais : 1,4 % par transaction (courtage 0,8 % + TVA + BRVM), appliqués à chaque
  vente/achat dans la simulation complète des règles spéculation.

Sorties :
A. Seuil noyau SNTS : optimal in-sample → confirmé out-of-sample ?
B. Paliers spéculation : simulation de la règle réelle avec frais, par période.
C. Zone morte : retour médian net (liquidation avec frais).
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi

FEE = 0.014  # ~1,4 % par transaction (courtage 0,8 % + TVA 18 % + BRVM 0,456 %)
STOP, T1, T2, T3 = 0.15, 0.20, 0.35, 0.50
TRAILING = 0.10
SPLIT_DATE = "2023-01-01"  # frontière in-sample / out-of-sample

hist_all = load_all_history(BSApi(), force=False)


def bars_in(code: str, after: str = "", before: str = ""):
    out = []
    for b in hist_all.get(code, []):
        d = str(b.date)[:10]
        if after and d < after:
            continue
        if before and d >= before:
            continue
        out.append(b)
    return out


def independent_episodes(bars, lo=0.13, hi=0.65):
    closes = [float(b.close) for b in bars]
    raw = [i for i in range(20, len(closes) - 20)
           if lo <= closes[i] / closes[i - 20] - 1 <= hi]
    out = []
    for i in raw:
        if not out or i - out[-1] >= 10:
            out.append(i)
    return out


def print_section(title: str) -> None:
    print("\n" + "=" * 74 + f"\n{title}\n" + "=" * 74)


# ------------------------------------------------- A. seuil noyau SNTS
print_section("A. SEUIL NOYAU SNTS — calibrage in-sample (2017-2022) → validation (2023-2026)")
for label, period_bars in (("IN-SAMPLE 2017-2022", bars_in("SNTS", before=SPLIT_DATE)),
                           ("OUT-OF-SAMPLE 2023-2026", bars_in("SNTS", after=SPLIT_DATE))):
    closes = [float(b.close) for b in period_bars]
    row = []
    for th in (0.10, 0.12, 0.13, 0.15):
        idx = independent_episodes(period_bars, lo=th)
        if len(idx) < 5:
            row.append(f"  {th*100:.0f}% : {len(idx)} ép. (trop peu)")
            continue
        fwds = [closes[i + 20] / closes[i] - 1 for i in idx]
        down = sum(1 for f in fwds if f < 0) / len(fwds) * 100
        med = statistics.median(fwds) * 100
        row.append(f"  {th*100:.0f}% : {len(idx)} ép. · {down:.0f}% ↓ J+20 · médiane {med:+.1f}%")
    print(f"{label} ({len(closes)} barres) :")
    print("\n".join(row))

# ------------------------------------------------- B. paliers avec frais
print_section("B. PALIERS SPÉCULATION — simulation complète de la règle AVEC frais 1,4 %")


def simulate_entry(bars, i: int) -> tuple[float, str]:
    """Simule la règle réelle (stops, paliers, ventes ⅓, frais) sur 60 séances.

    Retourne (rendement net, issue). Capital initial = 1.
    """
    closes = [float(b.close) for b in bars]
    entry = closes[i]
    qty = (1.0 - FEE) / entry  # 1 F investi, frais d'entrée déduits
    cash = 0.0
    stop = entry * (1 - STOP)
    sold_1 = sold_2 = False
    highest = entry
    reason = "zone morte"
    for j in range(i + 1, min(i + 61, len(closes))):
        p = closes[j]
        # stop (suiveur inclus)
        if p <= stop:
            cash += qty * p * (1 - FEE)
            qty = 0.0
            reason = "stop"
            break
        if p > highest:
            highest = p
        # palier +20 : vendre 1/3, stop -> break-even
        if not sold_1 and p >= entry * (1 + T1):
            third = qty / 3
            cash += third * p * (1 - FEE)
            qty -= third
            sold_1 = True
            stop = entry
        # palier +35 : vendre 1/3, stop suiveur
        if not sold_2 and p >= entry * (1 + T2):
            third = qty / 2  # 1/3 de la position initiale = 1/2 de ce qui reste
            cash += third * p * (1 - FEE)
            qty -= third
            sold_2 = True
            stop = highest * (1 - TRAILING)
        # palier +50 : clôture
        if p >= entry * (1 + T3):
            cash += qty * p * (1 - FEE)
            qty = 0.0
            reason = "+50 clôture"
            break
    if qty > 0:  # fin de fenêtre : liquidation théorique avec frais
        cash += qty * closes[min(i + 60, len(closes) - 1)] * (1 - FEE)
        if reason == "zone morte" and (sold_1 or sold_2):
            reason = "paliers partiels"
    return cash - 1.0, reason  # capital initial = 1 F


for label, bounds in (("IN-SAMPLE 2017-2022", (None, SPLIT_DATE)),
                      ("OUT-OF-SAMPLE 2023-2026", (SPLIT_DATE, None))):
    total_rets: list[float] = []
    total_n = 0
    reasons_all: list[str] = []
    for code in hist_all:
        bars = bars_in(code, after=bounds[0] or "", before=bounds[1] or "")
        if len(bars) < 140:
            continue
        closes = [float(b.close) for b in bars]
        vols = [float(b.volume) for b in bars]
        for i in range(21, len(closes) - 60):
            if closes[i] <= 0 or closes[i] <= max(closes[i - 20:i]):
                continue
            avg20 = statistics.mean(vols[i - 20:i])
            if avg20 <= 0 or vols[i] < 2 * avg20:
                continue
            r, reason = simulate_entry(bars, i)
            total_rets.append(r)
            reasons_all.append(reason)
            total_n += 1
    print(f"\n{label} (tous titres) : {total_n} entrées — rendement net médian "
          f"{statistics.median(total_rets)*100:+.1f} % · moyen {statistics.mean(total_rets)*100:+.1f} %")
    for reason in ("stop", "+50 clôture", "paliers partiels", "zone morte"):
        cnt = reasons_all.count(reason)
        print(f"    {reason:<16s}: {cnt:>4d} ({cnt/total_n*100:.0f} %)")
    print(f"    gagnants nets : {sum(1 for r in total_rets if r > 0)/total_n*100:.0f} %")

# ------------------------------------------------- C. zone morte nette
print_section("C. ZONE MORTE — retour médian NET (liquidation avec frais) après J+60")
for label, bounds in (("IN-SAMPLE 2017-2022", (None, SPLIT_DATE)),
                      ("OUT-OF-SAMPLE 2023-2026", (SPLIT_DATE, None))):
    nets: list[float] = []
    for code in hist_all:
        bars = bars_in(code, after=bounds[0] or "", before=bounds[1] or "")
        if len(bars) < 240:
            continue
        closes = [float(b.close) for b in bars]
        vols = [float(b.volume) for b in bars]
        for i in range(21, len(closes) - 180):
            if closes[i] <= 0 or closes[i] <= max(closes[i - 20:i]):
                continue
            avg20 = statistics.mean(vols[i - 20:i])
            if avg20 <= 0 or vols[i] < 2 * avg20:
                continue
            _, reason = simulate_entry(bars, i)
            if reason != "zone morte":
                continue  # même détection que la simulation B
            nets.append(closes[i + 120] / closes[i + 60] * (1 - FEE) - 1)
    print(f"{label} : {len(nets)} zones mortes détectées")
    if nets:
        print(f"    J+60 → J+120 : médiane nette {statistics.median(nets)*100:+.1f} % "
              f"· moyenne {statistics.mean(nets)*100:+.1f} % · "
              f"{sum(1 for r in nets if r > 0)/len(nets)*100:.0f} % positives")
