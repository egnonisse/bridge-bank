"""Diagnostic de FIABILITE des donnees par periode.

Question : la source contient-elle des erreurs (cours faux) independamment
des divisions ? Indice : une action BRVM ne peut pas multiplier sa valeur par
plus de 3 en un an, ni la diviser par plus de 3, sans evenement documente.

On mesure donc, pour chaque titre et chaque annee, le rapport entre la
mediane de l'annee et celle de l'annee precedente. Tout rapport extreme
(hors division connue) signale une donnee suspecte.

Sortie : la ou les periodes FIABLES, pour restreindre un backtest honnete.
"""
import pickle
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src import divisions_officielles as dv  # noqa: E402

def _j(d1, d2):
    """Ecart en jours entre deux dates AAAA-MM-JJ."""
    from datetime import date
    try:
        a = date(*[int(x) for x in d1[:10].split("-")])
        b = date(*[int(x) for x in d2[:10].split("-")])
        return (a - b).days
    except Exception:
        return 9999


# Operations detectees par les cours mais absentes du releve Richbourse
DIVISIONS_COMPLEMENTAIRES = {
    "PRSC": [{"date": "2019-09-17", "facteur": 64.0, "nouvelles": 64, "anciennes": 1}],
    "SLBC": [{"date": "2024-03-27", "facteur": 5.0, "nouvelles": 5, "anciennes": 1}],
}

with open(RACINE / "data" / "history_cache.pkl", "rb") as fh:
    hist = pickle.load(fh)

OPS = dv.charger()
# Injection des divisions complementaires
for code, liste in DIVISIONS_COMPLEMENTAIRES.items():
    existantes = OPS.setdefault(code, [])
    for d in liste:
        if not any(abs(_j(o.date, d["date"])) < 30 for o in existantes):
            existantes.append(dv.Operation(
                code=code, date=d["date"], facteur=d["facteur"],
                nouvelles=d["nouvelles"], anciennes=d["anciennes"]))
    existantes.sort(key=lambda x: x.date)


# Ajustement avec les operations completes
ajuste = {}
for code, bs in hist.items():
    if not bs:
        continue
    ops = OPS.get(code.upper(), [])
    debut = str(getattr(bs[0], "date", ""))[:10]
    ajuste[code] = dv.ajuster_barres(bs, dv.utiles(ops, debut))

# Profil annuel (mediane) par titre
profil = {}
for code, bs in ajuste.items():
    par_an = defaultdict(list)
    for b in bs:
        c = getattr(b, "close", None)
        if c:
            par_an[str(b.date)[:4]].append(float(c))
    profil[code] = {a: statistics.median(v) for a, v in par_an.items() if len(v) >= 5}

ANNEES = [str(a) for a in range(2017, 2027)]

print("=" * 96)
print("  FIABILITE PAR ANNEE — nombre de titres avec un saut annuel ABSURDE (> x3 ou < /3)")
print("=" * 96)
print(f"\n  {'Annee':<8} {'titres':>8} {'sauts absurdes':>16} {'taux':>8}")
print("  " + "-" * 44)
fiabilite = {}
for i, an in enumerate(ANNEES[1:], 1):
    prec = ANNEES[i - 1]
    n = 0
    absurdes = 0
    for code, p in profil.items():
        if an in p and prec in p and p[prec] > 0:
            n += 1
            r = p[an] / p[prec]
            if r > 3 or r < 1 / 3:
                absurdes += 1
    taux = (absurdes / n * 100) if n else 0
    fiabilite[an] = taux
    print(f"  {an:<8} {n:>8} {absurdes:>16} {taux:>7.1f}%")

print("\n  Lecture : un taux eleve signifie que beaucoup de titres changent")
print("  de niveau de plus d'un facteur 3 d'une annee sur l'autre, sans")
print("  division documentee -> donnees suspectes pour cette transition.\n")

# Detail des pires cas
print("=" * 96)
print("  DETAIL DES SAUTS ANNUEUX EXTREMES (hors operations connues)")
print("=" * 96)
cas = []
for code, p in profil.items():
    for i, an in enumerate(ANNEES[1:], 1):
        prec = ANNEES[i - 1]
        if an in p and prec in p and p[prec] > 0:
            r = p[an] / p[prec]
            if r > 3 or r < 1 / 3:
                cas.append((code, prec, an, r, p[prec], p[an]))
for code, a1, a2, r, v1, v2 in sorted(cas, key=lambda x: -max(x[3], 1 / x[3]))[:30]:
    print(f"  {code:<8} {a1}->{a2}  x{r:>7.2f}   {v1:>11,.0f} -> {v2:>11,.0f}")

print(f"\n  Total de sauts annuels extremes : {len(cas)}")
print("=" * 96)
