"""Épreuve du groupe spéculatif : 4 hypothèses robustes sur les points morts.

H1 — Contamination par les splits : les fenêtres de simulation qui traversent
     une division de nominal (x0.05-0.27, 2017-2019) créent de FAUX stops (−80 %)
     → les backtests de la règle sont-ils biaisés ?
H2 — Le déclencheur volume ≥ 2× prédit-il vraiment le succès ? (cœur du système)
     Comparaison breakouts avec volume ≥ 2× vs < 2× + test de permutation.
H3 — Réalisme d'exécution : entrer à l'OPEN de J+1 (comme le fera le check de
     16h) au lieu de la clôture du signal change-t-il les résultats ?
H4 — Frais RÉELS des petits ordres : le minimum de 1 000 F par ordre (Bridge)
     écrase les ventes partielles d'une poche de 70 000 F → les seuils nets
     affichés (+18,6/+33,6/+48,4 %) tiennent-ils pour LEO ?
"""
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi
from src.taxation import commission

FEE = 0.014
STOP, T1, T2, T3 = 0.15, 0.20, 0.35, 0.50
TRAILING = 0.10
POCKET = 70_000.0  # poche spéculation de LEO

hist_all = load_all_history(BSApi(), force=False)


# ------------------------------------------------------------------ moteurs
def simulate_entry(bars, i: int, entry_mode: str = "close", fees_mode: str = "flat",
                   amount: float = POCKET) -> tuple[float, str]:
    """Règle réelle sur 60 séances. entry_mode: close|open_next ; fees_mode: flat|real."""
    closes = [float(b.close) for b in bars]
    if entry_mode == "open_next" and i + 1 < len(bars):
        entry = float(bars[i + 1].open)
        if entry <= 0:
            entry = closes[i + 1]
    else:
        entry = closes[i]

    def fee(montant: float) -> float:
        if fees_mode == "real":
            return commission(montant)
        return montant * FEE

    qty = (amount - fee(amount)) / entry
    cash = 0.0
    stop = entry * (1 - STOP)
    sold_1 = sold_2 = False
    highest = entry
    reason = "zone morte"
    start = i + 1 if entry_mode == "open_next" else i + 1
    for j in range(start, min(i + 61, len(closes))):
        p = closes[j]
        if p <= stop:
            cash += qty * p - fee(qty * p)
            qty = 0.0
            reason = "stop"
            break
        if p > highest:
            highest = p
        if not sold_1 and p >= entry * (1 + T1):
            third = qty / 3
            cash += third * p - fee(third * p)
            qty -= third
            sold_1 = True
            stop = entry
        if not sold_2 and p >= entry * (1 + T2):
            third = qty / 2
            cash += third * p - fee(third * p)
            qty -= third
            sold_2 = True
            stop = highest * (1 - TRAILING)
        if p >= entry * (1 + T3):
            cash += qty * p - fee(qty * p)
            qty = 0.0
            reason = "+50 clôture"
            break
    if qty > 0:
        last_p = closes[min(i + 60, len(closes) - 1)]
        cash += qty * last_p - fee(qty * last_p)
        if reason == "zone morte" and (sold_1 or sold_2):
            reason = "paliers partiels"
    return cash / amount - 1.0, reason


def has_split_in_window(closes, i: int, lo: int = 20, hi: int = 60) -> bool:
    for j in range(max(1, i - lo), min(len(closes), i + hi)):
        if closes[j - 1] <= 0 or closes[j] <= 0:
            continue
        r = closes[j] / closes[j - 1]
        if r > 2.5 or r < 1 / 2.5:
            return True
    return False


def collect_entries(bars, require_volume: str, skip_splits: bool = False):
    """require_volume: 'high' (>=2x) | 'low' (<2x) | 'any'."""
    closes = [float(b.close) for b in bars]
    vols = [float(b.volume) for b in bars]
    out = []
    for i in range(21, len(closes) - 60):
        if closes[i] <= 0 or closes[i] <= max(closes[i - 20:i]):
            continue
        avg20 = statistics.mean(vols[i - 20:i])
        if avg20 <= 0:
            continue
        ratio = vols[i] / avg20
        if require_volume == "high" and ratio < 2:
            continue
        if require_volume == "low" and ratio >= 2:
            continue
        if skip_splits and has_split_in_window(closes, i):
            continue
        out.append(i)
    return out


def print_section(title: str) -> None:
    print("\n" + "=" * 74 + f"\n{title}\n" + "=" * 74)


# ----------------------------------------------------------------------- H1
print_section("H1 — Les splits 2017-2019 contaminent-ils les backtests ?")
for label, bounds in (("2017-2022", (None, "2023-01-01")),
                      ("2023-2026", ("2023-01-01", None))):
    rets_all, rets_clean, n_clean = [], [], 0
    for code in hist_all:
        bars = [b for b in hist_all[code]
                if (not bounds[0] or str(b.date)[:10] >= bounds[0])
                and (not bounds[1] or str(b.date)[:10] < bounds[1])]
        if len(bars) < 140:
            continue
        closes = [float(b.close) for b in bars]
        for i in collect_entries(bars, "high", skip_splits=False):
            r, _ = simulate_entry(bars, i)
            rets_all.append(r)
        for i in collect_entries(bars, "high", skip_splits=True):
            r, _ = simulate_entry(bars, i)
            rets_clean.append(r)
            n_clean += 1
    med_all = statistics.median(rets_all) * 100
    med_clean = statistics.median(rets_clean) * 100
    print(f"{label} : médiane nette AVEC splits {med_all:+.1f} % ({len(rets_all)} entrées) → "
          f"SANS splits {med_clean:+.1f} % ({n_clean} entrées) | delta {med_clean-med_all:+.1f} pt")

# ----------------------------------------------------------------------- H2
print_section("H2 — Le volume ≥ 2× prédit-il le succès ? (test de permutation)")
scores_high, scores_low = [], []
for code in hist_all:
    bars = hist_all[code]
    if len(bars) < 140:
        continue
    closes = [float(b.close) for b in bars]
    for i in collect_entries(bars, "high", skip_splits=True):
        fut = closes[i + 1:i + 61]
        hit_up = max(fut) / closes[i] - 1 >= T1
        hit_down = min(fut) / closes[i] - 1 <= STOP
        scores_high.append(1 if (hit_up and not hit_down) or (hit_up and hit_down and fut[-1] >= closes[i]) else 0)
    for i in collect_entries(bars, "low", skip_splits=True):
        fut = closes[i + 1:i + 61]
        hit_up = max(fut) / closes[i] - 1 >= T1
        hit_down = min(fut) / closes[i] - 1 <= STOP
        scores_low.append(1 if (hit_up and not hit_down) or (hit_up and hit_down and fut[-1] >= closes[i]) else 0)

p_high = statistics.mean(scores_high) * 100
p_low = statistics.mean(scores_low) * 100
print(f"Breakouts volume ≥ 2× : {p_high:.1f} % de succès ({len(scores_high)} entrées)")
print(f"Breakouts volume < 2× : {p_low:.1f} % de succès ({len(scores_low)} entrées)")
diff = p_high - p_low
# test de permutation (mélange des labels, 10 000 itérations)
rng = random.Random(42)
combined = scores_high + scores_low
n1 = len(scores_high)
extreme = 0
for _ in range(10_000):
    rng.shuffle(combined)
    d = statistics.mean(combined[:n1]) - statistics.mean(combined[n1:])
    if d >= diff / 100:
        extreme += 1
p_value = extreme / 10_000
print(f"Différence {diff:+.1f} pt — p-value (permutation) = {p_value:.4f} → "
      f"{'SIGNIFICATIF : le volume prédit le succès' if p_value < 0.05 else 'NON significatif : le filtre volume est un placebo statistique'}")

# ----------------------------------------------------------------------- H3
print_section("H3 — Entrer à l'open de J+1 (réalité du check 16h) vs clôture du signal")
for label, bounds in (("2017-2022", (None, "2023-01-01")),
                      ("2023-2026", ("2023-01-01", None))):
    rets_close, rets_open = [], []
    for code in hist_all:
        bars = [b for b in hist_all[code]
                if (not bounds[0] or str(b.date)[:10] >= bounds[0])
                and (not bounds[1] or str(b.date)[:10] < bounds[1])]
        if len(bars) < 140:
            continue
        for i in collect_entries(bars, "high", skip_splits=True):
            r1, _ = simulate_entry(bars, i, entry_mode="close")
            r2, _ = simulate_entry(bars, i, entry_mode="open_next")
            rets_close.append(r1)
            rets_open.append(r2)
    m_close = statistics.median(rets_close) * 100
    m_open = statistics.median(rets_open) * 100
    print(f"{label} : médiane entrée clôture {m_close:+.1f} % → entrée open J+1 {m_open:+.1f} % "
          f"| delta {m_open-m_close:+.1f} pt ({len(rets_close)} entrées)")

# ----------------------------------------------------------------------- H4
print_section("H4 — Frais RÉELS (min 1 000 F/ordre) sur une poche de 70 000 F")
for label, bounds in (("2017-2022", (None, "2023-01-01")),
                      ("2023-2026", ("2023-01-01", None))):
    rets_flat, rets_real = [], []
    for code in hist_all:
        bars = [b for b in hist_all[code]
                if (not bounds[0] or str(b.date)[:10] >= bounds[0])
                and (not bounds[1] or str(b.date)[:10] < bounds[1])]
        if len(bars) < 140:
            continue
        for i in collect_entries(bars, "high", skip_splits=True):
            r1, _ = simulate_entry(bars, i, fees_mode="flat")
            r2, _ = simulate_entry(bars, i, fees_mode="real")
            rets_flat.append(r1)
            rets_real.append(r2)
    m_flat = statistics.median(rets_flat) * 100
    m_real = statistics.median(rets_real) * 100
    cost_ex = commission(70_000) / 70_000 * 100
    cost_part = commission(70_000 / 3) / (70_000 / 3) * 100
    print(f"{label} : frais 1,4 % uniforme {m_flat:+.1f} % → frais RÉELS (min 1 000 F) {m_real:+.1f} % "
          f"| delta {m_real-m_flat:+.1f} pt ({len(rets_flat)} entrées)")
    print(f"    rappel : frais réels sur 70 000 F = {cost_ex:.1f} % · sur une vente ⅓ (23 333 F) = {cost_part:.1f} %")
