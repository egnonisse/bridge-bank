"""Croisement des prix avec la source OFFICIELLE BRVM (bfin.brvm.org).

POURQUOI
--------
Toute l'analyse reposait sur UNE source de prix (BSTrade). Une source unique
ne se verifie pas elle-meme : un decalage systematique passerait inapercu.
La regle du projet est >= 3 sources croisees ; ce script realise le croisement
qui compte vraiment — contre la BOURSE elle-meme.

SOURCE
------
`bfin.brvm.org/Activites_marche.aspx` publie, pour chaque journee de cotation,
le tableau officiel : Code | Designation | Pays | Cours precedent | Cours jour
| Volume echange | Nombre transactions. La page est PUBLIQUE (les fiches
emetteur, elles, exigent un abonnement). Le choix de la journee passe par un
postback ASP.NET (__VIEWSTATE / __EVENTVALIDATION).

METHODE
-------
1. GET la page, extraire les champs caches et la liste des journees.
2. POST pour chaque date d'echantillon -> tableau des 47 actions.
3. Comparer au cache BSTrade sur les memes dates.

Sortie : `data/croisement_officiel.json`
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from src.infrastructure.paths import HISTORY_BRUT, chemin_data  # noqa: E402  (B2-09)

PAGE = "https://bfin.brvm.org/Activites_marche.aspx"
SORTIE = chemin_data("croisement_officiel.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _nombre(txt: str):
    """« 31 600 » -> 31600.0 ; vide -> None."""
    t = re.sub(r"[^\d,.\-]", "", (txt or "").replace("\u00a0", ""))
    if not t or t in ("-", "."):
        return None
    t = t.replace(" ", "").replace(",", "")
    try:
        v = float(t)
        return v if v > 0 else None
    except ValueError:
        return None


def _session():
    cj = CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA),
                     ("Accept-Language", "fr-FR,fr;q=0.9"),
                     ("Accept", "text/html,application/xhtml+xml")]
    return op


def charger_formulaire(op):
    """GET la page et extrait les champs caches + les journees proposees."""
    with op.open(PAGE, timeout=60) as r:
        html = r.read().decode("utf-8", errors="replace")

    caches = {}
    for nom in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
                "__VIEWSTATEFIELDCOUNT", "__LASTFOCUS"):
        m = re.search(rf'name="{nom}"[^>]*value="([^"]*)"', html)
        if m:
            caches[nom] = m.group(1)
    # __VIEWSTATE peut etre decoupe en __VIEWSTATE1, __VIEWSTATE2...
    for m in re.finditer(r'name="(__VIEWSTATE\d+)"[^>]*value="([^"]*)"', html):
        caches[m.group(1)] = m.group(2)

    # Les journees : le select qui contient des dates JJ/MM/AAAA
    journees = []
    for sel in re.findall(r"<select[^>]*>(.*?)</select>", html, re.S | re.I):
        opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', sel)
        dates = [(v, t.strip()) for v, t in opts
                 if re.match(r"^\d{2}/\d{2}/\d{4}$", t.strip())]
        if len(dates) > len(journees):
            journees = dates
    return html, caches, journees


def extraire_cotation(html: str) -> dict[str, dict]:
    """Extrait {code: {cours, precedent, volume, transactions}} du tableau officiel."""
    out = {}
    for tab in re.findall(r"<table.*?</table>", html, re.S | re.I):
        lignes = re.findall(r"<tr.*?</tr>", tab, re.S | re.I)
        if not lignes:
            continue
        entete = " ".join(
            re.sub(r"<[^>]+>", " ", c).lower()
            for c in re.findall(r"<t[dh].*?</t[dh]>", lignes[0], re.S | re.I)
        )
        if "cours jour" not in entete and "cours precedent" not in entete:
            continue
        for l in lignes[1:]:
            brut = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", l, re.S | re.I)
            # La 1re cellule est un bouton <input type="image"> : sans texte.
            # On nettoie, puis on retire les cellules vides.
            cells = [re.sub(r"<[^>]+>", " ", c).replace("&nbsp;", " ").strip()
                     for c in brut]
            cells = [re.sub(r"\s+", " ", c) for c in cells]
            propres = [c for c in cells if c]
            if len(propres) < 3:
                continue
            # Le code titre = premier element purement alphabetique (4-6 lettres)
            idx_code = None
            for k, c in enumerate(propres):
                if re.match(r"^[A-Za-z]{4,6}$", c):
                    idx_code = k
                    break
            if idx_code is None:
                continue
            code = propres[idx_code].strip().upper()
            if code in out:
                continue
            nums = [_nombre(c) for c in propres[idx_code + 1:]]
            nums = [n for n in nums if n is not None]
            if len(nums) < 2:
                continue
            precedent, cours = nums[0], nums[1]
            volume = nums[2] if len(nums) > 2 else None
            trans = nums[3] if len(nums) > 3 else None
            out[code] = {"precedent": precedent, "cours": cours,
                         "volume": volume, "transactions": trans}
        if out:
            break
    return out


def cotations_du_jour(op, caches: dict, journee: str, select_id: str) -> dict:
    """POST pour une journee donnee et retourne la cotation."""
    donnees = dict(caches)
    donnees.update({
        "__EVENTTARGET": select_id,
        "__EVENTARGUMENT": "",
        select_id: journee,
    })
    corps = urllib.parse.urlencode(donnees).encode("utf-8")
    req = urllib.request.Request(PAGE, data=corps, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Referer", PAGE)
    req.add_header("Origin", "https://bfin.brvm.org")
    with op.open(req, timeout=90) as r:
        html = r.read().decode("utf-8", errors="replace")
    return extraire_cotation(html), html


def main():
    import pickle

    with open(HISTORY_BRUT, "rb") as fh:
        hist = pickle.load(fh)

    print("=" * 88)
    print("  CROISEMENT OFFICIEL — BSTrade (cache)  x  BRVM bfin.brvm.org")
    print("=" * 88)

    op = _session()
    print("\n  [1] Chargement du formulaire officiel...")
    html, caches, journees = charger_formulaire(op)
    print(f"      champs caches : {len(caches)}")
    print(f"      journees disponibles : {len(journees)}")
    if journees:
        print(f"      plage : {journees[-1][1]} -> {journees[0][1]}")

    if not journees:
        raise SystemExit("Aucune journee trouvee — structure de page inattendue.")

    # Selecteur de la liste des journees
    m = re.search(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S | re.I)
    select_id = m.group(1) if m else "ctl00$Main$DropDownList1"
    # Verifier que c'est bien celui des dates
    for sm in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S | re.I):
        if re.search(r"\d{2}/\d{2}/\d{4}", sm.group(2)):
            select_id = sm.group(1)
            break
    print(f"      selecteur : {select_id}")

    # Echantillon : dates presentes dans le cache (fin de serie surtout)
    fin_cache = max(str(b.date)[:10] for b in hist.get("SGBC", []))
    print(f"\n  [2] Derniere date du cache BSTrade : {fin_cache}")

    # Choisir des journees proches de la fin du cache + quelques anciennes
    a_croiser = []
    for v, t in journees:
        d_iso = f"{t[6:10]}-{t[3:5]}-{t[0:2]}"
        a_croiser.append((d_iso, v, t))
    a_croiser.sort(reverse=True)

    # Garder 1 journee sur ~6 mois : echantillon regulier
    echantillon = []
    annee_vue = set()
    for d_iso, v, t in a_croiser:
        if d_iso <= fin_cache:
            an = d_iso[:4]
            if an not in annee_vue or len(echantillon) < 12:
                echantillon.append((d_iso, v, t))
                annee_vue.add(an)
    echantillon = echantillon[:15]

    print(f"\n  [3] Echantillon de {len(echantillon)} journee(s) :")
    for d_iso, v, t in echantillon:
        print(f"      {t}  ({d_iso})")

    resultats = []
    print(f"\n  [4] Interrogation de la source officielle...\n")
    for d_iso, v, t in echantillon:
        try:
            cot, _ = cotations_du_jour(op, caches, v, select_id)
            if not cot:
                print(f"      {d_iso}  aucun titre extrait")
                continue

            # Comparer avec le cache
            ecarts, comparaisons = [], 0
            details = []
            for code, vals in cot.items():
                bs = hist.get(code)
                if not bs:
                    continue
                c_cache = None
                for b in reversed(bs):
                    if str(b.date)[:10] == d_iso:
                        c_cache = float(b.close)
                        break
                if c_cache is None:
                    continue
                comparaisons += 1
                e = (vals["cours"] / c_cache - 1) * 100 if c_cache else None
                if e is not None:
                    ecarts.append(abs(e))
                    if abs(e) > 0.01:
                        details.append({"code": code, "officiel": vals["cours"],
                                        "cache": c_cache, "ecart_pct": round(e, 4)})

            med = statistics.median(ecarts) if ecarts else None
            mx = max(ecarts) if ecarts else None
            resultats.append({
                "date": d_iso, "journee": t,
                "titres_officiel": len(cot), "comparaisons": comparaisons,
                "ecart_median_pct": round(med, 4) if med is not None else None,
                "ecart_max_pct": round(mx, 4) if mx is not None else None,
                "nb_divergences": len(details), "details": details[:10],
            })
            print(f"      {d_iso}  {len(cot):>3} titres officiels, {comparaisons:>3} compares  "
                  f"ecart median {med if med is None else round(med,4)} %  "
                  f"max {mx if mx is None else round(mx,4)} %")
        except Exception as e:
            print(f"      {d_iso}  ERREUR : {str(e)[:70]}")
        time.sleep(1.5)

    SORTIE.write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + "=" * 88)
    print("  BILAN")
    print("=" * 88)
    valides = [r for r in resultats if r["comparaisons"] > 0]
    if valides:
        toutes = [r["ecart_median_pct"] for r in valides if r["ecart_median_pct"] is not None]
        maxis = [r["ecart_max_pct"] for r in valides if r["ecart_max_pct"] is not None]
        print(f"\n  Journees comparees        : {len(valides)}")
        print(f"  Comparaisons titre/date   : {sum(r['comparaisons'] for r in valides):,}")
        print(f"  Ecart MEDIAN global       : {statistics.median(toutes):.4f} %")
        print(f"  Ecart MAXIMAL global      : {max(maxis):.4f} %")
        div = sum(r["nb_divergences"] for r in valides)
        print(f"  Divergences (> 0,01 %)    : {div}")
        if div:
            print("\n  --- divergences a examiner ---")
            for r in valides:
                for d in r["details"][:4]:
                    print(f"    {r['date']}  {d['code']:<7} officiel {d['officiel']:>10,.0f}  "
                          f"cache {d['cache']:>10,.0f}  ({d['ecart_pct']:+.3f} %)")
    else:
        print("\n  Aucune comparaison possible.")
    print(f"\n  Ecrit : {SORTIE.name}")
    print("=" * 88)


if __name__ == "__main__":
    main()
