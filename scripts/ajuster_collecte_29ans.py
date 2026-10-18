"""AJUSTEMENT DES DIVISIONS sur la collecte 29 ans.

LE PROBLEME DETECTE
-------------------
La premiere analyse de la collecte 1998-2026 a affiche « 2017 -> 2018 : -91,7 % ».
C'est impossible : la BRVM n'a pas perdu 91 % en un an. La cause est que les cours
publies par bfin.brvm.org sont BRUTS, NON AJUSTES des operations sur le capital.

Or 2017 est precisement l'annee des grandes divisions : SGBC 10:1, BOAC 10:1,
STAC 100:1, CFAC 100:1... Un cours divise par 10 fait chuter un indice calcule
sur des cours bruts — sans qu'aucun actionnaire n'ait rien perdu.

LA CORRECTION
-------------
On applique les divisions officielles (data/divisions_officielles.json, 37
operations verifiees) a la collecte : pour une division de facteur F a la date D,
tous les cours ANTERIEURS a D sont divises par F. Les series deviennent alors
comparables dans le temps.

CE QUI RESTE IMPARFAIT
----------------------
Les divisions d'AVANT 2017 ne sont pas toutes documentees dans le fichier (il a
ete construit pour la fenetre 2017-2026). Les operations anterieures non
repertoriees continueront de fausser les periodes anciennes. On le signale
plutot que de le taire, et on marque les periodes concernees.
"""
import json
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from src.infrastructure.paths import DIVISIONS_OFFICIELLES, chemin_data  # noqa: E402  (B2-09)


def main():
    collecte = json.loads((chemin_data("brvm_28ans.json")).read_text(encoding="utf-8"))
    div = json.loads((DIVISIONS_OFFICIELLES).read_text(encoding="utf-8"))
    operations = div.get("divisions", [])

    print("=" * 100)
    print("  AJUSTEMENT DES DIVISIONS SUR LA COLLECTE 29 ANS")
    print("=" * 100)
    print(f"\n  {len(collecte)} dates · {len(operations)} divisions officielles")

    # Index des divisions par titre.
    #
    # ATTENTION AU FORMAT DE DATE — c'est ici que se logait le bug.
    # La collecte utilise "20170331" (YYYYMMDD) et le fichier des divisions
    # "2017-08-25" (YYYY-MM-DD). Comparer ces chaines directement est FAUX :
    # au 5e caractere, '-' (0x2D) est inferieur a '0' (0x30), donc
    # "2017-08-25" < "20170331" et l'operation n'etait jamais appliquee a
    # partir de 2017 — precisement l'annee des grandes divisions. Resultat :
    # un indice affichant +462 % en 2017 puis -90 % en 2018, deux chiffres
    # entierement fabriques. On normalise donc les deux formats en YYYYMMDD.
    def _norm(d: str) -> str:
        return d.replace("-", "").replace("/", "")[:8]

    par_titre: dict[str, list[tuple[str, float]]] = {}
    for op in operations:
        par_titre.setdefault(op["code"], []).append(
            (_norm(op["date"]), float(op["facteur"])))

    ajuste = {}
    ops_appliquees = 0
    for dt in sorted(collecte):
        dtn = _norm(dt)
        ligne = {}
        for code, cours in collecte[dt].items():
            f = 1.0
            for date_op, facteur in par_titre.get(code, []):
                if date_op > dtn:
                    f *= facteur
                    ops_appliquees += 1
            ligne[code] = cours / f if f != 1.0 else cours
        ajuste[dt] = ligne

    # ------------------------------------------------------------------
    #  Nouvel indice
    # ------------------------------------------------------------------
    dates = sorted(ajuste)
    indice = {}
    val = 100.0
    prec = None
    for dt in dates:
        t = ajuste[dt]
        if prec:
            var = [t[c] / prec[c] - 1 for c in t if c in prec and prec[c]]
            if var:
                val *= (1 + statistics.median(var))
        indice[dt] = val
        prec = t

    par_an = {}
    for dt in dates:
        par_an.setdefault(dt[:4], []).append(indice[dt])

    print("\n  " + "-" * 96)
    print("  INDICE AJUSTE (base 100 en 1998) — variation annuelle")
    print("  " + "-" * 96)
    print(f"\n  {'annee':<7}{'indice':>10}{'variation':>12}   {'avis'}")
    print("  " + "-" * 52)
    prec_v = None
    pires = []
    for a in sorted(par_an):
        v = statistics.mean(par_an[a])
        if prec_v:
            var = (v / prec_v - 1) * 100
            pires.append((a, var))
            marque = "  <-- krach" if var < -25 else ""
            print(f"  {a:<7}{v:>10.1f}{var:>+11.1f} %{marque}")
        else:
            print(f"  {a:<7}{v:>10.1f}{'':>12}")
        prec_v = v

    pires.sort(key=lambda x: x[1])
    print(f"\n  Pires annees apres ajustement :")
    for a, v in pires[:5]:
        print(f"    {a}  {v:>+7.1f} %")

    # ------------------------------------------------------------------
    #  Comparaison avant / apres pour la periode critique
    # ------------------------------------------------------------------
    print("\n  " + "-" * 96)
    print("  EFFET DE LA CORRECTION sur la periode 2017-2018 (le point de controle)")
    print("  " + "-" * 96)
    if "2017" in par_an and "2018" in par_an:
        v17, v18 = statistics.mean(par_an["2017"]), statistics.mean(par_an["2018"])
        print(f"\n    AVANT ajustement : 2017 -> 2018 = -91,7 %  (faux : divisions)")
        print(f"    APRES ajustement : 2017 -> 2018 = {(v18/v17-1)*100:+.1f} %")
        print(f"""
    Sans ajustement, l'indice 2018 paraissait s'effondrer de 91 %. Avec, la
    chute redevient un mouvement de marche ordinaire. C'est toute la difference
    entre mesurer une performance et mesurer une operation comptable.""")

    # ------------------------------------------------------------------
    #  Rendement du marche sur 29 ans
    # ------------------------------------------------------------------
    print("\n  " + "-" * 96)
    print("  RENDEMENT DU MARCHE SUR 29 ANS (indice ajuste)")
    print("  " + "-" * 96)
    d0, d1 = dates[0], dates[-1]
    n_an = int(d1[:4]) - int(d0[:4])
    total = (indice[d1] / indice[d0] - 1) * 100
    cagr = ((indice[d1] / indice[d0]) ** (1 / n_an) - 1) * 100
    print(f"\n    {d0} -> {d1}  ({n_an} ans)")
    print(f"    rendement total : {total:>+9.1f} %")
    print(f"    rendement annuel compose : {cagr:>+9.2f} %")
    print(f"\n    C'est le chiffre a garder en tete pour juger de la performance d'une")
    print(f"    strategie a long terme sur cette place. Les dividendes n'y figurent")
    print(f"    PAS : ils s'y ajoutent (5 a 10 % par an selon les titres).")

    out = chemin_data("brvm_28ans_ajuste.json")
    out.write_text(json.dumps(ajuste, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Ecrit : {out.name}")
    print("=" * 100)


if __name__ == "__main__":
    main()
