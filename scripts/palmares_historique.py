"""Palmarès des titres qui se démarquent selon leur historique (10 ans).

Pour chaque titre : perf 1/3/5/10 ans, volatilité, distance ATH, et les 3 profils
éprouvés de durée : T (repassage EMA200), DH (début de hausse), MR (RSI < 30).

Usage : python scripts/palmares_historique.py
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi


def ema(vals, n):
    k = 2 / (n + 1)
    out = []
    e = None
    for v in vals:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def rsi(vals, n=14):
    out = [None] * len(vals)
    gains = losses = 0.0
    avg_g = avg_l = 0.0
    for i in range(1, len(vals)):
        d = vals[i] - vals[i - 1]
        g, l = max(d, 0.0), max(-d, 0.0)
        if i <= n:
            gains += g
            losses += l
            if i == n:
                avg_g, avg_l = gains / n, losses / n
                out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
        else:
            avg_g = (avg_g * (n - 1) + g) / n
            avg_l = (avg_l * (n - 1) + l) / n
            out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


hist = load_all_history(BSApi(), force=False)
rows = []
for code, bars in hist.items():
    closes = [b.close for b in bars]
    if len(closes) < 400 or closes[0] <= 0:
        continue
    last = closes[-1]
    ath = max(closes)
    def perf(n):
        return None if len(closes) <= n else (last / closes[-1 - n] - 1) * 100

    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    vol = statistics.pstdev(rets) * 100

    # profils ACTIFS aujourd'hui
    e200 = ema(closes, 200)
    below = sum(1 for j in range(-21, -1) if closes[j] < e200[j])
    t_active = closes[-1] > e200[-1] and below >= 18 and closes[-2] <= e200[-2]

    creux60 = min(closes[-61:-1])
    dh_active = last / creux60 - 1 >= 0.10

    r = rsi(closes)
    mr_active = r[-1] is not None and r[-1] < 30

    rows.append({
        "code": code, "last": last, "ath": ath, "vol": vol,
        "p1": perf(252), "p3": perf(756), "p5": perf(1260),
        "t": t_active, "dh": dh_active, "mr": mr_active,
        "nb": len(closes),
    })

n_t = sum(r["t"] for r in rows)
n_dh = sum(r["dh"] for r in rows)
n_mr = sum(r["mr"] for r in rows)
print(f"{len(rows)} titres analysés.")
print(f"Profils ACTIFS aujourd'hui : T={n_t} · DH={n_dh} · MR={n_mr}\n")

print("=== 🚀 TITRES QUI SE DÉMARQUENT — profil de durée ACTIF ===")
print(f'{"Titre":<8}{"Cours":>9}{"1 an":>8}{"3 ans":>8}{"5 ans":>8}{"ATH":>8}{"Vol":>6}  Profils')
for r in sorted(rows, key=lambda r: -(r["t"] + r["dh"] + r["mr"])):
    if not (r["t"] or r["dh"] or r["mr"]):
        continue
    tags = " ".join(filter(None, [
        "T" if r["t"] else "",
        "DH" if r["dh"] else "",
        "MR" if r["mr"] else "",
    ]))
    p = lambda v: f"{v:+.0f}" if v is not None else "  —"
    print(f'{r["code"]:<8}{r["last"]:>9,.0f}{p(r["p1"]):>8}{p(r["p3"]):>8}{p(r["p5"]):>8}'
          f'{r["last"]/r["ath"]*100-100:>+7.0f}%{r["vol"]:>5.1f}%  {tags}')

print("\n=== 🏆 PALMARÈS PERFORMANCE 1 AN (top 8) ===")
for r in sorted([r for r in rows if r["p1"] is not None], key=lambda r: -r["p1"])[:8]:
    print(f'  {r["code"]:<8} {r["p1"]:>+8.0f} %   (cours {r["last"]:,.0f} · vol {r["vol"]:.1f} %)')

print("\n=== 💥 LES PLUS VOLATILS (profils de cycle, jouables en durée) ===")
for r in sorted(rows, key=lambda r: -r["vol"])[:8]:
    print(f'  {r["code"]:<8} ±{r["vol"]:.1f} %/j   (ATH {r["ath"]:,.0f} · actuel {r["last"]/r["ath"]*100-100:+.0f} %)')

print("\n=== 📉 LES PLUS LOIN DE LEUR ATH (candidats « revenants ») ===")
for r in sorted(rows, key=lambda r: r["last"] / r["ath"])[:8]:
    print(f'  {r["code"]:<8} {r["last"]/r["ath"]*100-100:>+7.0f} % vs ATH {r["ath"]:,.0f}   (actuel {r["last"]:,.0f} · 1 an {r["p1"] if r["p1"] is not None else 0:+.0f} %)')
