"""Client API BS Trade (Bridge Securities).

L'API interne expose les données de marché BRVM SANS authentification :
- MarketDetails.aspx?mode=1 : horaires de séance
- MarketDetails.aspx?mode=2 : flux continu des indices
- MarketDetails.aspx?mode=3 : snapshot complet (indices + titres + carnet)
- Service.svc/GetDataStockByCodeAndInterval2 : historique OHLCV (JSON)

Note : le certificat SSL du serveur est invalide → verify=False (données publiques).
"""
from __future__ import annotations

import re
import urllib3
from datetime import datetime
from typing import Optional

import requests

from .models import HistoryBar, Quote, Snapshot

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://bstrade.bridge-securities.com/BSTradeServer/"
SESSION_TIMEOUT = 20


class BSApiError(Exception):
    pass


class BSApi:
    def __init__(self, base_url: str = BASE_URL, timeout: int = SESSION_TIMEOUT) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False

    # ------------------------------------------------------------------ market
    def market_snapshot(self) -> Snapshot:
        """Snapshot complet : indices + titres cotés."""
        url = self.base_url + "MarketDetails.aspx?mode=3"
        resp = self.session.post(url, timeout=self.timeout)
        resp.raise_for_status()
        lines = re.findall(r"<PAC_DET>([^<]+)</PAC_DET>", resp.text)
        indices: list[Quote] = []
        stocks: list[Quote] = []
        for line in lines:
            q = _parse_market_line(line)
            if q is None:
                continue
            if q.is_index:
                indices.append(q)
            else:
                stocks.append(q)
        return Snapshot(indices=indices, stocks=stocks)

    def session_times(self) -> dict:
        """Horaires de séance : {open, close, start, mode}."""
        url = self.base_url + "MarketDetails.aspx?mode=1"
        resp = self.session.post(url, timeout=self.timeout)
        resp.raise_for_status()
        m = re.search(r"<PACQ>([^<]+)</PACQ>", resp.text)
        if not m:
            return {}
        parts = m.group(1).split("|")
        return {
            "open": parts[0] if len(parts) > 0 else "",
            "close": parts[1] if len(parts) > 1 else "",
            "start": parts[2] if len(parts) > 2 else "",
            "mode": parts[3] if len(parts) > 3 else "",
        }

    # --------------------------------------------------------------- history
    def history(self, code: str, start: str, end: str) -> list[HistoryBar]:
        """Historique OHLCV d'un titre entre deux dates (YYYYMMDD)."""
        url = self.base_url + "Service.svc/GetDataStockByCodeAndInterval2"
        params = {"codeStock": code, "StartDate": start, "EndDate": end}
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        bars: list[HistoryBar] = []
        for item in data:
            ts = item.get("CurrentDate", 0)
            bars.append(
                HistoryBar(
                    date=datetime.fromtimestamp(ts / 1000) if ts else datetime.now(),
                    open=float(item.get("OpenP") or 0),
                    high=float(item.get("HighP") or 0),
                    low=float(item.get("LowP") or 0),
                    close=float(item.get("CloseP") or 0),
                    volume=int(item.get("Volume") or 0),
                )
            )
        bars.sort(key=lambda b: b.date)
        return bars


# ------------------------------------------------------------------- parsing
_NUM = re.compile(r"^-?\d+(\.\d+)?$")


def _to_float(value: str) -> float:
    value = (value or "").strip()
    try:
        return float(value)
    except ValueError:
        return 0.0


def _parse_market_line(line: str) -> Optional[Quote]:
    parts = line.split("|")
    if len(parts) < 8:
        return None
    raw_code = (parts[0] or "").replace("~Re/!", "").strip()
    if not raw_code:
        return None

    name = _extract_name(parts)
    is_index = raw_code.startswith("BRVM")

    if is_index:
        return Quote(
            code=raw_code,
            name=name or raw_code,
            isin=parts[1].strip(),
            last=_to_float(parts[3]),
            open=_to_float(parts[4]) if _to_float(parts[4]) else 0.0,
            high=_to_float(parts[5]),
            low=_to_float(parts[6]),
            traded_at=_parse_date(parts[-1]),
            is_index=True,
        )

    # Actions / obligations
    quote = Quote(
        code=raw_code,
        name=name or raw_code,
        isin=parts[1].strip(),
        last=_to_float(parts[3]),
        open=_to_float(parts[4]),
        high=_to_float(parts[5]),
        low=_to_float(parts[6]),
        change_pct=_to_float(parts[7]),
        volume=_to_int(parts[8]),
        high_52w=_to_float(parts[10]),
        low_52w=_to_float(parts[9]),
        traded_at=_parse_date(parts[-1]),
    )
    # VWAP / prix moyen : champ numérique immédiatement avant le nom
    name_idx = None
    for i in range(len(parts) - 1, -1, -1):
        p = (parts[i] or "").strip()
        if p and not _NUM.match(p) and not _looks_like_date(p) and p != "~Re/!":
            name_idx = i
            break
    if name_idx is not None and name_idx > 0 and _NUM.match(parts[name_idx - 1].strip()):
        quote.vwap = _to_float(parts[name_idx - 1])
    return quote


def _to_int(value: str) -> int:
    try:
        return int(float((value or "").strip()))
    except ValueError:
        return 0


def _parse_date(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _extract_name(parts: list[str]) -> str:
    """Le nom est le champ alpha qui précède les champs finaux numériques."""
    for part in reversed(parts):
        p = (part or "").strip()
        if p and not _NUM.match(p) and not _looks_like_date(p) and p != "~Re/!":
            return p
    return ""


def _looks_like_date(value: str) -> bool:
    return bool(re.search(r"\d{2}/\d{2}/\d{4}", value))
