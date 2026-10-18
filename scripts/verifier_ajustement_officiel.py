"""Verification de l'ajustement par les divisions OFFICIELLES.

Trois controles independants :
  1. Le drawdown median doit redevenir plausible (marche BRVM peu volatil)
  2. Chaque titre ajuste doit etre coherent avec son cours actuel publie
  3. Confrontation heuristique vs officiel : l'heuristique en a-t-elle rate ?
"""
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.collecte import divisions_officielles as dv  # noqa: E402
from src.ajustement import detecter_divisions  # noqa: E402
from src.infrastructure.paths import HISTORY_BRUT  # noqa: E402  (B2-09)

with open(HISTORY_BRUT, "rb") as fh:
    hist = pickle.load(fh)

# Cours de cloture publies au 07/10/2026 (releves sur la page BRVM)
COURS_ACTUELS = {
    "ABJC": 3300, "BBGC": 9900, "BNBC": 1945, "BOAC": 11285, "NTLC": 15490,
    "PRSC": 4370, "CFAC": 1535, "SGBC": 18700, "STAC": 4640, "STBC": 3695,
    "CABC": 3600, "SDCC": 9800, "SIVC": 3300, "UNXC": 815, "SPHC": 1030,
    "NEIC": 850, "BOAB": 4900, "BOAN": 3600, "BOAS": 2650, "BOABF": 3600,
    "CBIBF": 4700, "ECOC": 1100, "SCRC": 2700, "BOAM": 2400, "PALC": 3950,
    "TTLC": 1950, "TTLS": 2950, "SIBC": 3000, "ONTBF": 2700, "FTSC": 1500,
    "SAFC": 850, "SMBC": 4200, "BICC": 5250, "SLBC": 37000, "SNTS": 32000,
}


def drawdown(barres):
    """Drawdown max et perf totale d'une serie de barres."""
    cl = [float(b.close) for b in barres if getattr(b, "close", None)]
    if len(cl) < 2 or not cl[0]:
        return 0.0, 0.0, 0.0
    pic, dd = cl[0], 0.0
    for c in cl:
        if c > pic:
            pic = c
        if pic:
            dd = min(dd, (c - pic) / pic)
    return dd * 100, (cl[-1] / cl[0] - 1) * 100, cl[-1]


print("=" * 88)
print("  1. EFFET DE L'AJUSTEMENT OFFICIEL SUR LES DRAWDOWNS")
print("=" * 88)

res = dv.ajuster_historique(hist)
hist2 = res["historique"]

print(f"\n  Titres ajustes : {res['nb_titres_ajustes']}")
print(f"  Sans division  : {len(res['sans_division'])}\n")
print(dv.resume(res["rapport"]))

def stats(h):
    dds, perfs = [], []
    for code, bs in h.items():
        dd, pf, _ = drawdown(bs)
        if dd:
            dds.append(dd)
            perfs.append(pf)
    return dds, perfs

dd1, pf1 = stats(hist)
dd2, pf2 = stats(hist2)

print("\n" + "-" * 88)
print(f"  {'Mesure':<34} {'AVANT':>16} {'APRES':>16}")
print("-" * 88)
print(f"  {'drawdown median':<34} {statistics.median(dd1):>15.2f} % {statistics.median(dd2):>15.2f} %")
print(f"  {'drawdown moyen':<34} {statistics.mean(dd1):>15.2f} % {statistics.mean(dd2):>15.2f} %")
print(f"  {'pire drawdown':<34} {min(dd1):>15.2f} % {min(dd2):>15.2f} %")
print(f"  {'perf mediane':<34} {statistics.median(pf1):>15.1f} % {statistics.median(pf2):>15.1f} %")
n1 = sum(1 for x in dd1 if x < -50)
n2 = sum(1 for x in dd2 if x < -50)
print(f"  {'titres a drawdown < -50 %':<34} {n1:>16} {n2:>16}")

print("\n" + "=" * 88)
print("  2. COHERENCE AVEC LES COURS ACTUELS PUBLIES (07/10/2026)")
print("=" * 88)
print(f"\n  {'Code':<8} {'dernier ajuste':>16} {'cours publie':>14} {'ecart':>10}")
print("  " + "-" * 54)
ecarts = []
for code, valeur_publiee in sorted(COURS_ACTUELS.items()):
    if code not in hist2 or not hist2[code]:
        continue
    dernier = float(hist2[code][-1].close)
    ecart = (dernier / valeur_publiee - 1) * 100
    ecarts.append(abs(ecart))
    if abs(ecart) > 5:
        print(f"  {code:<8} {dernier:>16,.0f} {valeur_publiee:>14,} {ecart:>9.1f} %")
print(f"\n  ecart median : {statistics.median(ecarts):.2f} %")
print(f"  titres a plus de 5 % d'ecart : {sum(1 for e in ecarts if e > 5)}/{len(ecarts)}")

print("\n" + "=" * 88)
print("  3. AUDIT : L'HEURISTIQUE A-T-ELLE RATE DES DIVISIONS ?")
print("=" * 88)
def dv_ecart(d1, d2):
    """Ecart en jours entre deux dates AAAA-MM-JJ (9999 si illisible)."""
    from datetime import date
    try:
        a = date(*[int(x) for x in d1[:10].split("-")])
        b = date(*[int(x) for x in d2[:10].split("-")])
        return (a - b).days
    except Exception:
        return 9999


officiel = dv.charger()
ratees, trouvees = [], []
for code, bs in hist.items():
    if not bs:
        continue
    dates = [str(getattr(b, "date", ""))[:10] for b in bs]
    closes = [float(getattr(b, "close", 0) or 0) for b in bs]
    det = detecter_divisions(closes, dates)
    off = dv.utiles(officiel.get(code, []), dates[0])
    for o in off:
        if any(abs(dv_ecart(o.date, d.date)) <= 10 for d in det):
            trouvees.append((code, o.date, o.ratio))
        else:
            ratees.append((code, o.date, o.ratio))

print(f"\n  Divisions officielles retrouvees par l'heuristique : {len(trouvees)}")
print(f"  Divisions officielles RATEES                        : {len(ratees)}")
if ratees:
    print("\n  Detail des rates (justifie la source officielle) :")
    for code, date, ratio in sorted(ratees)[:20]:
        print(f"    {code:8} {date}  ratio {ratio}")

print("\n" + "=" * 88)
