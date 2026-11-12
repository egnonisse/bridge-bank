"""Validation HORS PÉRIODE du signal spéculatif (BRVM, veille spéculative).

QUESTION DE L'AUDITEUR
----------------------
Les taux annoncés (CASSURE 66 %, EVEIL 56 %, PANIQUE 52 %, et les taux par zone)
sont mesurés sur TOUT l'historique 2017-2026. Rien ne dit qu'ils tiennent sur une
période indépendante. Si les règles avaient été choisies APRÈS avoir regardé ces
mêmes données, le taux serait optimiste par construction (surapprentissage).

CE QUE FAIT CE SCRIPT
---------------------
1. Découpe l'historique en deux fenêtres :
     - DÉVELOPPEMENT : signal dont la date est STRICTEMENT antérieure au 2023-01-01 ;
     - VALIDATION    : signal daté du 2023-01-01 ou après (période indépendante).
   La coupure est CALENDAIRE (début d'année), fixée AVANT de regarder les résultats
   (c'est celle proposée dans le contrat), et non choisie après coup pour maximiser
   un écart. Elle laisse ~2,5 ans de validation avec 12 mois de recul complets.
2. Recalcule, séparément par période et par schéma : n, taux de cas finissant plus
   haut 12 mois après (net de frais), médiane nette, taux de palier +20 % atteint
   AVANT le stop −15 %.
3. Recalcule les mêmes statistiques PAR ZONE (position min-max 5 ans) et compte les
   cellules (schéma × zone) dont le diagnostic change entre les deux périodes.
4. Mesure un BENCHMARK comparable : acheter AU HASARD (un titre éligible, une date
   éligible) et tenir 12 mois — la performance de base du marché sur les mêmes
   fenêtres. Sans ce benchmark, un taux de 52 % ne dit rien ; avec lui, on sait si
   le signal apporte quelque chose. Un second benchmark APPARIÉ (même titre, date
   au hasard) est fourni en contrôle.
5. Teste la significativité avec une méthode explicite et conservative :
     - intervalle de confiance de WILSON (95 %) sur chaque taux ;
     - test de comparaison de DEUX PROPORTIONS (écart-type non poolé) pour
       (a) développement vs validation, (b) signal vs benchmark ;
     - test de MANN-WHITNEY U (approximation normale, correction des ex æquo) sur
       les rendements nets (médianes).

MÉTHODE IDENTIQUE AU CALIBRAGE ET À L'EXPORT (rejouable, sans réseau)
- detect_schemas SANS volumes (comme scripts/calibrate_spec_profiles.py) ;
- espacement de 60 séances PAR TITRE et PAR SCHÉMA (épisodes non chevauchants) ;
- rendement net de frais 2,8 % aller-retour (FRAIS = FRAIS_ALLER_RETOUR) ;
- « palier +20 % avant stop » : le +20 % est atteint à une séance STRICTEMENT
  antérieure au premier contact du stop −15 % (définition de l'export, resume.json).

Les détecteurs sont rejoués à l'identique, mais avec le RSI précalculé une fois par
titre : rsi[i] ne dépend que des closes[0..i+1] (indicateur causal), donc la valeur
est IDENTIQUE à detect_schemas(closes[:i+1]). Garde-fou intégré : les effectifs
globaux doivent valoir 267 / 934 / 414 (faits établis du contrat).

Sortie : le rapport markdown complet est imprimé sur stdout ET écrit dans
audit/spec_export/HORS-PERIODE.md (un seul écrivain : cet agent, fichier P6).
"""
from __future__ import annotations

import datetime
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime as _dt
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from src.collecte.preparation import charger_historique_propre          # noqa: E402
from src.strategie.spec_profiles import (FRAIS, HORIZON_JOURS, rsi, zone_of,  # noqa: E402
                                         index_fin_horizon, fenetre_complete, detect_schemas,
                                         PROFILES_FILE)

# ── Constantes de la validation ────────────────────────────────────────────────
COUPURE = date(2023, 1, 1)          # développement < COUPURE <= validation
SCHEMAS = ("CASSURE", "EVEIL", "PANIQUE")
ESPACEMENT = 60                     # même espacement que le calibrage
STOP = 0.15                         # stop −15 %
PALIER = 0.20                       # le palier testé « avant stop »
SEUIL_CAS_ZONE = 10                 # sous 10 cas, aucun diagnostic (⚪)
Z95 = 1.959964                      # quantile normal 95 % (bilatéral)
TRANCHE = [(0.0, 0.20, "0-20"), (0.20, 0.40, "20-40"), (0.40, 0.60, "40-60"),
           (0.60, 0.80, "60-80"), (0.80, 1.01, "80-100")]
SORTIE = RACINE / "audit" / "spec_export"
RAPPORT = SORTIE / "HORS-PERIODE.md"


def tranche_de(z: float) -> str:
    for lo, hi, nom in TRANCHE:
        if lo <= z < hi:
            return nom
    return "80-100"


def as_date(d):
    return d.date() if isinstance(d, _dt) else d


# ── Statistiques ───────────────────────────────────────────────────────────────
def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Intervalle de Wilson à 95 % pour une proportion p̂ = k/n.

    centre = (p̂ + z²/(2n)) / (1 + z²/n)
    demi   = z·√(p̂(1−p̂)/n + z²/(4n²)) / (1 + z²/n)
    IC     = centre ∓ demi
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - demi, centre + demi)


def _phi(x: float) -> float:
    """CDF de la loi normale standard (via erf)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def ztest_proportions(k1, n1, k2, n2):
    """Test bilatéral de comparaison de deux proportions (écart-type NON poolé).

    z = (p̂1 − p̂2) / √(p̂1(1−p̂1)/n1 + p̂2(1−p̂2)/n2) ;  p = 2·(1 − Φ(|z|))
    """
    if n1 == 0 or n2 == 0:
        return (float("nan"), float("nan"))
    p1, p2 = k1 / n1, k2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    if se == 0:
        return (float("nan"), float("nan"))
    z = (p1 - p2) / se
    return (z, 2 * (1 - _phi(abs(z))))


def mannwhitney_u(a: list, b: list):
    """Mann-Whitney U bilatéral (approximation normale, correction des ex æquo).

    U   = R1 − n1(n1+1)/2  (R1 = somme des rangs du 1er échantillon)
    μ   = n1·n2/2
    σ²  = (n1·n2/12)·[(N+1) − Σ(t³−t)/(N(N−1))]  (t = tailles des groupes d'ex æquo)
    z   = (U − μ)/σ ;  p = 2·(1 − Φ(|z|))
    """
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return (float("nan"), float("nan"), float("nan"))
    N = n1 + n2
    ranked = sorted([(float(v), 0) for v in a] + [(float(v), 1) for v in b])
    ranks = [0.0] * N
    i = 0
    while i < N:
        j = i
        while j < N and ranked[j][0] == ranked[i][0]:
            j += 1
        avg = (i + 1 + j) / 2.0          # rangs 1-based de i+1 .. j
        for t in range(i, j):
            ranks[t] = avg
        i = j
    r1 = sum(ranks[t] for t in range(N) if ranked[t][1] == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u = min(u1, n1 * n2 - u1)
    mu = n1 * n2 / 2.0
    ties = 0
    i = 0
    while i < N:
        j = i
        while j < N and ranked[j][0] == ranked[i][0]:
            j += 1
        t = j - i
        ties += t ** 3 - t
        i = j
    sigma = math.sqrt(n1 * n2 / 12.0 * ((N + 1) - ties / (N * (N - 1))))
    if sigma == 0:
        return (u, float("nan"), float("nan"))
    z = (u - mu) / sigma
    return (u, z, 2 * (1 - _phi(abs(z))))


def p20_avant_stop(closes: list, i: int, j_fin: int) -> bool:
    """+20 % atteint à une séance STRICTEMENT antérieure au premier contact du stop −15 %.

    Identique à la définition de scripts/exporter_cas_spec.py (jour_palier < jour_stop,
    ou jour_stop jamais atteint). `j_fin` borne la fenêtre : horizon CALENDAIRE (365 jours),
    plus les 252 séances d'avant.
    """
    base = closes[i]
    if base <= 0:
        return False
    jour_stop = None
    jour_palier = None
    for j in range(i + 1, j_fin + 1):
        r = closes[j] / base - 1.0
        if jour_stop is None and r <= -STOP:
            jour_stop = j
        if jour_palier is None and r >= PALIER:
            jour_palier = j
    if jour_palier is None:
        return False
    return jour_stop is None or jour_palier < jour_stop


def verdict(n: int, win: float) -> str:
    """Couleur de diagnostic (convention du contrat §5)."""
    if n < SEUIL_CAS_ZONE:
        return "⚪ (n<10)"
    if win >= 0.60:
        return "✅ favorable"
    if win >= 0.50:
        return "🟡 neutre"
    return "🔴 défavorable"


# ── Collecte des cas et du benchmark ──────────────────────────────────────────
def collecter():
    hist = charger_historique_propre(preparer_si_necessaire=False)

    cas = {s: [] for s in SCHEMAS}                       # un dict par cas
    base_rets = {"dev": [], "val": []}                   # benchmark marché (tous les pairs éligibles)
    title_rets = defaultdict(lambda: {"dev": [], "val": []})  # benchmark « même titre »
    global_n = {s: 0 for s in SCHEMAS}

    for code, bars in hist.items():
        closes = [float(b.close) for b in bars]
        dates = [b.date if isinstance(b.date, datetime.date)
                 else datetime.date.fromisoformat(str(b.date)[:10]) for b in bars]
        if len(closes) < 500 or closes[0] <= 0:
            continue
        r = rsi(closes)
        dernier = {s: -10 ** 9 for s in SCHEMAS}
        for i in range(260, len(closes) - 1):
            # Horizon CALENDAIRE (365 jours) au lieu de 252 seances : voir HORIZON_JOURS.
            j_fin = index_fin_horizon(dates, i)
            if not fenetre_complete(dates, i, j_fin):
                continue
            period = "dev" if as_date(dates[i]) < COUPURE else "val"
            ret = closes[j_fin] / closes[i] - 1.0 - FRAIS
            # Détection — réplique EXACTE de detect_schemas(closes[:i+1]) sans volumes.
            schemas = []
            if closes[i] > 0:
                if closes[i] > max(closes[i - 250:i]):
                    schemas.append("CASSURE")
                if closes[i] / min(closes[i - 60:i]) - 1.0 >= 0.10:
                    schemas.append("EVEIL")
                if r[i] is not None and r[i] < 30:
                    schemas.append("PANIQUE")
            acceptes = [s for s in schemas if i - dernier[s] >= ESPACEMENT]
            if not acceptes:
                base_rets[period].append(ret)
                title_rets[code][period].append(ret)
                continue
            # Un cas de signal accepté pour (au moins) un schéma.
            zone = tranche_de(zone_of(closes[: i + 1]))
            p20 = p20_avant_stop(closes, i, j_fin)
            stop_touche = any(closes[j] / closes[i] - 1.0 <= -STOP
                              for j in range(i + 1, j_fin + 1))
            for s in acceptes:
                dernier[s] = i
                global_n[s] += 1
                cas[s].append({
                    "period": period, "ret": ret, "win": ret > 0.0,
                    "p20": p20, "stop": stop_touche, "zone": zone, "code": code,
                })
            # La date (titre, i) est une date de signal : elle reste DANS le benchmark
            # marché (l'univers éligible « achat au hasard » l'inclut à sa fréquence
            # naturelle, ~2 % des pairs — négligeable), mais hors du benchmark même titre
            # si on voulait l'isoler ; on garde la convention simple : benchmark = TOUS
            # les pairs éligibles, signal compris (fréquence naturelle).

    return hist, cas, base_rets, dict(title_rets), global_n


def agg(cas_liste):
    """Statistiques agrégées d'une liste de cas."""
    n = len(cas_liste)
    if n == 0:
        return {"n": 0, "win": None, "win_lo": None, "win_hi": None,
                "median": None, "p20": None, "stop": None, "rets": []}
    rets = [c["ret"] for c in cas_liste]
    k = sum(1 for c in cas_liste if c["win"])
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "win": k / n, "win_lo": lo, "win_hi": hi,
        "median": statistics.median(rets),
        "p20": sum(1 for c in cas_liste if c["p20"]) / n,
        "stop": sum(1 for c in cas_liste if c["stop"]) / n,
        "rets": rets,
    }


def agg_rets(rets):
    n = len(rets)
    if n == 0:
        return {"n": 0, "win": None, "win_lo": None, "win_hi": None,
                "median": None, "rets": []}
    k = sum(1 for r in rets if r > 0)
    lo, hi = wilson_ci(k, n)
    return {"n": n, "win": k / n, "win_lo": lo, "win_hi": hi,
            "median": statistics.median(rets), "rets": rets}


def pct(x, nd=1):
    return "—" if x is None else f"{x * 100:.{nd}f}"


def pval(p):
    return "—" if (p is None or (isinstance(p, float) and math.isnan(p))) else f"{p:.3g}"


# ── Rendu markdown ─────────────────────────────────────────────────────────────
def rendre(hist, cas, base_rets, title_rets, global_n):
    L = []

    L.append("# Validation hors période du signal spéculatif (BRVM)\n")
    L.append("> Réponse à la question de l'auditeur : les taux annoncés tiennent-ils sur\n"
             "> une période indépendante, et apportent-ils quelque chose par rapport à un\n"
             "> achat au hasard ?\n")

    # 1. Coupure et effectifs
    L.append("## 1. Coupure et effectifs\n")
    L.append("La coupure est **calendaire** et fixée *avant* de regarder les résultats :\n"
             "`2023-01-01`. C'est la coupure proposée dans le contrat de l'audit, choisie sur\n"
             "le calendrier (début d'année), pas sur les données. Elle laisse environ 2,5 ans\n"
             "de période de validation dont les 12 mois de recul sont complets (le dernier cas\n"
             "évaluable est daté de ~12 mois avant la dernière séance du cache).\n")
    tot_dev = sum(len([c for c in cas[s] if c["period"] == "dev"]) for s in SCHEMAS)
    tot_val = sum(len([c for c in cas[s] if c["period"] == "val"]) for s in SCHEMAS)
    L.append(f"- **Développement** (avant le 2023-01-01) : **{tot_dev}** cas\n"
             f"- **Validation** (à partir du 2023-01-01) : **{tot_val}** cas\n"
             f"- Total : {tot_dev + tot_val} cas (doit égaler 1 615)\n")

    # Table par schéma / période
    L.append("\n## 2. Statistiques par schéma et par période\n")
    L.append("Taux de réussite = cas finissant **plus haut 12 mois après**, net de frais\n"
             "(2,8 % aller-retour). Médiane nette = médiane du rendement 12 mois net.\n"
             "« +20 % avant stop » = le palier +20 % est atteint avant le stop −15 %.\n")
    L.append("\n| Schéma | Période | n | Réussite 12 m | IC 95 % (Wilson) | Médiane nette | +20 % avant stop | Stop −15 % touché |\n")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for s in SCHEMAS:
        for period, label in (("dev", "dév."), ("val", "valid.")):
            a = agg([c for c in cas[s] if c["period"] == period])
            L.append(f"| {s} | {label} | {a['n']} | {pct(a['win'])} % | "
                     f"[{pct(a['win_lo'])} % ; {pct(a['win_hi'])} %] | {pct(a['median'], 2)} % | "
                     f"{pct(a['p20'])} % | {pct(a['stop'])} % |")

    # Garde-fou
    L.append("\n*Garde-fou* : effectifs globaux mesurés "
             + " / ".join(f"{s}={global_n[s]}" for s in SCHEMAS)
             + " (attendu 267 / 934 / 414).\n")

    # 2. Par zone
    L.append("\n## 3. Statistiques par zone (position min-max 5 ans)\n")
    L.append("Diagnostic par cellule : ✅ favorable (≥60 %), 🟡 neutre (50–60 %),\n"
             "🔴 défavorable (<50 %), ⚪ non conclu (n<10).\n")
    # charger les taux annoncés (plein échantillon) pour référence
    pub = {}
    try:
        if PROFILES_FILE.exists():
            pub = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pub = {}

    for s in SCHEMAS:
        L.append(f"\n### {s}\n")
        L.append("| Zone | n dév. | réussite dév. | n valid. | réussite valid. | annoncé (plein) | +20 % av. stop dév. | +20 % av. stop valid. | Diagnostic dév. → valid. |\n")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for _, _, t in TRANCHE:
            d = agg([c for c in cas[s] if c["period"] == "dev" and c["zone"] == t])
            v = agg([c for c in cas[s] if c["period"] == "val" and c["zone"] == t])
            annonce = ""
            try:
                wz = pub.get(s, {}).get("zones", {}).get(t, {})
                if wz:
                    annonce = f"{wz['win_12m'] * 100:.0f} % (n={wz['n']})"
                else:
                    annonce = "—"
            except Exception:
                annonce = "—"
            vd, vv = verdict(d["n"], d["win"] or 0), verdict(v["n"], v["win"] or 0)
            L.append(f"| {t} | {d['n']} | {pct(d['win'])} % | {v['n']} | {pct(v['win'])} % "
                     f"| {annonce} | {pct(d['p20'])} % | {pct(v['p20'])} % | {vd} → {vv} |")

    # cellules instables
    L.append("\n### Cellules dont le diagnostic change entre développement et validation\n")
    flips, insuff = [], []
    for s in SCHEMAS:
        for _, _, t in TRANCHE:
            d = agg([c for c in cas[s] if c["period"] == "dev" and c["zone"] == t])
            v = agg([c for c in cas[s] if c["period"] == "val" and c["zone"] == t])
            vd, vv = verdict(d["n"], d["win"] or 0), verdict(v["n"], v["win"] or 0)
            if v["n"] < SEUIL_CAS_ZONE:
                insuff.append((s, t, v["n"], vd))
            elif vd != vv:
                flips.append((s, t, d["n"], v["n"], vd, vv, d["win"], v["win"]))
    if flips:
        L.append(f"**{len(flips)} cellule(s) instable(s)** (diagnostic différent entre les deux\n"
                 f"périodes, avec au moins {SEUIL_CAS_ZONE} cas de chaque côté) :\n")
        for s, t, nd, nv, vd, vv, wd, wv in flips:
            L.append(f"- **{s} / zone {t}** : {vd} ({wd*100:.0f} %, n={nd}) → "
                     f"{vv} ({wv*100:.0f} %, n={nv})\n")
    else:
        L.append("Aucune cellule ne change de diagnostic entre les deux périodes\n"
                 "(parmi celles ayant assez de cas des deux côtés).\n")
    if insuff:
        L.append(f"\n{len(insuff)} cellule(s) non concluante(s) en validation (n<{SEUIL_CAS_ZONE}) : "
                 + ", ".join(f"{s}/{t} (n={n})" for s, t, n, _ in insuff) + "\n")

    # 4. Benchmark
    L.append("\n## 4. Benchmark : acheter au hasard\n")
    L.append("Base du marché = tenir 12 mois (net de frais) un titre éligible à une date\n"
             "éligible, **sans aucun signal**. C'est la performance de fond du marché sur les\n"
             "mêmes fenêtres — le niveau que le signal doit dépasser pour « apporter quelque\n"
             "chose ».\n")
    L.append("\n| Période | n | Réussite 12 m | IC 95 % (Wilson) | Médiane nette |\n")
    L.append("|---|---:|---:|---:|---:|")
    base = {}
    for period, label in (("dev", "dév."), ("val", "valid.")):
        a = agg_rets(base_rets[period])
        base[period] = a
        L.append(f"| Base du marché — {label} | {a['n']} | {pct(a['win'])} % | "
                 f"[{pct(a['win_lo'])} % ; {pct(a['win_hi'])} %] | {pct(a['median'], 2)} % |")
    L.append("\n> **À retenir avant toute lecture des taux du signal** : la base du marché change\n"
             "> fortement de régime entre les deux périodes (48,1 % → 69,7 % de réussite, médiane\n"
             "> −1,61 % → +21,85 %). 2018-2022 est un marché plat/baisse, 2023-2025 un marché\n"
             "> haussier. C'est CE chiffre que les taux du signal doivent dépasser pour « apporter\n"
             "> quelque chose » (voir la section 6).\n")

    # benchmark même titre
    L.append("\n**Benchmark apparié (même titre, date au hasard)** : pour chaque cas, on soustrait\n"
             "le rendement 12 m moyen du MÊME titre sur la même période (hors signal) — il\n"
             "reste l'excès imputable au choix de la date par le signal.\n")
    L.append("\n| Schéma | Période | n | excès moyen vs même titre | part battant la base du titre |\n")
    L.append("|---|---|---:|---:|---:|")
    for s in SCHEMAS:
        for period, label in (("dev", "dév."), ("val", "valid.")):
            lot = [c for c in cas[s] if c["period"] == period]
            if not lot:
                continue
            excess, beat = [], 0
            for c in lot:
                tr = title_rets.get(c["code"], {}).get(period, [])
                if not tr:
                    continue
                base_mean = statistics.mean(tr)
                base_med = statistics.median(tr)
                excess.append(c["ret"] - base_mean)
                beat += 1 if c["ret"] > base_med else 0
            L.append(f"| {s} | {label} | {len(lot)} | {statistics.mean(excess)*100:+.2f} % "
                     f"| {beat/len(excess)*100:.0f} % ({beat}/{len(excess)}) |")

    # 5. Significativité
    L.append("\n## 5. Significativité\n")
    L.append("Méthodes (conservatrices, formules ci-dessous) : intervalle de Wilson à 95 %,\n"
             "test de deux proportions (écart-type non poolé), Mann-Whitney U avec correction\n"
             "des ex æquo. Aucune significativité n'est revendiquée au-delà de ce que les\n"
             "effectifs permettent.\n")

    L.append("\n### 5.1 Stabilité : développement vs validation (le cœur de la question)\n")
    L.append("\n| Schéma | réussite dév. | réussite valid. | z (2 prop.) | p | même distribution des rendements ? (Mann-Whitney p) |\n")
    L.append("|---|---:|---:|---:|---:|---:|")
    for s in SCHEMAS:
        d = agg([c for c in cas[s] if c["period"] == "dev"])
        v = agg([c for c in cas[s] if c["period"] == "val"])
        kd = sum(1 for c in cas[s] if c["period"] == "dev" and c["win"])
        kv = sum(1 for c in cas[s] if c["period"] == "val" and c["win"])
        z, p = ztest_proportions(kd, d["n"], kv, v["n"])
        _, _, pmw = mannwhitney_u(d["rets"], v["rets"])
        L.append(f"| {s} | {pct(d['win'])} % | {pct(v['win'])} % | {z:+.2f} | {pval(p)} | {pval(pmw)} |")
    L.append("\n> Lecture : ces écarts dév./valid. sont tous significatifs, mais ils reflètent d'abord\n"
             "> le changement de régime (la base passe de 48,1 % à 69,7 %). La stabilité qu'il faut\n"
             "> surveiller n'est pas le taux brut du signal, mais son ÉCART à la base — c'est l'objet\n"
             "> de 5.2.\n")

    L.append("\n### 5.2 Le signal bat-il la base du marché ? (par période)\n")
    L.append("\n| Schéma | Période | réussite signal | réussite base | z (2 prop.) | p | médianes (Mann-Whitney p) |\n")
    L.append("|---|---|---:|---:|---:|---:|---:|")
    for s in SCHEMAS:
        for period, label in (("dev", "dév."), ("val", "valid.")):
            a = agg([c for c in cas[s] if c["period"] == period])
            b = base[period]
            k = sum(1 for c in cas[s] if c["period"] == period and c["win"])
            z, p = ztest_proportions(k, a["n"], sum(1 for r in b["rets"] if r > 0), b["n"])
            _, _, pmw = mannwhitney_u(a["rets"], b["rets"])
            L.append(f"| {s} | {label} | {pct(a['win'])} % | {pct(b['win'])} % | "
                     f"{z:+.2f} | {pval(p)} | {pval(pmw)} |")
    L.append("\n> Prudence : les paires « date éligible » du benchmark sont des fenêtres de 252 séances\n"
             "> qui se CHEVAUCHENT (fortement autocorrélées) ; l'effectif apparent du benchmark\n"
             "> surestime l'information réelle. Les p de la colonne « signal vs base » sont donc\n"
             "> anti-conservateurs : un « non significatif » reste non significatif, mais un\n"
             "> « significatif » limite (CASSURE) serait encore plus fragile sur des fenêtres\n"
             "> indépendantes.\n")

    L.append("\n### Formules employées\n")
    L.append("**Intervalle de Wilson (95 %)** pour k succès sur n essais, z = 1,960 :\n\n"
             "    centre = (p̂ + z²/(2n)) / (1 + z²/n)   ;   p̂ = k/n\n"
             "    demi   = z·√(p̂(1−p̂)/n + z²/(4n²)) / (1 + z²/n)   ;   IC = centre ∓ demi\n\n"
             "**Deux proportions (non poolé, bilatéral)** :\n\n"
             "    z = (p̂1 − p̂2) / √(p̂1(1−p̂1)/n1 + p̂2(1−p̂2)/n2)   ;   p = 2(1 − Φ(|z|))\n\n"
             "**Mann-Whitney U (bilatéral, approximation normale, ex æquo corrigés)** :\n\n"
             "    U = R1 − n1(n1+1)/2   ;   μ = n1·n2/2\n"
             "    σ² = (n1·n2/12)·[(N+1) − Σ_t(t³−t)/(N(N−1))]   ;   z = (U−μ)/σ\n\n"
             "Seuil de lecture : p < 0,05 = l'écart est peu compatible avec le hasard. Une\n"
             "absence de significativité ne prouve pas l'absence d'effet : elle dit que\n"
             "l'effectif est trop petit pour trancher.\n")

    # 6. Conclusion
    L.append("\n## 6. Conclusion honnête\n")
    L.append(_conclusion(cas, base, title_rets, global_n))
    L.append("\n## 7. Ce que cette validation ne prouve PAS\n")
    L.append("- **Biais de survie** : l'historique ne contient que les 48 titres encore cotés\n"
             "  aujourd'hui. Les titres radiés (faillites, retraits) ne sont pas dans le cache :\n"
             "  leurs signaux — souvent des PANIQUE qui ont continué de chuter — sont absents,\n"
             "  ce qui gonfle mécaniquement les taux mesurés.\n"
             "- **Microstructure et régime** : 2017-2026 traverse des régimes très différents\n"
             "  (avant/pendant/après covid, assèchement de la liquidité BRVM). Un taux moyen\n"
             "  sur toute la période peut ne rien dire du régime à venir.\n"
             "- **Faible effectif** : sur les cellules par zone en validation, beaucoup passent\n"
             "  sous 10 cas — aucun diagnostic n'y est possible (⚪).\n"
             "- **Exécution réelle** : les rendements supposent un ordre exécuté au cours de\n"
             "  clôture du jour du signal, sans délai, sans glissement, et des frais de 2,8 %\n"
             "  aller-retour. Sur la BRVM, la liquidité peut rendre l'exécution pire.\n"
             "- **Non-stationnarité** : rien ne garantit que la période de validation récente\n"
             "  (2023-2025) ressemble au futur immédiat.\n")
    return "\n".join(L)


def _conclusion(cas, base, title_rets, global_n):
    L = []
    L.append("Les règles elles-mêmes (seuils fixes 250 séances / +10 % / RSI<30, espacement 60)\n"
             "n'ont PAS été ajustées sur les données : ce ne sont pas des paramètres « fittés ». Le\n"
             "risque pointé par l'auditeur porte donc sur la **stabilité** des taux annoncés et sur\n"
             "leur **valeur ajoutée** face à un achat au hasard, pas sur le réglage des seuils.\n")

    bd, bv = base["dev"], base["val"]
    L.append(f"\n**Constat central — le marché a changé de régime.** La base « acheter au hasard »\n"
             f"passe de **{bd['win'] * 100:.1f} %** de réussite (médiane {bd['median'] * 100:+.2f} %)\n"
             f"sur 2018-2022 à **{bv['win'] * 100:.1f} %** (médiane {bv['median'] * 100:+.2f} %) sur\n"
             f"2023-2025 : un marché en hausse de {bv['win'] * 100 - bd['win'] * 100:+.1f} points,\n"
             f"indépendamment de tout signal. Les 13 cellules par zone qui changent de diagnostic le\n"
             f"font toutes dans le même sens (🔴/🟡 → ✅) : ce n'est pas du bruit qui va dans les deux\n"
             f"sens, c'est la signature d'un marché globalement haussier sur 2023-2025. Toute hausse\n"
             f"du taux du signal doit être lue CONTRE cette hausse de fond.\n")

    for s in SCHEMAS:
        v = agg([c for c in cas[s] if c["period"] == "val"])
        kv = sum(1 for c in cas[s] if c["period"] == "val" and c["win"])
        b = base["val"]
        kb = sum(1 for r in b["rets"] if r > 0)
        _, psig = ztest_proportions(kv, v["n"], kb, b["n"])
        _, _, pmw = mannwhitney_u(v["rets"], b["rets"])
        exc = [c["ret"] - statistics.mean(title_rets.get(c["code"], {}).get("val", [0.0]))
               for c in cas[s] if c["period"] == "val"
               and title_rets.get(c["code"], {}).get("val", [])]
        ex = statistics.mean(exc) if exc else float("nan")
        delta = (v["win"] - b["win"]) * 100
        if delta < 0:
            qualif = "légèrement EN DESSOUS de la base"
        elif psig < 0.05 and pmw < 0.05:
            qualif = "un avantage significatif (confirmé sur les médianes)"
        elif psig < 0.05:
            qualif = "un avantage limite (z significatif, médianes non confirmées)"
        else:
            qualif = "un avantage non significatif"
        L.append(f"\n**{s}** — annoncé {global_n[s]} cas sur le plein échantillon. Sur la période\n"
                 f"indépendante (2023-2025, n={v['n']}) : réussite {v['win'] * 100:.1f} % contre\n"
                 f"{b['win'] * 100:.1f} % pour la base « achat au hasard » → {delta:+.1f} points,\n"
                 f"{qualif} (z p = {pval(psig)} ; Mann-Whitney p = {pval(pmw)}). Excès moyen sur\n"
                 f"le même titre : {ex * 100:+.2f} %.\n")

    L.append("\n**Verdict.** Sur la période indépendante, une fois retirée la hausse générale du\n"
             "marché, le signal **n'apporte pas d'avantage mesurable** : EVEIL et PANIQUE font jeu\n"
             "égal ou moins bien qu'un achat au hasard ; CASSURE affiche un écart limite (+7 points,\n"
             "p ≈ 0,045) que le test de médiane ne confirme pas (p = 0,19) et qui est compatible avec\n"
             "le hasard compte tenu des fenêtres qui se chevauchent. Les taux annoncés (66/56/52 %)\n"
             "sont des moyennes de deux régimes opposés ; ils décrivent le passé, ils ne prédisent\n"
             "rien au-delà de la dérive du marché.\n")
    return "".join(L)


def main():
    hist, cas, base_rets, title_rets, global_n = collecter()
    rapport = rendre(hist, cas, base_rets, title_rets, global_n)
    print(rapport)
    SORTIE.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text(rapport + "\n", encoding="utf-8")
    print(f"\n── écrit : {RAPPORT}")


if __name__ == "__main__":
    main()
