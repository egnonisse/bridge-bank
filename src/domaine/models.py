"""Modèles de données pour BS Trade Analyzer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Quote:
    """Cotation d'une valeur (action ou obligation) sur la BRVM."""

    code: str
    name: str
    isin: str = ""
    last: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    high_52w: float = 0.0
    low_52w: float = 0.0
    vwap: float = 0.0
    traded_at: Optional[datetime] = None
    is_index: bool = False

    @property
    def is_obligation(self) -> bool:
        return "." in self.code or self.code.startswith("TP") and "O" in self.code

    @property
    def range_52w(self) -> float:
        """Position dans le range 52 semaines (0..1), None si indisponible."""
        if self.high_52w <= 0 or self.low_52w <= 0 or self.high_52w <= self.low_52w:
            return 0.0
        return (self.last - self.low_52w) / (self.high_52w - self.low_52w)


@dataclass
class Snapshot:
    """Snapshot marché complet."""

    indices: list[Quote] = field(default_factory=list)
    stocks: list[Quote] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.now)

    def by_code(self, code: str) -> Optional[Quote]:
        code = code.strip().upper()
        for q in self.stocks + self.indices:
            if q.code.strip().upper() == code:
                return q
        return None


@dataclass
class HistoryBar:
    """Barre OHLCV journalière."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class Analysis:
    """Résultat d'analyse d'un titre."""

    quote: Quote
    bars: list[HistoryBar] = field(default_factory=list)
    rsi: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    sma20: Optional[float] = None
    avg_volume_20: float = 0.0
    change_5d: float = 0.0
    change_20d: float = 0.0
    volume_ratio: float = 0.0
    signals: list[str] = field(default_factory=list)
    score: float = 0.0
