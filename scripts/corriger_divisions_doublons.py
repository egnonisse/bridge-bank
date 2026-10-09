"""CORRECTION : supprimer la division SLBC fabriquee, et controler les doublons.

CE QUI S'EST PASSE
------------------
Richbourse (source officielle) ne liste qu'UNE division pour SLBC :
  30 Septembre 2024 — 10 nouvelles pour 1 ancienne.

Or `data/divisions_officielles.json` en contient DEUX :
  2024-03-27 — 5 nouvelles pour 1 ancienne   <-- ajoutee par une mesure
                                                heuristique (« les cours la
                                                revelent »), jamais publiee
  2024-09-30 — 10 nouvelles pour 1 ancienne  <-- la vraie

L'effet mesure sur les prix : le cours du 30/12/2022 est a 1 665 F dans le cache
contre 83 250 F dans les releves officiels de la BRVM — un facteur d'erreur de
50 (5 x 10). Consequence : SLBC affichait une progression de x13 sur 4 ans, et le
test du noyau rendait +366 % sur la periode. Chiffres entierement fabriques.

Une mesure heuristique ne doit JAMAIS etre melangee a une donnee publiee : quand
les deux divergent, c'est la source publiee qui tranche, ou l'entree est retiree.

CE QUE FAIT CE SCRIPT
---------------------
1. Repere les titres ayant plusieurs divisions rapprochees (doublon probable).
2. Retire l'entree SLBC du 2024-03-27 (avec sauvegarde du fichier).
3. Affiche l'etat final des divisions par titre pour verification.

Ce script ne reconstruit pas l'historique : c'est le role de
`scripts/preparer_historique_propre.py`, a relancer ensuite.
"""
import json
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "divisions_officielles.json"

# Entrees retirees : (code, date) — motif documente
A_RETIRER = [
    ("SLBC", "2024-03-27"),
]


def _parse(d: str) -> date:
    return date(*(int(x) for x in d.split("-")))


def main():
    if not FICHIER.exists():
        raise SystemExit("divisions_officielles.json absent")

    d = json.loads(FICHIER.read_text(encoding="utf-8"))
    divs = d.get("divisions", [])

    print("=" * 92)
    print("  CONTROLE DES DOUBLONS DE DIVISION")
    print("=" * 92)

    par_code: dict[str, list] = defaultdict(list)
    for x in divs:
        par_code[x["code"]].append(x)

    suspects = []
    for code, ls in sorted(par_code.items()):
        if len(ls) < 2:
            continue
        ls = sorted(ls, key=lambda x: x["date"])
        for i in range(1, len(ls)):
            jours = (_parse(ls[i]["date"]) - _parse(ls[i - 1]["date"])).days
            if jours <= 400:
                suspects.append((code, ls[i - 1], ls[i], jours))

    if suspects:
        print(f"\n  {len(suspects)} paire(s) rapprochee(s) — doublon probable :\n")
        for code, a, b, jours in suspects:
            print(f"    {code} : {a['date']} (x{a['facteur']}) puis "
                  f"{b['date']} (x{b['facteur']})  —  {jours} jours d'ecart")
            print(f"       effet cumule si les deux sont gardees : "
                  f"x{a['facteur'] * b['facteur']:.0f} sur les cours anterieurs")
    else:
        print("\n  Aucune paire rapprochee.")

    # --- Retrait ------------------------------------------------------
    print("\n" + "=" * 92)
    print("  RETRAIT DES ENTREES FABRIQUEES")
    print("=" * 92)

    avant = len(divs)
    retires = []
    restants = []
    for x in divs:
        if (x["code"], x["date"]) in A_RETIRER:
            retires.append(x)
        else:
            restants.append(x)

    if not retires:
        print("\n  Aucune entree a retirer (deja corrige).")
        return

    backup = FICHIER.with_suffix(".json.bak-avant-correction")
    shutil.copy2(FICHIER, backup)
    print(f"\n  Sauvegarde : {backup.name}")

    d["divisions"] = restants
    d["_correction_07_10_2026"] = {
        "retirees": [
            {"code": x["code"], "date": x["date"], "facteur": x["facteur"],
             "motif": "mesure heuristique confondue avec une donnee publiee : "
                      "la fiche officielle ne liste pas cette operation"}
            for x in retires
        ],
        "effet": "SLBC etait divise par 50 au lieu de 10 sur les cours "
                 "anterieurs a mars 2024 (progression x13 fabriquee)",
    }
    FICHIER.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                       encoding="utf-8")

    print(f"  Retirees  : {len(retires)}")
    for x in retires:
        print(f"     {x['code']} {x['date']} facteur x{x['facteur']}")
    print(f"  Divisions : {avant} -> {len(restants)}")

    # --- Etat final ---------------------------------------------------
    print("\n" + "=" * 92)
    print("  SLBC APRES CORRECTION")
    print("=" * 92)
    for x in [y for y in restants if y["code"] == "SLBC"]:
        print(f"    {x['date']} — {x['nouvelles']} nouvelles pour "
              f"{x['anciennes']} ancienne(s)  -> cours divise par {x['facteur']}")

    print("\n" + "=" * 92)
    print("  PROCHAINE ETAPE : relancer scripts/preparer_historique_propre.py")
    print("  puis revalider contre les releves officiels de la BRVM.")
    print("=" * 92)


if __name__ == "__main__":
    main()
