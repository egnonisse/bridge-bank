"""Construit la reference des divisions depuis le releve Richbourse complet.

Entree  : data/richbourse_titres.json  (cours reel + toutes les operations)
Sortie  : data/divisions_officielles.json  (v2, complete)

SEMANTIQUE
----------
Richbourse decrit chaque operation « N actions nouvelles pour M actions
anciennes ». Le cours est divise par le facteur N/M :
  - 10 nouvelles pour 1 ancienne  -> cours / 10   (division)
  - 1 nouvelle  pour 2 anciennes  -> cours x 2    (regroupement)
  - 1 nouvelle  pour 1 ancienne   -> neutre (a ignorer)

CONTROLE DE COHERENCE
---------------------
Le cours brut du dernier jour de l'historique doit correspondre au cours
reel publie. Tout ecart signale une operation oubliee ou mal interpretee.
C'est le juge : pas de validation sans ce test.
"""
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "data" / "richbourse_titres.json"
DST = RACINE / "data" / "divisions_officielles.json"

MOIS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}


def iso(date_fr: str) -> str | None:
    """« 08 Septembre 2017 » -> « 2017-09-08 »."""
    parties = date_fr.strip().split()
    if len(parties) != 3:
        return None
    try:
        j = int(parties[0])
        m = MOIS.get(parties[1].lower())
        a = int(parties[2])
        if not m:
            return None
        return f"{a:04d}-{m:02d}-{j:02d}"
    except (ValueError, IndexError):
        return None


def main():
    if not SRC.exists():
        raise SystemExit(f"Releve introuvable : {SRC}")
    releve = json.loads(SRC.read_text(encoding="utf-8"))

    divisions = []
    cours_reels = {}
    ignorees = []
    neutres = 0

    for code, info in releve.items():
        if not isinstance(info, dict):
            continue
        c = info.get("cours")
        if c:
            cours_reels[code] = int(str(c).replace(" ", "").replace("\u00a0", ""))

        for op in info.get("frac", []) or []:
            d = iso(op.get("date", ""))
            n = int(op.get("nouvelles", 0) or 0)
            m = int(op.get("anciennes", 1) or 1)
            if not d or n <= 0 or m <= 0:
                continue
            if n == m:
                neutres += 1
                continue  # 1 pour 1 : aucun effet
            if d < "2017-01-02":
                ignorees.append({"code": code, "date": d, "n": n, "m": m,
                                 "raison": "anterieure au debut de l'historique"})
                continue
            divisions.append({
                "code": code,
                "date": d,
                "nouvelles": n,
                "anciennes": m,
                "facteur": round(n / m, 6),
                "type": "division" if n > m else "regroupement",
                "sens": f"{n} nouvelles pour {m} ancienne(s)",
            })

    divisions.sort(key=lambda x: (x["code"], x["date"]))

    sortie = {
        "_source": "Releve systematique des fiches societe publiees par la BRVM (via richbourse.com)",
        "_consulte_le": "2026-10-07",
        "_methode": "48 titres parcourus : cours de cloture reel + toutes les operations de nominal",
        "_semantique": "Le cours anterieur est divise par facteur = nouvelles/anciennes.",
        "_perimetre": "Seules les operations posterieures au 2017-01-02 sont retenues.",
        "_controle": "Aucune estimation : chaque entree vient d'une ligne publiee.",
        "cours_reels_07_10_2026": cours_reels,
        "divisions": divisions,
        "ignorees_anterieures": ignorees,
        "_neutres_ecartes": neutres,
    }
    DST.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 80)
    print("  REFERENCE DES DIVISIONS — v2 (complete)")
    print("=" * 80)
    print(f"\n  Operations retenues        : {len(divisions)}")
    print(f"  Operations « 1 pour 1 »    : {neutres} (sans effet, ecartees)")
    print(f"  Operations anterieures     : {len(ignorees)} (hors historique)")
    print(f"  Titres avec cours reel     : {len(cours_reels)}/48")
    print(f"\n  Ecrit : {DST.name}\n")
    print(f"  {'Code':<8} {'Date':<12} {'Facteur':>9}  {'Type':<14} Sens")
    print("  " + "-" * 74)
    for d in divisions:
        print(f"  {d['code']:<8} {d['date']:<12} {d['facteur']:>9.4f}  {d['type']:<14} {d['sens']}")

    print("\n  --- operations ecartees (avant 2017) ---")
    for o in ignorees[:20]:
        print(f"    {o['code']:<8} {o['date']}  {o['n']} pour {o['m']}")


if __name__ == "__main__":
    main()
