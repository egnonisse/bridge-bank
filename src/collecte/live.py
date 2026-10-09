"""Cours temps réel BRVM + horaires de séance + délais d'exécution Bridge Securities.

L'API BSTrade (MarketDetails mode=3) renvoie les cours de CLÔTURE de la veille.
Pendant la séance, la source temps réel publique est brvm.org (page
cours-actions, scrapée ici). L'interface web BSTrade a aussi le streaming
(Ticker, palmarès, graphique intraday) mais elle est authentifiée.

Références (docs/) :
  - Manuel BSTrade : détails marché en temps réel, ticker streaming.
  - Note @ORDERS : ordre courriel après 11h → J+1 ; BSTrade jusqu'à 13h30 ;
    annulation sous 5 min ; Règlement/Livraison T+3.
  - Procédure d'approvisionnement : versement espèces J → comptabilisé J+1.
"""
from __future__ import annotations

import re
from datetime import datetime, time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
URL = "https://www.brvm.org/fr/cours-actions/0"

# --- horaires de séance (API BSTrade mode=1) --------------------------------
SESSION_START = time(9, 0)   # début de séance (pré-ouverture 09:00)
SESSION_CLOSE = time(15, 0)  # clôture 15:00 (heure Abidjan, GMT)

# --- délais d'exécution Bridge Securities (note @ORDERS) ---------------------
ORDER_CUTOFF_BSTRADE = time(13, 30)  # dernier ordre du jour via BSTrade
ORDER_CUTOFF_EMAIL = time(11, 0)     # dernier ordre du jour par courriel
SETTLEMENT_DAYS = 3                  # Règlement/Livraison : T+3 jours ouvrés
CASH_CREDIT_OFFSET_DAYS = 1          # versement espèces J → comptabilisé J+1


def session_open(now: datetime | None = None) -> bool:
    """La séance BRVM est-elle ouverte (09h00-15h00, jours ouvrés) ?"""
    now = now or datetime.now()
    if now.weekday() >= 5:  # samedi / dimanche
        return False
    return SESSION_START <= now.time() <= SESSION_CLOSE


def live_quotes(codes: list[str], timeout: int = 30) -> dict[str, float]:
    """Cours temps réel des actions depuis brvm.org. Retourne {code: cours}.

    Le cours est le premier montant formaté (ex. « 34 400 ») qui suit le code
    dans la page. Codes inconnus ou non cotés : absents du résultat.
    """
    resp = requests.get(URL, headers=HEADERS, timeout=timeout, verify=False)
    resp.raise_for_status()
    txt = resp.text
    out: dict[str, float] = {}
    for code in codes:
        m = re.search(re.escape(code.strip()) + r"[^0-9]{0,100}(\d[\d\s\xa0.,]{3,12})", txt)
        if not m:
            continue
        raw = m.group(1)
        if raw.count(",") + raw.count(".") > 1:
            continue  # volume formaté (ex. 2,133,627), pas un cours
        # heuristique française : virgule + 3 chiffres = milliers, sinon décimale
        raw = re.sub(r",(\d{3})(?!\d)", r"\1", raw)
        raw = raw.replace(" ", "").replace("\xa0", "").replace(",", ".")
        try:
            price = float(raw)
        except ValueError:
            continue
        if 0 < price <= 999_999:  # aucun cours BRVM au-delà
            out[code.strip().upper()] = price
    return out
