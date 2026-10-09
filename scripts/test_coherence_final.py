"""TEST DE COHERENCE — le juge final.

Le dernier cours de l'historique doit correspondre au cours reel publie
(07/10/2026, releve sur les fiches BRVM). C'est la seule preuve que
l'ajustement est juste : un ecart signale une operation oubliee ou mal
interpretee.

Tolerance : 8 % (l'historique s'arrete au 30/09/2026, une semaine d'ecart).
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

reels = dv.cours_reels()
res = dv.ajuster_historique(hist)
hist2 = res["historique"]
TOL = 8.0


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


print("=" * 92)
print("  TEST 1 — COHERENCE DU DERNIER COURS AVEC LE COURS REEL PUBLIE")
print("=" * 92)
print(f"\n  {'Code':<8} {'hist. brut':>12} {'hist. ajuste':>13} {'reel':>10} {'ecart brut':>11} {'ecart ajuste':>13}")
print("  " + "-" * 72)

ok_brut = ok_ajuste = total = 0
lignes_ko = []
for code in sorted(reels):
    if code not in hist or not hist[code] or code not in hist2:
        continue
    total += 1
    reel = reels[code]
    dernier_brut = float(hist[code][-1].close)
    dernier_aj = float(hist2[code][-1].close)
    e_brut = (dernier_brut / reel - 1) * 100
    e_aj = (dernier_aj / reel - 1) * 100
    if abs(e_brut) <= TOL:
        ok_brut += 1
    if abs(e_aj) <= TOL:
        ok_ajuste += 1
    else:
        lignes_ko.append((code, dernier_brut, dernier_aj, reel, e_brut, e_aj))

for code, db, da, r, eb, ea in sorted(lignes_ko, key=lambda x: -abs(x[5])):
    print(f"  {code:<8} {db:>12,.0f} {da:>13,.0f} {r:>10,} {eb:>10.1f}% {ea:>12.1f}%")

print(f"\n  Titres coherents AVANT ajustement : {ok_brut}/{total}")
print(f"  Titres coherents APRES ajustement : {ok_ajuste}/{total}")

print("\n" + "=" * 92)
print("  TEST 2 — DRAWDOWNS APRES AJUSTEMENT")
print("=" * 92)
dds = [dd(bs) for bs in hist2.values() if len(bs) > 20]
dds_b = [dd(bs) for bs in hist.values() if len(bs) > 20]
print(f"\n  {'Mesure':<32} {'AVANT':>14} {'APRES':>14}")
print("  " + "-" * 62)
print(f"  {'drawdown median':<32} {statistics.median(dds_b):>13.2f} % {statistics.median(dds):>13.2f} %")
print(f"  {'drawdown moyen':<32} {statistics.mean(dds_b):>13.2f} % {statistics.mean(dds):>13.2f} %")
print(f"  {'pire drawdown':<32} {min(dds_b):>13.2f} % {min(dds):>13.2f} %")
print(f"  {'titres < -50 %':<32} {sum(1 for x in dds_b if x < -50):>14} {sum(1 for x in dds if x < -50):>14}")

# Titres restant problematiques
print(f"\n  Titres encore sous -70 % de drawdown :")
restants = sorted(((c, dd(b)) for c, b in hist2.items() if len(b) > 20 and dd(b) < -70),
                  key=lambda x: x[1])
for c, d in restants[:15]:
    b = hist2[c]
    print(f"    {c:<8} {d:>7.1f} %   {float(b[0].close):>10,.0f} -> {float(b[-1].close):>10,.0f}")

print("\n" + "=" * 92)
print("  TEST 3 — OPERATIONS APPLIQUEES")
print("=" * 92)
print(f"\n  {res['nb_titres_ajustes']} titres ajustes, {len(res['sans_division'])} sans operation\n")
print(dv.resume(res["rapport"]))
print("\n" + "=" * 92)
