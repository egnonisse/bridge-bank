"""Mesure la couverture RELLE de l'historique fondamental disponible.

OBJECTIF
--------
Avant de s'engager dans une reconstitution des fondamentaux historiques, il
faut savoir ce qu'on peut reellement obtenir. Ce script interroge la source
pour chaque titre et mesure :
  - le nombre d'annees de dividendes connues (et la plage de dates)
  - si le BPA (EPS) historique est extractible
  - donc : quelle periode serait testable en point-in-time

C'est ce chiffre qui decide. Si la couverture est de 1-2 ans, le chantier ne
vaut pas son cout. Si elle est de 4-5 ans, il permet de tester les strategies
fondamentales honnetement.

Source : stockanalysis.com (pages dividend et financials, HTML public).
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
import urllib3
from pathlib import Path

import requests

urllib3.disable_warnings()

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "couverture_fondamentaux.json"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _get(url: str, essais: int = 2) -> str | None:
    for i in range(essais):
        try:
            r = requests.get(url, headers=H, timeout=40, verify=False)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        time.sleep(1.5)
    return None


def extraire_dividendes(html: str) -> list[dict]:
    """Extrait l'historique des dividendes du JSON embarque.

    Structure : history:[{dt:"2026-08-21",amt:"2,606.000 XOF",pay:"..."},...]
      dt  = date de DETACHEMENT (celle qui compte pour le point-in-time)
      amt = montant par action
    """
    if not html:
        return []
    i = html.find("history:[{")
    if i < 0:
        return []
    bloc = html[i:i + 8000]
    out = []
    for m in re.finditer(
            r'\{dt:"(\d{4}-\d{2}-\d{2})",\s*amt:"([0-9.,]+)\s*[A-Z]{3}"'
            r'(?:,\s*dec:"[^"]*")?(?:,\s*record:"([^"]*)")?(?:,\s*pay:"([^"]*)")?\}',
            bloc):
        dt, amt = m.group(1), m.group(2)
        try:
            val = float(amt.replace(",", ""))
        except ValueError:
            continue
        out.append({"ex_date": dt, "montant": val,
                    "record": m.group(3) or None, "paiement": m.group(4) or None})
    out.sort(key=lambda x: x["ex_date"])
    return out


def extraire_eps(html: str) -> dict[str, float]:
    """Extrait le BPA (EPS) par annee si present dans la page financials."""
    if not html:
        return {}
    out: dict[str, float] = {}
    # Les tableaux financiers listent des annees et des valeurs ; on cherche
    # la ligne EPS et on capture les nombres qui suivent.
    for m in re.finditer(r"EPS[^<]{0,40}", html, re.I):
        ctx = html[m.start():m.start() + 1200]
        vals = re.findall(r"(-?[0-9][0-9,]*\.?[0-9]*)", ctx)
        if len(vals) >= 3:
            # Annees presentes dans la page
            annees = re.findall(r"20[12]\d", ctx)
            for an, v in zip(annees, vals[:len(annees)]):
                try:
                    out.setdefault(an, float(v.replace(",", "")))
                except ValueError:
                    continue
            if out:
                break
    return out


def main():
    sys.path.insert(0, str(RACINE))
    from src.backtesting.challenge_validateur import charger_historique

    hist = charger_historique()
    codes = sorted(hist.keys())
    print("=" * 88)
    print("  COUVERTURE DE L'HISTORIQUE FONDAMENTAL (source externe)")
    print("=" * 88)
    print(f"\n  {len(codes)} titres a sonder\n")

    resultats = {}
    for i, code in enumerate(codes, 1):
        divs = extraire_dividendes(
            _get(f"https://stockanalysis.com/quote/brvm/{code}/dividend/") or "")
        eps_html = _get(f"https://stockanalysis.com/quote/brvm/{code}/financials/") or ""
        eps = extraire_eps(eps_html)

        annees = sorted({d["ex_date"][:4] for d in divs})
        resultats[code] = {
            "nb_dividendes": len(divs),
            "annees_dividendes": annees,
            "plage": [divs[0]["ex_date"], divs[-1]["ex_date"]] if divs else None,
            "dividendes": divs,
            "eps_annees": sorted(eps.keys()),
            "eps": eps,
        }
        pl = resultats[code]["plage"]
        print(f"  [{i:>2}/{len(codes)}] {code:<8} {len(divs):>2} dividende(s)  "
              f"{annees[0] if annees else '----'}-{annees[-1] if annees else '----'}  "
              f"EPS : {len(eps)} annee(s)")

    SORTIE.write_text(json.dumps(resultats, ensure_ascii=False, indent=1),
                      encoding="utf-8")

    # --- Bilan -----------------------------------------------------------
    print("\n" + "=" * 88)
    print("  BILAN DE COUVERTURE")
    print("=" * 88)

    avec_div = [c for c, r in resultats.items() if r["nb_dividendes"] >= 3]
    avec_eps = [c for c, r in resultats.items() if len(r["eps_annees"]) >= 3]
    annees_tot = [a for r in resultats.values() for a in r["annees_dividendes"]]

    print(f"\n  Titres avec >= 3 dividendes dates : {len(avec_div)}/{len(codes)}")
    print(f"  Titres avec >= 3 annees de BPA    : {len(avec_eps)}/{len(codes)}")

    if annees_tot:
        from collections import Counter
        c = Counter(annees_tot)
        print(f"\n  Annees couvertes (nombre de titres ayant un dividende cette annee-la) :")
        for a in sorted(c):
            barre = "#" * int(c[a] / 2)
            print(f"    {a}  {c[a]:>3}  {barre}")

    nb_div = [r["nb_dividendes"] for r in resultats.values()]
    print(f"\n  Dividendes par titre : median {statistics.median(nb_div):.0f}, "
          f"max {max(nb_div)}, min {min(nb_div)}")

    # Periode reellement testable
    annees_communes = [a for a, n in
                       __import__("collections").Counter(annees_tot).items() if n >= 20]
    if annees_communes:
        print(f"\n  >>> PERIODE TESTABLE EN POINT-IN-TIME : "
              f"{min(annees_communes)} a {max(annees_communes)} "
              f"({max(annees_communes) and len(annees_communes)} annees, "
              f"avec >= 20 titres)")
    print("=" * 88)
    print(f"\n  Ecrit : {SORTIE.name}")


if __name__ == "__main__":
    main()
