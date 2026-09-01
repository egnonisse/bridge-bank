"""Épreuve du PAIRS TRADING (cointégration) sur la BRVM — frais réels, out-of-sample.

Protocole maison (même esprit que test_momentum_hypotheses.py) :
  1. CALIBRAGE 2017-2022 : ~1 081 paires (47 titres). Fenêtres glissantes de 250
     séances : régression OLS Y = a + b*X, test ADF (1 lag) du spread.
     Paires retenues : >= 60 % des fenêtres stationnaires (t-stat < -2.86).
     Biais ASSUMÉ favorable : ADF standard (les valeurs critiques Engle-Granger
     pour cointégration sont plus strictes) -> on garde PLUS de paires qu'un
     protocole académique strict. Si la stratégie échoue malgré ce biais, le
     verdict est d'autant plus solide.
  2. TEST 2023-2026, deux variantes :
     A. MARKET-NEUTRAL (théorique : la vente à découvert n'existe pas sur la
        BRVM — variante irréalisable, montrée pour information) :
        |Z| > 2 -> long/short des deux jambes ; sortie Z ~ 0 ou 60 séances.
     B. LONG-SEULE (la seule exécutable sans short) :
        Z < -2 -> achat de Y seul ; sortie Z >= 0 ou 60 séances.
     Frais RÉELS (commission, min 1 000 F) sur chaque jambe.
  3. Benchmark : trade aléatoire médian sur 60 séances (même fenêtre).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history
from src.bsapi import BSApi
from src.taxation import commission

WINDOW = 250          # fenêtre de régression
Z_ENTRY = 2.0         # seuil d'entrée (écarts-types)
MAX_HOLD = 60         # sortie forcée (séances)
AMOUNT = 70_000.0     # montant par jambe
ADF_CRIT = -2.86      # valeur critique ADF 5 % (standard, laxiste exprès)

hist_all = load_all_history(BSApi(), force=False)


def ols_beta(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """b, a de y = a + b*x (moindres carrés)."""
    b = np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1)
    a = y.mean() - b * x.mean()
    return float(b), float(a)


def adf_stat(resid: np.ndarray, lag: int = 1) -> float:
    """t-statistique de gamma dans Δε_t = c + γ·ε_{t-1} + δ·Δε_{t-1} + u_t."""
    y = np.diff(resid)[1:]          # n-2 observations (alignées sur lag 1)
    x1 = resid[1:-1]
    x2 = np.diff(resid)[:-1] if lag else None
    n = len(y)
    X = np.column_stack([np.ones(n), x1] + ([x2] if lag else []))
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid_reg = y - X @ beta
    dof = n - X.shape[1]
    sigma2 = resid_reg @ resid_reg / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    return float(beta[1] / np.sqrt(cov[1, 1]))


def common_bars(a_bars, b_bars):
    """Closes alignées sur les dates communes, triées."""
    idx = {}
    for b in a_bars:
        idx[str(b.date)[:10]] = float(b.close)
    out = []
    for b in b_bars:
        k = str(b.date)[:10]
        if k in idx:
            out.append((k, idx[k], float(b.close)))
    out.sort()
    return out


def period_filter(pairs, lo=None, hi=None):
    return [(d, x, y) for d, x, y in pairs if (not lo or d >= lo) and (not hi or d < hi)]


# ---------------------------------------------------------------- sélection
codes = [c for c in hist_all if len(hist_all[c]) >= 600]
print(f"{len(codes)} titres éligibles -> {len(codes)*(len(codes)-1)//2} paires brutes")

selected = []
for i, ca in enumerate(codes):
    for cb in codes[i + 1:]:
        pairs = common_bars(hist_all[ca], hist_all[cb])
        cal = period_filter(pairs, "2017-01-01", "2023-01-01")
        if len(cal) < WINDOW + 30:
            continue
        xs = np.array([x for _, x, _ in cal])
        ys = np.array([y for _, _, y in cal])
        n_w, n_stat = 0, 0
        for t in range(WINDOW, len(cal) - 10, 20):  # pas de 20 séances
            b, a = ols_beta(xs[t - WINDOW:t], ys[t - WINDOW:t])
            resid = ys[t - WINDOW:t] - (a + b * xs[t - WINDOW:t])
            n_w += 1
            if np.std(resid) > 0 and adf_stat(resid) < ADF_CRIT:
                n_stat += 1
        if n_w and n_stat / n_w >= 0.6:
            selected.append((ca, cb))
            print(f"  paire retenue : {ca} / {cb} ({n_stat}/{n_w} fenêtres stationnaires)")

print(f"\n{len(selected)} paires retenues sur le calibrage 2017-2022")

if not selected:
    print("Aucune paire — l'épreuve s'arrête ici : le signal n'existe même pas dans les données.")
    sys.exit(0)


# ------------------------------------------------------------------- test
def simulate_variant(ca, cb, bounds, variant: str) -> list[float]:
    """variant: 'neutral' (2 jambes) | 'long_only' (1 jambe, Z<-2 -> acheter Y)."""
    pairs = common_bars(hist_all[ca], hist_all[cb])
    test = period_filter(pairs, bounds[0], bounds[1])
    xs = np.array([x for _, x, _ in test])
    ys = np.array([y for _, _, y in test])
    dates = [d for d, _, _ in test]
    rets = []
    in_pos = False
    pos_type = None  # 'longY' | 'shortY' | None
    entry_y = entry_x = entry_i = 0.0
    for t in range(WINDOW, len(test) - 1):
        b, a = ols_beta(xs[t - WINDOW:t], ys[t - WINDOW:t])
        resid = ys[t - WINDOW:t] - (a + b * xs[t - WINDOW:t])
        mu, sd = resid.mean(), resid.std()
        if sd <= 0:
            continue
        z = (ys[t] - (a + b * xs[t]) - mu) / sd
        if in_pos:
            exit_sig = (z >= -0.3 if pos_type == "longY" else z <= 0.3) or (t - entry_i >= MAX_HOLD)
            if exit_sig:
                if variant == "neutral":
                    gain_y = (ys[t] / entry_y - 1) * (1 if pos_type == "longY" else -1)
                    gain_x = (xs[t] / entry_x - 1) * (-1 if pos_type == "longY" else 1)
                    fee = (commission(AMOUNT) + commission(AMOUNT)) / (2 * AMOUNT)
                    rets.append((gain_y + gain_x) / 2 - fee)
                else:
                    ret = ys[t] / entry_y - 1
                    rets.append(ret - commission(AMOUNT) * 2 / AMOUNT)
                in_pos = False
        else:
            if variant == "neutral" and abs(z) > Z_ENTRY:
                pos_type = "longY" if z < -Z_ENTRY else "shortY"
                entry_y, entry_x, entry_i = ys[t], xs[t], t
                in_pos = True
            elif variant == "long_only" and z < -Z_ENTRY:
                pos_type, entry_y, entry_i = "longY", ys[t], t
                in_pos = True
    return rets


def summarize(label: str, rets: list[float]) -> None:
    if not rets:
        print(f"  {label:<40} : aucun trade")
        return
    med = np.median(rets) * 100
    mean = np.mean(rets) * 100
    win = sum(1 for r in rets if r > 0) / len(rets) * 100
    print(f"  {label:<40} : n={len(rets):>3} | méd {med:+6.1f} % | moy {mean:+6.1f} % | "
          f"gagnants {win:>3.0f} % | pire {min(rets)*100:+6.1f} % | best {max(rets)*100:+6.1f} %")


def benchmark(bounds) -> float:
    all_win = []
    for code in hist_all:
        bars = [b for b in hist_all[code]
                if (not bounds[0] or str(b.date)[:10] >= bounds[0])
                and (not bounds[1] or str(b.date)[:10] < bounds[1])]
        closes = [float(b.close) for b in bars]
        for i in range(21, len(closes) - MAX_HOLD):
            if closes[i] > 0 and closes[i + MAX_HOLD] > 0 and closes[i - 1] > 0:
                if abs(closes[i] / closes[i - 1] - 1) < 0.5:
                    all_win.append(closes[i + MAX_HOLD] / closes[i] - 1)
    return float(np.median(all_win)) * 100


print(f"\n{'=' * 96}\nTEST 2023-2026 (out-of-sample, frais réels, position {AMOUNT:,.0f} F/jambe)\n{'=' * 96}")
bm = benchmark(("2023-01-01", None))
print(f"  Benchmark « trade aléatoire » médian (60 séances, brut) : {bm:+.1f} %\n")

rets_neutral, rets_long = [], []
for ca, cb in selected:
    rets_neutral += simulate_variant(ca, cb, ("2023-01-01", None), "neutral")
    rets_long += simulate_variant(ca, cb, ("2023-01-01", None), "long_only")
summarize("A. MARKET-NEUTRAL (théorique, short impossible)", rets_neutral)
summarize("B. LONG-SEULE (seule exécutable sur la BRVM)", rets_long)
