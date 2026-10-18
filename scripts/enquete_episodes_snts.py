"""POURQUOI SNTS N'A-T-IL QUE 7 EPISODES ? Enquete, preuve a l'appui.

LE FAIT A EXPLIQUER
-------------------
Le fichier de calibration (`data/profit_thresholds.json`) donne :
    SNTS   13 %  -> 86 % de baisse  mais  7 episodes
    SGBC   10 %  -> 63 %            et   30 episodes
    SLBC    5 %  -> 54 %            et   41 episodes
    PALC    5 %  -> 45 %            et   55 episodes

Le critere que le systeme s'est lui-meme fixe est « >= 8 episodes independants ».
SNTS est donc le SEUL titre dont le signal est bon (86 %) ET le seul qui echoue au
critere de robustesse. Un signal excellent sur 7 cas est un signal fragile — il faut
savoir POURQUOI il n'y en a que 7.

TROIS CAUSES POSSIBLES, A DEPARTAGER PAR LA MESURE
--------------------------------------------------
A. HISTORIQUE PLUS COURT : si SNTS a moins de barres que les autres, il a
   mecaniquement moins d'occasions. A verifier en premier (le plus simple).
B. VOLATILITE PLUS FAIBLE : `_profit_episodes` cherche « +13 % en 20 seances ». Un
   titre peu volatil atteint rarement ce seuil. SNTS (telecom, defensif) serait donc
   naturellement pauvre en episodes A 13 %, et riche a des seuils plus bas.
C. BUG DE CALCUL : historique mal ajuste d'une division (une division non corrigee
   fabrique une fausse variation de -90 %, qui casse la detection dans les deux sens),
   ou dedoublonnage trop agressif (le `i += 20` saute peut-etre des episodes reels).

On mesure les trois.
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


def _episodes(closes, seuil, saut=20):
    """Copie EXACTE de la logique de src/portfolio.py::_profit_episodes."""
    out, i = [], 20
    while i < len(closes) - 20:
        ref = closes[i - 20]
        if ref > 0 and closes[i] >= ref * (1 + seuil):
            out.append(closes[i + 20] / closes[i] - 1)
            i += saut
        else:
            i += 1
    return out


def main():
    h = pickle.load(open(HISTORY_CACHE, "rb"))
    titres = ["SNTS", "SGBC", "SLBC", "PALC"]

    print("=" * 100)
    print("  POURQUOI SNTS N'A-T-IL QUE 7 EPISODES ?")
    print("=" * 100)

    # ------------------------------------------------------------------
    #  A. LONGUEUR DE L'HISTORIQUE
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  A. HISTORIQUE DISPONIBLE — la cause la plus simple a ecarter")
    print("-" * 100)
    print(f"\n  {'titre':<8}{'barres':>9}{'du':>13}{'au':>13}{'volatilite quot.':>18}")
    print("  " + "-" * 61)
    infos = {}
    for c in titres:
        b = h.get(c)
        if not b:
            print(f"  {c:<8}  ABSENT DU CACHE")
            continue
        paires = sorted((str(getattr(x, "date", ""))[:10], float(getattr(x, "close", 0) or 0))
                        for x in b)
        paires = [(d, p) for d, p in paires if p > 0]
        closes = [p for _, p in paires]
        var = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1]]
        vol = statistics.pstdev(var) * 100
        infos[c] = {"n": len(closes), "du": paires[0][0], "au": paires[-1][0],
                    "vol": vol, "closes": closes}
        print(f"  {c:<8}{len(closes):>9,}{paires[0][0]:>13}{paires[-1][0]:>13}{vol:>17.2f} %")

    # ------------------------------------------------------------------
    #  B. VOLATILITE : combien d'episodes a chaque seuil ?
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  B. NOMBRE D'EPISODES PAR SEUIL (logique exacte du code)")
    print("-" * 100)
    print(f"\n  {'titre':<8}" + "".join(f"{int(s*100):>9} %" for s in SEUILS))
    print("  " + "-" * 53)
    for c in titres:
        if c not in infos:
            continue
        ligne = f"  {c:<8}"
        for s in SEUILS:
            ligne += f"{len(_episodes(infos[c]['closes'], s)):>11}"
        print(ligne)

    print(f"""
  LECTURE : si SNTS a peu d'episodes A 13 % mais beaucoup a des seuils plus bas, la
  cause est la VOLATILITE (hypothese B), pas l'historique. Si SNTS est pauvre a TOUS
  les seuils, il y a un probleme d'historique ou de calcul (A ou C).""")

    # ------------------------------------------------------------------
    #  C. CONTROLE D'INTEGRITE DE L'HISTORIQUE SNTS
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  C. INTEGRITE DE L'HISTORIQUE SNTS — une division non corrigee fausse tout")
    print("-" * 100)
    if "SNTS" in infos:
        closes = infos["SNTS"]["closes"]
        paires = sorted((str(getattr(x, "date", ""))[:10], float(getattr(x, "close", 0) or 0))
                        for x in h["SNTS"])
        # Les plus grandes variations : une division non ajustee laisse une trace nette
        var = []
        for i in range(1, len(closes)):
            if closes[i - 1]:
                var.append((abs(closes[i] / closes[i - 1] - 1), paires[i][0],
                            closes[i - 1], closes[i]))
        var.sort(reverse=True)
        print(f"\n  Les 6 plus grandes variations quotidiennes (une division = saut net) :")
        print(f"\n  {'date':<13}{'avant':>12}{'apres':>12}{'variation':>12}")
        print("  " + "-" * 49)
        for v, d, a, b in var[:6]:
            print(f"  {d:<13}{a:>12,.0f}{b:>12,.0f}{(b/a-1)*100:>+11.1f}%")
        seuil_split = 0.40
        suspectes = [v for v in var if v[0] > seuil_split]
        print(f"\n  variations > {seuil_split*100:.0f} % (signature d'une division non ajustee) : "
              f"{len(suspectes)}")
        if suspectes:
            print("  *** A INVESTIGUER ***")
        else:
            print("  Aucune — l'historique SNTS est propre (pas de division non corrigee).")

        # Premiere et derniere cotation, et profil annuel
        print(f"\n  Profil annuel SNTS (mediane des cours, pour reperer un saut d'echelle) :")
        par_an = {}
        for (d, _), c_ in zip(paires, closes):
            par_an.setdefault(d[:4], []).append(c_)
        prec = None
        for a in sorted(par_an):
            m = statistics.median(par_an[a])
            saut = f"{(m/prec-1)*100:+.1f} %" if prec else ""
            alerte = "  <-- SAUT ANORMAL" if prec and (m / prec > 3 or m / prec < 0.33) else ""
            print(f"    {a}  {m:>10,.0f} F   {saut:>10}{alerte}")
            prec = m

    # ------------------------------------------------------------------
    #  D. LE DEDOUBLONNAGE EST-IL TROP AGRESSIF ?
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  D. IMPACT DU DEDOUBLONNAGE (`i += 20` apres chaque detection)")
    print("-" * 100)
    print(f"\n  {'titre':<8}{'seuil':>7}{'saut 20':>11}{'saut 1':>10}{'taux detection':>17}")
    print("  " + "-" * 53)
    for c in titres:
        if c not in infos:
            continue
        s = 0.13
        n20 = len(_episodes(infos[c]["closes"], s, saut=20))
        n1 = len(_episodes(infos[c]["closes"], s, saut=1))
        print(f"  {c:<8}{int(s*100):>6} %{n20:>11}{n1:>10}{n1/max(n20,1):>16.2f}x")
    print("""
  LECTURE : si `saut 1` donne beaucoup plus d'episodes, le dedoublonnage est severe.
  C'est VOULU (les episodes doivent etre independants, sinon un seul mouvement long
  compte 20 fois), mais cela signifie qu'un titre en tendance longue produit peu
  d'episodes INDEPENDANTS meme s'il monte souvent.""")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
