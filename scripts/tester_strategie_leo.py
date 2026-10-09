"""PHASES 2 et 3 — Attribution : quel composant de la strategie de LEO gagne ou coute ?

PROTOCOLE
---------
Cinq variantes, memes titres, meme periode, meme capital. Seuls les COMPOSANTS
changent. On mesure les 5 metriques du projet.

  A  noyau passif          achat unique, conservation            (reference)
  B  strategie complete    les 5 composants de LEO
  C  noyau + renforcement  isole l'effet de la moyenne a la baisse
  D  noyau + paliers       isole l'effet de la vente par fractions

Le titres sont ceux que LEO detient reellement : SGB, SOLIBRA, SONATEL, PALM,
SMB. Ce n'est pas un echantillon choisi pour l'occasion, c'est son portefeuille —
ce qui rend le test directement parlant pour lui.

LIMITE ASSUMEE
--------------
Ces 5 titres ont ete choisis PAR LEO, donc la comparaison porte sur sa
selection, pas sur l'univers complet. C'est voulu : la question est « ses
composants ajoutent-ils quelque chose a sa selection ? ».
"""
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.backtesting.challenge_indicateurs import charger_historique_fondamentaux  # noqa: E402
from src.backtesting.challenge_validateur import charger_historique  # noqa: E402
from src.strategie.strategie_leo import (  # noqa: E402
    MoteurLeo, Parametres, variante_complete, variante_noyau_passif,
    variante_paliers_seuls, variante_renforcement_seul,
)

TITRES_LEO = ["SGB", "SOLIBRA", "SONATEL", "PALM", "SMB"]
# Les codes BRVM reels dans le cache
ALIAS = {
    "SGB": "SGBC", "SOLIBRA": "SLBC", "SONATEL": "SNTS",
    "PALM": "PALC", "SMB": "SMBC",
}
CAPITAL = 1_000_000.0
DEBUT = "2022-01-03"
FIN = "2026-09-30"


def main():
    hist = charger_historique()
    hf = charger_historique_fondamentaux()

    # Resolution des codes
    codes = []
    for nom, code in ALIAS.items():
        if code in hist:
            codes.append(code)
        else:
            print(f"  [!] {nom} ({code}) absent du cache")
    print("=" * 104)
    print("  ATTRIBUTION — QUEL COMPOSANT DE LA STRATEGIE DE LEO APPORTE OU COUTE ?")
    print("=" * 104)
    print(f"\n  Titres reels de LEO : {', '.join(codes)}")
    print(f"  Periode : {DEBUT} -> {FIN}   Capital : {CAPITAL:,.0f} F")
    print(f"  Frais : 1,4 % par sens (minimum 1 000 F par ordre)\n")

    variantes = [
        ("A  noyau passif", variante_noyau_passif()),
        ("B  strategie complete", variante_complete()),
        ("C  noyau + renforcement", variante_renforcement_seul()),
        ("D  noyau + paliers", variante_paliers_seuls()),
    ]

    resultats = {}
    for nom, params in variantes:
        m = MoteurLeo(hist, hf, params, CAPITAL)
        r = m.executer(DEBUT, FIN, univers=codes)
        resultats[nom] = r
        print(f"  {nom} : execute ({r.nb_achats} achats, {r.nb_ventes} ventes)")

    # ------------------------------------------------------------------
    #  TABLEAU COMPARATIF
    # ------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("  RESULTATS")
    print("=" * 104)
    print(f"\n  {'Variante':<24}{'valeur fin.':>13}{'rendement':>11}{'revenu/an':>11}"
          f"{'frais':>10}{'achats':>8}{'ventes':>8}{'expo moy':>10}{'DD max':>9}")
    print("  " + "-" * 114)
    for nom, r in resultats.items():
        print(f"  {nom:<24}{r.valeur_finale:>12,.0f} F{r.rendement_pct:>10.1f}%"
              f"{r.revenu_annuel_pct:>10.2f}%{r.frais_payes:>9,.0f}F"
              f"{r.nb_achats:>8}{r.nb_ventes:>8}{r.exposition_moyenne_pct:>9.1f}%"
              f"{r.drawdown_max_pct:>8.1f}%")

    # ------------------------------------------------------------------
    #  ATTRIBUTION
    # ------------------------------------------------------------------
    ref = resultats["A  noyau passif"]
    print("\n" + "=" * 104)
    print("  ATTRIBUTION — ecart a la reference (noyau passif)")
    print("=" * 104)
    print(f"\n  {'Variante':<24}{'ecart rendement':>18}{'ecart frais':>16}"
          f"{'ecart revenu':>15}{'ecart expo':>13}  verdict")
    print("  " + "-" * 105)
    for nom, r in resultats.items():
        if nom.startswith("A"):
            continue
        d_ren = r.rendement_pct - ref.rendement_pct
        d_fr = r.frais_payes - ref.frais_payes
        d_rev = r.revenu_annuel_pct - ref.revenu_annuel_pct
        d_exp = r.exposition_moyenne_pct - ref.exposition_moyenne_pct
        verdict = "APPORTE" if d_ren > 1 else ("NEUTRE" if d_ren > -1 else "COUTE")
        print(f"  {nom:<24}{d_ren:>+16.2f} pt{d_fr:>+15,.0f}F{d_rev:>+14.2f} pt"
              f"{d_exp:>+12.1f} pt  {verdict}")

    # ------------------------------------------------------------------
    #  NORMALISATION PAR L'EXPOSITION (le point cle)
    # ------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("  NORMALISATION — rendement ramene a l'exposition (comparaison equitable)")
    print("=" * 104)
    print("""
  Une regle qui vend tot est MOINS investie : dans un marche haussier elle
  gagne moins, sans que sa methode soit en cause. On divise donc le rendement
  par l'exposition moyenne pour comparer ce qui est comparable : le rendement
  PAR UNITE DE CAPITAL EXPOSE.""")
    print(f"\n  {'Variante':<24}{'rendement':>12}{'expo moy':>11}"
          f"{'rend./expo':>13}{'rendement ajuste':>18}")
    print("  " + "-" * 80)
    base_norm = None
    for nom, r in resultats.items():
        expo = r.exposition_moyenne_pct / 100 if r.exposition_moyenne_pct else 0.01
        norm = r.rendement_pct / expo
        if nom.startswith("A"):
            base_norm = norm
        print(f"  {nom:<24}{r.rendement_pct:>11.1f}%{r.exposition_moyenne_pct:>10.1f}%"
              f"{norm:>12.1f}%{norm - base_norm:>+17.1f} pt"
              if base_norm is not None else
              f"  {nom:<24}{r.rendement_pct:>11.1f}%{r.exposition_moyenne_pct:>10.1f}%"
              f"{norm:>12.1f}%{'':>18}")
    print("""
  LECTURE : si un composant reste nettement negatif APRES normalisation, son
  cout ne vient pas de l'exposition — il vient vraiment de la methode.""")

    # ------------------------------------------------------------------
    #  DETAIL DE LA STRATEGIE COMPLETE
    # ------------------------------------------------------------------
    b = resultats["B  strategie complete"]
    print("\n" + "=" * 104)
    print("  DETAIL — STRATEGIE COMPLETE (B) : que reste-t-il en portefeuille ?")
    print("=" * 104)
    print(f"\n  cash final : {b.cash_final:,.0f} F   "
          f"({b.cash_final/b.valeur_finale*100:.1f} % du total)")
    print(f"\n  {'titre':<10}{'actions':>10}{'CMP':>12}{'cours fin':>12}"
          f"{'valeur':>12}{'dividendes':>13}{'tranches':>10}{'ventes':>8}")
    print("  " + "-" * 87)
    for code, d in sorted(b.detail.items()):
        print(f"  {code:<10}{d['actions']:>10.2f}{d['cmp']:>12,.0f}"
              f"{d['cours_final']:>12,.0f}{d['valeur']:>12,.0f}"
              f"{d['dividendes']:>13,.0f}{d['tranches']:>10}{d['ventes']:>8}")

    print("\n" + "=" * 104)
    print("  COMMENT LIRE")
    print("=" * 104)
    print("""
  Le test repond a UNE question : les habitudes de LEO (entrer par tranches,
  renforcer a la baisse, vendre par paliers) ajoutent-elles de la valeur a sa
  SELECTION de titres ?

  Un composant qui COUTE n'est pas forcement a abandonner : il peut acheter du
  confort (moins de volatilite) ou de la discipline (ne pas tout miser d'un
  coup). Mais le cout doit etre connu.

  Attention : les frais d'un ordre representent 1,4 %, avec un minimum de
  1 000 F. Multiplier les petites tranches coute donc cher en proportion.""")


if __name__ == "__main__":
    main()
