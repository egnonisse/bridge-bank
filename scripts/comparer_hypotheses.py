"""Comparaison de trois hypotheses d'ajustement — la donnee tranche.

A. AUCUN ajustement (reference brute)
B. DIVISIONS PURES : seulement « N nouvelles pour 1 ancienne » (N > 1)
C. TOUTES les operations, y compris les « N pour M » (M > 1)

Critere de decision : une bonne reference doit produire des drawdowns
PLAUSIBLES pour la BRVM. La BRVM est un marche peu volatil et peu profond :
un drawdown median de -78 % sur 47 titres est impossible (cela signifierait
que la moitie des societes cotees ont perdu 4/5 de leur valeur).
Le vrai ordre de grandeur attendu est -30 % a -55 %.
"""
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.collecte import divisions_officielles as dv  # noqa: E402
from src.infrastructure.paths import HISTORY_BRUT  # noqa: E402  (B2-09)
from dataclasses import replace  # noqa: E402

with open(HISTORY_BRUT, "rb") as fh:
    hist = pickle.load(fh)

TOUTES = dv.charger()


def pures(ops):
    """Ne garde que les divisions veritables : N nouvelles pour 1 ancienne."""
    return [o for o in ops if o.anciennes == 1 and o.facteur > 1]


def pures_et_regroupements_nets(ops):
    """Divisions + regroupements ou TOUTES les anciennes deviennent 1 action."""
    return [o for o in ops if (o.anciennes == 1 and o.facteur > 1)
            or (o.nouvelles == 1 and o.anciennes > 1)]


def ajuster(hist, filtre):
    out = {}
    rapp = []
    for code, barres in hist.items():
        if not barres:
            out[code] = barres
            continue
        ops = filtre(TOUTES.get(str(code).upper(), []))
        debut = str(getattr(barres[0], "date", ""))[:10]
        actives = dv.utiles(ops, debut)
        copie = dv.ajuster_barres(barres, actives)
        out[code] = copie
        if actives:
            c = 1.0
            for o in actives:
                c *= o.facteur
            rapp.append((code, len(actives), c))
    return out, rapp


def dd(bs):
    cl = [float(b.close) for b in bs if getattr(b, "close", None)]
    if len(cl) < 2 or not cl[0]:
        return 0.0
    pic, m = cl[0], 0.0
    for c in cl:
        if c > pic:
            pic = c
        if pic:
            m = min(m, (c - pic) / pic)
    return m * 100


def bilan(nom, h):
    dds = [dd(b) for b in h.values() if len(b) > 20]
    return {
        "nom": nom,
        "median": statistics.median(dds),
        "moyen": statistics.mean(dds),
        "pire": min(dds),
        "sous_50": sum(1 for x in dds if x < -50),
        "sous_70": sum(1 for x in dds if x < -70),
    }


A = {c: b for c, b in hist.items()}
B, rapB = ajuster(hist, pures)
C, rapC = ajuster(hist, pures_et_regroupements_nets)

print("=" * 84)
print("  COMPARAISON DES HYPOTHESES — LE DRAWDOWN DEPARTAGE")
print("=" * 84)
print(f"\n  {'Hypothese':<44} {'median':>9} {'moyen':>9} {'< -50':>7} {'< -70':>7}")
print("  " + "-" * 78)
for nom, h in [("A. aucun ajustement (brut)", A),
               ("B. divisions pures (N pour 1)", B),
               ("C. divisions + regroupements nets", C)]:
    r = bilan(nom, h)
    print(f"  {r['nom']:<44} {r['median']:>8.1f}% {r['moyen']:>8.1f}% {r['sous_50']:>7} {r['sous_70']:>7}")

print("\n  Attendu sur la BRVM (marche peu volatil) : median entre -30 % et -55 %\n")

print("=" * 84)
print("  COHERENCE AVEC LES COURS REELS (07/10/2026) — CONTROLE CROISE")
print("=" * 84)
reels = dv.cours_reels()
print(f"\n  {'Hypothese':<44} {'coherents (±8%)':>18}")
print("  " + "-" * 78)
for nom, h in [("A. brut", A), ("B. divisions pures", B), ("C. divisions+regroupements", C)]:
    ok = tot = 0
    for code, reel in reels.items():
        if code not in h or not h[code]:
            continue
        tot += 1
        dernier = float(h[code][-1].close)
        if abs(dernier / reel - 1) * 100 <= 8:
            ok += 1
    print(f"  {nom:<44} {ok:>10}/{tot}")

print("\n" + "=" * 84)
print("  DETECTION DES TITRES ENCORE ABERRANTS (hypothese B)")
print("=" * 84)
restants = sorted(((c, dd(b), float(b[0].close), float(b[-1].close))
                   for c, b in B.items() if len(b) > 20 and dd(b) < -70),
                  key=lambda x: x[1])
print(f"\n  {len(restants)} titres sous -70 % :")
for c, d, pre, der in restants[:15]:
    print(f"    {c:<8} {d:>7.1f} %   {pre:>12,.0f} -> {der:>10,.0f}")

print("\n" + "=" * 84)
print("  OPERATIONS RETENUES EN HYPOTHESE B")
print("=" * 84)
for code, n, cum in sorted(rapB):
    print(f"  {code:<8} {n} division(s)   facteur cumule {cum:g}")

print("\n" + "=" * 84)
