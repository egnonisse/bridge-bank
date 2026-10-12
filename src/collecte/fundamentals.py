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
import os
import re
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import requests
from ..infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

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
    """Cache {code: {"per": float, "date": ISO}} — rétro-compatible avec l'ancien format plat.

    B2-01/B2-03 (lot 2, 12/10) :
    - schéma DATÉ (la fraîcheur du PER est enfin lisible) ;
    - toute valeur ≤ 0 est ÉCARTÉE : brvm.org affiche « 0.00 » quand le PER n'est pas
      calculable — la stocker faisait croire à un payout de 0 % (fausse sécurité).
    """
    if not PER_CACHE_FILE.exists():
        return {}
    try:
        brut = json.loads(PER_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    cache: dict = {}
    for code, val in brut.items():
        if isinstance(val, dict):  # schéma daté
            per, date_ = val.get("per"), val.get("date", "")
        else:  # ancien schéma plat (float) — migré à la lecture
            per, date_ = val, ""
        if isinstance(per, (int, float)) and per > 0:
            cache[code.upper()] = {"per": float(per), "date": date_}
    return cache


def _save_per_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PER_CACHE_FILE.with_name(PER_CACHE_FILE.name + ".tmp")
    tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PER_CACHE_FILE)  # écriture atomique (même règle que portfolio.json, B1-04)


LOCK_FILE = DATA_DIR / "per_cache.lock"
LOCK_STALE_SECONDS = 60  # verrou considéré orphelin (process tué en pleine écriture) au-delà


@contextmanager
def _cache_lock(timeout: float = 15.0):
    """Verrou inter-processus simple (fichier O_EXCL) autour du load/modify/save du cache PER.

    Incident du 12/10/2026 : le screener scrape avec 3 threads ; sans verrou ni atomicité,
    un thread lisait le fichier pendant qu'un autre l'écrivait (JSON tronqué → {} →
    sauvegarde d'une seule entrée) — le cache complet a été écrasé (48 → 5 entrées).
    Écriture atomique + ce verrou ferment la course. En cas de timeout on continue SANS
    verrou (le cache n'est pas vital : pire cas, une mise à jour perdue, pas un écrasement).
    """
    t0 = time.time()
    fd = None
    while fd is None:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:  # purge d'un verrou orphelin (process tué sans libérer)
                if time.time() - LOCK_FILE.stat().st_mtime > LOCK_STALE_SECONDS:
                    LOCK_FILE.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.time() - t0 > timeout:
                yield False  # dégradé mais jamais bloquant
                return
            time.sleep(0.05)
    try:
        yield True
    finally:
        try:
            os.close(fd)
        finally:
            try:
                LOCK_FILE.unlink(missing_ok=True)
            except OSError:
                pass


def per_cache_info(code: str) -> dict:
    """Entrée du cache PER pour un code : {"per": float, "date": ISO} — {} si absente (B2-03)."""
    return _load_per_cache().get(code.strip().upper(), {})


def get_per_brvm(code: str) -> float | None:
    """PER d'un titre (scraping brvm.org), avec cache daté du dernier PER réussi.

    Si le scraping échoue (site indisponible, rate-limit), retourne le dernier
    PER connu pour ne pas perdre l'info (utilisé par limits/sustain/report).
    Un PER ≤ 0 (« 0.00 » affiché par brvm.org = non calculable) est traité comme
    INDISPONIBLE, jamais comme une valeur (B2-01, lot 2).
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

    if per is not None and per > 0:
        with _cache_lock() as ok:
            if ok:
                cache = _load_per_cache()  # relire SOUS verrou (état à jour d'un autre thread)
                cache[code] = {"per": per, "date": date.today().isoformat()}
                _save_per_cache(cache)
        return per
    entree = _load_per_cache().get(code)  # lecture hors verrou (écriture atomique côté fichier)
    return entree["per"] if entree else None


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
    """PER + dividende/action pour un titre. Champs à None si indisponibles.

    `per_date` (B2-03, lot 2) : date de collecte du PER affiché ("" si inconnue — ancien
    cache migré ou jamais scrapé).
    """
    code_ = code.upper().strip()
    return {
        "code": code_,
        "per": get_per_brvm(code),
        "dps": get_dps(code),
        "per_date": per_cache_info(code).get("date", ""),
    }
