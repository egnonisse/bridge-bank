"""Épreuve « profils de spéculation jouables sur la DURÉE » — 10 ans de BRVM.

Teste 4 profils d'entrée moyen/long terme, net de frais (2,8 % aller-retour) :
  T   : tendance — close repasse au-dessus de l'EMA200 après >= 20 séances en dessous
  GC  : golden cross — EMA50 croise au-dessus de l'EMA200 (après >= 20 séances dessous)
  DH  : début de hausse — rebond +10 % depuis le creux 60 séances
  MR  : mean reversion — RSI14 < 30 (rachat de panique)

Baseline : entrées ALÉATOIRES (mêmes contraintes de spacing) pour mesurer le hasard.
Métriques par profil : n signaux, % gagnants à 6m et 12m, gain médian net à 12m.

Usage : python scripts/epreuve_profils_duree.py
"""
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi

FRAIS = 0.028  # 2,8 % aller-retour
MIN_SEANCES = 260  # minimum d'historique par titre


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


def fwd(closes, i, horizon):
    """Rendement forward net de frais."""
    j = i + horizon
    if j >= len(closes):
        return None
    return (closes[j] / closes[i] - 1) - FRAIS


def run_profile(name, signal_fn, horizon_list=(126, 252)):
    """Applique signal_fn(closes, i) -> bool, avec spacing >= 60 séances."""
    all_r = {h: [] for h in horizon_list}
    wins = {h: 0 for h in horizon_list}
    n = 0
    last_entry = -10**9
    for code, bars in hist.items():
        closes = [b.close for b in bars]
        if len(closes) < MIN_SEANCES or closes[0] <= 0:
            continue
        for i in range(220, len(closes) - 252):
            if i - last_entry < 60:
                continue
            if signal_fn(closes, i):
                ok = True
                row = {}
                for h in horizon_list:
                    r = fwd(closes, i, h)
                    if r is None:
                        ok = False
                        break
                    row[h] = r
                if not ok:
                    continue
                n += 1
                last_entry = i
                for h in horizon_list:
                    all_r[h].append(row[h])
                    if row[h] > 0:
                        wins[h] += 1
    print(f"\n=== {name} ===")
    print(f"  n = {n} entrées")
    for h in horizon_list:
        rs = all_r[h]
        if not rs:
            print(f"  {h} séances : aucune donnée")
            continue
        med = statistics.median(rs)
        print(f"  {h} séances ({h // 21} mois) : {wins[h]/len(rs)*100:.0f} % gagnants · "
              f"gain médian net {med*100:+.1f} % · gain moyen {statistics.mean(rs)*100:+.1f} %")
    return all_r


def sig_tendance(closes, i):
    e200 = ema(closes[: i + 1], 200)
    if len(e200) < 220:
        return False
    # repasse au-dessus après >= 20 séances en dessous
    below = sum(1 for j in range(i - 20, i) if closes[j] < e200[j])
    return closes[i] > e200[i] and below >= 18 and closes[i - 1] <= e200[i - 1]


def sig_golden_cross(closes, i):
    e50 = ema(closes[: i + 1], 50)
    e200 = ema(closes[: i + 1], 200)
    if len(e200) < 220:
        return False
    below = sum(1 for j in range(i - 20, i) if e50[j] < e200[j])
    return e50[i] > e200[i] and e50[i - 1] <= e200[i - 1] and below >= 18


def sig_debut_hausse(closes, i):
    creux60 = min(closes[max(0, i - 60):i])
    return closes[i] / creux60 - 1 >= 0.10


def sig_mean_reversion(closes, i):
    r = rsi(closes)
    return r[i] is not None and r[i] < 30


def sig_aleatoire(closes, i):
    return random.random() < 0.05


if __name__ == "__main__":
    print("Chargement de l'historique…")
    hist = load_all_history(BSApi(), force=False)
    print(f"{len(hist)} titres chargés.\nFrais appliqués : 2,8 % aller-retour.")

    random.seed(42)
    run_profile("T — Repassage au-dessus de l'EMA200 (tendance longue)", sig_tendance)
    run_profile("GC — Golden cross EMA50/EMA200", sig_golden_cross)
    run_profile("DH — Début de hausse (+10 % depuis le creux 60j)", sig_debut_hausse)
    run_profile("MR — Rachat de panique (RSI14 < 30)", sig_mean_reversion)
    run_profile("BASELINE — Entrées aléatoires (le hasard)", sig_aleatoire)
