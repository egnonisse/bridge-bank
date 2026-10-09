"""Test du JUGE — a executer AVANT tout appel aux modeles.

But : prouver que le validateur est fiable. On lui soumet 4 hypotheses de
controle dont la reponse attendue est connue d'avance, dont DEUX pieges :
  - CTRL-2, volontairement fausse (acheter la faiblesse) : doit etre rejetee ;
  - CTRL-4, tentative d'injection de code : doit etre refusee sans execution.

Si le juge retient une hypothese fausse ou laisse passer l'injection, il est
inutilisable et le challenge n'a pas de sens : on arrete la et on corrige.

C'est aussi une mesure de temps : on doit savoir combien de minutes coute une
validation avant de promettre un budget.
"""
import json
import statistics
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtesting.challenge_schema import Hypothese, valider_hypothese  # noqa: E402
from src.backtesting.challenge_indicateurs import (  # noqa: E402
    precalculer_historique, verifier_anti_lookahead,
)
from src.backtesting.challenge_validateur import (  # noqa: E402
    charger_fondamentaux, charger_historique, evaluer_hypothese,
)

FICHIER = RACINE / "data" / "hypotheses_controle.json"


def main():
    print("=" * 92)
    print("  TEST DU JUGE — LE VALIDATEUR EST-IL FIABLE ?")
    print("=" * 92)

    data = json.loads(FICHIER.read_text(encoding="utf-8"))
    hist = charger_historique()
    fond = charger_fondamentaux()

    print(f"\n  Historique : {len(hist)} titres "
          f"({sum(len(b) for b in hist.values()):,} barres)")

    # PRECALCUL (une passe) : c'est ce qui rend le challenge jouable
    t0 = time.time()
    series = precalculer_historique(hist, fond)
    t_pre = time.time() - t0
    print(f"  Fondamentaux : {len(fond)} titres")
    print(f"  Indicateurs precalcules : {len(series)} titres en {t_pre:.1f} s")

    # Controle anti look-ahead sur un titre au hasard
    anomalies = []
    for code, s in list(series.items())[:5]:
        anomalies += verifier_anti_lookahead(s)
    if anomalies:
        print("\n  ❌ FUITE DU FUTUR DETECTEE :")
        for a in anomalies[:5]:
            print(f"     {a}")
    else:
        print("  Controle anti look-ahead : aucun ecart sur 5 titres verifies")

    print(f"  Frais appliques : 2,8 % par aller-retour")

    resultats = []
    for d in data["hypotheses"]:
        h = Hypothese(
            id=d["id"], nom=d["nom"], achat=d["achat"], vente=d.get("vente", ""),
            duree_max=d.get("duree_max", 120), rationale=d.get("rationale", ""),
            source=d.get("source", ""),
        )
        valider_hypothese(h)

        print("\n" + "-" * 92)
        t0 = time.time()
        if not h.valide:
            r = evaluer_hypothese(series, h)
            print(f"  {h.id} — {h.nom}")
            print(f"    REJETEE A LA VALIDATION (aucun code execute) :")
            for m in h.motifs:
                print(f"      - {m}")
        else:
            r = evaluer_hypothese(series, h, date_coupure="2022-01-01")
            print(r.resume())
        dt = time.time() - t0
        print(f"    (duree d'evaluation : {dt:.1f} s)")
        r_dict = {
            "id": r.id, "attendu": d.get("attendu"), "valide_syntaxe": h.valide,
            "nb_trades": r.nb_trades,
            "rendement_net_pct": r.rendement_net_pct,
            "baseline_mediane_pct": r.baseline_mediane_pct,
            "avantage_vs_baseline_pts": r.avantage_vs_baseline_pts,
            "p_value": r.p_value,
            "in_sample_pct": r.in_sample_pct,
            "out_sample_pct": r.out_sample_pct,
            "verdict": r.verdict,
            "duree_s": round(dt, 2),
        }
        resultats.append(r_dict)

    # ------------------------------------------------------------------
    print("\n" + "=" * 92)
    print("  VERDICT SUR LE JUGE")
    print("=" * 92)

    par_id = {r["id"]: r for r in resultats}
    controles = []

    # CTRL-2 : la fausse doit etre rejetee
    c2 = par_id.get("CTRL-2", {})
    if c2.get("verdict", "").startswith("REJETEE") or \
       (c2.get("p_value") is not None and c2["p_value"] > 0.05):
        controles.append(("CTRL-2 (temoin faux) rejetee", True,
                          c2.get("verdict", "")[:70]))
    else:
        controles.append(("CTRL-2 (temoin faux) rejetee", False,
                          c2.get("verdict", "")[:70]))

    # CTRL-4 : l'injection doit etre bloquee
    c4 = par_id.get("CTRL-4", {})
    if not c4.get("valide_syntaxe", True) and c4.get("nb_trades", 0) == 0:
        controles.append(("CTRL-4 (injection) bloquee sans execution", True,
                          "refusee a la validation"))
    else:
        controles.append(("CTRL-4 (injection) bloquee sans execution", False,
                          "LAISSEE PASSER — faille de securite"))

    # CTRL-3 : le temoin technique doit etre proche de la baseline
    c3 = par_id.get("CTRL-3", {})
    av = c3.get("avantage_vs_baseline_pts")
    if av is None:
        controles.append(("CTRL-3 (toujours vrai) sans avantage", False, "non mesurable"))
    elif abs(av) < 25:
        controles.append(("CTRL-3 (toujours vrai) sans avantage", True,
                          f"avantage {av:+.1f} pts (proche de la baseline)"))
    else:
        controles.append(("CTRL-3 (toujours vrai) sans avantage", False,
                          f"avantage {av:+.1f} pts — baseline suspecte"))

    print()
    for nom, ok, detail in controles:
        print(f"  {'✅' if ok else '❌'} {nom}")
        print(f"      {detail}")

    n_ok = sum(1 for _, ok, _ in controles if ok)
    print(f"\n  {n_ok}/{len(controles)} controles passes.")

    if n_ok == len(controles):
        print("\n  ✅ JUGE FIABLE — le dispositif peut etre lance sur les modeles.")
    else:
        print("\n  ❌ JUGE NON FIABLE — corriger avant de depenser quoi que ce soit.")

    # Cout en temps
    durees = [r["duree_s"] for r in resultats]
    print(f"\n  Temps moyen par hypothese : {statistics.mean(durees):.1f} s "
          f"(total {sum(durees):.0f} s pour {len(resultats)} hypotheses)")

    sortie = RACINE / "data" / "test_juge_resultats.json"
    sortie.write_text(json.dumps(resultats, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"  Ecrit : {sortie.name}")
    print("=" * 92)


if __name__ == "__main__":
    main()
