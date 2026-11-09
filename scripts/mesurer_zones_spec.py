"""Mesure des taux de réussite par ZONE pour les schémas de la poche spé BRVM.

POURQUOI CE SCRIPT
------------------
La fiche spé affiche des taux de réussite par ZONE codés en dur dans
`src/strategie/spec_fiche.py` (ZONE_LABELS) : FORCE 83 %, BAS_SOLIDE 80 %,
HAUT_FRAGILE « 0 gagnant sur 4 », BAS_ECRASE 50 %. Ces taux ne sont ni datés
ni re-mesurés (constat du contrat chantier-spec-prix, 02/11/2026). Ce script
rejoue sur les données RÉELLES du cache (`data/history_clean.pkl`, ajusté des
divisions et nettoyé) le calcul des fréquences historiques et le croise avec la
zone (position du cours dans la fourchette des ~5 ans), pour savoir si ces taux
sont confirmés, infirmés ou non mesurables faute d'échantillon.

MÉTHODE (réutilise la machinerie existante, ne réinvente pas de backtest)
-------------------------------------------------------------------------
- Lecture du cache : `history_io.charger_cache` + `paths.HISTORY_CACHE`
  (le cache canonique des décisions, empreinte SHA-256 vérifiée).
- Détection des schémas : `spec_profiles.detect_schemas` (CASSURE / EVEIL /
  PANIQUE), appelée SANS volumes — exactement comme
  `scripts/calibrate_spec_profiles.py` qui produit les fréquences affichées.
  (En production la fiche exige en plus la confirmation par le volume : les
  signaux réellement déclenchés sont un sous-ensemble de ceux comptés ici.)
- Zone : `spec_profiles.zone_of(closes[:i+1])` (flottant 0-1) puis
  `zone_label` → tranches 0-20 / 20-40 / 40-60 / 60-80 / 80-100.
- Rendement : horizon 252 séances (`HORIZON`), net des frais aller-retour
  (`FRAIS` = 0,028), et pic maximal touché sur l'horizon (brut, pour les
  paliers +20 % / +50 %).
- Espacement anti-recouvrement : 60 séances par schéma (règle du calibrate,
  sinon les signaux fréquents se mangent les rares).
- Filtre d'entrée : séries d'au moins 500 barres, première barre > 0
  (identique au calibrate).

AUCUN accès réseau : tout vient du cache local. Si un fichier de données
manque, le script lève une erreur claire au lieu d'inventer un chiffre.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from src.collecte.history_io import charger_cache          # lecture centralisée P6-04
from src.infrastructure.paths import HISTORY_CACHE         # chemin central (lot 0)
from src.strategie.spec_profiles import (                  # machinerie existante
    FRAIS, HORIZON, detect_schemas, zone_of, zone_label,
)

SCHEMAS = ("CASSURE", "EVEIL", "PANIQUE")
ZONES = ("BAS_ECRASE", "BAS_SOLIDE", "MILIEU", "HAUT_FRAGILE", "FORCE")
# Libellés de tranche (vocabulaire du contrat) — zone_label retourne ces codes.
TRANCHE = {
    "BAS_ECRASE": "0-20",
    "BAS_SOLIDE": "20-40",
    "MILIEU": "40-60",
    "HAUT_FRAGILE": "60-80",
    "FORCE": "80-100",
}
# Taux codés en dur dans ZONE_LABELS (spec_fiche.py) — à comparer à la mesure.
# MILIEU n'a AUCUN taux codé en dur (« zone neutre ») ; HAUT_FRAGILE : « 0 gagnant sur 4 ».
TAUX_CODE_DUR = {
    "FORCE": 0.83,
    "BAS_SOLIDE": 0.80,
    "MILIEU": None,
    "HAUT_FRAGILE": 0.0,
    "BAS_ECRASE": 0.50,
}
SEUIL_ECHANTILLON = 10  # en dessous : non mesurable


def charger_series() -> tuple[dict, dict]:
    """Charge le cache propre et retourne (closes par code, volumes par code)."""
    hist = charger_cache(HISTORY_CACHE)
    closes_by_code: dict = {}
    volumes_by_code: dict = {}
    for code, barres in hist.items():
        closes_by_code[code] = [b.close for b in barres]
        volumes_by_code[code] = [getattr(b, "volume", 0) for b in barres]
    return closes_by_code, volumes_by_code


def mesurer() -> dict:
    """Rejoue la détection + zone sur l'historique, agrège rets et pics par (schéma, zone)."""
    closes_by_code, _ = charger_series()

    # agg[schéma][zone] = {"rets": [...], "peaks": [...]}
    agg = {s: {z: {"rets": [], "peaks": []} for z in ZONES} for s in SCHEMAS}
    last_entry = {s: -10**9 for s in SCHEMAS}
    series_prises = 0

    for code, closes in closes_by_code.items():
        if len(closes) < 500 or closes[0] <= 0:
            continue
        series_prises += 1
        for i in range(260, len(closes) - HORIZON):
            schemas = detect_schemas(closes[: i + 1])
            if not schemas:
                continue
            zone = zone_of(closes[: i + 1])
            zl = zone_label(zone)
            ret = closes[i + HORIZON] / closes[i] - 1 - FRAIS
            peak = max(closes[i + 1 : i + HORIZON + 1]) / closes[i] - 1
            for s in schemas:
                if i - last_entry[s] < 60:
                    continue
                agg[s][zl]["rets"].append(ret)
                agg[s][zl]["peaks"].append(peak)
                last_entry[s] = i
    return {"agg": agg, "series_prises": series_prises,
            "codes": list(closes_by_code.keys())}


def stats_cellule(rets: list, peaks: list) -> dict | None:
    """Statistiques d'une cellule (schéma × zone) ; None si aucun cas."""
    n = len(rets)
    if n == 0:
        return None
    return {
        "n": n,
        "win_12m": sum(1 for r in rets if r > 0) / n,
        "median_net": statistics.median(rets),
        "touche_20": sum(1 for p in peaks if p >= 0.20) / n,
        "touche_50": sum(1 for p in peaks if p >= 0.50) / n,
        "suffisant": n >= SEUIL_ECHANTILLON,
    }


def rapport_texte(mesure: dict) -> str:
    agg = mesure["agg"]
    lignes: list[str] = []
    a = lignes.append

    a("=" * 92)
    a("MESURE DES TAUX PAR ZONE — poche spéculative BRVM")
    a("=" * 92)
    a(f"Séries retenues (≥ 500 barres) : {mesure['series_prises']} / {len(mesure['codes'])} titres du cache")
    a(f"Frais aller-retour déduits : {FRAIS*100:.1f} %   Horizon : {HORIZON} séances")
    a(f"Seuil d'échantillon suffisant : {SEUIL_ECHANTILLON} cas")
    a("")

    # Tableau par schéma × zone
    for s in SCHEMAS:
        total_n = 0
        total_rets: list = []
        a(f"── {s} ──")
        a(f"{'zone':<8}{'n':>5}{'% hausse':>10}{'médian':>9}{'% +20':>8}{'% +50':>8}"
          f"{'codé dur':>10}{'échantillon':>13}")
        for z in ZONES:
            st = stats_cellule(agg[s][z]["rets"], agg[s][z]["peaks"])
            code = TAUX_CODE_DUR[z]
            code_txt = "—" if code is None else f"{code*100:.0f} %"
            if st is None:
                a(f"{TRANCHE[z]:<8}{'—':>5}{'—':>10}{'—':>9}{'—':>8}{'—':>8}"
                  f"{code_txt:>10}{'aucun cas':>13}")
                continue
            total_n += st["n"]
            total_rets.extend(agg[s][z]["rets"])
            suff = "suffisant" if st["suffisant"] else "INSUFFISANT"
            a(f"{TRANCHE[z]:<8}{st['n']:>5}{st['win_12m']*100:>9.0f}%{st['median_net']*100:>8.1f}%"
              f"{st['touche_20']*100:>7.0f}%{st['touche_50']*100:>7.0f}%"
              f"{code_txt:>10}{suff:>13}")
        if total_n:
            win = sum(1 for r in total_rets if r > 0) / len(total_rets)
            med = statistics.median(total_rets)
            a(f"{'TOTAL':<12}{total_n:>5}{win*100:>13.0f}%{med*100:>11.1f}%")
        a("")

    # Tableau par zone (toutes schémas confondus) + comparaison au codé dur
    a("── PAR ZONE (schémas confondus) vs taux codés en dur dans ZONE_LABELS ──")
    a(f"{'zone':<8}{'n':>5}  {'mesuré':>7} {'médian':>8}  {'codé dur':>10}  {'écart':>7}  {'verdict':<24}")
    for z in ZONES:
        rets = []
        peaks = []
        for s in SCHEMAS:
            rets.extend(agg[s][z]["rets"])
            peaks.extend(agg[s][z]["peaks"])
        st = stats_cellule(rets, peaks)
        if st is None:
            a(f"{TRANCHE[z]:<8}{'—':>5}  {'—':>7} {'—':>8}  {'—':>10}  {'—':>7}  {'aucun cas':<24}")
            continue
        code = TAUX_CODE_DUR[z]
        code_txt = "— (neutre)" if code is None else f"{code*100:.0f} %"
        ecart = "—" if code is None else f"{(st['win_12m'] - code)*100:+.0f} pt"
        if not st["suffisant"]:
            verdict = "NON MESURABLE (<10 cas)"
        elif code is None:
            verdict = "aucun taux codé"
        else:
            delta = st["win_12m"] - code
            if abs(delta) <= 0.15:
                verdict = "compatible"
            elif delta < 0:
                verdict = "INFIRMÉ (mesuré plus bas)"
            else:
                verdict = "dépasse le codé dur"
        a(f"{TRANCHE[z]:<8}{st['n']:>5}  {st['win_12m']*100:>6.0f}% {st['median_net']*100:>7.1f}%  "
          f"{code_txt:>10}  {ecart:>7}  {verdict:<24}")
    a("")

    # Machine-readable JSON (pratique pour le parent)
    a("── JSON ──")
    import json
    out = {}
    for s in SCHEMAS:
        out[s] = {}
        for z in ZONES:
            st = stats_cellule(agg[s][z]["rets"], agg[s][z]["peaks"])
            out[s][TRANCHE[z]] = st
    a(json.dumps(out, ensure_ascii=False))
    return "\n".join(lignes)


def main() -> None:
    mesure = mesurer()
    print(rapport_texte(mesure))


if __name__ == "__main__":
    main()
