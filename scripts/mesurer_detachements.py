"""MESURE DU DETACHEMENT — le cours baisse-t-il vraiment du dividende ?

POURQUOI CE SCRIPT
------------------
Le revenu du noyau est mesure sur 2022-2026 (190 dividendes dates, 42 titres) :
+11,03 %/an. Sur 1998-2021, AUCUNE source gratuite ne donne l'historique des
dividendes (richbourse verrouille le sien derriere un abonnement Premium, la page
publique n'affiche que l'annee en cours ; les bulletins BOC de brvm.org existent
mais couvrent 28 annees de PDF). Le revenu sur 28 ans n'est donc PAS mesurable.

Ce qui EST mesurable, et qui sert directement : la BAISSE REELLE du cours au
detachement, sur les 190 cas dont on connait la date. Trois questions de LEO y
trouvent une reponse chiffree :

  1. Le cours baisse-t-il vraiment du montant du dividende au detachement ?
  2. De combien, et avec quelle dispersion (le marche « oublie »-t-il parfois) ?
  3. Quelle est la recuperation typique dans les jours qui suivent ?

Cela documente aussi une piste pour combler le trou : si la baisse au detachement
est un signal FIABLE et peu bruite, on pourrait a terme deduire les dividendes des
annees anciennes depuis les seuls cours. Le script mesure justement la fiabilite de
ce signal (rapport signal/bruit), pour dire si la piste tient ou non.
"""
import json
import pickle
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from src.infrastructure.paths import FUNDAMENTALS_HISTORIQUES, HISTORY_CACHE, chemin_data  # noqa: E402  (B2-09)


def main():
    fond = json.loads((FUNDAMENTALS_HISTORIQUES).read_text(encoding="utf-8"))
    h = pickle.load(open(HISTORY_CACHE, "rb"))

    # Index quotidien par titre
    series = {}
    for code, barres in h.items():
        d = {}
        for b in barres:
            dt = str(getattr(b, "date", ""))[:10].replace("-", "")
            c = getattr(b, "close", None) or getattr(b, "cours", None)
            if dt and c:
                d[dt] = float(c)
        if d:
            series[code] = dict(sorted(d.items()))
    jours_par_titre = {c: sorted(s) for c, s in series.items()}

    print("=" * 100)
    print("  LE COURS BAISSE-T-IL VRAIMENT DU DIVIDENDE AU DETACHEMENT ?")
    print("=" * 100)
    print(f"\n  {len(series)} titres dans le cache quotidien")

    cas = []
    for code, t in fond.items():
        divs = t.get("dividendes", []) if isinstance(t, dict) else []
        if not divs or code not in series:
            continue
        jours = jours_par_titre[code]
        for d in divs:
            ex = str(d.get("ex_date", "")).replace("-", "")
            montant = d.get("montant")
            if not ex or not montant:
                continue
            # Le premier jour de cotation >= date de detachement
            apres = [j for j in jours if j >= ex]
            if len(apres) < 11:
                continue
            j_ex = apres[0]
            i_ex = jours.index(j_ex)
            if i_ex < 1:
                continue
            j_av = jours[i_ex - 1]
            p_av, p_ex = series[code][j_av], series[code][j_ex]
            # Rendement attendu = montant / cours AVANT detachement
            attendu = montant / p_av
            observe = p_ex / p_av - 1
            # Recuperation a J+10 de cotation
            j10 = jours[i_ex + 10] if i_ex + 10 < len(jours) else jours[-1]
            recup = series[code][j10] / p_ex - 1
            cas.append({
                "code": code, "ex": ex, "montant": montant,
                "p_av": p_av, "p_ex": p_ex,
                "attendu": attendu, "observe": observe,
                "capture": attendu + observe, "recup10": recup,
            })

    print(f"  {len(cas)} detachements mesures (sur les 190 dates, ceux couverts par le cache quotidien)")

    # FILTRAGE DES CAS ABERRANTS — indispensable avant toute moyenne.
    # Deux familles d'anomalies, toutes deux verifiees :
    #  (a) dividende > 30 % du cours : soit une distribution exceptionnelle (FTSC
    #      53 %), soit une donnee corrompue. Ex. ETIT 2022-06-16 : montant 101 F
    #      pour un cours de ~15 F, soit 672 % — le montant n'est pas a l'echelle du
    #      cours de ce jour (division de nominal ou erreur de source). Un tel cas
    #      porte a lui seul une moyenne.
    #  (b) dividende < 0,5 % du cours : le montant est probablement en centimes ou
    #      la date decalee ; le signal est plus petit que le bruit de cotation.
    # On garde donc une bande [0,5 %, 30 %], et on signale combien de cas sont
    # ecartes plutot que de les taire.
    total_brut = len(cas)
    cas = [c for c in cas if 0.005 <= c["attendu"] <= 0.30]
    ecartes = total_brut - len(cas)
    print(f"  {ecartes} cas aberrants ecartes (dividende hors bande 0,5-30 %, "
          f"ex. ETIT a 672 % = montant non a l'echelle) -> {len(cas)} cas retenus")

    if not cas:
        print("  Aucun cas exploitable.")
        return

    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  1. BAISSE OBSERVEE AU DETACHEMENT vs DIVIDENDE ATTENDU")
    print("-" * 100)
    att = [c["attendu"] for c in cas]
    obs = [c["observe"] for c in cas]
    capt = [c["capture"] for c in cas]
    print(f"\n  dividende moyen (en % du cours) : {statistics.mean(att)*100:>7.2f} %"
          f"   median {statistics.median(att)*100:.2f} %")
    print(f"  baisse REELLE du cours le jour J : {statistics.mean(obs)*100:>7.2f} %"
          f"   median {statistics.median(obs)*100:.2f} %")
    cap_moy, cap_med = statistics.mean(capt), statistics.median(capt)
    # ATTENTION AU SIGNE. capture = dividende attendu + variation observee.
    #   capture > 0  => le cours a baisse MOINS que le dividende (le titre a tenu)
    #   capture < 0  => le cours a baisse PLUS que le dividende (le titre a decroche)
    # Conclure « la baisse est plus forte » sur une capture positive serait une
    # inversion de lecture — l'erreur a ete commise dans la premiere version.
    sens = ("le cours a baisse MOINS que le dividende — le titre a tenu"
            if cap_moy > 0 else
            "le cours a baisse PLUS que le dividende — le titre a decroche")
    print(f"\n  => capture moyenne : {cap_moy*100:+.2f} %  ·  mediane {cap_med*100:+.2f} %")
    print(f"     {sens}")
    neg = sum(1 for c in capt if c < 0)
    print(f"     cas ou l'achat la veille du detachement PERD : {neg}/{len(capt)}"
          f" ({neg/len(capt)*100:.0f} %)")

    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  2. RECUPERATION DANS LES 10 SEANCES SUIVANTES")
    print("-" * 100)
    rec = [c["recup10"] for c in cas]
    print(f"\n  variation mediane a J+10 : {statistics.median(rec)*100:+.2f} %"
          f"  ·  moyenne {statistics.mean(rec)*100:+.2f} %")
    pos = sum(1 for r in rec if r > 0)
    print(f"  seances ou le cours remonte : {pos}/{len(rec)} ({pos/len(rec)*100:.0f} %)")

    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  3. PISTE « DEDUIRE LE DIVIDENDE DE LA BAISSE » — TIENT-ELLE ?")
    print("-" * 100)
    # Signal = baisse observee ; bruit = ecart-type des variations normales du titre
    ratios = []
    for code in {c["code"] for c in cas}:
        s = series[code]
        j = jours_par_titre[code]
        var = [s[j[i]] / s[j[i - 1]] - 1 for i in range(1, len(j)) if s[j[i - 1]]]
        if len(var) > 30:
            ecart = statistics.pstdev(var)
            div_moy = statistics.mean([c["attendu"] for c in cas if c["code"] == code])
            if ecart:
                ratios.append(div_moy / ecart)
    if ratios:
        print(f"\n  rapport dividende / volatilite quotidienne (mediane) : "
              f"{statistics.median(ratios):.2f}")
        print(f"""
  LECTURE : un rapport proche de 1 signifie que la baisse au detachement est du
  meme ordre que le bruit quotidien du titre — impossible a isoler. Un rapport
  > 3 serait un signal exploitable.

  VERDICT sur la piste : {"NON EXPLOITABLE — signal confondu avec le bruit" if statistics.median(ratios) < 3 else "exploitable, a approfondir"}.
  Le trou 1998-2021 du revenu reste donc OUVERT : aucune reconstitution honnete
  des dividendes anciens n'est possible avec les seules donnees gratuites.""")

    # ------------------------------------------------------------------
    print("\n" + "-" * 100)
    print("  4. LES CAS LES PLUS INSTRUCTIFS")
    print("-" * 100)
    cas.sort(key=lambda c: c["capture"])
    print(f"\n  {'code':<7}{'detach.':<10}{'divid.':>9}{'attendu':>10}{'observe':>10}{'capture':>10}")
    print("  " + "-" * 56)
    for c in cas[-5:]:
        print(f"  {c['code']:<7}{c['ex']:<10}{c['montant']:>9,.0f}{c['attendu']*100:>9.2f} %"
              f"{c['observe']*100:>9.2f} %{c['capture']*100:>+9.2f} %")
    print("  " + "-" * 56)
    for c in cas[:5]:
        print(f"  {c['code']:<7}{c['ex']:<10}{c['montant']:>9,.0f}{c['attendu']*100:>9.2f} %"
              f"{c['observe']*100:>9.2f} %{c['capture']*100:>+9.2f} %")

    out = chemin_data("mesure_detachements.json")
    out.write_text(json.dumps({"n": len(cas),
                               "baisse_mediane_pct": round(statistics.median(obs) * 100, 3),
                               "capture_mediane_pct": round(statistics.median(capt) * 100, 3),
                               "perte_pct_cas": round(neg / len(capt) * 100, 1),
                               "ratio_signal_bruit": round(statistics.median(ratios), 2) if ratios else None,
                               "cas": cas}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  Ecrit : {out.name}")
    print("=" * 100)


if __name__ == "__main__":
    main()
