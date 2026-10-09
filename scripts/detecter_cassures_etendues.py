"""Detection de TOUTES les cassures de niveau, y compris progressives.

Le detecteur du projet (cache_integrity) cherche un saut BRUTAL sur une
seance. Or certaines cassures se font sur plusieurs seances (ou plusieurs
semaines) et passent inapercues.

Methode : comparer la MEDIANE MOBILE sur 30 seances avant et apres chaque
point. Une cassure = le niveau d'apres est nettement plus bas que celui
d'avant, et le nouveau niveau est PERMANENT (il tient sur les 30 seances
suivantes).

Sortie : liste des cassures par titre, croisee avec les operations officielles.
"""
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src import divisions_officielles as dv  # noqa: E402

with open(RACINE / "data" / "history_cache.pkl", "rb") as fh:
    hist = pickle.load(fh)
OFFICIEL = dv.charger()

FENETRE = 30
SEUIL = 2.0


def _jours(d1, d2):
    """Ecart en jours entre deux dates AAAA-MM-JJ."""
    from datetime import date
    try:
        a = date(*[int(x) for x in d1[:10].split("-")])
        b = date(*[int(x) for x in d2[:10].split("-")])
        return (a - b).days
    except Exception:
        return 9999


def cassures(barres, fenetre=FENETRE, seuil=SEUIL):
    """Repere les cassures de niveau permanentes."""
    cl = [float(b.close) for b in barres if getattr(b, "close", None)]
    dt = [str(b.date)[:10] for b in barres]
    out = []
    i = fenetre
    while i < len(cl) - fenetre:
        avant = statistics.median(cl[max(0, i - fenetre):i])
        apres = statistics.median(cl[i:i + fenetre])
        if avant > 0 and apres > 0:
            r = avant / apres
            if r >= seuil:
                # Verifier la PERMANENCE : le niveau bas doit tenir
                suite = statistics.median(cl[i:min(len(cl), i + fenetre * 2)])
                if suite > 0 and apres / suite < 1.4:
                    out.append({"date": dt[i], "avant": avant, "apres": apres,
                                "ratio": r, "index": i})
                    i += fenetre  # sauter la fenetre pour eviter les doublons
                    continue
        i += 1
    return out


print("=" * 90)
print("  CASSURES DE NIVEAU PERMANENTES (mediane mobile 30 seances, ratio >= 2)")
print("=" * 90)

total_cassures = 0
casse_avec_op = 0
casse_sans_op = 0
detail_sans = []

for code in sorted(hist):
    bs = hist[code]
    if len(bs) < 200:
        continue
    cs = cassures(bs)
    if not cs:
        continue
    ops = OFFICIEL.get(code.upper(), [])
    print(f"\n  {code}  ({len(cs)} cassure(s) — {len(ops)} operation(s) officielle(s))")
    for c in cs:
        total_cassures += 1
        # Y a-t-il une operation officielle proche (+- 60 jours) ?
        proche = [o for o in ops if abs(_jours(o.date, c["date"])) <= 60]
        if proche:
            casse_avec_op += 1
            tag = f"OK  operation officielle {proche[0].date} ({proche[0].sens})"
        else:
            casse_sans_op += 1
            tag = "!!! AUCUNE OPERATION OFFICIELLE"
            detail_sans.append((code, c["date"], c["ratio"], c["avant"], c["apres"]))
        print(f"    {c['date']}  {c['avant']:>11,.0f} -> {c['apres']:>11,.0f}  "
              f"(x{c['ratio']:>6.2f})  {tag}")

print("\n" + "=" * 90)
print("  BILAN")
print("=" * 90)
print(f"\n  Cassures detectees                    : {total_cassures}")
print(f"  Expliquees par une operation officielle: {casse_avec_op}")
print(f"  NON expliquees                        : {casse_sans_op}")
print("\n  --- cassures inexpliquees (ratio cumule a corriger) ---")
for code, date, ratio, av, ap in sorted(detail_sans, key=lambda x: -x[2])[:25]:
    print(f"    {code:<8} {date}  x{ratio:>6.2f}   {av:>11,.0f} -> {ap:>11,.0f}")
print("\n" + "=" * 90)
