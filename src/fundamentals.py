"""Récupération des fondamentaux (PER, dividende/action) d'un titre BRVM.

Sources croisées :
  - PER : https://www.brvm.org/fr/<code> (officiel)
  - dividende/action : avis officiels BRVM (source de vérité), sinon
    https://afx.kwayisi.org/brvm/<code>.html (fallback)

Les dividendes officiels sont en BRUT par action (exercice 2025) ; l'IRVM
(12 % personnes physiques) est déduit dans le calcul du rendement net.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from .paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Dividendes BRUT par action (exercice 2025) — source de vérité : avis de
# paiement de dividendes brvm.org. Prime sur le scraping afx (imprécis).
OFFICIAL_DPS = {
    "SNTS": 1977.0,   # avis n°111 23/04/2026 : 1 740 net -> brut (IRVM 12 %)
    "BOAS": 511.0,    # avis n°122 08/05/2026 : 450 net -> brut (IRVM 12 %)
    "PALC": 501.6,    # avis n°162 10/06/2026 : 501,596 brut
    "SOGC": 570.0,    # avis n°213 22/07/2026 : 570 brut
    "SLBC": 2127.0,   # avis n°208 13/07/2026 : 2 127 brut
    "SGBC": 2606.0,   # avis n°231 06/08/2026 : 2 606 brut
}


def _parse_num(s: str | None) -> float | None:
    s = (s or "").strip().replace("%", "").replace(" ", "").replace(",", "")
    if not s or s in ("-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


PER_CACHE_FILE = DATA_DIR / "per_cache.json"


def _load_per_cache() -> dict:
    if not PER_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(PER_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_per_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PER_CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def get_per_brvm(code: str) -> float | None:
    """PER d'un titre (scraping brvm.org), avec cache du dernier PER réussi.

    Si le scraping échoue (site indisponible, rate-limit), retourne le dernier
    PER connu pour ne pas perdre l'info (utilisé par limits/sustain/report).
    """
    code = code.strip().upper()
    url = f"https://www.brvm.org/fr/{code.lower()}"
    per = None
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            m = re.search(
                r'PER:&nbsp;</div><div class="field-items"><div class="field-item[^"]*">([\d.,]+)</div>',
                r.text,
            )
            per = _parse_num(m.group(1)) if m else None
    except requests.RequestException:
        per = None

    cache = _load_per_cache()
    if per is not None:
        cache[code] = per
        _save_per_cache(cache)
        return per
    return cache.get(code)


def get_dps_afx(code: str) -> float | None:
    url = f"https://afx.kwayisi.org/brvm/{code.lower().strip()}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None
        text = re.sub(r"<[^>]+>", "|", r.text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\|+", "|", text)
        m = re.search(r"Dividend Per Share\s*\|\s*([^|]+)", text)
        return _parse_num(m.group(1)) if m else None
    except requests.RequestException:
        return None


def get_dps(code: str) -> float | None:
    """Dividende BRUT par action : officiel BRVM si connu, sinon scrape afx."""
    code = code.strip().upper()
    if code in OFFICIAL_DPS:
        return OFFICIAL_DPS[code]
    return get_dps_afx(code)


def get_fundamentals(code: str) -> dict:
    """PER + dividende/action pour un titre. Champs à None si indisponibles."""
    return {
        "code": code.upper().strip(),
        "per": get_per_brvm(code),
        "dps": get_dps(code),
    }
