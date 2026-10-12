"""Historique des dividendes (stockanalysis) pour les filtres noyau ajoutés le 25/09.

Filtres calibrés (décision LEO après challenge croisé de 3 IA) :
  - RÉGULARITÉ : dividende versé >= 4 des 5 dernières années (fenêtre GLISSANTE)
  - CROISSANCE : croissance du dividende (1 an) >= -10 % (calibré : garde
    SNTS -5,4 % et PALC -2,2 %, exclut les coupeurs en série)
  - LIQUIDITÉ  : volume moyen 60 séances >= 5 M F/j (vérifié : 41/43 titres)

Source : https://stockanalysis.com/quote/brvm/<CODE>/dividend/
Les parseurs sont séparés du fetch pour être testables sur des fixtures.
"""
from __future__ import annotations

import re
import statistics

import requests
import urllib3

urllib3.disable_warnings()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

REGULARITY_MIN_YEARS = 4      # >= 4 des 5 dernières années
GROWTH_MIN_PCT = -10.0        # croissance 1 an >= -10 %
MIN_VOLUME_MILLIONS = 5.0     # volume moyen 60 séances >= 5 M F/j


def fetch_dividend_page(code: str) -> str | None:
    """HTML de la page dividend de stockanalysis (None si injoignable)."""
    url = f"https://stockanalysis.com/quote/brvm/{code}/dividend/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=40)
        if r.status_code != 200:
            return None
        return r.text
    except Exception:
        return None


def parse_growth_1y(html: str) -> float | None:
    """Croissance du dividende sur 1 an (%), ou None si « n/a »/absent."""
    m = re.search(r"Dividend Growth.*?\(1Y\)</span>.*?<div[^>]*>([^<]+)</div>",
                  html, re.S)
    if not m:
        return None
    raw = m.group(1).strip()
    if raw.lower() in ("n/a", "—", "-", ""):
        return None
    try:
        return float(raw.replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None


def parse_payout_years_last5(html: str) -> int:
    """Nombre d'années (parmi les 5 dernières) avec au moins un paiement.

    Les dates ISO de la page incluent la date de publication du site (la plus
    récente) : on la retire, puis on compte les années uniques restantes.
    Retourne -1 si l'historique disponible est trop court (< 3 années).
    """
    isos = sorted(set(re.findall(r"(20[12]\d-\d{2}-\d{2})", html)))
    if not isos:
        return -1
    # la date de PUBLICATION du site est la plus récente : on la retire
    # (elle n'est pas un paiement), puis on compte les années uniques.
    years = sorted({d[:4] for d in isos[:-1] or isos})
    if len(years) < 3:
        return -1
    return len([y for y in years[-5:]])


def volume_moyen_millions(bars) -> float:
    """Volume moyen des 60 dernières séances, en millions de FCFA."""
    if not bars or len(bars) < 20:
        return 0.0
    return statistics.mean([b.volume * b.close for b in bars[-60:]]) / 1e6


def dividend_filters(code: str, hist: dict | None) -> dict:
    """Applique les 3 nouveaux filtres (régularité, croissance, liquidité).

    Retourne {"ok": bool, "reasons": [str], "notes": [str]}.
    hist : cache complet {code: bars} (pour la liquidité), None = non vérifié.
    """
    reasons: list[str] = []
    notes: list[str] = []
    html = fetch_dividend_page(code)
    if html is None:
        return {"ok": False, "reasons": ["historique des dividendes illisible (source injoignable)"],
                "notes": notes}

    years = parse_payout_years_last5(html)
    if years == -1:
        return {"ok": False, "reasons": ["historique des dividendes trop court (< 3 années) — régularité non prouvée"],
                "notes": notes}
    if years < REGULARITY_MIN_YEARS:
        reasons.append(f"dividende versé seulement {years}/5 des dernières années (exigé ≥ 4/5)")
    else:
        notes.append(f"régularité : {years}/5 dernières années")

    growth = parse_growth_1y(html)
    if growth is None:
        notes.append("croissance du dividende non calculable")
    elif growth < GROWTH_MIN_PCT:
        reasons.append(f"croissance du dividende {growth:+.1f} %/an (exigé ≥ {GROWTH_MIN_PCT:.0f} %)")
    else:
        notes.append(f"croissance du dividende : {growth:+.1f} %/an")

    if hist is not None:
        vol = volume_moyen_millions(hist.get(code, []))
        if vol <= 0:
            notes.append("liquidité non vérifiée (données absentes)")
        elif vol < MIN_VOLUME_MILLIONS:
            reasons.append(f"liquidité {vol:.1f} M F/j (exigé ≥ {MIN_VOLUME_MILLIONS:.0f} M F/j)")
        else:
            notes.append(f"liquidité : {vol:.1f} M F/j")
    else:
        notes.append("liquidité non vérifiée")

    return {"ok": not reasons, "reasons": reasons, "notes": notes}
