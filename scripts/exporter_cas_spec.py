"""EXPORT des cas de la veille speculative — pour audit externe.

Produit, pour chaque schema (CASSURE / EVEIL / PANIQUE), un CSV d'une ligne par cas :
titre, date du signal, cours, zone (position min-max ET percentile de rang), volume,
puis le parcours des 12 mois suivants — dont LA mesure qui manquait :

    les paliers (+20 / +35 / +50 %) sont-ils atteints AVANT que le stop -15 % ne soit touche ?

C'est la difference entre « le titre a touche +50 % dans l'annee » (mesure optimiste, ignore
le stop) et « le plan aurait encaisse +50 % » (mesure executable).

Methode IDENTIQUE au calibrage (scripts/calibrate_spec_profiles.py) :
  - detect_schemas sans volumes (comme le calibrate)
  - espacement de 60 seances PAR TITRE et par schema (episodes non chevauchants)
  - rendement net de frais 2,8 % aller-retour
Sortie : audit/spec_export/ (3 CSV + un resume JSON).
"""
import csv
import json
import statistics
import sys
from pathlib import Path

RACINE = Path("C:/Users/LEO/projects/Bridge Bank")
sys.path.insert(0, str(RACINE))
from src.infrastructure.paths import HISTORY_CACHE                        # noqa: E402
from src.collecte.history_io import charger_cache                          # noqa: E402
from src.strategie.spec_profiles import FRAIS, HORIZON, detect_schemas, zone_of  # noqa: E402

SORTIE = RACINE / "audit" / "spec_export"
SORTIE.mkdir(parents=True, exist_ok=True)
STOP = 0.15
PALIERS = (0.20, 0.35, 0.50)
ESPACEMENT = 60
TRANCHE = [(0.0, 0.20, "0-20"), (0.20, 0.40, "20-40"), (0.40, 0.60, "40-60"),
           (0.60, 0.80, "60-80"), (0.80, 1.01, "80-100")]


def tranche_de(z):
    for lo, hi, nom in TRANCHE:
        if lo <= z < hi:
            return nom
    return "80-100"


def percentile_rang(closes, prix):
    """Part des seances de la fenetre 5 ans STRICTEMENT sous le prix (le vrai percentile)."""
    fen = closes[-1261:-1] + [closes[-1]]
    return sum(1 for c in fen if c < prix) / len(fen)


hist = charger_cache(HISTORY_CACHE)
cas = {"CASSURE": [], "EVEIL": [], "PANIQUE": []}

for code, bars in hist.items():
    # MÉTHODE IDENTIQUE AU CALIBRATE : aucune barre n'est filtrée (pas de `close > 0`).
    # Filtrer les barres à zéro raccourcit la série et change les cas retenus — mesuré :
    # 414 cas PANIQUE au lieu de 421. Pour qu'un tiers puisse recouper nos chiffres, l'export
    # doit rejouer EXACTEMENT le même univers que scripts/calibrate_spec_profiles.py.
    closes = [float(b.close) for b in bars]
    vols = [float(getattr(b, "volume", 0) or 0) for b in bars]
    if len(closes) < 500 or closes[0] <= 0:
        continue
    dernier = {"CASSURE": -10**9, "EVEIL": -10**9, "PANIQUE": -10**9}
    for i in range(260, len(closes) - HORIZON):
        schemas = detect_schemas(closes[: i + 1])
        if not schemas:
            continue
        zone = zone_of(closes[: i + 1])
        pct = percentile_rang(closes[: i + 1], closes[i])
        futur = closes[i + 1: i + HORIZON + 1]
        # parcours jour par jour : ou est le stop, et quand les paliers sont-ils atteints ?
        jour_stop = None
        jours_palier = {}
        for j, c in enumerate(futur, 1):
            r = c / closes[i] - 1
            if jour_stop is None and r <= -STOP:
                jour_stop = j
            for p in PALIERS:
                if p not in jours_palier and r >= p:
                    jours_palier[p] = j
        rendement = futur[-1] / closes[i] - 1 - FRAIS
        pic = max(futur) / closes[i] - 1
        creux = min(futur) / closes[i] - 1
        for s in schemas:
            if i - dernier[s] < ESPACEMENT:
                continue
            dernier[s] = i
            ligne = {
                "code": code,
                "date_signal": str(bars[i].date)[:10],
                "cours_signal": round(closes[i], 2),
                "schema": s,
                "zone_minmax": round(zone, 4),
                "zone_tranche": tranche_de(zone),
                "percentile_rang": round(pct, 4),
                "rendement_12m_net": round(rendement, 4),
                "pic_max_12m": round(pic, 4),
                "creux_min_12m": round(creux, 4),
                "stop_15_touche": jour_stop is not None,
                "jours_avant_stop": jour_stop if jour_stop else "",
                "volume_jour": vols[i] if i < len(vols) else 0,
                "volume_median_60j": round(statistics.median(vols[i - 60: i]), 0)
                                      if len(vols) > i and i >= 60 else 0,
            }
            for p in PALIERS:
                atteint = p in jours_palier
                avant = atteint and (jour_stop is None or jours_palier[p] < jour_stop)
                ligne[f"p{int(p*100)}_touche"] = atteint
                ligne[f"p{int(p*100)}_avant_stop"] = avant
                ligne[f"p{int(p*100)}_jour"] = jours_palier.get(p, "")
            cas[s].append(ligne)

print(f"{'schema':9} {'cas':>5} {'exporte':>8}")
for s, lignes in cas.items():
    chemin = SORTIE / f"cas_{s}.csv"
    if lignes:
        with chemin.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes[0]))
            w.writeheader()
            w.writerows(lignes)
    print(f"{s:9} {len(lignes):>5}   -> {chemin.name}")

# --- le resume qui compte : les taux AVANT stop, par schema et par zone ---------
print("\n=== LA MESURE QUI MANQUAIT : paliers atteints AVANT le stop -15 % ===")
resume = {}
for s, lignes in cas.items():
    if not lignes:
        continue
    resume[s] = {}
    n = len(lignes)
    resume[s]["total"] = {
        "n": n,
        "win": round(sum(1 for x in lignes if x["rendement_12m_net"] > 0) / n, 3),
        "median": round(statistics.median([x["rendement_12m_net"] for x in lignes]), 3),
        "stop_touche": round(sum(1 for x in lignes if x["stop_15_touche"]) / n, 3),
    }
    for p in PALIERS:
        cle = f"p{int(p*100)}_avant_stop"
        resume[s]["total"][cle] = round(sum(1 for x in lignes if x[cle]) / n, 3)
        resume[s]["total"][f"p{int(p*100)}_touche_sans_contrainte"] = round(
            sum(1 for x in lignes if x[f"p{int(p*100)}_touche"]) / n, 3)
    print(f"\n{s} ({n} cas) :")
    t = resume[s]["total"]
    print(f"  rendement median 12 mois net : {t['median']*100:+.1f} %   "
          f"({t['win']*100:.0f} % de cas positifs)")
    print(f"  stop -15 % touche dans       : {t['stop_touche']*100:.0f} % des cas")
    for p in PALIERS:
        k = int(p * 100)
        print(f"  +{k} % : touche {t[f'p{k}_touche_sans_contrainte']*100:>3.0f} % brut  ->  "
              f"AVANT LE STOP {t[f'p{k}_avant_stop']*100:>3.0f} %")
    # par zone
    resume[s]["zones"] = {}
    for _, _, tr in TRANCHE:
        lot = [x for x in lignes if x["zone_tranche"] == tr]
        if not lot:
            continue
        m = len(lot)
        resume[s]["zones"][tr] = {
            "n": m,
            "win": round(sum(1 for x in lot if x["rendement_12m_net"] > 0) / m, 3),
            "median": round(statistics.median([x["rendement_12m_net"] for x in lot]), 3),
            "p20_avant_stop": round(sum(1 for x in lot if x["p20_avant_stop"]) / m, 3),
        }
        z = resume[s]["zones"][tr]
        print(f"    zone {tr:7} n={m:>4}  {z['win']*100:>5.1f} % positifs  "
              f"median {z['median']*100:>+6.1f} %  +20 % avant stop : {z['p20_avant_stop']*100:>5.1f} %")

(SORTIE / "resume.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
print(f"\n-> {SORTIE / 'resume.json'}")
