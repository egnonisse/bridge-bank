"""VALIDATION LONGUE — le renforcement sur faiblesse tient-il PENDANT un krach ?

LA QUESTION
-----------
L'attribution menee sur 2022-2026 a montre que le renforcement sur faiblesse apporte
+25,8 points ajustes a l'exposition, et que les paliers coutent -43,1 points. Mais
2022-2026 est une phase HAUSSIERE de la BRVM (indice +43 % sur la seule annee 2026).
Dans un marche qui monte, « acheter le repli » gagne par construction : le repli est
efface quelques semaines plus tard. La question qui decide est donc :

    PENDANT un krach (-47 % en 2018, -31 % en 1999), le renforcement aide-t-il
    encore, ou transforme-t-il une perte en perte doublee ?

C'est exactement ce qu'aucune fenetre courte ne peut montrer, et c'est pourquoi les
28 ans de donnees officielles ont ete collectees.

PROTOCOLE
---------
Pour CHAQUE date d'entree disponible (77 dates, 1998-2026) et CHAQUE titre cote
ce jour-la, on compare deux facons d'engager le meme capital :

  HOLD    un tiers acheté a t0, tenu jusqu'a l'horizon. Les deux autres tiers
          restent engages des t0 aussi (achat immediat total) : c'est le noyau
          passif, entierement investi des le premier jour.
  RENFORT un tiers a t0, puis un tiers a chaque fois que le cours passe SOUS le
          dernier prix paye de 4,5 % (le seuil observe sur les achats PALM de LEO),
          jusqu'a 3 tranches. Le capital non investi reste en cash (rendement 0).

Deux mesures sont produites, et c'est la comparaison des deux qui est honnete :
  - rendement du CAPITAL TOTAL (le cash dormant coute, c'est un vrai cout) ;
  - rendement du capital INVESTI (normalise par l'exposition, sinon on compare
    une strategie investie a une strategie a moitie en cash et on ne juge que
    la quantite de cash).

DECOUPAGE PAR REGIME
--------------------
Les dates d'entree sont classees selon l'annee de depart : ANNEE DE KRACH (marche
en baisse > 15 % cette annee-la) contre ANNEE NORMALE. C'est le seul decoupage qui
reponde a la question posee.

LIMITES — A LIRE AVANT LES CHIFFRES
-----------------------------------
1. BIAIS DU SURVIVANT : le jeu de donnees ne contient que les titres ENCORE cotes
   aujourd'hui (46). Les 11 valeurs radiées depuis 1998 sont absentes. Toute
   performance absolue est donc surestimee, et un titre qui a fait faillite aurait
   ete le pire cas du renforcement (on « renforce » jusqu'a zero).
2. AUCUN DIVIDENDE : les cours officiels BRVM en sont purges. Le revenu n'est pas
   mesure ici (il l'est dans `tester_noyau.py` sur 2022-2026, +11 %/an).
3. GRANULARITE : ~2,7 dates par an. Un repli de 4,5 % entre deux dates est vu ;
   un repli plus fin peut etre manque. Le renforcement est donc SOUS-estime.
"""
import json
import statistics
import sys
from pathlib import Path
from src.infrastructure.paths import chemin_data  # noqa: E402  (B2-09)

RACINE = Path(__file__).resolve().parent.parent
SEUIL_REPLI = 0.045   # seuil observe sur les achats PALM de LEO
NB_TRANCHES = 3
HORIZONS = (3, 5, 10)


def _valeur_a(dates, serie, i0, horizon_an, capital, tranches, seuil, titre):
    """Simule LES DEUX strategies sur un titre a partir de l'indice i0.

    Renvoie (rendement_hold, rendement_renfort, exposition_renfort).
    """
    an0 = int(dates[i0][:4])
    an_fin = an0 + horizon_an

    # Bornes de la fenetre
    fin = None
    for j in range(i0, len(dates)):
        if int(dates[j][:4]) <= an_fin:
            fin = j
        else:
            break
    if fin is None or fin <= i0:
        return None

    # Prix du titre sur la fenetre (il peut disparaitre : on garde la derniere cote)
    cours = []
    for j in range(i0, fin + 1):
        c = serie.get(dates[j])
        if c:
            cours.append((j, c))
    if len(cours) < 3:
        return None

    prix_fin = cours[-1][1]

    # --- HOLD : tout investi a t0 ---
    prix_debut = cours[0][1]
    r_hold = prix_fin / prix_debut - 1

    # --- RENFORT : 1 tranche a t0, puis sur repli de 4,5 % sous le dernier prix paye ---
    part = 1.0 / tranches
    montant_engage = part            # fraction du capital reellement investie
    actions = part / prix_debut      # en « parts de capital »
    dernier_prix = prix_debut
    n_tranches = 1
    for j, c in cours[1:]:
        if n_tranches >= tranches:
            break
        if c <= dernier_prix * (1 - seuil):
            actions += part / c
            montant_engage += part
            dernier_prix = c
            n_tranches += 1

    valeur_finale = actions * prix_fin
    r_total = valeur_finale - 1                      # capital total (cash dormant = 0 %)
    r_investi = (valeur_finale / montant_engage - 1) if montant_engage else 0
    return r_hold, r_total, r_investi, montant_engage


def main():
    data = json.loads((chemin_data("brvm_28ans_ajuste.json")).read_text(encoding="utf-8"))
    dates = sorted(data)

    # --- Classification des annees : krach ou normale ---
    indice_an = {}
    val, prec = 100.0, None
    for dt in dates:
        t = data[dt]
        if prec:
            v = [t[c] / prec[c] - 1 for c in t if c in prec and prec[c]]
            if v:
                val *= (1 + statistics.median(v))
        indice_an.setdefault(dt[:4], []).append(val)
        prec = t
    moy_an = {a: statistics.mean(v) for a, v in indice_an.items()}
    annees = sorted(moy_an)
    var_an = {}
    for i, a in enumerate(annees):
        var_an[a] = (moy_an[a] / moy_an[annees[i - 1]] - 1) if i else 0.0
    krachs = {a for a, v in var_an.items() if v < -0.15}

    print("=" * 104)
    print("  VALIDATION LONGUE — LE RENFORCEMENT SUR FAIBLESSE TIENT-IL PENDANT UN KRACH ?")
    print("=" * 104)
    print(f"\n  77 dates · {len(dates)} points · 1998 -> 2026 · seuil de repli {SEUIL_REPLI*100:.1f} %"
          f" · {NB_TRANCHES} tranches")
    print(f"  Annees de KRACH identifiees : {', '.join(sorted(krachs))}")

    # --- Collecte des observations ---
    obs = []   # (annee, r_hold, r_total, r_investi, expo, horizon)
    for i0, dt in enumerate(dates):
        an = dt[:4]
        serie_titre = {}
        for c in data[dt]:
            serie_titre[c] = {d: data[d][c] for d in dates if c in data[d]}
        for titre in data[dt]:
            for h in HORIZONS:
                r = _valeur_a(dates, serie_titre[titre], i0, h, 1.0, NB_TRANCHES,
                              SEUIL_REPLI, titre)
                if r:
                    rh, rt, ri, ex = r
                    obs.append((an, rh, rt, ri, ex, h))

    print(f"\n  {len(obs)} observations (date d'entree x titre x horizon)")

    # --- Resultats globaux ---
    print("\n" + "-" * 104)
    print("  1. GLOBAL — toutes dates, tous titres")
    print("-" * 104)
    print(f"\n  {'horizon':<10}{'n':>7}{'HOLD':>11}{'RENFORT':>11}{'vs HOLD':>11}"
          f"{'expo':>8}{'RENFORT ajuste':>16}{'vs ajuste':>11}")
    print("  " + "-" * 78)
    for h in HORIZONS:
        s = [o for o in obs if o[5] == h]
        if not s:
            continue
        rh = statistics.median(o[1] for o in s)
        rt = statistics.median(o[2] for o in s)
        ri = statistics.median(o[3] for o in s)
        ex = statistics.median(o[4] for o in s)
        print(f"  {h} ans{'':<5}{len(s):>7}{rh*100:>10.1f} %{rt*100:>10.1f} %"
              f"{(rt-rh)*100:>+10.1f} pt{ex*100:>7.0f} %{ri*100:>15.1f} %"
              f"{(ri-rh)*100:>+10.1f} pt")

    # --- Le decoupage qui repond a la question ---
    print("\n" + "-" * 104)
    print("  2. PAR REGIME — c'est ICI que se joue la reponse")
    print("-" * 104)
    for libelle, filtre in (("ENTREE EN ANNEE DE KRACH", lambda a: a in krachs),
                            ("ENTREE EN ANNEE NORMALE", lambda a: a not in krachs)):
        print(f"\n  ### {libelle}")
        print(f"\n  {'horizon':<10}{'n':>7}{'HOLD':>11}{'RENFORT':>11}{'vs HOLD':>11}"
              f"{'expo':>8}{'RENFORT ajuste':>16}{'vs ajuste':>11}")
        print("  " + "-" * 78)
        for h in HORIZONS:
            s = [o for o in obs if o[5] == h and filtre(o[0])]
            if len(s) < 15:
                print(f"  {h} ans{'':<5}{len(s):>7}   (echantillon trop petit)")
                continue
            rh = statistics.median(o[1] for o in s)
            rt = statistics.median(o[2] for o in s)
            ri = statistics.median(o[3] for o in s)
            ex = statistics.median(o[4] for o in s)
            gagn = sum(1 for o in s if o[2] > o[1]) / len(s) * 100
            print(f"  {h} ans{'':<5}{len(s):>7}{rh*100:>10.1f} %{rt*100:>10.1f} %"
                  f"{(rt-rh)*100:>+10.1f} pt{ex*100:>7.0f} %{ri*100:>15.1f} %"
                  f"{(ri-rh)*100:>+10.1f} pt")
            print(f"           {'':<7}{'':<11}{'':<11}{f'{gagn:.0f} % des cas':>11}")

    # --- Detail par annee d'entree, horizon 5 ans ---
    print("\n" + "-" * 104)
    print("  3. DETAIL PAR ANNEE D'ENTREE (horizon 5 ans) — les annees qui font la difference")
    print("-" * 104)
    print(f"\n  {'annee':<7}{'marche':>9}{'n':>6}{'HOLD':>11}{'RENFORT':>11}{'vs HOLD':>11}"
          f"{'expo':>8}")
    print("  " + "-" * 62)
    for a in sorted({o[0] for o in obs}):
        s = [o for o in obs if o[0] == a and o[5] == 5]
        if len(s) < 3:
            continue
        rh = statistics.median(o[1] for o in s)
        rt = statistics.median(o[2] for o in s)
        ex = statistics.median(o[4] for o in s)
        marque = " KRACH" if a in krachs else ""
        print(f"  {a:<7}{var_an[a]*100:>8.1f} %{len(s):>6}{rh*100:>10.1f} %"
              f"{rt*100:>10.1f} %{(rt-rh)*100:>+10.1f} pt{ex*100:>7.0f} %{marque}")

    # --- Verdict ---
    print("\n" + "=" * 104)
    print("  VERDICT")
    print("=" * 104)
    for h in (5, 10):
        sk = [o for o in obs if o[5] == h and o[0] in krachs]
        sn = [o for o in obs if o[5] == h and o[0] not in krachs]
        if len(sk) < 15 or len(sn) < 15:
            continue
        gk = sum(1 for o in sk if o[2] > o[1]) / len(sk) * 100
        gn = sum(1 for o in sn if o[2] > o[1]) / len(sn) * 100
        dk = (statistics.median(o[2] for o in sk) - statistics.median(o[1] for o in sk)) * 100
        dn = (statistics.median(o[2] for o in sn) - statistics.median(o[1] for o in sn)) * 100
        print(f"\n  Horizon {h} ans :")
        print(f"    entree en KRACH  : renfort gagne dans {gk:.0f} % des cas"
              f"  · ecart median {dk:+.1f} pt")
        print(f"    entree NORMALE   : renfort gagne dans {gn:.0f} % des cas"
              f"  · ecart median {dn:+.1f} pt")
    print("""
  RAPPEL DES LIMITES : biais du survivant (46 titres encore cotes sur 57), aucun
  dividende, granularite trimestrielle. Ces chiffres mesurent le PRIX, pas le revenu.""")
    print("=" * 104)

    out = chemin_data("validation_longue.json")
    out.write_text(json.dumps({"seuil": SEUIL_REPLI, "tranches": NB_TRANCHES,
                               "krachs": sorted(krachs),
                               "observations": len(obs)}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n  Ecrit : {out.name}")


if __name__ == "__main__":
    main()
