"""LE VRAI DEFAUT : le calibrage choisit le seuil sur un POINT ESTIME, pas sur un intervalle.

CE QUE FAIT LE CODE (src/portfolio.py::calibrate_profit_threshold)
------------------------------------------------------------------
    for seuil in (0.05, 0.08, 0.10, 0.13, 0.15):
        ep = episodes(seuil)
        if len(ep) < 6: continue
        down = % de baisses
        if down > best: best = ce seuil

Il prend le MAXIMUM de `down` parmi les seuils ayant au moins 6 episodes. Consequences
mecaniques, verifiables :

  1. Plus le seuil est HAUT, plus la baisse qui suit est probable (on a deja beaucoup
     monte) — donc le maximum est generalement atteint au seuil le PLUS HAUT passe.
  2. Plus le seuil est haut, moins il y a d'episodes. Le seuil gagnant est donc
     structurellement celui qui a le MOINS de cas.
  3. Le garde-fou `len(ep) < 6` autorise 6 episodes : une probabilite estimee sur 6
     cas a un intervalle de confiance de l'ordre de +/- 35 points.

Le resultat est un BIAIS DE SELECTION SUR PETIT ECHANTILLON : le titre le plus CALME
(SNTS, 1,37 %/jour) est mecaniquement celui dont le seuil retenu est le plus fragile —
7 episodes — et c'est exactement le seuil qu'on s'appretait a conserver.

CE QUE CE SCRIPT MESURE
-----------------------
Pour chaque titre et chaque seuil : la probabilite de baisse, l'INTERVALLE DE CONFIANCE
a 95 % (methode de Wilson, correcte sur petits echantillons), et la BORNE INFERIEURE.
Puis il rejoue le calibrage avec un critere corrige : retenir le seuil dont la borne
INFERIEURE est la plus haute, et non la probabilite ponctuelle.
"""
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "src"))
from src.infrastructure.paths import HISTORY_CACHE  # noqa: E402  (B2-09)

SEUILS = (0.05, 0.08, 0.10, 0.13, 0.15)
Z = 1.96
TITRES = ["SNTS", "SGBC", "SLBC", "PALC"]


def _episodes(closes, seuil):
    out, i = [], 20
    while i < len(closes) - 20:
        ref = closes[i - 20]
        if ref > 0 and closes[i] >= ref * (1 + seuil):
            out.append(closes[i + 20] / closes[i] - 1)
            i += 20
        else:
            i += 1
    return out


def wilson(k, n):
    """Intervalle de confiance 95 % de Wilson. Correct sur petits echantillons,
    contrairement a l'intervalle normal qui donne des bornes hors [0,1]."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p = k / n
    d = 1 + Z * Z / n
    centre = (p + Z * Z / (2 * n)) / d
    demi = Z * ((p * (1 - p) / n + Z * Z / (4 * n * n)) ** 0.5) / d
    return p, max(0.0, centre - demi), min(1.0, centre + demi)


def main():
    h = pickle.load(open(HISTORY_CACHE, "rb"))
    print("=" * 102)
    print("  LE CALIBRAGE CHOISIT-IL LE BON SEUIL ? Intervalle de confiance a 95 % (Wilson)")
    print("=" * 102)

    details = {}
    for c in TITRES:
        b = h.get(c)
        if not b:
            continue
        closes = [float(getattr(x, "close", 0) or 0) for x in b]
        closes = [p for p in closes if p > 0]
        details[c] = {}
        for s in SEUILS:
            ep = _episodes(closes, s)
            n = len(ep)
            k = sum(1 for r in ep if r < 0)
            p, lo, hi = wilson(k, n)
            details[c][s] = {"n": n, "k": k, "p": p, "lo": lo, "hi": hi,
                             "med": statistics.median(ep) * 100 if ep else 0.0}

    # ------------------------------------------------------------------
    for c in TITRES:
        if c not in details:
            continue
        print(f"\n{'-'*102}")
        print(f"  {c}")
        print(f"{'-'*102}")
        print(f"\n  {'seuil':>7}{'cas':>6}{'baisses':>9}{'prob.':>8}{'IC 95 %':>17}"
              f"{'borne BASSE':>13}{'mediane':>10}")
        print("  " + "-" * 76)
        for s in SEUILS:
            d = details[c][s]
            if d["n"] == 0:
                print(f"  {int(s*100):>6} %{0:>6}{'-':>9}{'-':>8}{'-':>17}{'-':>13}{'-':>10}")
                continue
            marque = ""
            if d["n"] < 8:
                marque = "  <-- sous le seuil de robustesse (8)"
            print(f"  {int(s*100):>6} %{d['n']:>6}{d['k']:>9}{d['p']*100:>7.0f} %"
                  f"{f'{d[chr(108)+chr(111)]*100:.0f}-{d[chr(104)+chr(105)]*100:.0f} %':>17}"
                  f"{d['lo']*100:>12.0f} %{d['med']:>9.1f} %{marque}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 102)
    print("  CE QUE CHOISIT LE CODE (probabilite ponctuelle maximale)")
    print("=" * 102)
    print(f"\n  {'titre':<8}{'seuil retenu':>14}{'cas':>6}{'prob.':>8}{'borne basse':>13}   verdict")
    print("  " + "-" * 72)
    choix_code = {}
    for c in TITRES:
        if c not in details:
            continue
        cand = [(s, d) for s, d in details[c].items() if d["n"] >= 6]
        if not cand:
            continue
        s, d = max(cand, key=lambda x: x[1]["p"])
        choix_code[c] = (s, d)
        verdict = "FRAGILE (n<8)" if d["n"] < 8 else "ok"
        print(f"  {c:<8}{int(s*100):>13} %{d['n']:>6}{d['p']*100:>7.0f} %"
              f"{d['lo']*100:>12.0f} %   {verdict}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 102)
    print("  CE QUE CHOISIRAIT UN CRITERE CORRIGE (borne INFERIEURE la plus haute)")
    print("=" * 102)
    print(f"\n  {'titre':<8}{'seuil retenu':>14}{'cas':>6}{'prob.':>8}{'borne basse':>13}"
          f"   change ?")
    print("  " + "-" * 76)
    for c in TITRES:
        if c not in details:
            continue
        cand = [(s, d) for s, d in details[c].items() if d["n"] >= 6]
        if not cand:
            continue
        s2, d2 = max(cand, key=lambda x: x[1]["lo"])
        s1, d1 = choix_code[c]
        change = "OUI" if s2 != s1 else "non"
        print(f"  {c:<8}{int(s2*100):>13} %{d2['n']:>6}{d2['p']*100:>7.0f} %"
              f"{d2['lo']*100:>12.0f} %   {change}")

    print("""
  LECTURE — ce que ce tableau etablit
  -----------------------------------
  Le code retient pour chaque titre le seuil ou la probabilite PONCTUELLE est la plus
  haute. Comme cette probabilite monte mecaniquement avec le seuil (on n'exige +X % que
  si le titre a deja beaucoup monte) ET que le nombre de cas diminue en meme temps, le
  seuil gagnant est TOUJOURS celui qui a le MOINS de cas. Le garde-fou a 6 episodes
  etant tres bas, le resultat est un biais de selection sur petit echantillon.

  La colonne « borne basse » est la seule qui permette de comparer honnetement : elle
  repond a « quelle est la PIRE probabilite compatible avec ce que j'ai observe ? ».
  Un seuil a 86 % sur 7 cas et un seuil a 65 % sur 34 cas ne sont pas comparables sur
  leur point estime — mais ils le sont sur leur borne inferieure.""")

    print("\n" + "=" * 102)


if __name__ == "__main__":
    main()
