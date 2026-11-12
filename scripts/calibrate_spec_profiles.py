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
from src.collecte.preparation import charger_historique_propre
from src.infrastructure.paths import HISTORY_BRUT, HISTORY_CACHE
from src.strategie.spec_profiles import (FRAIS, HORIZON, detect_schemas, zone_of,
                                         zone_label, PROFILES_FILE)

# CORRECTIF 12/11/2026 — le calibrage tournait sur des cours FAUX pour 37 titres sur 48.
#
# Il lisait `load_all_history(BSApi())`, qui renvoie CACHE_BRUT : les cours NON AJUSTÉS des
# divisions du nominal. Une division « 10 nouvelles pour 1 ancienne » y apparaît comme une
# chute de −90 % en une séance, ce qui :
#   - fait plonger le RSI sous 30            -> FAUX signal PANIQUE,
#   - projette le titre dans la zone basse   -> fausse répartition par zone,
#   - fausse le rendement à 12 mois          -> il traverse la division.
# Mesure : 421 cas sur le brut (dont 39 en zone 20-40) contre 414 sur le propre (81 en 20-40).
# C'est le piège que le skill interdit explicitement : « ajustement des divisions VÉRIFIÉ
# avant de backtester ». Il avait été respecté pour le noyau, pas pour ce calibrage.
hist = charger_historique_propre()

# Garde-fou de fraîcheur : si le cache brut a été rafraîchi APRÈS le propre, le propre ne
# contient pas les dernières séances — on le DIT plutôt que de calibrer en silence sur du retard.
try:
    if HISTORY_BRUT.exists() and HISTORY_CACHE.exists():
        retard_j = (HISTORY_CACHE.stat().st_mtime - HISTORY_BRUT.stat().st_mtime) / 86400
        if retard_j < 0:
            print(f"ATTENTION : le cache PROPRE a {-retard_j:.1f} jour(s) de retard sur le "
                  f"brut — lancer scripts/preparer_historique_propre.py avant de publier.")
except OSError:
    pass

# Agrégation par schéma — spacing INDÉPENDANT par schéma (sinon les signaux
# rares se font manger par les signaux fréquents et faussent les stats).
# CORRECTIF 12/11/2026 : le compteur d'espacement vivait HORS de la boucle sur les titres,
# donc il comparait l'index d'un titre à celui d'un AUTRE titre et écrasait la majorité des
# cas (PANIQUE : 18 cas au lieu de 414 ; EVEIL : 28 au lieu de 934). Il est désormais remis
# à zéro POUR CHAQUE TITRE — c'est le sens d'« épisodes non chevauchants ».
SCHEMAS = ("CASSURE", "EVEIL", "PANIQUE")
TRANCHE = [(0.0, 0.20, "0-20"), (0.20, 0.40, "20-40"), (0.40, 0.60, "40-60"),
           (0.60, 0.80, "60-80"), (0.80, 1.01, "80-100")]
ESPACEMENT = 60


def tranche_de(zone: float) -> str:
    for lo, hi, nom in TRANCHE:
        if lo <= zone < hi:
            return nom
    return "80-100"


agg = {s: {"rets": [], "peaks": [], "n": 0} for s in SCHEMAS}
# Le croisement (schéma x zone) : c'est la donnée qui manquait. La fiche affichait un taux
# TOUS SCHÉMAS CONFONDUS (10 épisodes) sur une alerte d'un schéma précis — d'où un « 100 %
# de réussite » annoncé sur un rachat de panique qui vaut 49 % pour ce schéma.
agg_zones = {s: {t: {"rets": [], "peaks": []} for _, _, t in TRANCHE} for s in SCHEMAS}

for code, bars in hist.items():
    closes = [b.close for b in bars]
    if len(closes) < 500 or closes[0] <= 0:
        continue
    last_entry = {s: -10**9 for s in SCHEMAS}     # LE CORRECTIF : un compteur par titre
    for i in range(260, len(closes) - HORIZON):
        schemas = detect_schemas(closes[: i + 1])
        if not schemas:
            continue
        ret = closes[i + HORIZON] / closes[i] - 1 - FRAIS
        peak = max(closes[i + 1 : i + HORIZON + 1]) / closes[i] - 1
        zone = tranche_de(zone_of(closes[: i + 1]))
        for s in schemas:
            if i - last_entry[s] < ESPACEMENT:
                continue
            agg[s]["rets"].append(ret)
            agg[s]["peaks"].append(peak)
            agg[s]["n"] += 1
            agg_zones[s][zone]["rets"].append(ret)
            agg_zones[s][zone]["peaks"].append(peak)
            last_entry[s] = i

PALIERS = ("0.10", "0.20", "0.35", "0.50", "1.00")

def _stats(rets, peaks) -> dict:
    if not rets:
        return {"n": 0}
    return {
        "n": len(rets),
        "win_12m": round(sum(1 for r in rets if r > 0) / len(rets), 3),
        "median_net_12m": round(statistics.median(rets), 3),
        "touched": {
            p: round(sum(1 for pk in peaks if pk >= float(p)) / len(peaks), 3)
            for p in PALIERS
        },
    }


out = {}
for s, a in agg.items():
    if not a["rets"]:
        continue
    out[s] = _stats(a["rets"], a["peaks"])
    # Les stats de la zone POUR CE SCHÉMA : ce sont elles que la fiche doit lire, au lieu
    # d'un taux tous schémas confondus qui décrit une autre population.
    out[s]["zones"] = {t: _stats(agg_zones[s][t]["rets"], agg_zones[s][t]["peaks"])
                       for _, _, t in TRANCHE}

# Les LIBELLÉS de zone restent dans src/spec_fiche.py ; ce fichier porte les MESURES,
# désormais ventilées par schéma (out[s]["zones"]).
PROFILES_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
