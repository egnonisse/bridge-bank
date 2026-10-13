"""Notification Telegram (bot personnel) — et journal des envois.

CE MODULE EST LE POINT DE PASSAGE UNIQUE
-----------------------------------------
18 endroits du projet appellent `notifier.send(...)`. Poser l'empreinte ici plutôt que dans les
18 appelants, c'est la seule façon d'être sûr qu'AUCUN envoi ne passe sans sa trace — un
appelant oublié, et la traçabilité deviendrait partielle sans que personne ne s'en aperçoive.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

import requests

from .alertes import journal_alertes
from .infrastructure.empreinte import carte

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Limite dure de l'API Telegram (400 « message is too long » au-delà) ; la marge couvre
# le suffixe d'empreinte éventuel (`_suffixe`), ajouté avant le découpage.
LIMITE_TELEGRAM = 4096
MARGE_DECOUPE = 96


def _decouper(texte: str, limite: int = LIMITE_TELEGRAM - MARGE_DECOUPE) -> list[str]:
    """Découpe un message trop long en morceaux ≤ limite, aux frontières de lignes.

    Une ligne seule plus longue que la limite est coupée brutalement (cas rare : une
    alerte est faite de lignes courtes). Un texte vide donne un unique morceau vide,
    que l'appelant envoie tel quel (comportement d'origine conservé).
    """
    if len(texte) <= limite:
        return [texte]
    morceaux: list[str] = []
    courant = ""
    for ligne in texte.splitlines(keepends=True):
        if len(courant) + len(ligne) > limite and courant:
            morceaux.append(courant.rstrip())
            courant = ""
        while len(ligne) > limite:
            morceaux.append(ligne[:limite])
            ligne = ligne[limite:]
        courant += ligne
    if courant.strip():
        morceaux.append(courant.rstrip())
    return morceaux or [""]


def _origine() -> str:
    """Module ayant demandé l'envoi (« src.main »), lu dans la pile d'appels.

    Éviter de modifier 18 appelants pour un seul champ de traçabilité. Si la lecture échoue,
    on écrit « inconnu » — l'empreinte de version, elle, reste complète.
    """
    try:
        return sys._getframe(2).f_globals.get("__name__", "inconnu")
    except Exception:                      # pragma: no cover - jamais attendu
        return "inconnu"


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, empreinte_dans_message: bool = False) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        # Faux par défaut : les messages restent exactement ce qu'ils étaient. La trace vit
        # dans le journal ; ce réglage n'ajoute qu'un rappel visible à la fin du message.
        self.empreinte_dans_message = empreinte_dans_message

    def send(self, text: str) -> bool:
        """Envoie le message et l'INSCRIT AU JOURNAL, avec son empreinte de version.

        L'ordre compte : on tente l'envoi, PUIS on inscrit le résultat réel. Un message qui
        n'est pas parti est un fait à conserver (l'alerte a bien été déclenchée, Telegram ne
        l'a pas reçue) — c'est exactement ce qu'on veut pouvoir relire trois semaines plus tard.
        """
        empreinte = carte()
        envoye = self._envoyer(text + self._suffixe(empreinte))
        try:
            journal_alertes.enregistrer(
                {
                    "horodatage": datetime.now().isoformat(timespec="seconds"),
                    "origine": _origine(),
                    "envoye": envoye,
                    "empreinte": empreinte,
                    "message": text,
                }
            )
        except Exception as exc:               # pragma: no cover - ceinture et bretelles
            # `enregistrer` ne lève pas (il attrape les erreurs d'écriture). Ce garde couvre
            # l'inattendu : une alerte doit partir même si la traçabilité est cassée.
            log.error("Journal des alertes indisponible (%s) — le message est parti", exc)
        return envoye

    def _suffixe(self, empreinte: dict) -> str:
        """Rappel visible, si `alerts.empreinte_dans_message` est actif. Vide sinon."""
        if not self.empreinte_dans_message:
            return ""
        return f"\n\n— v{empreinte['code']} · seuils {empreinte['seuils']}"

    def _envoyer(self, texte: str) -> bool:
        if not self.enabled:
            log.warning("Telegram non configuré (token/chat_id manquants)")
            return False
        # Découpage (13/10/2026) : l'API refuse > 4096 caractères par message — sans lui,
        # un rapport long (radar, analyse value) était PERDU à l'envoi (B2-07 et radar).
        for morceau in _decouper(texte):
            try:
                resp = requests.post(
                    TELEGRAM_API.format(token=self.bot_token),
                    json={"chat_id": self.chat_id, "text": morceau, "disable_web_page_preview": True},
                    timeout=15,
                )
                if resp.status_code != 200:
                    log.error("Telegram %s: %s", resp.status_code, resp.text[:200])
                    return False
            except requests.RequestException as exc:
                log.error("Telegram send failed: %s", exc)
                return False
        return True
