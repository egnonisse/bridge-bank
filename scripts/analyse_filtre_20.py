"""ANALYSE (sans implémentation) — l'exigence d'achat bas paie-t-elle ?

Question de LEO : pour viser ~20 %/an (Warren), faut-il durcir le filtre d'entrée ?
Proxy mesurable sur 9 ans (pas de DPS/PER historiques structurés) : la PROFONDEUR
du drawdown au moment de l'achat vs le haut 1 an (post-division de nominal).

Protocole :
  1. Chaque point d'achat possible (séance avec >= 250 barres de recul ET de futur)
     est classé par profondeur : d = close / max(close[-250:]) - 1.
  2. Rendement réalisé à 250 séances, NET des frais réels (commission, min 1 000 F,
     position 100 000 F, aller-retour).
  3. Déciles de profondeur : D0 (près du haut) → D9 (fond du fond).
  4. Test du « filtre 20 % » : n'acheter QUE les points profonds (d <= -70 %)
     AVEC rebond naissant (r60 > 0 — la « sortie de fond » du radar), vs
     « acheter n'importe quand » (tous les points).
  5. Calibrage 2017-2022 vs test 2023-2026.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history
from src.bsapi import BSApi
from src.taxation import commission

AMOUNT = 100_000.0
HOLD = 250  # ~1 an de séances

hist_all = load_all_history(BSApi(), force=False)


def _post_split_closes(closes: list[float]) -> list[float]:
    """Closes après la dernière division de nominal (niveaux comparables)."""
    from src.radar import _last_split_index
    return closes[_last_split_index(closes):]


def collect(hist_all, lo=None, hi=None):
    """(d, r60, r250_net) pour chaque point d'achat de la période."""
    out = []
    for code in hist_all:
        bars = [b for b in hist_all[code]
                if (not lo or str(b.date)[:10] >= lo)
                and (not hi or str(b.date)[:10] < hi)]
        if len(bars) < HOLD * 2 + 60:
            continue
        closes = _post_split_closes([float(b.close) for b in bars])
        if len(closes) < HOLD * 2 + 60:
            continue
        for i in range(HOLD, len(closes) - HOLD):
            p = closes[i]
            if p <= 0:
                continue
            past = [c for c in closes[i - HOLD:i] if c > 0]
            if not past:
                continue
            d = p / max(past) - 1.0
            r60 = p / closes[i - 60] - 1.0 if closes[i - 60] > 0 else 0.0
            sell = closes[i + HOLD]
            if sell <= 0:
                continue
            # net de frais réels (entrée + sortie, position AMOUNT)
            qty = (AMOUNT - commission(AMOUNT)) / p
            cash = qty * sell - commission(qty * sell)
            out.append((d, r60, cash / AMOUNT - 1.0))
    return out


def stats(label, rows):
    if not rows:
        print(f"  {label:<44} : aucun point")
        return
    rets = [r[2] for r in rows]
    med = statistics.median(rets) * 100
    mean = statistics.mean(rets) * 100
    win = sum(1 for r in rets if r > 0) / len(rets) * 100
    print(f"  {label:<44} : n={len(rets):>5} | méd {med:+6.1f} % | moy {mean:+6.1f} % | "
          f"gagnants {win:>3.0f} %")


for bounds, period in (((None, "2023-01-01"), "CALIBRAGE 2017-2022"),
                       (("2023-01-01", None), "TEST 2023-2026")):
    print(f"\n{'=' * 96}\n{period}\n{'=' * 96}")
    rows = collect(hist_all, bounds[0], bounds[1])
    print("Rendement à 250 séances (net frais réels, 100 kF/position) par PROFONDEUR d'achat :\n")
    deciles = sorted(rows, key=lambda r: r[0])
    n = len(deciles)
    for k in range(10):
        lo_i, hi_i = int(n * k / 10), int(n * (k + 1) / 10)
        seg = deciles[lo_i:hi_i]
        if not seg:
            continue
        d_min = min(r[0] for r in seg) * 100
        d_max = max(r[0] for r in seg) * 100
        stats(f"D{k} — achat entre {d_min:.0f} % et {d_max:.0f} % sous le haut 1 an", seg)
    print()
    deep = [r for r in rows if r[0] <= -0.70]
    deep_rebound = [r for r in deep if r[1] > 0]
    stats("« FILTRE 20 % » : fond profond (<= -70 %) SEUL", deep)
    stats("« FILTRE 20 % » : fond profond + rebond naissant (r60 > 0)", deep_rebound)
    stats("RÉFÉRENCE : acheter n'importe quand (tous les points)", rows)
