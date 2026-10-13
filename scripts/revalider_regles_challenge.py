"""Re-validation des 6 regles retenues du challenge sur l'historique CORRIGE.

POURQUOI
--------
Les 6 regles ont ete jugees AVANT que deux defauts soient corriges :
  1. la division SLBC etait appliquee deux fois (cours de 2022 divises par 50
     au lieu de 10, progression x13 fabriquee au lieu de x2,6) ;
  2. les dividendes n'etaient pas credites dans le rendement des trades.

Les regles avaient toutes ete classees « retenues ». La question est simple :
tiennent-elles toujours sur des donnees justes ?

CE QU'ON MESURE
---------------
Pour chaque regle : nombre de trades, rendement net, baseline aleatoire
(dividendes credites des deux cotes), avantage, p-value, robustesse in/out.
Puis on compare au chiffre publie dans data/challenge_resultats.json.

Une regle qui perd son avantage apres correction n'etait pas une regle : c'etait
un artefact des donnees.
"""
import json
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtesting.challenge_indicateurs import (  # noqa: E402
    charger_historique_fondamentaux, precalculer_historique,
)
from src.backtesting.challenge_schema import Hypothese, valider_hypothese  # noqa: E402
from src.backtesting.challenge_validateur import charger_historique, evaluer_hypothese  # noqa: E402


def main():
    res_path = RACINE / "data" / "challenge_resultats.json"
    d = json.loads(res_path.read_text(encoding="utf-8"))
    publiees = {}
    for r in d["resultats"]:
        publiees[r["id"]] = r

    # Les 6 retenues = celles que le challenge avait classées gagnantes
    retenues = [r for r in d["resultats"]
                if r.get("verdict", "").startswith("RETENUE")]
    # Filet : si le tri a bouge, on prend celles a avantage positif
    if not retenues:
        retenues = [r for r in d["resultats"]
                    if (r.get("avantage_vs_baseline_pts") or 0) > 0]

    print("=" * 108)
    print("  RE-VALIDATION DES REGLES RETENUES — HISTORIQUE CORRIGE")
    print("=" * 108)
    print(f"\n  {len(retenues)} regle(s) a re-juger")
    print(f"  Corrections appliquees : division SLBC (÷50 -> ÷10) "
          f"+ dividendes credites")
    seuil_ajuste = 0.05 / max(len(retenues), 1)
    print(f"  JUGE DURCI (13/10/2026) : execution J+1, p=(1+#>=)/(1+N), "
          f"avantage par moitie, seuil Bonferroni p <= {seuil_ajuste:.4f}")

    hist = charger_historique()
    hf = charger_historique_fondamentaux()
    print(f"\n  Precalcul des indicateurs...")
    series = precalculer_historique(hist, None, hf)
    print(f"  {len(series)} titres prets\n")

    resultats = []
    for r in retenues:
        h = Hypothese(id=r["id"], nom=r["nom"], achat=r["achat"],
                      vente=r.get("vente", ""), duree_max=r.get("duree_max", 120))
        valider_hypothese(h)
        if not h.valide:
            print(f"  {r['id']} : REJETEE par le DSL — {h.motifs[:1]}")
            continue
        # Le juge, avec dividendes des deux cotes ; A3-05 : seuil ajuste au
        # nombre de regles re-jugees (Bonferroni).
        res = evaluer_hypothese(series, h, historique_fond=hf,
                                seuil_p=seuil_ajuste)
        resultats.append((r, res))

    # ---------------------------------------------------------------
    #  TABLEAU COMPARATIF
    # ---------------------------------------------------------------
    print("=" * 108)
    print("  AVANT / APRES")
    print("=" * 108)
    print(f"\n  {'regle':<22}{'trades':>8}{'net AVANT':>11}{'net APRES':>11}"
          f"{'hasard':>9}{'avantage':>10}{'p':>7}  verdict")
    print("  " + "-" * 100)

    tiennent = 0
    perdues = 0
    for avant, apres in resultats:
        av_avant = avant.get("rendement_net_pct")
        av_apres = apres.rendement_net_pct
        bas = apres.baseline_mediane_pct
        advantage = apres.avantage_vs_baseline_pts
        p = apres.p_value
        # ⚠️ corrigé le 13/10/2026 : `res` (variable de la boucle d'évaluation
        # précédente) était utilisé ici — TOUTES les lignes affichaient le
        # verdict de la DERNIÈRE règle. Le verdict de LA règle est `apres`.
        ok = bool(apres.verdict.startswith("RETENUE"))
        if ok:
            tiennent += 1
        else:
            perdues += 1
        nom = avant["id"].replace("-", " ")[:21]
        print(f"  {nom:<22}{apres.nb_trades:>8}"
              f"{av_avant if av_avant is not None else 0:>10.2f}%"
              f"{av_apres if av_apres is not None else 0:>10.2f}%"
              f"{bas if bas is not None else 0:>8.2f}%"
              f"{advantage if advantage is not None else 0:>+9.2f}pt"
              f"{p if p is not None else 1:>7.3f}  "
              f"{'TIENT' if ok else 'PERD'}")

    # ---------------------------------------------------------------
    #  SYNTHESE
    # ---------------------------------------------------------------
    print("\n" + "=" * 108)
    print("  SYNTHESE")
    print("=" * 108)
    print(f"\n  Regles qui TIENNENT apres correction : {tiennent}/{len(resultats)}")
    print(f"  Regles qui PERDENT                    : {perdues}/{len(resultats)}")

    if resultats:
        var = [(a.get("rendement_net_pct") or 0) - (b.rendement_net_pct or 0)
               for a, b in resultats]
        print(f"\n  Variation moyenne du rendement net : "
              f"{statistics.mean(var):+.2f} pts")
        pires = sorted(resultats,
                       key=lambda x: (x[0].get("rendement_net_pct") or 0)
                       - (x[1].rendement_net_pct or 0), reverse=True)[:3]
        print(f"\n  Les 3 regles les plus affectees par la correction :")
        for a, b in pires:
            print(f"    {a['id']:<22} {(a.get('rendement_net_pct') or 0):>+8.2f} % "
                  f"-> {b.rendement_net_pct:>+8.2f} %   "
                  f"({(a.get('rendement_net_pct') or 0) - b.rendement_net_pct:+.2f} pts)")

    # Lesquelles impliquaient SLBC ?
    print(f"\n  Regles dont les trades incluaient SLBC :")
    for a, b in resultats:
        n_slbc = sum(1 for t in b.trades if t.code == "SLBC")
        if n_slbc:
            print(f"    {a['id']:<22} {n_slbc:>4} trades sur SLBC "
                  f"({n_slbc/max(b.nb_trades,1)*100:.1f} %)")
    if not any(any(t.code == "SLBC" for t in b.trades) for _, b in resultats):
        print("    aucune — les corrections SLBC n'affectent donc pas ces regles")

    print("\n" + "=" * 108)
    print("  LECTURE")
    print("=" * 108)
    print("""
  Une regle qui garde son avantage sur des donnees corrigees est robuste :
  elle ne dependait pas de l'erreur. Une regle qui le perd n'etait pas une
  regle, c'etait un artefact — et il vaut mieux le savoir maintenant.

  Rappel : ces regles visent la poche SPECULATIVE (horizon 60-250 seances).
  Elles ne disent rien du noyau, mesure separement.""")
    print("=" * 108)


if __name__ == "__main__":
    main()
