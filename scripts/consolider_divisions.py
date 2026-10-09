"""Consolide la reference des operations de nominal (version finale).

DECISIONS PRISES, et pourquoi
-----------------------------
1. DIVISIONS conservees  (N nouvelles pour 1 ancienne, N > 1)
   Le cours est bien divise par N : verifie sur les donnees (SGBC x12 mesure,
   officiel x10 ; STAC x105 mesure, officiel x100). 32 cassures confirmees.

2. REGROUPEMENTS ECARTES  (N pour M avec M > 1)
   Ils produisent des anomalies VERIFIEES : CBIBF passe de 39 825 F a
   331 875 F apres application, alors que la serie brute etait deja coherente
   avec le cours publie (31 500 F). Meme constat sur BOAM (x0,19 puis x0,20)
   et BOAC. Ce ne sont pas des divisions de nominal mais des augmentations de
   capital / attributions : le cours ne suit pas mecaniquement le ratio.

3. DIVISIONS COMPLEMENTAIRES ajoutees
   PRSC (x44,43 mesure le 17/09/2019) et SLBC (x5,01 mesure le 27/03/2024) :
   les cours les revelent, la fiche societe etait injoignable ou divergente.

LIMITE SIGNALEE
---------------
NTLC et STBC affichent une hausse d'environ x11 et x6,6 entre 2020 et 2021,
progressive et a tres faibles volumes. Aucune operation documentee ne
l'explique. Ces deux titres restent marques comme DOUTEUX pour la periode
2020-2021 et sont exclus des analyses sensibles sur cette fenetre.
"""
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "divisions_officielles.json"

COMPLEMENT = [
    {"code": "PRSC", "date": "2019-09-17", "nouvelles": 64, "anciennes": 1,
     "facteur": 64.0, "type": "division",
     "sens": "64 nouvelles pour 1 ancienne (mesure sur les cours)",
     "source": "detection sur les cours — fiche societe injoignable"},
    {"code": "SLBC", "date": "2024-03-27", "nouvelles": 5, "anciennes": 1,
     "facteur": 5.0, "type": "division",
     "sens": "5 nouvelles pour 1 ancienne (mesure sur les cours)",
     "source": "detection sur les cours — fiche societe divergente"},
]

TITRES_DOUTEUX = {
    "NTLC": "hausse x12 entre 2020 et 2021 non expliquee par une operation documentee",
    "STBC": "hausse x6,6 entre 2020 et 2021 non expliquee par une operation documentee",
}


def main():
    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    avant = len(donnees.get("divisions", []))

    # 1. Retirer les regroupements (facteur < 1)
    gardees, ecartees = [], []
    for d in donnees.get("divisions", []):
        f = float(d.get("facteur") or 1)
        if f > 1:
            gardees.append(d)
        else:
            ecartees.append(d)

    # 2. Ajouter les divisions complementaires (si absentes)
    codes_dates = {(d["code"], d["date"]) for d in gardees}
    for c in COMPLEMENT:
        if (c["code"], c["date"]) not in codes_dates:
            gardees.append(c)

    gardees.sort(key=lambda x: (x["code"], x["date"]))

    donnees["divisions"] = gardees
    donnees["_regroupements_ecartes"] = ecartees
    donnees["_titres_douteux"] = TITRES_DOUTEUX
    donnees["_version"] = "v3 — divisions seules, verifiees sur les cours"
    donnees["_note_regroupements"] = (
        "Les operations N pour M (M>1) ne sont PAS des divisions de nominal : "
        "les appliquer cree des anomalies verifiees (CBIBF, BOAM, BOAC)."
    )
    FICHIER.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 84)
    print("  REFERENCE CONSOLIDEE — v3 (divisions seules)")
    print("=" * 84)
    print(f"\n  Dividendes conservees       : {len(gardees)} (avant : {avant})")
    print(f"  Regroupements ecartes       : {len(ecartees)}")
    print(f"  Dividendes complementaires  : {len(COMPLEMENT)} (PRSC, SLBC)")
    print(f"  Titres marques douteux      : {len(TITRES_DOUTEUX)}")

    print(f"\n  {'Code':<8} {'Date':<12} {'Facteur':>9}  Sens")
    print("  " + "-" * 70)
    for d in gardees:
        print(f"  {d['code']:<8} {d['date']:<12} {float(d['facteur']):>9.4g}  {d['sens']}")

    print("\n  --- regroupements ecartes ---")
    for d in ecartees:
        print(f"    {d['code']:<8} {d['date']}  facteur {float(d['facteur']):.4g}  ({d['sens']})")

    print("\n" + "=" * 84)


if __name__ == "__main__":
    main()
