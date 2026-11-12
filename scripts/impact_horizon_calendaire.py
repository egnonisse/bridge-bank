"""IMPACT DE LA DEFINITION D'HORIZON sur les taux de la veille speculative.

PROBLEME MESURE (audit du 12/11/2026, rejeu du script de l'auditeur externe) :
les taux publies mesurent le rendement a 252 SEANCES apres le signal. Or le cache local
manque 48 seances sur 1723 (2,8 %) par rapport a l'API independante : la 252e seance tombe
donc quelques JOURS plus tard en calendrier. Sur ORGT au 13/09/2024 l'ecart atteint
20,9 points de rendement (+57,6 % contre +36,8 %) pour 4 jours de decalage.

CE SCRIPT compare deux definitions sur LES MEMES cas :
  A. HORIZON_SEANCES    : les 252 seances qui suivent le signal (definition actuelle)
  B. HORIZON_CALENDAIRE : toutes les seances jusqu'a 365 jours calendaires apres le signal
                          (derniere seance <= date + 365 j)

Pour chaque cas et chaque definition : rendement net, pic, creux, stop -15 % touche,
et les trois paliers +20/+35/+50 % atteints AVANT le stop (hypothese pessimiste : si le
stop et un palier tombent la meme seance, le stop est cense passer d'abord).

Sortie : comparaison par schema et par zone, statistiques de l'ecart (test apparie),
et distribution du nombre reel de seances dans 365 jours calendaires.
"""
import csv
import datetime
import json
import statistics
import sys
from pathlib import Path

ROOT = Path("C:/Users/LEO/projects/Bridge Bank")
sys.path.insert(0, str(ROOT))
from src.collecte.preparation import charger_historique_propre  # noqa: E402

FRAIS = 0.028          # aller-retour 1,4 % + 1,4 %
STOP = -0.15
PALIERS = (0.20, 0.35, 0.50)
EXPORT = ROOT / "audit" / "spec_export"
SORTIE_MD = EXPORT / "HORIZON-CALENDAIRE.md"

hist = charger_historique_propre()
# Les dates sont normalisees en chaine ISO : selon la source, b.date peut etre un
# datetime.date, un pandas.Timestamp ou une chaine — comparer des types differents avec
# les dates du CSV (chaines) faisait echouer TOUS les appariements.
series = {code: [(str(b.date)[:10], float(b.close)) for b in bars] for code, bars in hist.items()}
index = {code: {d: k for k, (d, _) in enumerate(v)} for code, v in series.items()}


def vers_date(s):
    return datetime.date.fromisoformat(s)


def mesurer(seq, p_signal):
    """Retourne (rendement_net, pic, creux, stop_atteint, paliers_avant_stop, n).

    `seq` = liste de (date, cours) STRICTEMENT posterieure au signal.
    Hypothese pessimiste : sur une seance qui touche a la fois le stop et un palier,
    le stop est repute passer en premier (on ne peut pas connaitre l'ordre intra-seance).
    """
    if not seq:
        return None
    pic = creux = None
    stop_j = None
    paliers_j = {}
    for k, (d, c) in enumerate(seq):
        r = c / p_signal - 1
        pic = r if pic is None else max(pic, r)
        creux = r if creux is None else min(creux, r)
        if stop_j is None and r <= STOP:
            stop_j = k
        for p in PALIERS:
            if p not in paliers_j and r >= p:
                paliers_j[p] = k
    r_final = seq[-1][1] / p_signal - 1 - FRAIS
    avant = {}
    for p in PALIERS:
        k = paliers_j.get(p)
        avant[p] = (k is not None) and (stop_j is None or k < stop_j)
    return {"ret": r_final, "pic": pic, "creux": creux,
            "stop": stop_j is not None, "avant": avant, "n": len(seq)}


resultats = []
manquants = 0
for schema in ("CASSURE", "EVEIL", "PANIQUE"):
    with (EXPORT / f"cas_{schema}.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row["code"]
            d_sig = row["date_signal"]
            if code not in index or d_sig not in index[code]:
                manquants += 1
                continue
            i = index[code][d_sig]
            p = float(row["cours_signal"])
            serie = series[code]
            # A. 252 seances
            seq_seances = serie[i + 1:i + 253]
            # B. 365 jours calendaires
            d0 = vers_date(d_sig)
            limite = (d0 + datetime.timedelta(days=365)).isoformat()
            seq_cal = [x for x in serie[i + 1:] if x[0] <= limite]
            a = mesurer(seq_seances, p)
            b = mesurer(seq_cal, p)
            if a is None or b is None:
                manquants += 1
                continue
            resultats.append({"schema": schema, "code": code, "date": d_sig,
                              "zone": float(row["zone_minmax"]), "seances": a, "cal": b,
                              "n_cal": b["n"], "n_252": a["n"]})


def agg(sous, cle):
    if not sous:
        return None
    rets = [r[cle]["ret"] for r in sous]
    return {
        "n": len(sous),
        "moy": statistics.mean(rets),
        "med": statistics.median(rets),
        "win": sum(1 for x in rets if x > 0) / len(rets),
        "p20": sum(1 for r in sous if r[cle]["avant"][0.20]) / len(sous),
        "p50": sum(1 for r in sous if r[cle]["avant"][0.50]) / len(sous),
        "stop": sum(1 for r in sous if r[cle]["stop"]) / len(sous),
    }


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    m = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - m) / d, (c + m) / d)


lignes = []
lignes.append("# Impact de la définition d'horizon sur les taux de la veille spéculative\n")
lignes.append(f"Cas analysés : **{len(resultats)}** · non appariables : {manquants}\n")
lignes.append("Deux définitions, mêmes cas : **A** = 252 séances après le signal (définition "
              "publiée jusqu'ici) · **B** = toutes les séances jusqu'à **365 jours calendaires** "
              "après le signal.\n")

lignes.append("\n## 1. Combien de séances tient réellement une année calendaire ?\n")
ns = [r["n_cal"] for r in resultats]
lignes.append(f"- médiane **{statistics.median(ns):.0f}** séances · min {min(ns)} · max {max(ns)}")
lignes.append(f"- cas où la fenêtre calendaire contient MOINS de 252 séances : "
              f"**{sum(1 for x in ns if x < 252)}** ({sum(1 for x in ns if x < 252)/len(ns)*100:.1f} %)")
lignes.append(f"- cas où elle en contient PLUS : **{sum(1 for x in ns if x > 252)}** "
              f"({sum(1 for x in ns if x > 252)/len(ns)*100:.1f} %)")

lignes.append("\n## 2. Taux par schéma — les deux définitions\n")
lignes.append("| Schéma | n | Médiane A (252 séances) | Médiane B (365 j) | Écart | "
              "Réussite A | Réussite B | +20 % avant stop A → B | Stop touché A → B |")
lignes.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for s in ("CASSURE", "EVEIL", "PANIQUE"):
    sous = [r for r in resultats if r["schema"] == s]
    a, b = agg(sous, "seances"), agg(sous, "cal")
    lignes.append(f"| **{s}** | {a['n']} | {a['med']*100:+.1f} % | {b['med']*100:+.1f} % | "
                  f"{(b['med']-a['med'])*100:+.1f} pt | {a['win']*100:.1f} % | {b['win']*100:.1f} % | "
                  f"{a['p20']*100:.0f} % → {b['p20']*100:.0f} % | {a['stop']*100:.0f} % → {b['stop']*100:.0f} % |")

lignes.append("\n## 3. Écart apparié cas par cas\n")
lignes.append("| Schéma | n | Écart moyen de rendement | Écart médian | Cas où B > A | Cas où B < A | Écart > 5 pts |")
lignes.append("|---|---:|---:|---:|---:|---:|---:|")
for s in ("CASSURE", "EVEIL", "PANIQUE"):
    sous = [r for r in resultats if r["schema"] == s]
    ecarts = [r["cal"]["ret"] - r["seances"]["ret"] for r in sous]
    lignes.append(f"| {s} | {len(sous)} | {statistics.mean(ecarts)*100:+.2f} pt | "
                  f"{statistics.median(ecarts)*100:+.2f} pt | {sum(1 for e in ecarts if e > 0)} | "
                  f"{sum(1 for e in ecarts if e < 0)} | {sum(1 for e in ecarts if abs(e) > 0.05)} |")

lignes.append("\n## 4. Le verdict change-t-il ?\n")
lignes.append("| Schéma | Verdict avec A | Verdict avec B | Stable ? |")
lignes.append("|---|---|---|---|")
for s in ("CASSURE", "EVEIL", "PANIQUE"):
    sous = [r for r in resultats if r["schema"] == s]
    a, b = agg(sous, "seances"), agg(sous, "cal")

    def verdict(x):
        if x["med"] > 0 and x["win"] >= 0.55:
            return "favorable"
        if x["med"] > 0:
            return "neutre"
        return "défavorable"
    va, vb = verdict(a), verdict(b)
    lignes.append(f"| {s} | {va} ({a['med']*100:+.1f} %) | {vb} ({b['med']*100:+.1f} %) | "
                  f"{'OUI' if va == vb else '**NON**'} |")

lignes.append("\n## 5. Par zone (définition B)\n")
lignes.append("| Schéma | Zone | n | Médiane B | Réussite B | IC 95 % (Wilson) | +20 % avant stop |")
lignes.append("|---|---|---:|---:|---:|---|---:|")
for s in ("CASSURE", "EVEIL", "PANIQUE"):
    for lo, hi, lbl in ((0, .2, "0-20"), (.2, .4, "20-40"), (.4, .6, "40-60"),
                        (.6, .8, "60-80"), (.8, 1.01, "80-100")):
        sous = [r for r in resultats if r["schema"] == s and lo <= r["zone"] < hi]
        if not sous:
            continue
        b = agg(sous, "cal")
        k = sum(1 for r in sous if r["cal"]["ret"] > 0)
        bas, haut = wilson(k, len(sous))
        lignes.append(f"| {s} | {lbl} | {b['n']} | {b['med']*100:+.1f} % | {b['win']*100:.1f} % | "
                      f"[{bas*100:.1f} ; {haut*100:.1f}] | {b['p20']*100:.0f} % |")

lignes.append("\n## 6. Ce que ce recalcul ne change pas\n")
lignes.append("- Les **cas** eux-mêmes (1 615) et leur date de signal : inchangés.")
lignes.append("- Les **cours** d'entrée : inchangés, concordants à 99,3 % avec l'API indépendante.")
lignes.append("- Le **stop** (−15 %) et les **paliers** (+20/+35/+50 %) : inchangés.")
lignes.append("- Le **manque de 48 séances** dans le cache : ce recalcul le rend inoffensif "
              "sur la date de fin, mais il peut encore décaler le RSI et les fenêtres de "
              "création du signal — ce point reste ouvert.")

SORTIE_MD.write_text("\n".join(lignes), encoding="utf-8")

# --- sortie console ---
print("\n".join(lignes[:14]))
print("\n=== TAUX PAR SCHEMA ===")
for s in ("CASSURE", "EVEIL", "PANIQUE"):
    sous = [r for r in resultats if r["schema"] == s]
    a, b = agg(sous, "seances"), agg(sous, "cal")
    print(f"{s:8} n={a['n']:>4} | mediane A {a['med']*100:+6.1f}% -> B {b['med']*100:+6.1f}% "
          f"| reussite {a['win']*100:.1f}% -> {b['win']*100:.1f}% "
          f"| +20 avant stop {a['p20']*100:.0f}% -> {b['p20']*100:.0f}% "
          f"| stop {a['stop']*100:.0f}% -> {b['stop']*100:.0f}%")
print(f"\nrapport ecrit : {SORTIE_MD}")
