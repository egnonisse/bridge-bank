"""Screening et analyse technique des titres BRVM.

Les indicateurs sont calculés localement depuis l'historique OHLCV
(RSI Wilder, SMA/EMA, momentum, volumes) — pas de dépendance aux
endpoints d'indicateurs du serveur (moins d'appels, plus fiable).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from statistics import fmean

from ..collecte.bsapi import BSApi
from ..domaine.models import Analysis, HistoryBar, Quote

HISTORY_DAYS = 90
MAX_WORKERS = 6


# ------------------------------------------------------------- indicators
def rsi_wilder(closes: list[float], period: int = 14) -> float | None:
    """RSI selon la méthode de Wilder."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return fmean(values[-period:])


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    seed = fmean(values[:period])
    result = seed
    for v in values[period:]:
        result = v * k + result * (1 - k)
    return result


def change_pct(bars: list[HistoryBar], days: int) -> float:
    """Variation % sur ~N jours de séance (si dispo)."""
    if len(bars) < 2:
        return 0.0
    ref = bars[0].close
    target = bars[-1].close
    for b in reversed(bars[:-1]):
        if (bars[-1].date - b.date).days >= days:
            ref = b.close
            break
    if ref == 0:
        return 0.0
    return (target - ref) / ref * 100.0


def avg_volume(bars: list[HistoryBar], period: int = 20) -> float:
    vols = [b.volume for b in bars[-period:] if b.volume > 0]
    return fmean(vols) if vols else 0.0


def compute_score(
    rsi: float | None,
    ema20: float | None,
    ema50: float | None,
    last: float,
    change_5d: float,
    change_20d: float,
    volume_ratio: float,
    range_52w: float,
) -> float:
    """Score composite (pondérations heuristiques — à valider par backtest)."""
    score = 0.0
    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 1.0
        elif 30 <= rsi < 40:
            score += 0.5
    if ema20 and ema50 and last > ema50:
        score += 1.5
    score += min(max(change_20d / 10, -1.0), 1.0) * 1.5
    if change_5d > 0:
        score += 0.5
    if volume_ratio > 1.5:
        score += 0.5
    if range_52w >= 0.8:
        score += 0.5
    return round(score, 2)


# ------------------------------------------------------------------ signals
def _build_analysis(quote: Quote, bars: list[HistoryBar]) -> Analysis:
    closes = [b.close for b in bars if b.close > 0]
    vols = [b.volume for b in bars]
    a = Analysis(quote=quote, bars=bars)
    if not closes:
        return a

    a.rsi = rsi_wilder(closes)
    a.ema20 = ema(closes, 20)
    a.ema50 = ema(closes, 50) if len(closes) >= 50 else ema(closes, len(closes) // 2)
    a.sma20 = sma(closes, 20)
    a.avg_volume_20 = avg_volume(bars)
    a.change_5d = change_pct(bars, 5)
    a.change_20d = change_pct(bars, 20)
    a.volume_ratio = quote.volume / a.avg_volume_20 if a.avg_volume_20 > 0 else 0.0

    # Signaux
    if a.rsi is not None:
        if a.rsi < 30:
            a.signals.append("RSI survente (<30) — potentiel de rebond")
        elif a.rsi > 70:
            a.signals.append("RSI surchauffe (>70)")
    if a.ema20 and a.ema50:
        if quote.last > a.ema50:
            a.signals.append("Cours au-dessus de l'EMA50 (tendance haussière)")
        else:
            a.signals.append("Cours sous l'EMA50 (tendance baissière)")
    if a.change_20d > 5:
        a.signals.append(f"Momentum 20j positif (+{a.change_20d:.1f}%)")
    elif a.change_20d < -5:
        a.signals.append(f"Momentum 20j négatif ({a.change_20d:.1f}%)")
    if a.volume_ratio > 2:
        a.signals.append(f"Volume anormal ({a.volume_ratio:.1f}x la moyenne)")
    if quote.range_52w >= 0.9 and quote.high_52w > 0:
        a.signals.append("Proche du plus haut 52 semaines (tendance forte)")

    # Score composite (pondérations heuristiques)
    a.score = compute_score(
        a.rsi, a.ema20, a.ema50, quote.last,
        a.change_5d, a.change_20d, a.volume_ratio, quote.range_52w,
    )
    return a


# ------------------------------------------------------------------- screen
def screen(api: BSApi, top: int = 15, min_volume: int = 100) -> list[Analysis]:
    """Analyse toutes les actions et retourne le classement par score.

    Ignore les obligations (codes avec '.') et les titres sans activité.
    """
    snapshot = api.market_snapshot()
    today = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=HISTORY_DAYS)).strftime("%Y%m%d")

    candidates = [
        q for q in snapshot.stocks
        if not q.is_obligation and q.last > 0
    ]

    results: list[Analysis] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(api.history, q.code, start, today): q for q in candidates
        }
        for fut in as_completed(futures):
            q = futures[fut]
            try:
                bars = fut.result()
            except Exception:
                continue
            if not bars:
                continue
            a = _build_analysis(q, bars)
            if q.volume >= min_volume or a.change_5d != 0:
                results.append(a)

    results.sort(key=lambda a: a.score, reverse=True)
    return results[:top]


def analyze(api: BSApi, code: str) -> Analysis | None:
    """Analyse détaillée d'un titre précis."""
    snapshot = api.market_snapshot()
    quote = snapshot.by_code(code)
    if quote is None:
        return None
    today = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=HISTORY_DAYS)).strftime("%Y%m%d")
    bars = api.history(code, start, today)
    if not bars:
        return _build_analysis(quote, [])
    return _build_analysis(quote, bars)
