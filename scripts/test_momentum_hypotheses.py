"""Épreuve propre du MOMENTUM EXTRÊME (+100 % en 120 séances) sur la BRVM.

Question de LEO (01/09/2026) : « ce genre d'action peut être très intéressant,
le titre a quasiment triplé ». Le calcul exploratoire donnait +15,7 % médian
sur 60 séances après un triplement — mais avec 2 472 « épisodes » glissants
non indépendants, brut de frais, sans règle de sortie.

Cette épreuve corrige les 4 biais :
  1. DÉSAGRÉGATION : un seul épisode par rallye (cooldown 120 séances/titre).
  2. FRAIS RÉELS : commission(min 1 000 F) à l'entrée ET à la sortie.
  3. RÈGLE DE SORTIE : 3 variantes (60j fixe, 120j fixe, stop −15 % + 60j).
  4. OUT-OF-SAMPLE : calibrage 2017-2022, test 2023-2026.

Challenges intégrés (sensibilités) :
  - entrée à l'OPEN de J+1 (réalité d'exécution BSTrade, pas de look-ahead) ;
  - exclusion des sauts > 2,5× en une séance (regroupements de nominal) ;
  - filtre de liquidité (volume × cours ≥ 5 M F/jour) en sensibilité ;
  - benchmark : le « trade aléatoire » médian (toutes fenêtres de 60 séances).
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history
from src.bsapi import BSApi
from src.taxation import commission

COOLDOWN = 120          # séances sans nouveau signal après une entrée (désagrégation)
WIN = 120               # fenêtre de mesure du doublement
HOLD_A = 60             # sortie variante A
HOLD_B = 120            # sortie variante B
STOP = 0.15             # stop variante C
AMOUNTS = (70_000.0, 150_000.0)
LIQ_MIN_DAILY = 5_000_000.0  # volume × cours ≥ 5 M F/jour (sensibilité)

hist_all = load_all_history(BSApi(), force=False)


def has_artifact(closes, i: int, span: int = 130) -> bool:
    """Saut d'une séance > 2,5× (regroupement de nominal probable) dans la fenêtre."""
    lo, hi = max(1, i - 10), min(len(closes) - 1, i + span)
    for j in range(lo + 1, hi + 1):
        if closes[j - 1] > 0 and closes[j] > 0 and closes[j] / closes[j - 1] > 2.5:
            return True
    return False


def run(bars, bounds, hold: int, use_stop: bool, amount: float,
        min_liq: float | None) -> list[float]:
    """Épisodes désagrégés, entrée open J+1, frais réels. Retourne les rendements nets."""
    closes = [float(b.close) for b in bars]
    opens = [float(b.open) for b in bars]
    vols = [float(b.volume) for b in bars]
    rets, cooldown_until = [], -1
    for i in range(WIN + 1, len(closes) - hold - 1):
        d = str(bars[i].date)[:10]
        if (bounds[0] and d < bounds[0]) or (bounds[1] and d >= bounds[1]):
            continue
        if i < cooldown_until:
            continue
        if closes[i] <= 0 or closes[i - WIN] <= 0 or closes[i] / closes[i - WIN] < 2.0:
            continue
        if has_artifact(closes, i):
            continue
        if min_liq is not None:
            med_vol = statistics.median(vols[max(0, i - 20):i])
            if med_vol * closes[i] < min_liq:
                continue
        entry = opens[i + 1] if opens[i + 1] > 0 else closes[i + 1]
        qty = (amount - commission(amount)) / entry
        stop_price = entry * (1 - STOP)
        exit_i = i + 1 + hold
        if use_stop:
            for j in range(i + 2, exit_i + 1):
                if closes[j] <= stop_price:
                    exit_i = j
                    break
        p_out = closes[min(exit_i, len(closes) - 1)]
        cash = qty * p_out - commission(qty * p_out)
        rets.append(cash / amount - 1.0)
        cooldown_until = i + COOLDOWN
    return rets


def summarize(label: str, rets: list[float], amount: float) -> None:
    if not rets:
        print(f"  {label:<46} : aucun épisode")
        return
    med = statistics.median(rets) * 100
    mean = statistics.mean(rets) * 100
    win = sum(1 for r in rets if r > 0) / len(rets) * 100
    print(f"  {label:<46} : n={len(rets):>3} | méd {med:+6.1f} % | moy {mean:+6.1f} % | "
          f"gagnants {win:>4.0f} % | pire {min(rets)*100:+6.1f} % | best {max(rets)*100:+6.1f} %")


def benchmark(bounds) -> float:
    """Trade aléatoire médian : rendement de TOUTES les fenêtres de 60 séances, brut."""
    all_win = []
    for code in hist_all:
        bars = [b for b in hist_all[code]
                if (not bounds[0] or str(b.date)[:10] >= bounds[0])
                and (not bounds[1] or str(b.date)[:10] < bounds[1])]
        closes = [float(b.close) for b in bars]
        for i in range(21, len(closes) - HOLD_A):
            if closes[i] > 0 and closes[i + HOLD_A] > 0 and closes[i - 1] > 0:
                if abs(closes[i] / closes[i - 1] - 1) < 0.5:  # hors artefacts
                    all_win.append(closes[i + HOLD_A] / closes[i] - 1)
    return statistics.median(all_win) * 100


for bounds, period in (((None, "2023-01-01"), "CALIBRAGE 2017-2022"),
                       (("2023-01-01", None), "TEST 2023-2026")):
    lo, hi = bounds
    print(f"\n{'=' * 100}\n{period}\n{'=' * 100}")
    bm = benchmark(bounds)
    print(f"  Benchmark « trade aléatoire » médian (60 séances, brut)        : {bm:+5.1f} %\n")
    for amount in AMOUNTS:
        print(f"  — Taille de position {amount:,.0f} F —")
        for label, hold, use_stop in (("sortie fixe 60 séances", HOLD_A, False),
                                      ("sortie fixe 120 séances", HOLD_B, False),
                                      ("stop −15 % + sortie 60 séances", HOLD_A, True)):
            rets = []
            for code in hist_all:
                bars = hist_all[code]
                if len(bars) < 2 * WIN + 60:
                    continue
                rets += run(bars, bounds, hold, use_stop, amount, min_liq=None)
            summarize(label, rets, amount)
        liq_rets = []
        for code in hist_all:
            bars = hist_all[code]
            if len(bars) < 2 * WIN + 60:
                continue
            liq_rets += run(bars, bounds, HOLD_A, False, amount, min_liq=LIQ_MIN_DAILY)
        summarize("SENSIBILITÉ : + filtre liquidité ≥ 5 M F/j", liq_rets, amount)
    print()
