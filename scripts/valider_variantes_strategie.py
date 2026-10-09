"""PHASE 4 (R3 et R4) — LE CODE JUGE les variantes proposees par les modeles.

REGLE ANTI-TRICHE
-----------------
Les modeles ont produit ces variantes SANS connaitre aucun resultat de
backtest. Ce script les evalue sur l'historique reel et classe les variantes.
Les modeles ne verront jamais ces resultats : ils ne peuvent donc pas ajuster
leurs propositions en fonction des reponses.

CE QU'ON MESURE PAR VARIANTE
----------------------------
  - rendement total (dividendes reinvestis par le moteur)
  - revenu annuel encaisse
  - drawdown maximal
  - exposition moyenne (indispensable : une regle peu investie gagne moins sans
    que sa methode soit en cause)
  - frais payes et nombre d'ordres
  - RENDEMENT AJUSTE A L'EXPOSITION, la seule comparaison equitable

REFERENCE
---------
La strategie reelle de LEO (parametres observes) sert de point de comparaison.
Une variante ne vaut que si elle fait MIEUX qu'elle.
"""
import json
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtesting.challenge_indicateurs import charger_historique_fondamentaux  # noqa: E402
from src.backtesting.challenge_validateur import charger_historique  # noqa: E402
from src.strategie_leo import MoteurLeo, Parametres, variante_complete  # noqa: E402

TITRES = ["SGBC", "SLBC", "SNTS", "PALC", "SMBC"]
CAPITAL = 1_000_000.0
DEBUT, FIN = "2022-01-03", "2026-09-30"


def _params_depuis_dict(d: dict) -> Parametres:
    """Construit un Parametres depuis le JSON propose par un modele.

    On borne chaque valeur : un modele peut proposer 60 tranches ou un seuil a
    0.90, ce qui n'est pas une strategie mais une erreur de comprehension. On
    garde la proposition si elle est realiste, sinon on ramene dans les bornes.
    """
    def _n(v, mini, maxi, defaut):
        try:
            x = float(v)
        except (TypeError, ValueError):
            return defaut
        return type(defaut)(max(mini, min(maxi, x)))

    seuils = []
    for s in (d.get("seuils_vente") or [])[:3]:
        try:
            if isinstance(s, (list, tuple)) and len(s) == 2:
                seuil = max(0.02, min(0.90, float(s[0])))
                frac = max(0.05, min(1.0, float(s[1])))
                seuils.append((seuil, frac))
        except (TypeError, ValueError):
            continue

    return Parametres(
        nb_tranches=_n(d.get("nb_tranches"), 1, 10, 3),
        espacement_jours=_n(d.get("espacement_jours"), 0, 60, 12),
        renforcement_actif=bool(d.get("renforcement_actif", False)),
        seuil_renforcement=_n(d.get("seuil_renforcement"), 0.01, 0.20, 0.045),
        paliers_actifs=bool(d.get("paliers_actifs", False)) and bool(seuils),
        seuils_vente=tuple(seuils) if seuils else ((0.15, 1/3),),
        cash_cible=_n(d.get("cash_cible"), 0.0, 0.40, 0.15),
    )


def main():
    src = RACINE / "data" / "challenge_strategie_variantes.json"
    if not src.exists():
        raise SystemExit("Lancez d'abord scripts/challenge_strategie.py")
    data = json.loads(src.read_text(encoding="utf-8"))
    variantes = data.get("variantes", [])
    critiques = data.get("critiques", {})

    hist = charger_historique()
    hf = charger_historique_fondamentaux()

    print("=" * 112)
    print("  PHASE 4 (R3/R4) — LE CODE JUGE LES VARIANTES DES MODELES")
    print("=" * 112)
    print(f"\n  {len(variantes)} variantes proposees par les modeles")
    print(f"  Titres : {', '.join(TITRES)} · periode {DEBUT} -> {FIN}\n")

    # --- Variantes ecartees par la critique croisee --------------------
    ecartees = set()
    for modele, liste in critiques.items():
        if not isinstance(liste, list):
            continue
        for c in liste:
            if isinstance(c, dict) and c.get("garde") is False:
                ecartees.add(str(c.get("id", "")))
    if ecartees:
        print(f"  Variantes ecartees par la critique croisee : {sorted(ecartees)}")

    # --- Reference : la strategie reelle de LEO ------------------------
    ref = MoteurLeo(hist, hf, variante_complete(), CAPITAL).executer(DEBUT, FIN, TITRES)
    ref_norm = (ref.rendement_pct / (ref.exposition_moyenne_pct / 100)
                if ref.exposition_moyenne_pct else 0.0)

    resultats = []
    for v in variantes:
        try:
            p = _params_depuis_dict(v.get("parametres", {}))
        except Exception:
            continue
        try:
            r = MoteurLeo(hist, hf, p, CAPITAL).executer(DEBUT, FIN, TITRES)
        except Exception as e:
            print(f"  [!] {v.get('nom','?')} : echec ({str(e)[:60]})")
            continue
        norm = (r.rendement_pct / (r.exposition_moyenne_pct / 100)
                if r.exposition_moyenne_pct else 0.0)
        resultats.append({
            "nom": str(v.get("nom", "?"))[:34],
            "source": v.get("source", "?"),
            "params": p,
            "r": r,
            "norm": norm,
            "ecartee": v.get("id", "") in ecartees,
        })

    resultats.sort(key=lambda x: -x["norm"])

    # ------------------------------------------------------------------
    #  CLASSEMENT
    # ------------------------------------------------------------------
    print("\n" + "=" * 112)
    print("  CLASSEMENT (par rendement ajuste a l'exposition)")
    print("=" * 112)
    print(f"\n  {'#':<3}{'variante':<36}{'rend.':>9}{'expo':>7}{'ajuste':>9}"
          f"{'vs LEO':>9}{'DD max':>8}{'frais':>9}{'ordres':>8}")
    print("  " + "-" * 96)

    print(f"  {'-':<3}{'REFERENCE : strategie reelle LEO':<36}"
          f"{ref.rendement_pct:>8.1f}%{ref.exposition_moyenne_pct:>6.1f}%"
          f"{ref_norm:>8.1f}%{'--':>9}{ref.drawdown_max_pct:>7.1f}%"
          f"{ref.frais_payes:>8,.0f}F{ref.nb_achats+ref.nb_ventes:>8}")
    print("  " + "-" * 96)

    meilleures = []
    for i, x in enumerate(resultats, 1):
        r = x["r"]
        ecart = x["norm"] - ref_norm
        flag = " *" if x["ecartee"] else ""
        print(f"  {i:<3}{x['nom']+flag:<36}{r.rendement_pct:>8.1f}%"
              f"{r.exposition_moyenne_pct:>6.1f}%{x['norm']:>8.1f}%"
              f"{ecart:>+8.1f}pt{r.drawdown_max_pct:>7.1f}%"
              f"{r.frais_payes:>8,.0f}F{r.nb_achats+r.nb_ventes:>8}")
        if ecart > 0 and not x["ecartee"]:
            meilleures.append(x)

    # ------------------------------------------------------------------
    #  R4 — VERDICT
    # ------------------------------------------------------------------
    print("\n" + "=" * 112)
    print("  R4 — VERDICT")
    print("=" * 112)

    n = len(resultats)
    bat = len(meilleures)
    print(f"\n  Variantes qui battent la strategie reelle : {bat}/{n}")

    if meilleures:
        best = meilleures[0]
        print(f"\n  MEILLEURE VARIANTE : {best['nom']}")
        print(f"    rendement ajuste {best['norm']:.1f} % contre {ref_norm:.1f} % "
              f"pour LEO  ({best['norm']-ref_norm:+.1f} pts)")
        print(f"    drawdown {best['r'].drawdown_max_pct:.1f} %  ·  "
              f"revenu {best['r'].revenu_annuel_pct:.2f} %/an  ·  "
              f"{best['r'].nb_achats+best['r'].nb_ventes} ordres")
        print(f"    parametres : nb_tranches={best['params'].nb_tranches}, "
              f"espacement={best['params'].espacement_jours} j, "
              f"renforcement={best['params'].renforcement_actif} "
              f"({best['params'].seuil_renforcement*100:.1f} %), "
              f"paliers={best['params'].paliers_actifs}, "
              f"cash={best['params'].cash_cible*100:.0f} %")

        # Ce que la meilleure change par rapport a LEO
        p0 = variante_complete()
        print(f"\n  DIFFERENCES AVEC LA PRATIQUE ACTUELLE :")
        if best["params"].nb_tranches != p0.nb_tranches:
            print(f"    - tranches : {p0.nb_tranches} -> {best['params'].nb_tranches}")
        if best["params"].espacement_jours != p0.espacement_jours:
            print(f"    - espacement : {p0.espacement_jours} j -> "
                  f"{best['params'].espacement_jours} j")
        if best["params"].seuil_renforcement != p0.seuil_renforcement:
            print(f"    - seuil de renfort : {p0.seuil_renforcement*100:.1f} % -> "
                  f"{best['params'].seuil_renforcement*100:.1f} %")
        if best["params"].paliers_actifs != p0.paliers_actifs:
            print(f"    - paliers de vente : {p0.paliers_actifs} -> "
                  f"{best['params'].paliers_actifs}")
        if best["params"].cash_cible != p0.cash_cible:
            print(f"    - reserve de cash : {p0.cash_cible*100:.0f} % -> "
                  f"{best['params'].cash_cible*100:.0f} %")
    else:
        print("\n  AUCUNE variante ne bat la pratique actuelle. C'est un resultat")
        print("  en soi : la methode de LEO resiste aux alternatives proposees.")

    # ------------------------------------------------------------------
    #  Apprentissage transversal : que font les variantes gagnantes ?
    # ------------------------------------------------------------------
    if meilleures:
        print("\n" + "=" * 112)
        print("  APPRENTISSAGE — que partagent les variantes gagnantes ?")
        print("=" * 112)
        print(f"\n  {'habitude':<32}{'gagnantes':>12}{'toutes':>10}")
        print("  " + "-" * 56)
        for cle, label, test in [
            ("renforcement_actif", "renforcement a la baisse", lambda p: p.renforcement_actif),
            ("paliers_actifs", "paliers de vente", lambda p: p.paliers_actifs),
            ("tranches_elevees", "plus de 3 tranches", lambda p: p.nb_tranches > 3),
            ("espacement_long", "espacement > 20 jours", lambda p: p.espacement_jours > 20),
            ("cash_eleve", "reserve de cash > 20 %", lambda p: p.cash_cible > 0.20),
            ("seuil_profond", "renfort au-dela de 6 %", lambda p: p.seuil_renforcement > 0.06),
        ]:
            ng = sum(1 for x in meilleures if test(x["params"]))
            nt = sum(1 for x in resultats if test(x["params"]))
            print(f"  {label:<32}{ng:>8}/{len(meilleures):<3}{nt:>7}/{n}")

    out = RACINE / "data" / "challenge_strategie_resultats.json"
    out.write_text(json.dumps({
        "reference_leo": {"rendement_pct": ref.rendement_pct,
                          "exposition_pct": ref.exposition_moyenne_pct,
                          "ajuste": ref_norm,
                          "drawdown_pct": ref.drawdown_max_pct,
                          "revenu_annuel_pct": ref.revenu_annuel_pct,
                          "frais": ref.frais_payes,
                          "ordres": ref.nb_achats + ref.nb_ventes},
        "classement": [
            {"nom": x["nom"], "source": x["source"], "ajuste": x["norm"],
             "rendement_pct": x["r"].rendement_pct,
             "exposition_pct": x["r"].exposition_moyenne_pct,
             "drawdown_pct": x["r"].drawdown_max_pct,
             "revenu_annuel_pct": x["r"].revenu_annuel_pct,
             "frais": x["r"].frais_payes,
             "ordres": x["r"].nb_achats + x["r"].nb_ventes,
             "ecartee_par_critique": x["ecartee"]}
            for x in resultats],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Ecrit : {out.name}")
    print("=" * 112)


if __name__ == "__main__":
    main()
