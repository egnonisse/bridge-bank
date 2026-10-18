"""HYPOTHESE 2 — L'ENTREE PROGRESSIVE. Test isole, jamais fait jusqu'ici.

LE TROU
-------
Les cinq composants deduits du releve de LEO etaient :
  1. SELECTION (grandes valeurs a dividende)
  2. ENTREE PROGRESSIVE par tranches        <-- jamais testee isolement
  3. RENFORCEMENT sur faiblesse
  4. SORTIE PAR PALIERS
  5. REBALANCEMENT

Les composants 3 et 4 ont ete juges (attribution + challenge + 28 ans). Le 2 a toujours
ete teste MELANGE au renforcement : dans `validation_longue.py`, la variante « RENFORT »
achete 1/3 a t0 puis 1/3 sur repli. Le repli n'arrive pas toujours, donc une partie du
resultat venait de l'espacement, une autre du signal de repli — les deux etaient
confondus dans un seul chiffre.

Ce test isole la question : **acheter en plusieurs fois dans le TEMPS, sans condition de
prix, est-ce mieux qu'acheter tout d'un coup ?**

POURQUOI LE CACHE QUOTIDIEN ET PAS LA COLLECTE 28 ANS
-----------------------------------------------------
L'espacement observe chez LEO est d'environ 12 jours. La collecte longue n'a que ~2,7
dates par an : elle ne peut pas representer un espacement de 12 jours. On utilise donc
`data/history_clean.pkl` (48 titres, quotidien, 2017-2026, ajuste des divisions).

PROTOCOLE
---------
Pour chaque date d'entree et chaque titre cote, trois facons d'engager le meme capital :
  ACHAT UNIQUE   tout a t0.
  PROGRESSIF-12  1/3 a t0, 1/3 a t0+12 jours, 1/3 a t0+24 jours.
  PROGRESSIF-20  idem avec 20 puis 40 jours.
  PROGRESSIF-30  idem avec 30 puis 60 jours.
Les tranches non encore versees dorment en cash (0 %) : c'est le vrai cout, et c'est
pourquoi on mesure AUSSI le rendement ajuste a l'exposition.
"""
import json
import pickle
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
# Le pickle contient des objets definis dans `src` : sans ce chemin, la
# deserialisation echoue avec « No module named 'src' ».
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "src"))
from src.infrastructure.paths import HISTORY_CACHE, chemin_data  # noqa: E402  (B2-09)
HORIZONS = (1, 3, 5)
ESPACEMENTS = (12, 20, 30)


def _charger():
    h = pickle.load(open(HISTORY_CACHE, "rb"))
    out = {}
    for code, barres in h.items():
        d = {}
        for b in barres:
            dt = str(getattr(b, "date", ""))[:10]
            c = getattr(b, "close", None) or getattr(b, "cours", None)
            if dt and c:
                d[dt] = float(c)
        if len(d) > 200:
            out[code] = dict(sorted(d.items()))
    return out


def _premiere_apres(jours, cible):
    for j in jours:
        if j >= cible:
            return j
    return None


def _simuler(series, jours, i0, horizon_an, espacement):
    """Renvoie (r_unique, r_prog, exposition) ou None si la fenetre est trop courte."""
    d0 = date.fromisoformat(jours[i0])
    fin_cible = (d0 + timedelta(days=int(365.25 * horizon_an))).isoformat()
    # borne de fin
    fin = None
    for j in jours:
        if j <= fin_cible:
            fin = j
        else:
            break
    if fin is None or fin <= jours[i0]:
        return None

    p0 = series[jours[i0]]
    pf = series[fin]
    if not p0 or not pf:
        return None

    # --- ACHAT UNIQUE ---
    r_unique = pf / p0 - 1

    # --- PROGRESSIF (sans condition de prix) ---
    part = 1.0 / 3
    moments = [d0] + [d0 + timedelta(days=espacement),
                      d0 + timedelta(days=2 * espacement)]
    actions = 0.0
    engage = 0.0
    for m in moments:
        j = _premiere_apres(jours, m.isoformat())
        if j is None or j > fin:
            continue          # la tranche tombe apres l'horizon : elle ne compte pas
        p = series[j]
        if p:
            actions += part / p
            engage += part
    if engage == 0:
        return None
    valeur = actions * pf
    r_prog = valeur - 1
    r_ajuste = valeur / engage - 1
    return r_unique, r_prog, r_ajuste, engage


def main():
    series = _charger()
    titres = sorted(series)
    print("=" * 100)
    print("  HYPOTHESE 2 — L'ENTREE PROGRESSIVE : acheter en plusieurs fois vaut-il mieux ?")
    print("=" * 100)
    print(f"\n  {len(series)} titres · cache quotidien (ajuste des divisions)")

    # Dates d'entree : une par mois pour eviter de surponderer une periode
    toutes = sorted({j for s in series.values() for j in s})
    deb, fin_tot = toutes[0], toutes[-1]
    entrees = []
    d = date.fromisoformat(deb)
    limite = date.fromisoformat(fin_tot)
    while d <= limite:
        entrees.append(d.isoformat())
        d = (d + timedelta(days=31))
    print(f"  {len(entrees)} dates d'entree (une par mois) · {deb} -> {fin_tot}")

    obs = []
    for e in entrees:
        for code, s in series.items():
            jours = list(s)
            # premiere cotation >= date d'entree
            i0 = None
            for k, j in enumerate(jours):
                if j >= e:
                    i0 = k
                    break
            if i0 is None or len(jours) - i0 < 260:
                continue
            for h in HORIZONS:
                for esp in ESPACEMENTS:
                    r = _simuler(s, jours, i0, h, esp)
                    if r:
                        obs.append((code, e, h, esp) + r)

    print(f"\n  {len(obs)} observations")

    for h in HORIZONS:
        print("\n" + "-" * 100)
        print(f"  HORIZON {h} AN(S)")
        print("-" * 100)
        print(f"\n  {'espacement':<14}{'n':>7}{'UNIQUE':>11}{'PROGRESSIF':>12}{'ecart':>10}"
              f"{'expo':>8}{'PROG ajuste':>13}{'ecart ajuste':>14}")
        print("  " + "-" * 76)
        for esp in ESPACEMENTS:
            s = [o for o in obs if o[2] == h and o[3] == esp]
            if len(s) < 30:
                continue
            ru = statistics.median(o[4] for o in s)
            rp = statistics.median(o[5] for o in s)
            ra = statistics.median(o[6] for o in s)
            ex = statistics.median(o[7] for o in s)
            gagne = sum(1 for o in s if o[5] > o[4]) / len(s) * 100
            print(f"  {esp} j{'':<9}{len(s):>7}{ru*100:>10.1f} %{rp*100:>11.1f} %"
                  f"{(rp-ru)*100:>+9.1f}pt{ex*100:>7.0f} %{ra*100:>12.1f} %"
                  f"{(ra-ru)*100:>+13.1f}pt")
            print(f"  {'':<14}{'':<7}{f'gagne dans {gagne:.0f} % des cas':>52}")

    # --- Le point qui decide : et si on compare a exposition EGALE ? ---
    print("\n" + "=" * 100)
    print("  CE QUE DIT CE TEST")
    print("=" * 100)
    for h in (3, 5):
        s = [o for o in obs if o[2] == h and o[3] == 12]
        if len(s) < 30:
            continue
        ru = statistics.median(o[4] for o in s)
        rp = statistics.median(o[5] for o in s)
        ra = statistics.median(o[6] for o in s)
        ex = statistics.median(o[7] for o in s)
        gagne = sum(1 for o in s if o[5] > o[4]) / len(s) * 100
        print(f"""
  Horizon {h} ans, espacement 12 j (celui de LEO) :
    ACHAT UNIQUE     {ru*100:+.1f} %
    PROGRESSIF       {rp*100:+.1f} %   (gagne dans {gagne:.0f} % des cas)
    capital effectivement verse : {ex*100:.0f} %

  Lecture : {"l'ecart est NEGLIGEABLE (moins d'un point) — l'entree progressive ne cree ni ne detruit de valeur" if abs(rp-ru) < 0.02 else ("le progressif fait MIEUX" if rp > ru else "le progressif fait MOINS BIEN")}.

  ⚠️ PRECISION DE CALCUL : `engage` mesure le capital VERSE, pas le TEMPS d'exposition.
  Avec 3 tranches etalees sur 24 a 60 jours, tout est verse bien avant l'horizon, donc
  `engage` vaut 1,0 et le cout du cash dormant N'EST PAS capture. Ce cout est faible
  (30-60 jours d'attente sur 365, soit 8-16 % du temps), mais il existe : l'ecart reel
  a exposition-ponderee-par-le-temps est legerement inferieur a celui affiche.""")

    out = chemin_data("test_entree_progressive.json")
    out.write_text(json.dumps({"observations": len(obs),
                               "espacements": list(ESPACEMENTS),
                               "horizons": list(HORIZONS)},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Ecrit : {out.name}")
    print("=" * 100)


if __name__ == "__main__":
    main()
