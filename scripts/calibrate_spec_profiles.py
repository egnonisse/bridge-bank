"""Calibrage des stats des profils de spé (une fois, rejouable).

Calcule pour chaque schéma (CASSURE/EVEIL/PANIQUE) : n, taux de réussite à
12 mois, médiane nette, et les paliers touchés (+10/+20/+35/+50/+100 %).
Écrit data/spec_profiles.json, lu par src/spec_profiles.py.

Usage : python scripts/calibrate_spec_profiles.py
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.collecte.backtest import load_all_history
from src.collecte.bsapi import BSApi
from src.strategie.spec_profiles import (FRAIS, HORIZON, detect_schemas, zone_of,
                               zone_label, PROFILES_FILE)

hist = load_all_history(BSApi(), force=False)

# Agrégation par schéma — spacing INDÉPENDANT par schéma (sinon les signaux
# rares se font manger par les signaux fréquents et faussent les stats)
agg = {s: {"rets": [], "peaks": [], "n": 0} for s in ("CASSURE", "EVEIL", "PANIQUE")}
last_entry = {s: -10**9 for s in agg}

for code, bars in hist.items():
    closes = [b.close for b in bars]
    if len(closes) < 500 or closes[0] <= 0:
        continue
    for i in range(260, len(closes) - HORIZON):
        schemas = detect_schemas(closes[: i + 1])
        if not schemas:
            continue
        ret = closes[i + HORIZON] / closes[i] - 1 - FRAIS
        peak = max(closes[i + 1 : i + HORIZON + 1]) / closes[i] - 1
        for s in schemas:
            if i - last_entry[s] < 60:
                continue
            agg[s]["rets"].append(ret)
            agg[s]["peaks"].append(peak)
            agg[s]["n"] += 1
            last_entry[s] = i

PALIERS = ("0.10", "0.20", "0.35", "0.50", "1.00")

out = {}
for s, a in agg.items():
    if not a["rets"]:
        continue
    out[s] = {
        "n": a["n"],
        "win_12m": round(sum(1 for r in a["rets"] if r > 0) / len(a["rets"]), 3),
        "median_net_12m": round(statistics.median(a["rets"]), 3),
        "touched": {
            p: round(sum(1 for pk in a["peaks"] if pk >= float(p)) / len(a["peaks"]), 3)
            for p in PALIERS
        },
    }

# Les ZONES restent celles de l'épreuve générale « acheter bas » (figées dans
# src/spec_profiles.py — elles ne sont PAS recalibrées ici, leurs n par
# tranche sont trop petits dans l'échantillon conditionnel).
PROFILES_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
