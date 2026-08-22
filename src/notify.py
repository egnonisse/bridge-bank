"""Notification Telegram (bot personnel)."""
from __future__ import annotations

import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

    def send(self, text: str) -> bool:
        """Envoie un message. Retourne True si envoyé."""
        if not self.enabled:
            log.warning("Telegram non configuré (token/chat_id manquants)")
            return False
        try:
            resp = requests.post(
                TELEGRAM_API.format(token=self.bot_token),
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
                timeout=15,
            )
            if resp.status_code != 200:
                log.error("Telegram %s: %s", resp.status_code, resp.text[:200])
                return False
            return True
        except requests.RequestException as exc:
            log.error("Telegram send failed: %s", exc)
            return False
