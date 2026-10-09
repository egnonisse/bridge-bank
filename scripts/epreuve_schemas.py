"""Épreuve « schémas récurrents exploitables » — 10 ans de BRVM, net de frais.

Schémas testés (entrées réparties, spacing >= 60 séances) :
  S1 : titre à <= -90 % de son ATH (les « détruits ») — forward 12 mois
  S2 : titre à <= -80 % de son ATH
  S3 : breakout du plus haut des 250 séances (sortie de 1 an de plafond)
  S4 : krach -40 % en 60 séances puis rebond +10 % (crach qui rebondit)
  S5 : le titre a doublé en 250 séances → les 126 séances suivantes (momentum long)

Baseline : entrées aléatoires. Tous nets de 2,8 % de frais aller-retour.

Usage : python scripts/epreuve_schemas.py
"""
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi

FRAIS = 0.028
HORIZONS = (126, 252)


def fwd(closes, i, h):
    j = i + h
    if j >= len(closes):
        return None
    return (closes[j] / closes[i] - 1) - FRAIS


def sig_drawdown(closes, i, pct):
    ath = max(closes[: i + 1])
    return closes[i] / ath - 1 <= pct and closes[i] > 0


def sig_breakout_250(closes, i):
    if i < 250:
        return False
    return closes[i] > max(closes[i - 250 : i])


def sig_krach_rebond(closes, i):
    if i < 60:
        return False
    prev = closes[i - 60]
    creux = min(closes[i - 30 : i])
    return creux / prev - 1 <= -0.40 and closes[i] / creux - 1 >= 0.10


def sig_doublement(closes, i):
    if i < 250:
        return False
    return closes[i] / closes[i - 250] - 1 >= 1.0


def run(name, fn):
    all_r = {h: [] for h in HORIZONS}
    wins = {h: 0 for h in HORIZONS}
    n = 0
    last_entry = -10**9
    for code, bars in hist.items():
        closes = [b.close for b in bars]
        if len(closes) < 500 or closes[0] <= 0:
            continue
        for i in range(250, len(closes) - 252):
            if i - last_entry < 60:
                continue
            if fn(closes, i):
                rows = {h: fwd(closes, i, h) for h in HORIZONS}
                if any(v is None for v in rows.values()):
                    continue
                n += 1
                last_entry = i
                for h in HORIZONS:
                    all_r[h].append(rows[h])
                    if rows[h] > 0:
                        wins[h] += 1
    print(f"\n=== {name} ===")
    print(f"  n = {n} entrées")
    for h in HORIZONS:
        rs = all_r[h]
        if not rs:
            continue
        print(f"  {h} séances ({h//21} mois) : {wins[h]/len(rs)*100:.0f} % gagnants · "
              f"médiane nette {statistics.median(rs)*100:+.1f} % · moyenne {statistics.mean(rs)*100:+.1f} %")


if __name__ == "__main__":
    print("Chargement…")
    hist = load_all_history(BSApi(), force=False)
    print(f"{len(hist)} titres. Frais 2,8 %.")
    random.seed(42)
    run("S1 — Les détruits (<= -90 % de l'ATH)", lambda c, i: sig_drawdown(c, i, -0.90))
    run("S2 — Les blessés (<= -80 % de l'ATH)", lambda c, i: sig_drawdown(c, i, -0.80))
    run("S3 — Sortie du plafond de 1 an (breakout 250j)", sig_breakout_250)
    run("S4 — Krach -40 % puis rebond +10 %", sig_krach_rebond)
    run("S5 — Après un doublement en 12 mois (momentum long)", sig_doublement)
    run("BASELINE — Hasard", lambda c, i: random.random() < 0.05)
