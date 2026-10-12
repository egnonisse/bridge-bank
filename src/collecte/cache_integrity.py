"""Contrôle d'intégrité du cache historique + versionning des profils dérivés.

Contexte (incident 21/08/2026) : le cache history_cache.pkl a été re-téléchargé
silencieusement avec des données différentes (fausse cassure de split 2017,
cours 2018-2025 ~5× trop bas) — détecté par hasard. Ces contrôles le rendent
automatique :

1. détection de cassures suspectes (ratio inter-closes > 3× ou < ⅓) ;
2. cohérence dernière barre du cache vs cours API (si le cache est frais) ;
3. fraîcheur du cache (alerte si la dernière barre date de plus de 8 jours) ;
4. versionning : les profils dérivés (reversal_profiles.json) portent la
   signature du cache qui les a produits — péremption détectée automatiquement.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path
from ..infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)
from ..portefeuille.format_fr import fcfa, nombre  # format FR (invariant E1, correction C1)

REVERSAL_FILE = DATA_DIR / "reversal_profiles.json"

MAX_JUMP = 3.0          # ratio close[i]/close[i-1] au-delà → cassure à examiner
PRICE_TOLERANCE = 0.25  # écart toléré entre dernière barre cache et cours API
MAX_COMPARE_AGE_DAYS = 3  # au-delà, le cache est en retard : pas de comparaison de prix
MAX_CACHE_AGE_DAYS = 8  # au-delà → cache en retard


def cache_signature(hist_all: dict) -> str:
    """Empreinte compacte du contenu du cache (nb de barres par titre)."""
    summary = "|".join(f"{code}:{len(bars)}" for code, bars in sorted(hist_all.items()))
    return hashlib.sha256(summary.encode("utf-8")).hexdigest()[:16]


def _is_probable_split(closes: list[float], i: int, lookback: int = 10) -> bool:
    """Changement de niveau permanent (>= 5× entre médianes avant/après) = split réel.

    Les divisions de nominal BRVM (oct-déc 2017, x0.05-0.21) sont des événements
    légitimes : le niveau bas persiste. Un ARTEFACT de données est une cassure
    isolée suivie d'un retour au niveau précédent.
    """
    before = [c for c in closes[max(0, i - lookback):i] if c > 0]
    after = [c for c in closes[i:i + lookback] if c > 0]
    if not before or not after:
        return False
    med_b = statistics.median(before)
    med_a = statistics.median(after)
    return med_b / med_a >= 2.5 or med_a / med_b >= 2.5


def detect_jumps(hist_all: dict) -> list[str]:
    """Cassures suspectes (artefacts) — les splits réels sont ignorés."""
    problems = []
    for code, bars in hist_all.items():
        closes = [float(b.close) for b in bars]
        for i in range(1, len(closes)):
            if closes[i - 1] <= 0 or closes[i] <= 0:
                continue
            ratio = closes[i] / closes[i - 1]
            if ratio > MAX_JUMP or ratio < 1.0 / MAX_JUMP:
                if _is_probable_split(closes, i):
                    continue  # division de nominal réelle → légitime
                problems.append(
                    f"cassure {code} : {bars[i-1].date:%Y-%m-%d} {fcfa(closes[i-1], signe=False)} → "
                    f"{bars[i].date:%Y-%m-%d} {fcfa(closes[i], signe=False)} (x{ratio:.2f})"
                )
    return problems


def check_against_api(hist_all: dict, snapshot, today: datetime | None = None) -> list[str]:
    """Dernière barre du cache vs cours API : écart suspect (> 25 %) si cache frais."""
    today = today or datetime.now()
    problems = []
    for code, bars in hist_all.items():
        if not bars:
            continue
        q = snapshot.by_code(code.strip())
        if q is None or q.last <= 0:
            continue
        last = bars[-1]
        if (today - last.date).days > MAX_COMPARE_AGE_DAYS:
            continue  # cache en retard → comparaison de prix non pertinente
        last_close = float(last.close)
        if last_close <= 0:
            continue
        gap = abs(last_close / q.last - 1)
        if gap > PRICE_TOLERANCE:
            problems.append(
                f"incohérence {code} : cache {fcfa(last_close, signe=False)} vs API {fcfa(q.last, signe=False)} "
                f"(écart {gap*100:.0f} %)"
            )
    return problems


def check_freshness(hist_all: dict, today: datetime | None = None) -> list[str]:
    """Cache en retard : dernière barre de plus de MAX_CACHE_AGE_DAYS jours."""
    today = today or datetime.now()
    problems = []
    for code, bars in hist_all.items():
        if not bars:
            continue
        age = (today - bars[-1].date).days
        if age > MAX_CACHE_AGE_DAYS:
            problems.append(f"cache en retard {code} : dernière barre au {bars[-1].date:%Y-%m-%d}")
    return problems


def reversal_profile_stale(hist_all: dict) -> bool:
    """True si les profils dérivés ont été calculés sur un cache différent."""
    try:
        data = json.loads(REVERSAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    stored = data.get("_meta", {}).get("cache_signature")
    return stored != cache_signature(hist_all)


def check_all_integrity(hist_all: dict, snapshot, today: datetime | None = None) -> list[str]:
    """Tous les contrôles → liste des problèmes (vide = données cohérentes)."""
    problems: list[str] = []
    problems.extend(detect_jumps(hist_all))
    problems.extend(check_against_api(hist_all, snapshot, today))
    problems.extend(check_freshness(hist_all, today))
    if reversal_profile_stale(hist_all):
        problems.append(
            "reversal_profiles.json périmé (cache différent) — relancer "
            "scripts/export_reversal_profiles.py"
        )
    return problems
