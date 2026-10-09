"""Moteur d'alertes personnalisées sur la watchlist.

Vérifie le snapshot marché (1 appel API) à intervalle régulier et notifie
Telegram quand un seuil est franchi. L'état des alertes déclenchées est
persisté dans data/alerts_state.json pour éviter les re-notifications
pendant la période de cooldown.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Optional

from .bsapi import BSApi
from .domaine.models import Quote
from .notify import TelegramNotifier
from .infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

log = logging.getLogger(__name__)

STATE_FILE = DATA_DIR / "alerts_state.json"


class AlertEngine:
    def __init__(
        self,
        api: BSApi,
        notifier: TelegramNotifier,
        watchlist: dict,
        cooldown_minutes: int = 30,
        session_only: bool = True,
        respect_session: bool = True,
    ) -> None:
        self.api = api
        self.notifier = notifier
        self.watchlist = watchlist or {}
        self.cooldown = cooldown_minutes * 60
        self.session_only = session_only
        self.respect_session = respect_session
        self.state: dict[str, float] = self._load_state()

    # ------------------------------------------------------------------ state
    def _load_state(self) -> dict:
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_state(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ------------------------------------------------------------- triggering
    def check_once(self) -> list[str]:
        """Vérifie les seuils une fois. Retourne les messages à notifier."""
        messages: list[str] = []
        if not self.watchlist:
            return messages
        if self.respect_session and self.session_only and not self._in_session():
            return messages

        try:
            snapshot = self.api.market_snapshot()
        except Exception as exc:
            log.error("Snapshot failed: %s", exc)
            return messages

        now = time.time()
        for code, rules in self.watchlist.items():
            quote = snapshot.by_code(code)
            if quote is None or quote.last <= 0:
                continue
            for cond in self._check_rules(quote, rules):
                key = f"{code}:{cond}"
                if self.state.get(key, 0) > now - self.cooldown:
                    continue
                self.state[key] = now
                messages.append(f"🔔 *{quote.name}* ({quote.code})\n{cond}")
        self._save_state()
        return messages

    def _check_rules(self, quote: Quote, rules: dict) -> list[str]:
        out: list[str] = []
        last = quote.last
        var = quote.change_pct

        if rules.get("max") and last >= float(rules["max"]):
            out.append(f"Prix atteint {last:,.0f} FCFA (seuil haut {float(rules['max']):,.0f})")
        if rules.get("min") and last <= float(rules["min"]):
            out.append(f"Prix tombé à {last:,.0f} FCFA (seuil bas {float(rules['min']):,.0f})")
        if rules.get("change_pct") and abs(var) >= float(rules["change_pct"]):
            out.append(f"Variation {var:+.2f}% (seuil ±{float(rules['change_pct']):.0f}%)")
        return out

    # ---------------------------------------------------------------- session
    def _in_session(self) -> bool:
        """Séance BRVM : lundi-vendredi, ~09:00-15:00 heure d'Abidjan (UTC)."""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        open_t, close_t = dtime(8, 30), dtime(16, 0)
        return open_t <= now.time() <= close_t


def run_loop(
    api: BSApi,
    notifier: TelegramNotifier,
    watchlist: dict,
    interval: int = 300,
    cooldown_minutes: int = 30,
    session_only: bool = True,
    max_runs: Optional[int] = None,
) -> None:
    """Boucle d'alertes : vérifie toutes les `interval` secondes."""
    engine = AlertEngine(api, notifier, watchlist, cooldown_minutes, session_only, respect_session=True)
    log.info("Moteur d'alertes démarré (interval=%ss, %d titres surveillés)", interval, len(watchlist))
    runs = 0
    while max_runs is None or runs < max_runs:
        runs += 1
        messages = engine.check_once()
        for msg in messages:
            log.info("ALERTE: %s", msg)
            notifier.send(msg)
        if max_runs is not None:
            break
        time.sleep(interval)
