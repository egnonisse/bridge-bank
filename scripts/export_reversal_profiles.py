"""Exporte les profils de retournement (seuil +13 %) dans data/reversal_profiles.json.

Pour chaque titre : épisodes indépendants « +13 % à +65 % en 20 séances » (9 ans),
statistiques de la suite (J+5/J+20/J+60, délai et profondeur du creux).
Seuls les titres avec >= 8 épisodes (signal fiable) sont exportés.
Relancer après un refresh du cache historique : python scripts/export_reversal_profiles.py
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import load_all_history
from src.bsapi import BSApi
from src.cache_integrity import cache_signature

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "reversal_profiles.json"
LO, HI = 0.13, 0.65
MIN_EPISODES = 8


def main() -> None:
    hist_all = load_all_history(BSApi(), force=False)
    profiles = {}
    for code, bars in hist_all.items():
        if len(bars) < 140:
            continue
        closes = [float(b.close) for b in bars]
        n = len(closes)
        raw = []
        for i in range(20, n - 60):
            ret = closes[i] / closes[i - 20] - 1
            if LO <= ret <= HI:
                raw.append(i)
        idx = []
        for i in raw:
            if not idx or i - idx[-1] >= 10:
                idx.append(i)
        if len(idx) < MIN_EPISODES:
            continue
        f5 = [closes[i + 5] / closes[i] - 1 for i in idx]
        f20 = [closes[i + 20] / closes[i] - 1 for i in idx]
        f60 = [closes[i + 60] / closes[i] - 1 for i in idx]
        delais, creux = [], []
        for i in idx:
            fut = closes[i + 1:i + 61]
            jmin = min(range(len(fut)), key=lambda j: fut[j])
            delais.append(jmin + 1)
            creux.append(fut[jmin] / closes[i] - 1)
        profiles[code] = {
            "episodes": len(idx),
            "pct_down_20j": round(sum(1 for f in f20 if f < 0) / len(f20) * 100),
            "median_5j": round(statistics.median(f5) * 100, 1),
            "median_20j": round(statistics.median(f20) * 100, 1),
            "median_60j": round(statistics.median(f60) * 100, 1),
            "trough_delay_median": round(statistics.median(delais)),
            "trough_depth_median": round(statistics.median(creux) * 100, 1),
            "trough_depth_worst": round(min(creux) * 100, 1),
        }
    OUT.write_text(
        json.dumps({"_meta": {"seuil_pct": 13, "fenetre": "20 séances", "min_episodes": MIN_EPISODES,
                              "cache_signature": cache_signature(hist_all)},
                    **profiles}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"{len(profiles)} profils exportés → {OUT}")
    for code, p in profiles.items():
        print(f"  {code}: {p['episodes']} épisodes, {p['pct_down_20j']}% ↓ à J+20, "
              f"creux J+{p['trough_delay_median']} à {p['trough_depth_median']}%")


if __name__ == "__main__":
    main()
