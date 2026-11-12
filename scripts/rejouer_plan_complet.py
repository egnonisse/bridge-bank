"""REJEU du PLAN DE VENTE COMPLET de la veille spéculative — pour audit externe.

Ce script répond à la critique de l'auditeur : publier « ton palier +20 % est touché
dans 59 % des cas » mesure le PLUS HAUT atteint dans les 12 mois. Ça ignore (a) le stop
−15 %, (b) le plan de vente par tiers, (c) les frais réels avec minimum par ordre, (d) la
capacité réelle du marché à absorber l'ordre (volume). On mesure ici le résultat
RÉELLEMENT ENCAISSABLE, séance par séance, sur le même univers que l'export
(scripts/exporter_cas_spec.py) : cache PROPRE, espacement 60 séances, 12 mois d'horizon.

LE PLAN (repris de src/strategie/spec_fiche.py, règles inchangées) :
  - achat au cours du signal (dernière clôture connue) ;
  - stop −15 % du PRIX PAYÉ → on vend tout, sans discuter ;
  - +20 % du prix payé → vends ⅓ du titre initial ;
  - +35 % → vends ⅓ ; +50 % → vends le reste (le 3e tiers) ;
  - reliquat (tiers jamais vendus) sorti au close de la dernière séance de l'horizon.

HYPOTHÈSES EXPLICITES (aucune ne peut être levée sans données intraday, absentes ici) :
  1. Exécution au CLOSE. Les barres portent OHLC mais l'export et le calibrage mesurent
     au close ; le rejeu reste au close pour être comparable. Le stop est donc évalué au
     close de la séance, pas en intraday — c'est OPTIMISTE (un stop intraday aurait
     souvent touché plus tôt, à un prix pire).
  2. Ordre des événements dans une même séance : stop et paliers vivent de part et d'autre
     de l'entrée (−15 % vs ≥ +20 %), ils ne peuvent PAS partager un même close. Le cas
     résiduel est une GAP qui traverse un palier : on remplit la tranche AU NIVEAU du
     palier (ordre limite), jamais au-dessus — hypothèse PESSIMISTE (on ne crédite pas
     l'excédent de la gap). S'il fallait trancher « stop ou palier le même jour », on
     retiendrait le STOP D'ABORD : le plan dit « vends tout, sans discuter », et supposer
     le stop premier est PESSIMISTE (on renonce au gain du palier plutôt que de le
     surestimer).
  3. Tiers = tiers du NOMBRE DE TITRES initial, pas du reliquat (le plan vend ⅓, ⅓, le
     reste → trois tiers égaux).
  4. Frais : commission() de src/taxation.py — courtage 0,80 % (min 1 000 F) + TVA 18 %
     sur le courtage + BRVM 0,456 %. Sous ~125 000 F, le minimum mord : un ordre de
     50 000 F supporte ~2,8 %, un tiers de 100 000 F revendu +20 % supporte ~3,4 %.
  5. Taille de position explicite (le minimum de frais ne se lit que sur un montant) :
     50 000 / 100 000 / 500 000 F, défaut 100 000 F.
  6. Contrainte de volume : un ordre ne peut absorber plus de 10 % du volume échangé de
     la séance (hypothèse de participation, unité = titres comme le champ `volume` du
     cache). Un ordre qui dépasse → la vente requise est INEXÉCUTABLE telle quelle.

Sortie : uniquement du texte sur stdout (aucun fichier écrit — ce script n'est pas
propriétaire des CSV de audit/spec_export/). Usage :
    python scripts/rejouer_plan_complet.py
"""
from __future__ import annotations

import datetime
import statistics
import sys
from pathlib import Path

RACINE = Path("C:/Users/LEO/projects/Bridge Bank")
sys.path.insert(0, str(RACINE))

from src.collecte.preparation import charger_historique_propre          # noqa: E402
from src.strategie.spec_profiles import (FRAIS, HORIZON_JOURS, detect_schemas,  # noqa: E402
                                         zone_of, index_fin_horizon, fenetre_complete)
from src.taxation import commission                                      # noqa: E402

STOP = 0.15
PALIERS = (0.20, 0.35, 0.50)
ESPACEMENT = 60
VOLUME_FRACTION = 0.10          # hypothèse de participation : 10 % du volume de la séance
POSITIONS = (50_000.0, 100_000.0, 500_000.0)
POSITION_DEFAUT = 100_000.0
SCHEMAS = ("CASSURE", "EVEIL", "PANIQUE")
TRANCHE = [(0.0, 0.20, "0-20"), (0.20, 0.40, "20-40"), (0.40, 0.60, "40-60"),
           (0.60, 0.80, "60-80"), (0.80, 1.01, "80-100")]


def tranche_de(z: float) -> str:
    for lo, hi, nom in TRANCHE:
        if lo <= z < hi:
            return nom
    return "80-100"


def taux_effectif(montant: float) -> float:
    return commission(montant) / montant if montant > 0 else 0.0


def simuler_plan(entry: float, futur: list, position: float,
                 futures_vols: list | None = None) -> dict:
    """Rejoue le plan complet sur les closes `futur` (séances i+1 … fin d'horizon)."""
    n_init = position / entry
    tranche = n_init / 3.0
    stop_level = entry * (1 - STOP)
    niveaux = [entry * (1 + p) for p in PALIERS]

    frais_achat = commission(position)
    restantes = n_init
    tranches_vendues = 0
    ventes: list = []                 # (jour, raison, montant_brut, nb_titres, prix)
    stop_touche = False
    jour_stop = None
    jours_palier: dict = {}

    for j, c in enumerate(futur, 1):
        if restantes <= 1e-12:
            break
        if c <= stop_level:                     # 1) stop d'abord
            stop_touche = True
            jour_stop = j
            ventes.append((j, "stop", restantes * c, restantes, c))
            restantes = 0.0
            break
        for k, p in enumerate(PALIERS):         # 2) paliers dans l'ordre croissant
            if tranches_vendues == k and c >= niveaux[k]:
                ventes.append((j, f"p{int(p*100)}", tranche * niveaux[k], tranche,
                               niveaux[k]))
                restantes -= tranche
                tranches_vendues += 1
                jours_palier[f"p{int(p*100)}"] = j

    if restantes > 1e-12:                       # 3) reliquat en fin d'horizon
        c_fin = futur[-1]
        ventes.append((len(futur), "reliquat", restantes * c_fin, restantes, c_fin))
        restantes = 0.0

    frais_ventes = 0.0
    produits_bruts = 0.0
    bloques = []
    for (j, raison, montant, nb, prix) in ventes:
        produits_bruts += montant
        if futures_vols and 0 < j <= len(futures_vols):
            cap = VOLUME_FRACTION * futures_vols[j - 1]
            if cap > 0 and nb > cap:
                bloques.append({"raison": raison, "jour": j,
                                "titres": round(nb, 4), "cap": round(cap, 4)})
        frais_ventes += commission(montant)

    investi = position + frais_achat
    encaisse_net = produits_bruts - frais_ventes
    pnl = encaisse_net - investi
    return {
        "rendement": pnl / investi,
        "pnl": pnl,
        "investi": investi,
        "stop_touche": stop_touche,
        "jour_stop": jour_stop,
        "paliers_vendus": jours_palier,
        "nb_paliers_vendus": tranches_vendues,
        "bloques": bloques,
        "nb_ordres": len(ventes),
    }


def stats(rendements: list, pnls: list, investis: list) -> dict:
    n = len(rendements)
    if n == 0:
        return {"n": 0}
    perdants = [r for r in rendements if r < 0]
    gagnants = [r for r in rendements if r >= 0]
    return {
        "n": n,
        "moyen": statistics.fmean(rendements),
        "median": statistics.median(rendements),
        "pct_perdants": len(perdants) / n,
        "perte_moyenne": statistics.fmean(perdants) if perdants else 0.0,
        "gain_moyen": statistics.fmean(gagnants) if gagnants else 0.0,
        "pnl_total": sum(pnls),
        "investi_total": sum(investis),
        "rendement_total": sum(pnls) / sum(investis) if investis else 0.0,
    }


def fmt_pct(x: float, digits: int = 1) -> str:
    return f"{x*100:+.{digits}f} %"


# ─────────────────────────────────────────────────────────────────────────────
hist = charger_historique_propre(preparer_si_necessaire=False)

cas_complets: list = []
cas_non_matures: list = []

for code, bars in hist.items():
    closes = [float(b.close) for b in bars]
    vols = [float(getattr(b, "volume", 0) or 0) for b in bars]
    if len(closes) < 500 or closes[0] <= 0:
        continue
    dates = [b.date if isinstance(b.date, datetime.date)
             else datetime.date.fromisoformat(str(b.date)[:10]) for b in bars]
    dernier = {s: -10**9 for s in SCHEMAS}
    for i in range(260, len(closes) - 1):
        # Horizon CALENDAIRE (365 jours) au lieu de 252 seances : voir HORIZON_JOURS.
        j_fin = index_fin_horizon(dates, i)
        if not fenetre_complete(dates, i, j_fin):
            continue
        schemas = detect_schemas(closes[: i + 1])
        if not schemas:
            continue
        zone = zone_of(closes[: i + 1])
        entry = closes[i]
        futur = closes[i + 1: j_fin + 1]
        futvols = vols[i + 1: j_fin + 1]
        complet = True
        for s in schemas:
            if i - dernier[s] < ESPACEMENT:
                continue
            dernier[s] = i
            rec = {
                "code": code, "schema": s, "date": str(bars[i].date)[:10],
                "entry": entry, "zone": zone,
                "zone_tranche": tranche_de(zone),
                "futur": futur, "futvols": futvols,
            }
            (cas_complets if complet else cas_non_matures).append(rec)

compte_c = {s: sum(1 for c in cas_complets if c["schema"] == s) for s in SCHEMAS}
compte_nm = {s: sum(1 for c in cas_non_matures if c["schema"] == s) for s in SCHEMAS}

vols_futurs = [v for c in cas_complets for v in c["futvols"]]
vols_nz = [v for v in vols_futurs if v > 0]

print("=" * 92)
print("REJEU DU PLAN COMPLET — veille spéculative (audit spec_export)")
print("=" * 92)
print("cache PROPRE lu en lecture seule : %d titres" % len(hist))
print("cas à horizon COMPLET : %d   %s" % (
    len(cas_complets),
    ", ".join("%s %d" % (s, compte_c[s]) for s in SCHEMAS)))
print("cas récents NON MATURES : %d   %s" % (
    len(cas_non_matures),
    ", ".join("%s %d" % (s, compte_nm[s]) for s in SCHEMAS)))
print("diagnostic volume des séances suivies : %.1f %% avec volume > 0, "
      "volume médian %.0f titres" % (
          100 * len(vols_nz) / len(vols_futurs), statistics.median(vols_nz)))

print()
print("=== FRAIS RÉELS PAR ORDRE — commission() de src/taxation.py ===")
print("%18s | %16s | %22s" % ("taille de position", "achat (1 ordre)", "tiers vendu +20 %"))
for pos in POSITIONS:
    t20 = pos / 3 * 1.20
    print("%18.0f F | %15.2f %% | %19.2f %% (tranche %.0f F)" % (
        pos, taux_effectif(pos) * 100, taux_effectif(t20) * 100, t20))

# ─── simulation du plan sur les cas complets, à la position par défaut ───────
for rec in cas_complets:
    rec["pic"] = max(rec["futur"]) / rec["entry"] - 1
    rec["naif_net"] = rec["futur"][-1] / rec["entry"] - 1 - FRAIS
    rec["sim"] = simuler_plan(rec["entry"], rec["futur"], POSITION_DEFAUT,
                              rec["futvols"])

# ─── 1. métriques par schéma (position 100 000 F) ────────────────────────────
print()
print("=== 1. PLAN COMPLET PAR SCHÉMA — position %.0f F, %d cas à horizon complet ===" % (
    POSITION_DEFAUT, len(cas_complets)))
print("  (rendement net = P&L encaissé / capital investi ; frais ACHAT + VENTE, "
      "minimum 1 000 F par ordre)")
print("%9s %5s %10s %9s %11s %11s %10s %10s %10s" % (
    "schéma", "n", "net moyen", "médian", "% perdants", "perte moy.",
    "gain moy.", "espérance", "net total"))
for s in SCHEMAS:
    lot = [c for c in cas_complets if c["schema"] == s]
    if not lot:
        continue
    rends = [c["sim"]["rendement"] for c in lot]
    pnls = [c["sim"]["pnl"] for c in lot]
    invs = [c["sim"]["investi"] for c in lot]
    st = stats(rends, pnls, invs)
    print("%9s %5d %10s %9s %10.1f %% %11s %10s %10s %10s" % (
        s, st["n"], fmt_pct(st["moyen"]), fmt_pct(st["median"]),
        st["pct_perdants"] * 100, fmt_pct(st["perte_moyenne"]),
        fmt_pct(st["gain_moyen"]), fmt_pct(st["moyen"]),
        fmt_pct(st["rendement_total"])))

# ─── 2. comparaison naïf (plus haut atteint) vs plan complet ─────────────────
print()
print("=== 2. CHIFFRE NAÏF (plus haut atteint) vs PLAN COMPLET — par schéma ===")
print("  naïf « touché » = le plus haut des 12 mois atteint le palier (IGNORE le stop).")
print("  plan « vendu »  = la tranche a réellement été vendue (palier atteint AVANT le stop).")
print("%9s %5s %10s %10s %10s %10s %12s %12s" % (
    "schéma", "n", "naïf +20 %", "plan +20 %", "naïf +50 %", "plan +50 %",
    "naïf médian", "plan médian"))
for s in SCHEMAS:
    lot = [c for c in cas_complets if c["schema"] == s]
    if not lot:
        continue
    n = len(lot)
    n20 = sum(1 for c in lot if c["pic"] >= 0.20) / n
    p20 = sum(1 for c in lot if "p20" in c["sim"]["paliers_vendus"]) / n
    n50 = sum(1 for c in lot if c["pic"] >= 0.50) / n
    p50 = sum(1 for c in lot if "p50" in c["sim"]["paliers_vendus"]) / n
    naif_med = statistics.median([c["naif_net"] for c in lot])
    plan_med = statistics.median([c["sim"]["rendement"] for c in lot])
    print("%9s %5d %9.1f %% %9.1f %% %9.1f %% %9.1f %% %12s %12s" % (
        s, n, n20 * 100, p20 * 100, n50 * 100, p50 * 100,
        fmt_pct(naif_med), fmt_pct(plan_med)))

# ─── 3. par zone × schéma ─────────────────────────────────────────────────────
print()
print("=== 3. PLAN COMPLET PAR ZONE × SCHÉMA (position 100 000 F) ===")
for s in SCHEMAS:
    lot_s = [c for c in cas_complets if c["schema"] == s]
    if not lot_s:
        continue
    print("\n  %s — n=%d" % (s, len(lot_s)))
    print("  %8s %5s %10s %9s %11s %12s %10s" % (
        "zone", "n", "net moyen", "médian", "% perdants", "stop touché", "+20 vendu"))
    for _, _, tr in TRANCHE:
        lot = [c for c in lot_s if c["zone_tranche"] == tr]
        if not lot:
            continue
        n = len(lot)
        rends = [c["sim"]["rendement"] for c in lot]
        stop = sum(1 for c in lot if c["sim"]["stop_touche"]) / n
        p20 = sum(1 for c in lot if "p20" in c["sim"]["paliers_vendus"]) / n
        print("  %8s %5d %10s %9s %10.1f %% %11.1f %% %9.1f %%" % (
            tr, n, fmt_pct(statistics.fmean(rends)),
            fmt_pct(statistics.median(rends)),
            sum(1 for r in rends if r < 0) / n * 100, stop * 100, p20 * 100))

# ─── 4. impact de la taille de position ───────────────────────────────────────
print()
print("=== 4. IMPACT DE LA TAILLE DE POSITION (minimum de frais) ===")
print("%14s %10s %9s %11s %10s %10s" % (
    "taille", "net moyen", "médian", "% perdants", "espérance", "net total"))
for pos in POSITIONS:
    rends, pnls, invs = [], [], []
    for rec in cas_complets:
        sim = simuler_plan(rec["entry"], rec["futur"], pos, rec["futvols"])
        rends.append(sim["rendement"])
        pnls.append(sim["pnl"])
        invs.append(sim["investi"])
    st = stats(rends, pnls, invs)
    print("%14.0f %10s %9s %10.1f %% %10s %10s" % (
        pos, fmt_pct(st["moyen"]), fmt_pct(st["median"]),
        st["pct_perdants"] * 100, fmt_pct(st["moyen"]),
        fmt_pct(st["rendement_total"])))

# ─── 5. contrainte de volume ──────────────────────────────────────────────────
print()
print("=== 5. CONTRAINTE DE VOLUME — un ordre ≤ 10 % du volume de la séance ===")
for pos in POSITIONS:
    print("  --- position %.0f F ---" % pos)
    print("  %9s %5s %14s %7s" % ("schéma", "n", "inexécutables", "%"))
    for s in SCHEMAS:
        lot = [c for c in cas_complets if c["schema"] == s]
        if not lot:
            continue
        n = len(lot)
        nb_inex = sum(1 for c in lot
                      if simuler_plan(c["entry"], c["futur"], pos,
                                      c["futvols"])["bloques"])
        print("  %9s %5d %14d %6.1f %%" % (s, n, nb_inex, nb_inex / n * 100))

# ─── 6. cas récents non matures ───────────────────────────────────────────────
print()
print("=== 6. CAS RÉCENTS NON MATURES (moins de 12 mois de recul) — EXCLUS des métriques ===")
print("%9s %5s %17s %14s %15s" % (
    "schéma", "n", "stop déjà touché", "encore ouvert", "3 tiers vendus"))
for s in SCHEMAS:
    lot = [c for c in cas_non_matures if c["schema"] == s]
    if not lot:
        continue
    n_stop = n_ouv = n_tout = 0
    for rec in lot:
        sim = simuler_plan(rec["entry"], rec["futur"], POSITION_DEFAUT, rec["futvols"])
        if sim["stop_touche"]:
            n_stop += 1
        elif sim["nb_paliers_vendus"] == 3:
            n_tout += 1
        else:
            n_ouv += 1
    print("%9s %5d %17d %14d %15d" % (s, len(lot), n_stop, n_ouv, n_tout))

print()
print("=" * 92)
print("FIN — chiffres réels, aucun fichier écrit, aucune donnée inventée.")
print("=" * 92)
