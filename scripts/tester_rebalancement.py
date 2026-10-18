"""HYPOTHESE 5 — LE REBALANCEMENT. Le seul composant jamais teste.

LE TROU
-------
Des cinq composants deduits du releve de LEO, le rebalancement est le seul qui n'avait
JAMAIS ete mesure. La raison : son declencheur n'est pas isolable du releve — on voit
qu'il a vendu SONATEL (gagnant) pour acheter PALM et SMB (retardataires), mais pas
POURQUOI (seuil de gain atteint ? poids devenu trop lourd ? envie de loyer plus eleve ?).
Un chiffre sans son declencheur ne se rejoue pas.

CE QU'ON PEUT FAIRE MALGRE TOUT
-------------------------------
On ne peut pas tester SA regle, mais on peut tester LA FAMILLE de regle a laquelle elle
appartient, et repondre par ordre de grandeur : « vendre les gagnants pour renforcer les
retardataires » est-il avantageux, neutre ou couteux sur la BRVM ?

Trois politiques comparees sur le cache quotidien (48 titres, 2017-2026, ajuste des
divisions), portefeuille de N titres equipondere, FRAIS COMPTES (1,4 % par ordre) :

  HOLD          on achete a t0 et on ne touche plus a rien.
  REBALANCE     une fois par an, on ramene chaque ligne a son poids cible (~= vendre les
                gagnants, renforcer les perdants : le comportement de LEO).
  CONTRARIAN    a chaque date annuelle, on vend la ligne qui a le PLUS monte et on met le
                produit dans celle qui a le MOINS monte (version dure du rebalancement).

La difference entre REBALANCE et CONTRARIAN dit si c'est le RETOUR A L'EQUILIBRE qui
compte, ou le CHOIX explicite des retardataires.

⚠️ FRAIS : chaque ordre coute 1,4 % a l'aller comme au retour (constat Bridge Bank). Un
rebalancement annuel de 8 lignes genere ~8 a 16 ordres par an, soit ~11-22 % du
portefeuille en frais cumules sur 10 ans. Ne PAS les omettre : c'est ce qui peut
transformer un avantage theorique en perte.
"""
import json
import pickle
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "src"))
from src.infrastructure.paths import HISTORY_CACHE, chemin_data  # noqa: E402  (B2-09)

FRAIS = 0.014          # 1,4 % par ordre (constat du releve Bridge Bank)
HORIZONS = (3, 5, 10)
NB_LIGNES = 5          # taille realiste d'un noyau (LEO en detient 5)


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


def _simuler(series, panier, debut, horizon_an, politique):
    """Simule une politique sur `panier` (liste de codes) a partir de `debut`.

    Renvoie (valeur_finale, nb_ordres) ou None. Capital initial = 1.0.
    """
    d0 = date.fromisoformat(debut)
    fin_cible = (d0 + timedelta(days=int(365.25 * horizon_an))).isoformat()

    # Calendrier commun : on prend les dates ou TOUT le panier cote (sinon la
    # comparaison est biaisee par les trous de cotation).
    calendriers = [set(series[c]) for c in panier]
    commun = sorted(set.intersection(*calendriers))
    commun = [j for j in commun if debut <= j <= fin_cible]
    if len(commun) < 50:
        return None

    # Une part par ligne, achetee au premier jour
    j0 = commun[0]
    part = 1.0 / len(panier)
    lignes = {}
    for c in panier:
        # frais a l'achat
        lignes[c] = {"parts": part * (1 - FRAIS) / series[c][j0], "prix_achat": series[c][j0]}
    ordres = len(panier)

    # Dates de rebalancement : tous les ~365 jours
    prochain = date.fromisoformat(j0) + timedelta(days=365)

    for j in commun:
        if politique == "hold":
            continue
        if date.fromisoformat(j) < prochain:
            continue
        prochain = date.fromisoformat(j) + timedelta(days=365)

        valeurs = {c: lignes[c]["parts"] * series[c][j] for c in panier}
        total = sum(valeurs.values())
        cible = total / len(panier)

        if politique == "rebalance":
            for c in panier:
                ecart = cible - valeurs[c]
                if abs(ecart) < 0.01 * total:      # seuil : 1 % du portefeuille
                    continue
                if ecart > 0:                      # renforcer
                    lignes[c]["parts"] += ecart * (1 - FRAIS) / series[c][j]
                else:                              # alleger (le gagnant)
                    lignes[c]["parts"] += ecart * (1 - FRAIS) / series[c][j]
                ordres += 1
        elif politique == "contrarian":
            perf = {c: series[c][j] / lignes[c]["prix_achat"] - 1 for c in panier}
            best = max(perf, key=perf.get)
            worst = min(perf, key=perf.get)
            montant = valeurs[best] * 0.5           # on vend la moitie du gagnant
            if montant > 0.01 * total:
                lignes[best]["parts"] -= montant / series[best][j]
                lignes[worst]["parts"] += montant * (1 - FRAIS) / series[worst][j]
                ordres += 2
        # memoriser le prix d'achat moyen pour la variante contrarian
        for c in panier:
            lignes[c]["prix_achat"] = series[c][j]

    jf = commun[-1]
    valeur = sum(lignes[c]["parts"] * series[c][jf] for c in panier)
    return valeur - 1, ordres


def main():
    series = _charger()
    codes = sorted(series)
    print("=" * 100)
    print("  HYPOTHESE 5 — LE REBALANCEMENT : vendre ses gagnants pour renforcer ses retardataires")
    print("=" * 100)
    print(f"\n  {len(series)} titres · frais {FRAIS*100:.1f} % par ordre · panier de {NB_LIGNES} lignes")

    # Dates d'entree : une par semestre, pour avoir plusieurs points de depart
    toutes = sorted({j for s in series.values() for j in s})
    deb, fin_tot = toutes[0], toutes[-1]
    entrees = []
    d = date.fromisoformat(deb)
    limite = date.fromisoformat(fin_tot)
    while d <= limite - timedelta(days=365 * min(HORIZONS)):
        entrees.append(d.isoformat())
        d = d + timedelta(days=182)
    print(f"  {len(entrees)} dates d'entree · paniers tires deterministiquement")

    resultats = {p: {h: [] for h in HORIZONS} for p in ("hold", "rebalance", "contrarian")}
    ordres_par = {p: [] for p in ("hold", "rebalance", "contrarian")}

    for e in entrees:
        jours = [j for j in toutes if j >= e]
        if len(jours) < 300:
            continue
        i0 = jours[0]
        # Panier deterministiquement reparti : on prend NB_LIGNES titres en tournant
        idx = entrees.index(e)
        for k in range(0, max(1, len(codes) - NB_LIGNES), NB_LIGNES):
            panier = codes[k:k + NB_LIGNES]
            if len(panier) < NB_LIGNES:
                continue
            for h in HORIZONS:
                for p in ("hold", "rebalance", "contrarian"):
                    r = _simuler(series, panier, i0, h, p)
                    if r:
                        resultats[p][h].append(r[0])
                        if p != "hold":
                            ordres_par[p].append(r[1])

    print(f"\n  {'politique':<13}{'horizon':>8}{'n':>7}{'rendement median':>18}{'pire':>10}{'meilleur':>10}")
    print("  " + "-" * 66)
    for p, libelle in (("hold", "HOLD"), ("rebalance", "REBALANCE"), ("contrarian", "CONTRARIAN")):
        for h in HORIZONS:
            v = resultats[p][h]
            if len(v) < 20:
                continue
            print(f"  {libelle:<13}{h:>7} an{len(v):>7}{statistics.median(v)*100:>17.1f} %"
                  f"{min(v)*100:>9.1f} %{max(v)*100:>9.1f} %")
        print()

    print("-" * 100)
    print("  ECART vs HOLD (mediane)")
    print("-" * 100)
    print(f"\n  {'horizon':<10}{'REBALANCE':>14}{'CONTRARIAN':>14}{'ordres/an (rebal.)':>20}")
    print("  " + "-" * 58)
    for h in HORIZONS:
        vh = resultats["hold"][h]
        vr = resultats["rebalance"][h]
        vc = resultats["contrarian"][h]
        if len(vh) < 20 or len(vr) < 20:
            continue
        mh, mr, mc = (statistics.median(vh), statistics.median(vr), statistics.median(vc))
        ordres = statistics.median(ordres_par["rebalance"]) if ordres_par["rebalance"] else 0
        print(f"  {h} an(s){'':<4}{(mr-mh)*100:>+13.1f}pt{(mc-mh)*100:>+13.1f}pt{ordres/h:>19.0f}")

    print("\n" + "=" * 100)
    print("  CE QUE DIT CE TEST")
    print("=" * 100)
    vh5, vr5 = resultats["hold"].get(5, []), resultats["rebalance"].get(5, [])
    vc5 = resultats["contrarian"].get(5, [])
    if len(vh5) >= 20 and len(vr5) >= 20:
        mh, mr, mc = (statistics.median(vh5), statistics.median(vr5), statistics.median(vc5))
        print(f"""
  Sur 5 ans, panier de {NB_LIGNES} lignes, frais compris :
    HOLD         {mh*100:+.1f} %
    REBALANCE    {mr*100:+.1f} %   ({(mr-mh)*100:+.1f} pt)
    CONTRARIAN   {mc*100:+.1f} %   ({(mc-mh)*100:+.1f} pt)

  Les frais sont COMPTES ({FRAIS*100:.1f} % par ordre) : un rebalancement annuel de
  {NB_LIGNES} lignes coute environ {statistics.median(ordres_par['rebalance'])/5:.0f} ordres par an, soit
  {statistics.median(ordres_par['rebalance'])/5*FRAIS*100:.1f} % du portefeuille par an.

  ATTENTION A LA LECTURE : le rebalancement MECANIQUE a une propriete connue — il vend ce
  qui monte et achete ce qui baisse, ce qui REDUIT la volatilite mais peut ROGNER le
  rendement dans un marche en tendance (la BRVM est un marche de tendance). Un ecart
  negatif n'est donc pas une erreur de methode : c'est le prix de la regularite.""")
    print("=" * 100)

    out = chemin_data("test_rebalancement.json")
    out.write_text(json.dumps({
        "frais_par_ordre": FRAIS, "nb_lignes": NB_LIGNES, "horizons": list(HORIZONS),
        "medianes": {p: {str(h): (round(statistics.median(resultats[p][h]), 4)
                                  if resultats[p][h] else None) for h in HORIZONS}
                     for p in resultats},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Ecrit : {out.name}")


if __name__ == "__main__":
    main()
