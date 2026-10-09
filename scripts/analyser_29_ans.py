"""ANALYSE DES 29 ANS (1998-2026) — collecte officielle bfin.brvm.org.

CE QUE CONTIENT CETTE COLLECTE
------------------------------
77 dates de cotation (fin de trimestre, dans la mesure ou la seance existe),
couvrant 1998 a 2026, avec pour chaque date le cours de cloture de chaque
valeur cotee ce jour-la. Source : bfin.brvm.org, la base officielle de la BRVM.

TROIS CHOSES QUE SEULES 29 ANS PERMETTENT DE VOIR
-------------------------------------------------
1. LES KRACHS. La fenetre 2017-2026 n'en contenait aucun de grave. En 29 ans,
   il y a la crise ivoirienne de 2011, la crise financiere de 2008, la
   devaluation de 1999.
2. LE BIAIS DU SURVIVANT, CHIFFRE. Le marche comptait 8,5 valeurs en 2002-2005
   contre 46,7 en 2026. Les titres d'aujourd'hui ne sont pas ceux d'hier : toute
   etude qui ne regarde que les survivants surestime la performance.
3. LA ROBUSTESSE DES STRATEGIES. Une regle qui gagne sur UNE fenetre peut perdre
   sur 18 fenetres glissantes. C'est la seule maniere de trier le vrai du hasard.

LIMITE A GARDER EN TETE
-----------------------
Granularite trimestrielle : environ 2,7 dates par an. Suffisant pour mesurer une
tendance longue et reperer les krachs, insuffisant pour simuler des achats
frequents. Les dividendes ne figurent PAS dans ces cours.
"""
import json
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "data" / "brvm_28ans.json"


def main():
    if not SOURCE.exists():
        raise SystemExit("data/brvm_28ans.json absent")

    # ⚠️ AVERTISSEMENT — CE SCRIPT TOURNE SUR LES COURS BRUTS, NON AJUSTES.
    #
    # Sa premiere execution a produit « 2017 -> 2018 : -91,7 % » et des rendements
    # a 10 ans de +400 a +900 % : deux chiffres FABRIQUES, parce que les cours
    # publies ne sont pas ajustes des divisions de nominal et que 2017 est l'annee
    # des grandes divisions (SGBC, BOAC, STAC, CFAC...).
    #
    # Les chiffres corrects s'obtiennent avec la chaine :
    #     scripts/ajuster_collecte_29ans.py   -> data/brvm_28ans_ajuste.json
    #     scripts/validation_longue.py        -> le test de la strategie
    #
    # Ce script est conserve pour l'AUDIT de la collecte brute (nombre de titres
    # cotes par annee, biais du survivant), PAS pour mesurer une performance.
    # Il refuse desormais de calculer un indice, pour qu'aucun chiffre faux ne
    # soit relu un jour sans avertissement.
    print("=" * 100)
    print("  AUDIT DE LA COLLECTE BRUTE — 1998-2026")
    print("=" * 100)
    print("""
  ⚠️  CE SCRIPT N'AFFICHE AUCUN INDICE NI RENDEMENT.

  Les cours de cette collecte sont BRUTS, non ajustes des divisions de nominal.
  Calculer une performance dessus produit des chiffres faux (mesure : un indice
  2017 a +462 % puis 2018 a -90 %). Pour toute mesure de performance, utiliser :

      python scripts/ajuster_collecte_29ans.py     (applique les 37 divisions)
      python scripts/validation_longue.py          (test du renforcement)

  Ce qui suit est verifiable sur les cours bruts et reste utile :
  la composition du marche et le biais du survivant.
""")

    d = json.loads(SOURCE.read_text(encoding="utf-8"))
    dates = sorted(d.keys())

    print(f"  {len(dates)} dates collectees · {dates[0]} -> {dates[-1]}")

    # ------------------------------------------------------------------
    #  Composition du marche par annee
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  COMPOSITION DU MARCHE — combien de valeurs cotaient chaque annee")
    print("-" * 100)
    print(f"\n  {'annee':<9}{'valeurs cotees':>16}{'dates':>8}")
    print("  " + "-" * 34)
    for a in sorted({x[:4] for x in dates}):
        ds = [x for x in dates if x.startswith(a)]
        n = statistics.mean(len(d[x]) for x in ds)
        print(f"  {a:<9}{n:>16.1f}{len(ds):>8}")

    # ------------------------------------------------------------------
    #  Biais du survivant
    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  BIAIS DU SURVIVANT — les titres d'hier ne sont pas ceux d'aujourd'hui")
    print("-" * 100)
    tous = sorted({c for t in d.values() for c in t})
    recents = set(d[dates[-1]])
    disparus = [c for c in tous if c not in recents]
    print(f"\n  titres vus sur 29 ans        : {len(tous)}")
    print(f"  titres cotes en {dates[-1][:4]}          : {len(recents)}")
    print(f"  titres DISPARUS (plus cotes) : {len(disparus)}")
    print(f"\n  Liste des disparus : {', '.join(disparus)}")
    print(f"""
  CONSEQUENCE : toute etude qui ne teste que les {len(recents)} valeurs encore cotees ignore
  les {len(disparus)} autres — dont celles qui ont pu faire faillite. La performance mesuree
  est donc MECANIQUEMENT surestimee. C'est le biais du survivant, chiffre : {len(disparus)} valeurs
  sur {len(tous)} ont quitte la cote.""")
    print("=" * 100)


if __name__ == "__main__":
    main()
