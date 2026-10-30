"""Notification Telegram (bot personnel) — et journal des envois.

CE MODULE EST LE POINT DE PASSAGE UNIQUE
-----------------------------------------
18 endroits du projet appellent `notifier.send(...)`. Poser l'empreinte ici plutôt que dans les
18 appelants, c'est la seule façon d'être sûr qu'AUCUN envoi ne passe sans sa trace — un
appelant oublié, et la traçabilité deviendrait partielle sans que personne ne s'en aperçoive.
"""
from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timedelta

import requests

from .alertes import journal_alertes
from .infrastructure.empreinte import carte

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _sans_token(texte: str) -> str:
    """Retire le jeton d'un message d'erreur (P7-02).

    Les exceptions `requests` incluent l'URL complète — donc le token — dans leur
    message : ce qu'on journalise ne doit jamais le contenir.
    """
    return re.sub(r"/bot[^/\s]+", "/bot***", texte)

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

    def send(self, text: str, reprise_de: str | None = None) -> bool:
        """Envoie le message et l'INSCRIT AU JOURNAL, avec son empreinte de version.

        L'ordre compte : on tente l'envoi, PUIS on inscrit le résultat réel. Un message qui
        n'est pas parti est un fait à conserver (l'alerte a bien été déclenchée, Telegram ne
        l'a pas reçue) — c'est exactement ce qu'on veut pouvoir relire trois semaines plus tard.

        `reprise_de` (30/10/2026) : horodatage de l'alerte d'origine quand CE message est la
        reprise d'un envoi raté — c'est ce champ qui empêche de renvoyer deux fois la même.
        """
        empreinte = carte()
        envoye = self._envoyer(text + self._suffixe(empreinte))
        entree = {
            "horodatage": datetime.now().isoformat(timespec="seconds"),
            "origine": _origine(),
            "envoye": envoye,
            "empreinte": empreinte,
            "message": text,
        }
        if reprise_de:
            entree["reprise_de"] = reprise_de
        try:
            journal_alertes.enregistrer(entree)
        except Exception as exc:               # pragma: no cover - ceinture et bretelles
            # `enregistrer` ne lève pas (il attrape les erreurs d'écriture). Ce garde couvre
            # l'inattendu : une alerte doit partir même si la traçabilité est cassée.
            log.error("Journal des alertes indisponible (%s) — le message est parti", exc)
        return envoye

    def renvoyer_non_delivrees(self, age_max_heures: int = 48,
                               max_envois: int = 5) -> list[str]:
        """Re-tente les alertes dont l'envoi a échoué — une seule fois chacune.

        Le 23/10/2026, l'alerte « check quotidien — 7 étapes en échec, BOC : événement »
        n'est jamais partie : Telegram était injoignable pour la même raison qui avait fait
        échouer le run (panne réseau). Une panne ne doit pas EFFACER une alerte.

        Garde-fous : âge maximal (une alerte périmée n'apprend plus rien), une seule reprise
        (les entrées de reprise portent `reprise_de`), plafond par run (pas de rafale).
        Retourne les horodatages rattrapés.
        """
        if not self.enabled:
            return []
        try:
            entrees = journal_alertes.lire()
        except Exception as exc:               # pragma: no cover - journal illisible
            log.warning("Renvoi impossible : journal illisible (%s)", exc)
            return []
        deja_reprises = {e.get("reprise_de") for e in entrees if e.get("reprise_de")}
        limite = datetime.now() - timedelta(hours=age_max_heures)
        ratees = []
        for e in entrees:
            if e.get("envoye") or not e.get("message") or not e.get("horodatage"):
                continue
            if e["horodatage"] in deja_reprises:
                continue
            try:
                if datetime.fromisoformat(str(e["horodatage"])) < limite:
                    continue
            except ValueError:
                continue
            ratees.append(e)
        rattrapees: list[str] = []
        for e in ratees[-max_envois:]:
            quand = str(e["horodatage"])[:16].replace("T", " ")
            texte = (f"🔁 ALERTE RATTRAPÉE (l'envoi du {quand} avait échoué) :\n"
                     f"{e['message']}")
            if self.send(texte, reprise_de=str(e["horodatage"])):
                rattrapees.append(str(e["horodatage"]))
        return rattrapees

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
                log.error("Telegram send failed: %s", _sans_token(str(exc)))  # P7-02 : jamais de jeton dans les logs
                return False
        return True
