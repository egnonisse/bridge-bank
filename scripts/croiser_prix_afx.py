"""Croisement des prix : BSTrade (cache) contre AFX — deux sources independantes.

POURQUOI
--------
Toute l'analyse reposait sur UNE seule source de prix (BSTrade). Une source
unique ne se verifie pas elle-meme : un decalage systematique passerait
inapercu et fausserait drawdowns, rendements et backtests.

La regle du projet est >= 3 sources croisees. Ce script fait le premier
croisement reel sur les PRIX.

SOURCE INDEPENDANTE
-------------------
`afx.kwayisi.org/brvm/<code>.html` publie un tableau
`Date | Volume | Close | Change | Change%` en HTML simple, accessible sans cle.

METHODE
-------
Pour chaque titre : on extrait la serie AFX, puis on la compare barre a barre
avec le cache sur les dates communes. On mesure :
  - le nombre de dates communes
  - l'ecart relatif du cours de cloture (median, max)
  - l'ecart relatif du volume
Sortie : `data/croisement_prix.json` + rapport lisible.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://afx.kwayisi.org/brvm/{}.html"
SORTIE = RACINE / "data" / "croisement_prix.json"


def _nombre(txt: str) -> float | None:
    """« 38,990 » ou « 5,987 » -> float."""
    txt = txt.strip().replace(",", "").replace("\u00a0", "").replace(" ", "")
    if not txt or txt in ("-", "N/A"):
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def telecharger(code: str, essais: int = 3) -> str | None:
    url = BASE.format(code.lower())
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i < essais - 1:
                time.sleep(2)
    return None


def extraire_serie(html_txt: str) -> dict[str, dict]:
    """Extrait {date: {close, volume}} du tableau AFX."""
    serie: dict[str, dict] = {}
    # Les lignes ont la forme : <tr><td>2026-09-30<td>2,986<td>38,990<td>...
    for ligne in re.findall(r"<tr>(.*?)(?=<tr>|</tbody>)", html_txt, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)(?=<td|$)", ligne, re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if len(cells) < 3:
            continue
        d = cells[0]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            continue
        vol = _nombre(cells[1])
        cl = _nombre(cells[2])
        if cl is None:
            continue
        serie[d] = {"close": cl, "volume": vol}
    return serie


def croiser(code: str, barres_cache: list) -> dict:
    """Compare la serie AFX et le cache BSTrade pour un titre."""
    html_txt = telecharger(code)
    if not html_txt:
        return {"code": code, "statut": "source_injoignable"}

    afx = extraire_serie(html_txt)
    if not afx:
        return {"code": code, "statut": "aucune_donnee_extraite"}

    cache = {}
    for b in barres_cache:
        d = str(getattr(b, "date", ""))[:10]
        c = getattr(b, "close", None)
        if d and c:
            cache[d] = {"close": float(c), "volume": getattr(b, "volume", None)}

    communes = sorted(set(afx) & set(cache))
    if len(communes) < 5:
        return {
            "code": code, "statut": "trop_peu_de_dates_communes",
            "dates_afx": len(afx), "dates_cache": len(cache),
            "communes": len(communes),
            "plage_afx": [min(afx), max(afx)] if afx else None,
        }

    ecarts_c, ecarts_v = [], []
    details = []
    for d in communes:
        a, c = afx[d]["close"], cache[d]["close"]
        if c:
            e = (a / c - 1) * 100
            ecarts_c.append(abs(e))
            if abs(e) > 0.5:
                details.append({"date": d, "afx": a, "cache": c, "ecart_pct": round(e, 3)})
        va, vc = afx[d].get("volume"), cache[d].get("volume")
        if va is not None and vc:
            ecarts_v.append(abs(va / float(vc) - 1) * 100)

    return {
        "code": code,
        "statut": "ok",
        "dates_afx": len(afx),
        "dates_cache": len(cache),
        "dates_communes": len(communes),
        "plage_afx": [min(afx), max(afx)],
        "ecart_close_median_pct": round(statistics.median(ecarts_c), 4) if ecarts_c else None,
        "ecart_close_max_pct": round(max(ecarts_c), 4) if ecarts_c else None,
        "ecart_close_p95_pct": round(sorted(ecarts_c)[int(len(ecarts_c) * 0.95)], 4) if ecarts_c else None,
        "ecart_volume_median_pct": round(statistics.median(ecarts_v), 2) if ecarts_v else None,
        "nb_dates_ecart_sup_05pct": len(details),
        "exemples_ecarts": details[:8],
    }


def main():
    import pickle

    with open(RACINE / "data" / "history_cache.pkl", "rb") as fh:
        hist = pickle.load(fh)

    codes = sorted(hist.keys())
    # On interroge tout le monde : le cout est faible, la couverture compte
    print("=" * 88)
    print("  CROISEMENT DES PRIX — BSTrade (cache)  x  AFX (source independante)")
    print("=" * 88)
    print(f"\n  {len(codes)} titres a verifier\n")

    resultats = []
    for i, code in enumerate(codes, 1):
        r = croiser(code, hist[code])
        resultats.append(r)
        if r["statut"] == "ok":
            print(f"  [{i:>2}/{len(codes)}] {code:<8} {r['dates_communes']:>5} dates communes  "
                  f"ecart close median {r['ecart_close_median_pct']:>7.4f} %  "
                  f"max {r['ecart_close_max_pct']:>8.4f} %")
        else:
            print(f"  [{i:>2}/{len(codes)}] {code:<8} {r['statut']}")
        time.sleep(0.4)

    SORTIE.write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")

    # Bilan
    ok = [r for r in resultats if r["statut"] == "ok"]
    print("\n" + "=" * 88)
    print("  BILAN DU CROISEMENT")
    print("=" * 88)
    print(f"\n  Titres croises avec succes : {len(ok)}/{len(resultats)}")
    if ok:
        med = statistics.median([r["ecart_close_median_pct"] for r in ok])
        mx = max(r["ecart_close_max_pct"] for r in ok)
        tot_dates = sum(r["dates_communes"] for r in ok)
        print(f"  Dates comparees au total   : {tot_dates:,}")
        print(f"  Ecart MEDIAN des cours     : {med:.4f} %")
        print(f"  Ecart MAXIMAL des cours    : {mx:.4f} %")

        print(f"\n  {'Code':<8} {'dates':>7} {'ecart median':>14} {'ecart max':>12} {'ecarts >0,5%':>14}")
        print("  " + "-" * 62)
        for r in sorted(ok, key=lambda x: -(x["ecart_close_max_pct"] or 0))[:20]:
            print(f"  {r['code']:<8} {r['dates_communes']:>7} "
                  f"{r['ecart_close_median_pct']:>13.4f}% {r['ecart_close_max_pct']:>11.4f}% "
                  f"{r['nb_dates_ecart_sup_05pct']:>14}")

        # Verdict
        print("\n" + "=" * 88)
        seuil = 1.0
        divergents = [r for r in ok if (r["ecart_close_max_pct"] or 0) > seuil]
        if not divergents:
            print(f"  ✅ AUCUNE divergence superieure a {seuil} % : les deux sources concordent.")
        else:
            print(f"  ⚠️  {len(divergents)} titre(s) avec un ecart > {seuil} % a examiner :")
            for r in divergents:
                print(f"     {r['code']:<8} max {r['ecart_close_max_pct']:.2f} %  "
                      f"({r['nb_dates_ecart_sup_05pct']} dates > 0,5 %)")
                for e in r["exemples_ecarts"][:3]:
                    print(f"        {e['date']}  AFX {e['afx']:>10,.0f}  cache {e['cache']:>10,.0f}  "
                          f"({e['ecart_pct']:+.2f} %)")
        print("=" * 88)

    print(f"\n  Ecrit : {SORTIE.name}")


if __name__ == "__main__":
    main()
