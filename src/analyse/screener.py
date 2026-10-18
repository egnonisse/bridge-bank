"""Screener fondamentaux BRVM : PER + dividende, avec cache disque.

Applique le filtre value+dividende et la Magic Formula (Greenblatt adapté)
sur l'ensemble du marché. Le scraping (lent, ~2 req/titre) est mis en cache
pour ne pas re-interroger les sites à chaque run.

Le rendement affiché est BRUT ; le rendement NET (après IRVM 15 % + frais
de conservation 0,80 %/an) est ajouté dans chaque résultat.

Sources : brvm.org (PER officiel), afx.kwayisi.org (dividende/action FCFA).
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from ..collecte.bsapi import BSApi
from ..collecte.fundamentals import get_dps, get_per_brvm
from ..taxation import TARGET_NET_YIELD_ENTRY, gross_yield_for_net, net_yield
from ..infrastructure.paths import DATA_DIR, FUNDAMENTALS_CACHE  # chemins centralisés (lot 0 du plan docs/architecture.md)
from ..infrastructure.ecriture import ecrire_json_atomique  # P7-01 : ecriture atomique

CACHE_FILE = FUNDAMENTALS_CACHE  # B2-09/C7 : nom centralisé dans paths.py (lot 12)
CACHE_MAX_AGE_HOURS = 24
MAX_WORKERS = 3  # faible pour éviter le rate-limiting des sites

# Filtres value+dividende
from ..regles import PER_MAX  # noqa: E402  (catalogue : src/regles.py)
# Rendement BRUT requis pour atteindre le rendement NET cible (4 % après IRVM + frais)
YIELD_MIN = gross_yield_for_net(TARGET_NET_YIELD_ENTRY) * 100  # ≈ 5,45 % brut
from ..regles import PER_ABSURD  # noqa: E402
YIELD_ABSURD = 30.0  # au-delà : dividende exceptionnel one-off


# ------------------------------------------------------------------- cache
def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    ecrire_json_atomique(CACHE_FILE, cache)  # P7-01 : écriture atomique


def _cache_fresh(cache: dict, code: str) -> bool:
    entry = cache.get(code, {})
    ts = entry.get("scraped_at", "")
    try:
        age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds() / 3600
        return age < CACHE_MAX_AGE_HOURS
    except (TypeError, ValueError):
        return False


# ----------------------------------------------------------------- scraping
def scrape_all_fundamentals(api: BSApi, force: bool = False) -> dict[str, dict]:
    """PER + dividende pour toutes les actions, avec cache (24 h) et délai anti-blocage."""
    snap = api.market_snapshot()
    codes = [q.code.strip() for q in snap.stocks if not q.is_obligation and q.last > 0]
    cache = _load_cache()

    to_fetch = [c for c in codes if force or c not in cache or not _cache_fresh(cache, c)]

    def _fetch(code: str) -> tuple[str, dict]:
        time.sleep(0.5)  # délai anti-blocage
        return code, {"per": get_per_brvm(code), "dps": get_dps(code), "scraped_at": datetime.now().isoformat()}

    if to_fetch:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            for fut in as_completed([pool.submit(_fetch, c) for c in to_fetch]):
                code, data = fut.result()
                cache[code] = data
        _save_cache(cache)

    return {c: cache.get(c, {}) for c in codes}


# ------------------------------------------------------------------ analyse
def screen_value_dividend(api: BSApi, force: bool = False) -> list[dict]:
    """Titres remplissant value+dividende : PER <= 14 ET rendement NET >= 4 % (hors aberrants)."""
    snap = api.market_snapshot()
    funds = scrape_all_fundamentals(api, force=force)
    out = []
    for code, f in funds.items():
        per, dps = f.get("per"), f.get("dps")
        if not per or per <= 0 or per > PER_ABSURD:
            continue
        if dps is None or dps <= 0:
            continue
        quote = snap.by_code(code)
        if quote is None or quote.last <= 0:
            continue
        yld = dps / quote.last * 100
        if yld > YIELD_ABSURD:  # dividende exceptionnel
            continue
        if per <= PER_MAX and yld >= YIELD_MIN:
            out.append({
                "code": code,
                "name": quote.name,
                "last": quote.last,
                "per": per,
                "dps": dps,
                "yield": round(yld, 2),
                "net_yield": round(net_yield(yld / 100) * 100, 2),
            })
    out.sort(key=lambda r: r["per"])
    return out


YIELD_SUSPECT = 10.0  # rendement anormal -> dividende exceptionnel suspect
PER_SUSPECT = 25.0  # PER élevé -> bénéfices faibles suspects


def flag_value_traps(api: BSApi, force: bool = False) -> list[dict]:
    """Titres suspects de value trap (rendement anormal ou PER élevé).

    Ce sont des ALERTES (à confirmer par le fondamental), pas des exclusions dures.
    Les seuils d'exclusion dure (YIELD_ABSURD, PER_ABSURD) sont déjà appliqués en amont.
    """
    snap = api.market_snapshot()
    funds = scrape_all_fundamentals(api, force=force)
    traps = []
    for code, f in funds.items():
        per, dps = f.get("per"), f.get("dps")
        if not per or per <= 0 or per > PER_ABSURD:
            continue
        quote = snap.by_code(code)
        if quote is None or quote.last <= 0:
            continue
        yld = (dps / quote.last * 100) if dps else 0.0
        if yld > YIELD_ABSURD:
            continue  # déjà exclu comme exceptionnel
        reasons = []
        if yld > YIELD_SUSPECT:
            reasons.append(f"rendement {yld:.0f}% anormal")
        if per > PER_SUSPECT:
            reasons.append(f"PER {per:.0f} élevé")
        if reasons:
            traps.append({
                "code": code, "name": quote.name, "per": per,
                "dps": dps, "yield": round(yld, 1), "reasons": reasons,
            })
    traps.sort(key=lambda r: -r["yield"])
    return traps


def screen_magic_formula(api: BSApi, force: bool = False) -> list[dict]:
    """Magic Formula adaptée : rang PER (croissant) + rang rendement (décroissant)."""
    snap = api.market_snapshot()
    funds = scrape_all_fundamentals(api, force=force)

    rows = []
    for code, f in funds.items():
        per, dps = f.get("per"), f.get("dps")
        if not per or per <= 0 or per > PER_ABSURD:
            continue
        if dps is None or dps <= 0:
            continue
        quote = snap.by_code(code)
        if quote is None or quote.last <= 0:
            continue
        yld = dps / quote.last * 100
        if yld > YIELD_ABSURD:
            continue
        rows.append((code, quote.name, quote.last, per, dps, yld))

    rows_by_per = sorted(rows, key=lambda r: r[3])
    rows_by_yld = sorted(rows, key=lambda r: -r[5])
    rank_per = {r[0]: i + 1 for i, r in enumerate(rows_by_per)}
    rank_yld = {r[0]: i + 1 for i, r in enumerate(rows_by_yld)}

    scored = []
    for code, name, last, per, dps, yld in rows:
        scored.append({
            "code": code, "name": name, "last": last, "per": per,
            "dps": dps, "yield": round(yld, 2),
            "net_yield": round(net_yield(yld / 100) * 100, 2),
            "rank_per": rank_per[code], "rank_yld": rank_yld[code],
            "score": rank_per[code] + rank_yld[code],
        })
    scored.sort(key=lambda r: r["score"])
    return scored


# ------------------------------------------------- détection de nouveautés
VALUE_STATE_FILE = DATA_DIR / "value_state.json"


def load_value_state() -> set[str]:
    """Codes des titres value+dividende vus au dernier run."""
    if not VALUE_STATE_FILE.exists():
        return set()
    try:
        data = json.loads(VALUE_STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("codes", []))
    except (OSError, json.JSONDecodeError):
        return set()


def save_value_state(codes: set[str]) -> None:
    ecrire_json_atomique(VALUE_STATE_FILE, {"codes": sorted(codes)})  # P7-01 : écriture atomique


def detect_new_value_opportunities(api: BSApi, force: bool = False) -> list[dict]:
    """Titres value+dividende qui ENTRENT dans les critères (absents du run précédent).

    Premier run : tous les titres sont « nouveaux » (baseline enregistrée).
    Les runs suivants ne signalent que les entrants.
    """
    current = screen_value_dividend(api, force=force)
    prev = load_value_state()
    new = [r for r in current if r["code"] not in prev]
    save_value_state({r["code"] for r in current})
    return new
