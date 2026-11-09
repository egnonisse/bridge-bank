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
import logging
import os
import re
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import requests
from ..infrastructure.paths import DATA_DIR, PER_CACHE  # chemins centralisés (lot 0 du plan docs/architecture.md)
from .divisions_officielles import charger as charger_divisions

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
log = logging.getLogger(__name__)

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

# Date de l'AVIS de dividende (brvm.org) pour chaque dps officiel ci-dessus. Le montant est
# déclaré sur le nombre d'actions EXISTANT à la date de l'avis : un dps déclaré avant une
# division de nominal est donc en base ANCIENNE et doit être divisé par le facteur des
# divisions POSTÉRIEURES (get_fundamentals le fait). L'avis précède le paiement : toute
# division postérieure à l'avis est postérieure au paiement.
OFFICIAL_DPS_DATE = {
    "SNTS": "2026-04-23",
    "BOAS": "2026-05-08",
    "PALC": "2026-06-10",
    "SOGC": "2026-07-22",
    "SLBC": "2026-07-13",
    "SGBC": "2026-08-06",
}

# Contrôle de VRAISEMBLANCE de l'ajustement (à proposer dans src/regles.py — règle du
# contrat : les seuils vivent dans regles.py, que ce chantier ne peut pas modifier).
# PROVENANCE (mesure du 02/11/2026) : un rendement brut dps/cours > ~15 % est incohérent
# sur la BRVM (cas mesuré SNTS : 1977/4350 = 45 %). Ce n'est pas une aubaine : c'est un
# dps en base ancienne (division postérieure non répercutée) ou un mirage. En dessous de
# ce seuil, le dps est plausible tel quel et ne doit JAMAIS être corrigé à l'aveugle.
SEUIL_RENDEMENT_INCOHERENT = 0.15


def _parse_num(s: str | None) -> float | None:
    s = (s or "").strip().replace("%", "").replace(" ", "").replace(",", "")
    if not s or s in ("-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


PER_CACHE_FILE = PER_CACHE  # B2-09/C7 : nom centralisé dans paths.py (alias local = point d'injection des tests)


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


def facteur_division_posterieure(code: str, date_dividende: str | None,
                                 chemin: Path | None = None) -> float:
    """Facteur cumulé des divisions officielles POSTÉRIEURES à la date du dividende.

    Un dps déclaré avant une division N pour 1 vaut N fois trop cher par action nouvelle :
    la correction est dps / facteur. Les divisions ANTÉRIEURES au dividende sont déjà
    reflétées (le dividende a été calculé sur le nominal déjà divisé). Retourne 1.0 si
    aucune division postérieure ou si la date est inconnue.

    N'avale jamais une fiche mal formée : `charger()` lève (ValueError/FileNotFoundError)
    et l'erreur remonte — doctrine B2-05/B2-16 (un ajustement silencieux fausse les cours).
    """
    if not date_dividende:
        return 1.0
    date_dividende = str(date_dividende)[:10]
    operations = charger_divisions(chemin).get(code.strip().upper(), [])
    facteur = 1.0
    for op in operations:
        if op.date > date_dividende:
            facteur *= op.facteur
    return facteur


def ajuster_dps_division(dps: float | None, price: float | None,
                         facteur: float | None) -> float | None:
    """Ajuste un dps encore en base ANCIENNE, avec contrôle de vraisemblance.

    Règles (décision du 02/11/2026, cas SNTS) :
      - facteur ≤ 1 (aucune division postérieure) → inchangé ;
      - rendement brut dps/cours ≤ SEUIL_RENDEMENT_INCOHERENT (15 %) → plausible, inchangé
        (le dps est déjà en base nouvelle, ou c'est un vrai payeur qu'on ne corrige pas) ;
      - rendement > 15 % ET facteur > 1 → incohérence de base expliquée par la division :
        dps / facteur.

    Utilisée là où le COURS est connu (l'appelant) ; get_fundamentals, lui, n'a pas le
    cours : il applique la correction déterministe par DATE (facteur_division_posterieure).
    """
    if dps is None or dps <= 0 or price is None or price <= 0:
        return dps
    if facteur is None or facteur <= 1.0:
        return dps
    if dps / price <= SEUIL_RENDEMENT_INCOHERENT:
        return dps
    return round(dps / facteur, 6)


def _dps_ajuste_apres_division(code: str, dps: float | None) -> float | None:
    """Ré-exprime en base nouvelle un dps officiel déclaré avant une division postérieure.

    Cas mesuré SNTS (02/11/2026) : dps 1 977 F déclaré le 23/04/2026, division 10 pour 1 le
    26/10/2026. Le cours est passé en base nouvelle (4 350 F) mais le dps restait en base
    ancienne → payout calculé = 1977 × 10.4 / 4350 = 473 % (fausse alerte « risque de coupe
    du dividende » sur le titre le plus performant) au lieu de 47 %. Ici on divise par le
    facteur des divisions postérieures.

    Le contrôle de vraisemblance par rendement (ajuster_dps_division) n'est pas applicable
    ici faute de cours : pour les dps officiels, la DATE de l'avis fait foi (montant déclaré
    sur les actions d'avant division). Pour un dps scrapé (afx) sans date connue, on
    s'abstient — jamais de correction à l'aveugle. L'ajustement se RECALCULE à chaque
    lecture (aucun cache en dur) : le prochain scrape repartira du 1977 brut et redivisera
    par 10, le correctif n'est donc jamais réécrit ni perdu.
    """
    if dps is None or dps <= 0:
        return dps
    date_dividende = OFFICIAL_DPS_DATE.get(code)
    if not date_dividende:
        return dps
    facteur = facteur_division_posterieure(code, date_dividende)
    if facteur <= 1.0:
        return dps
    ajuste = round(dps / facteur, 6)
    log.warning(
        "dps %s en base ancienne (déclaré le %s) : division cumulée ×%s postérieure -> "
        "%s -> %s F (ajusté à chaque lecture)",
        code, date_dividende, facteur, dps, ajuste,
    )
    return ajuste


def get_fundamentals(code: str) -> dict:
    """PER + dividende/action pour un titre. Champs à None si indisponibles.

    `per_date` (B2-03, lot 2) : date de collecte du PER affiché ("" si inconnue — ancien
    cache migré ou jamais scrapé).

    Le dps exposé est AJUSTÉ des divisions de nominal postérieures au dividende
    (cf. _dps_ajuste_apres_division) : sans cela, un dps en base ancienne fausse le
    payout (cas SNTS : 473 % affiché au lieu de 47 %). Le PER, scrapé en direct sur le
    cours courant, est déjà en base nouvelle : le bénéfice par action implicite (cours/PER)
    n'a donc pas besoin d'être ajusté.
    """
    code_ = code.upper().strip()
    return {
        "code": code_,
        "per": get_per_brvm(code),
        "dps": _dps_ajuste_apres_division(code_, get_dps(code)),
        "per_date": per_cache_info(code).get("date", ""),
    }
