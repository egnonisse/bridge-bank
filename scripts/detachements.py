"""Dates de détachement (ex-dividend) via stockanalysis.com/quote/brvm/<CODE>/dividend/.

La page affiche le DERNIER détachement (« Ex-Dividend Date ») + l'historique.
Le prochain détachement se déduit : +1 an sur le dernier (périodicité annuelle
BRVM), à confirmer par l'avis officiel au BOC.

Usage : python scripts/detachements.py [CODE...]
"""
import re
import sys
import requests
import urllib3

urllib3.disable_warnings()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

DEFAULT_CODES = ["BOAM", "BICC", "NSBC", "SHEC", "CBIBF",
                 "PALC", "SLBC", "SGBC", "SNTS"]


def last_ex_dates(code):
    url = f"https://stockanalysis.com/quote/brvm/{code}/dividend/"
    r = requests.get(url, headers=HEADERS, timeout=60, verify=False)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    t = r.text
    # dernier détachement (bloc d'en-tête)
    m = re.search(r"Ex-Dividend Date <div[^>]*>([^<]+)</div>", t)
    last = m.group(1).strip() if m else None
    # historique : les lignes du tableau avec dates (les 3 premières)
    hist = re.findall(r">([A-Z][a-z]{2} \d{1,2}, \d{4})</td>", t)
    return (last, hist[:3]), "ok"


if __name__ == "__main__":
    codes = [c.upper() for c in sys.argv[1:]] or DEFAULT_CODES
    print(f"{'Code':<7}{'Dernier détachement':<24}{'Historique récent':<40}Prochain estimé")
    for c in codes:
        (last, hist), status = last_ex_dates(c)
        if last:
            hist_txt = " · ".join(hist) if hist else "—"
            print(f"{c:<7}{last:<24}{hist_txt:<40}+1 an ≈ {last}")
        else:
            print(f"{c:<7}{status}")
