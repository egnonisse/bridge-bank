"""DETECTION DES SAUTS ANORMAUX du cache de prix.

POURQUOI
--------
Le noyau a rendu +366 % sur 4 ans, ce qui est impossible sur la BRVM. La cause :
SLBC passe de 2 886 F (2022) a 37 500 F (2026) — un facteur 13. Aucune division
n'explique cela : c'est un REGROUPEMENT (division inversee) non applique, qui
multiplie mecaniquement le cours.

Ces regroupements avaient ete ECARTES volontairement, au motif que « le cours ne
suit pas le ratio ». C'est faux pour certains titres, et l'erreur fabrique de
fausses croissances spectaculaires — donc de faux rendements dans TOUT ce qui
utilise cet historique : test du noyau, regles du challenge, radar, noyau-check.

CE QUE FAIT CE SCRIPT
---------------------
Repere les variations aberrantes entre deux seances consecutives, dans les deux
sens, et les classe :
  - hausse > +150 % en une seance  -> regroupement probable, non applique ;
  - baisse < -60 % en une seance   -> division probable, non appliquee.
Puis il chiffre l'ampleur du probleme titre par titre afin de trancher.

Ce script ne corrige rien : il mesure. La correction se decide apres.
"""
import pickle
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from src.infrastructure.paths import HISTORY_CACHE  # noqa: E402  (B2-09)

SEUIL_HAUSSE = 1.50     # +150 % en une seance
SEUIL_BAISSE = -0.60    # -60 % en une seance


def main():
    h = pickle.loads((HISTORY_CACHE).read_bytes())

    print("=" * 100)
    print("  SAUTS ANORMAUX DANS LE CACHE DE PRIX")
    print("=" * 100)
    print(f"\n  Seuils : hausse > +{SEUIL_HAUSSE*100:.0f} % ou baisse < {SEUIL_BAISSE*100:.0f} % "
          f"en UNE seance\n")

    suspects: dict[str, list] = {}
    for code, barres in sorted(h.items()):
        dates = [str(getattr(b, "date", ""))[:10] for b in barres]
        cl = [float(getattr(b, "close", 0) or 0) for b in barres]
        n = len(cl)
        for i in range(1, n):
            a, b = cl[i - 1], cl[i]
            if not a or not b:
                continue
            v = b / a - 1
            if v > SEUIL_HAUSSE or v < SEUIL_BAISSE:
                suspects.setdefault(code, []).append(
                    (dates[i], a, b, v))
        # Deuxieme signal : amplitude totale sur la periode 2022->fin
        i0 = next((k for k, d in enumerate(dates) if d >= "2022-01-01"), None)
        if i0 is not None and cl[i0] and cl[-1]:
            amp = cl[-1] / cl[i0]
            if amp > 6:
                suspects.setdefault(code, []).append(
                    ("AMPLITUDE", cl[i0], cl[-1], amp - 1))

    if not suspects:
        print("  ✅ Aucun saut anormal detecte.")
        return

    print(f"  {len(suspects)} TITRE(S) SUSPECT(S)\n")
    print(f"  {'Titre':<8} {'date':<12} {'avant':>11} {'apres':>11} {'variation':>11}  lecture")
    print("  " + "-" * 88)
    for code, evenements in sorted(suspects.items()):
        for (d, a, b, v) in evenements:
            if d == "AMPLITUDE":
                lecture = f"AMPLITUDE x{b/a:.1f} sur la periode"
                print(f"  {code:<8} {'2022->fin':<12} {a:>11,.0f} {b:>11,.0f} "
                      f"{v*100:>10.0f}%  {lecture}")
            else:
                if v > 0:
                    fac = b / a
                    lecture = f"REGROUPEMENT ? facteur x{fac:.2f}"
                else:
                    fac = a / b
                    lecture = f"division ? facteur x{fac:.2f}"
                print(f"  {code:<8} {d:<12} {a:>11,.0f} {b:>11,.0f} "
                      f"{v*100:>10.1f}%  {lecture}")
        print()

    # Synthese
    print("=" * 100)
    print("  LECTURE")
    print("=" * 100)
    hausses = sum(1 for ev in suspects.values() for e in ev if e[3] > 0 and e[0] != "AMPLITUDE")
    baisses = sum(1 for ev in suspects.values() for e in ev if e[3] < 0 and e[0] != "AMPLITUDE")
    print(f"\n  Sauts a la hausse (regroupements probables) : {hausses}")
    print(f"  Sauts a la baisse (divisions probables)     : {baisses}")
    print(f"  Titres concernes                            : {len(suspects)}/{len(h)}")
    print(f"\n  ⚠️  Un regroupement non applique fabrique une FAUSSE croissance :")
    print(f"      le titre parait multiplier par 10 alors qu'il a simplement")
    print(f"      consolide son nominal. Tout rendement calcule sur cet historique")
    print(f"      est gonfle du meme facteur.")
    print("=" * 100)


if __name__ == "__main__":
    main()
