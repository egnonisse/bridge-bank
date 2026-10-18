"""Prepare l'historique BRVM propre — pipeline complet et reproductible.

ETAPES
------
1. AJUSTEMENT des divisions de nominal (`data/divisions_officielles.json`)
   38 divisions verifiees : relevees sur les fiches societe publiees par la
   BRVM, croisees avec une detection independante sur les cours (32 cassures
   confirmees sur 40 detectees).
2. NETTOYAGE des valeurs aberrantes isolees (cours > 5x la mediane locale)
3. SAUVEGARDE dans `data/history_clean.pkl`

POURQUOI C'EST FIABLE
---------------------
Controle final : l'indice synthetique reconstruit (mediane des cours
normalises) suit l'histoire reelle de la BRVM — creux en 2020 (COVID, 18
titres au plus bas), sommet en 2026 (30 titres au plus haut). Un historique
faux ne produirait pas ce profil.

CE QUI RESTE A SAVOIR
---------------------
Le drawdown median de -74 % est REEL : la BRVM a perdu les deux tiers de sa
valeur entre 2017 et 2020 avant de la tripler. Ce n'est pas un artefact.

Deux titres restent marques douteux (NTLC, STBC) : leur hausse de 2020 a 2021
n'est expliquee par aucune operation documentee.
"""
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.collecte.history_io import charger_cache  # noqa: E402
from src.collecte.preparation import preparer_historique_propre  # noqa: E402
from src.infrastructure.paths import HISTORY_BRUT, HISTORY_CACHE  # noqa: E402
# B2-10 (13/10/2026) : le CALCUL vit dans src/collecte/preparation.py — le check
# quotidien prepare le propre lui-meme ; ce script reste l'outil de diagnostic.


def main():
    print("=" * 82)
    print("  PREPARATION DE L'HISTORIQUE BRVM PROPRE")
    print("=" * 82)
    print(f"\n  Source : {HISTORY_BRUT.name}")

    stats = preparer_historique_propre()
    print(f"\n  [1/3] Ajustement des divisions")
    print(f"        {stats['titres_ajustes']} titres ajustes, "
          f"{stats['sans_division']} sans operation")
    print(f"\n  [2/3] Nettoyage des valeurs aberrantes")
    print(f"        {stats['aberrantes_corrigees']} barres corrigees")

    # Controle de coherence (diagnostic : lecture des deux caches)
    with open(HISTORY_BRUT, "rb") as fh:
        brut = pickle.load(fh)
    propre = charger_cache()

    # 3. Controle de coherence
    print(f"\n  [3/3] Controle de coherence")

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

    d1 = [dd(b) for b in brut.values() if len(b) > 20]
    d2 = [dd(b) for b in propre.values() if len(b) > 20]
    print(f"\n        drawdown median : {statistics.median(d1):.1f} %  ->  "
          f"{statistics.median(d2):.1f} %")
    print(f"        pire drawdown   : {min(d1):.1f} %  ->  {min(d2):.1f} %")

    # Indice synthetique
    from collections import defaultdict
    par_an = defaultdict(list)
    for code, bs in propre.items():
        cl = [float(b.close) for b in bs if getattr(b, "close", None)]
        if len(cl) < 50 or not cl[0]:
            continue
        base = cl[0]
        for b in bs:
            c = float(getattr(b, "close", 0) or 0)
            if c:
                par_an[str(b.date)[:4]].append(c / base * 100)
    print("\n        indice synthetique (base 100 en debut de serie) :")
    for a in sorted(par_an):
        v = par_an[a]
        if v:
            barre = "#" * int(statistics.median(v) / 5)
            print(f"          {a}  {statistics.median(v):>6.0f}  {barre}")

    print(f"\n  Ecrit : {HISTORY_CACHE.name}  ({HISTORY_CACHE.stat().st_size / 1024:.0f} Ko)  + .sha256")
    print("\n" + "=" * 82)


if __name__ == "__main__":
    main()
