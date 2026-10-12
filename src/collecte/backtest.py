"""Backtest de validation du score de screening.

Rejoue la stratégie « top N par score » sur l'historique disponible
(~janvier 2017 → aujourd'hui), mesure le rendement sur horizon H, et compare :
  - au panier équipondéré (benchmark « acheter tout le marché »)
  - à un panier aléatoire (preuve que le score bat le hasard)

Règle anti-biais : le score à la date D n'utilise QUE les barres ≤ D
(pas de look-ahead). Le rendement est mesuré sur les `horizon` séances
suivantes du titre.

Limites connues :
  - Survivorship bias : seuls les titres encore cotés aujourd'hui sont testés.
  - Benchmark = panier équipondéré (l'historique de l'indice BRVM-C n'est pas
    exposé par l'API).
"""
from __future__ import annotations

import bisect
import json
import pickle
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean, pstdev

from .bsapi import BSApi
from ..domaine.models import HistoryBar
from ..analyse.screening import avg_volume, change_pct, compute_score, ema, rsi_wilder
from ..infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

CACHE_FILE = DATA_DIR / "history_cache.pkl"
HISTORY_START = "20170101"
MAX_WORKERS = 8
CACHE_MAX_AGE_DAYS = 7  # re-télécharger l'historique si le cache a plus d'une semaine
CACHE_STALE_DATA_DAYS = 4  # ... et dès que les DONNÉES ont plus de 4 jours (mtime ≠ fraîcheur)
INACTIFS_FILE = DATA_DIR / "titres_inactifs.json"  # titres vérifiés dormants (source muette)
INACTIF_APRES_JOURS = 8  # aligné sur cache_integrity.MAX_CACHE_AGE_DAYS


def _donnees_fraiches(data: dict, today: datetime | None = None) -> bool:
    """Les DONNÉES du cache sont-elles récentes (dernière barre < CACHE_STALE_DATA_DAYS) ?

    Le mtime seul ne suffit pas : un refresh peut capturer des données DÉJÀ en retard —
    cas vécu le 09/10 (fichier daté du jour, dernières barres au 30/09) qui a figé le
    cache sept jours de plus. Ici on re-télécharge dès que les données ont > 4 jours,
    ce qui rend aussi le système AUTO-RÉPARANT : un refresh raté est retenté chaque jour.
    """
    today = today or datetime.now()
    dernieres = [bars[-1].date for bars in data.values() if bars]
    return bool(dernieres) and (today - max(dernieres)).days < CACHE_STALE_DATA_DAYS


def _enregistrer_inactifs(data: dict, today: datetime | None = None) -> None:
    """Après un refresh, note les titres DORMANTS (source muette) dans `titres_inactifs.json`.

    Un titre dont la source interrogée ne fournit aucune barre récente (> INACTIF_APRES_JOURS)
    est « vérifié dormant » à cette date : le contrôle d'intégrité s'en sert pour ne pas
    signaler un « cache en retard » sur un titre simplement sans transactions (SEMC/SICC…).
    Toute barre plus récente au refresh suivant le sort naturellement du registre.
    """
    today = today or datetime.now()
    registre = {}
    try:
        registre = json.loads(INACTIFS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        registre = {}
    actuels = {}
    for code, bars in data.items():
        if not bars:
            continue
        age = (today - bars[-1].date).days
        if age > INACTIF_APRES_JOURS:
            actuels[code.upper()] = {
                "derniere_barre": bars[-1].date.strftime("%Y-%m-%d"),
                "verifie_le": today.strftime("%Y-%m-%d"),
            }
    if actuels or registre:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = INACTIFS_FILE.with_name(INACTIFS_FILE.name + ".tmp")
        tmp.write_text(json.dumps(actuels, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(INACTIFS_FILE)


# -------------------------------------------------------------------- data
def _fetch_history(api: BSApi, code: str, end: str) -> list[HistoryBar]:
    """Historique d'un titre, avec fallback si l'API timeout sur le start long.

    Titres récents/renommés (SAFC, ORAC, UNLC…) : l'API BSTrade plante en
    ReadTimeout quand l'historique est demandé depuis 2017 (le titre n'existait
    pas). On retente alors sur ~2 ans.
    """
    try:
        return api.history(code, HISTORY_START, end)
    except Exception:
        recent = (datetime.now() - timedelta(days=2 * 365)).strftime("%Y%m%d")
        return api.history(code, recent, end)


def load_all_history(api: BSApi, force: bool = False) -> dict[str, list[HistoryBar]]:
    """Historique de toutes les actions (pas les obligations), avec cache disque.

    Le cache est réutilisé s'il a moins de CACHE_MAX_AGE_DAYS jours, sinon
    l'historique est re-téléchargé pour rester à jour.
    """
    if CACHE_FILE.exists() and not force:
        age_days = (time.time() - CACHE_FILE.stat().st_mtime) / 86400
        if age_days < CACHE_MAX_AGE_DAYS:
            try:
                with CACHE_FILE.open("rb") as fh:
                    data = pickle.load(fh)
                if data and _donnees_fraiches(data):
                    return data
            except (pickle.PickleError, OSError):
                pass

    snapshot = api.market_snapshot()
    codes = [q.code for q in snapshot.stocks if not q.is_obligation and q.last > 0]
    end = datetime.now().strftime("%Y%m%d")
    data: dict[str, list[HistoryBar]] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_history, api, c, end): c for c in codes}
        for fut in as_completed(futures):
            code = futures[fut]
            try:
                bars = [b for b in fut.result() if b.close > 0]
            except Exception:
                continue
            if bars:
                data[code] = bars

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CACHE_FILE.open("wb") as fh:
        pickle.dump(data, fh)
    _enregistrer_inactifs(data)  # note les titres dormants (source muette) — anti-faux « retard »
    return data


# ------------------------------------------------------------ score + return
def _score_and_return(
    bars: list[HistoryBar], idx: int, horizon: int
) -> tuple[float, float] | None:
    """Score à la position idx (fenêtre ≤ idx) et rendement sur `horizon` séances."""
    if idx < 60 or idx + horizon >= len(bars):
        return None
    window = bars[max(0, idx - 99) : idx + 1]
    closes = [b.close for b in window]
    last = closes[-1]

    rsi = rsi_wilder(closes)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    chg5 = change_pct(window, 5)
    chg20 = change_pct(window, 20)
    vol_ratio = bars[idx].volume / avg_volume(window) if avg_volume(window) > 0 else 0.0

    # range ~52 semaines : min/max des 250 dernières séances
    win250 = [b.close for b in bars[max(0, idx - 249) : idx + 1]]
    hi, lo = max(win250), min(win250)
    range_52w = (last - lo) / (hi - lo) if hi > lo else 0.0

    score = compute_score(rsi, ema20, ema50, last, chg5, chg20, vol_ratio, range_52w)
    ret = bars[idx + horizon].close / last - 1.0
    return score, ret


# ------------------------------------------------------------------- metrics
@dataclass
class BacktestResult:
    decisions: list = field(default_factory=list)  # (date, strat_ret, bench_ret, rand_ret)
    top: int = 10
    horizon: int = 20
    n_titles: int = 0
    start_date: str = ""
    end_date: str = ""

    def series(self, key: str) -> list[float]:
        idx = {"strat": 1, "bench": 2, "rand": 3}[key]
        return [d[idx] for d in self.decisions]


def run_backtest(
    api: BSApi,
    top: int = 10,
    horizon: int = 20,
    step: int = 20,
    force: bool = False,
) -> BacktestResult:
    hist = load_all_history(api, force=force)
    hist = {c: b for c, b in hist.items() if len(b) >= 80}

    # dates de décision : union triée, échantillonnée tous les `step` jours
    all_dates = sorted({b.date.date() for bars in hist.values() for b in bars})
    decision_dates = all_dates[60::step]

    res = BacktestResult(top=top, horizon=horizon, n_titles=len(hist))
    rng = random.Random(42)

    for di, D in enumerate(decision_dates):
        rows: list[tuple[str, float, float]] = []
        for code, bars in hist.items():
            dates = [b.date.date() for b in bars]
            idx = bisect.bisect_right(dates, D) - 1
            if idx < 0:
                continue
            sr = _score_and_return(bars, idx, horizon)
            if sr is not None:
                rows.append((code, sr[0], sr[1]))
        if len(rows) < top + 5:
            continue

        rows.sort(key=lambda r: r[1], reverse=True)
        strat = fmean([r[2] for r in rows[:top]])
        bench = fmean([r[2] for r in rows])
        random_sel = rng.sample(rows, min(top, len(rows)))
        rand = fmean([r[2] for r in random_sel])
        res.decisions.append((D, strat, bench, rand))

    if res.decisions:
        res.start_date = str(res.decisions[0][0])
        res.end_date = str(res.decisions[-1][0])
    return res


def _cum_returns(rets: list[float]) -> list[float]:
    curve, val = [], 1.0
    for r in rets:
        val *= 1.0 + r
        curve.append(val)
    return curve


def _drawdown(curve: list[float]) -> float:
    peak, dd = 1.0, 0.0
    for v in curve:
        peak = max(peak, v)
        dd = max(dd, (peak - v) / peak)
    return dd


def summarize(res: BacktestResult) -> dict:
    """Métriques de synthèse pour stratégie / benchmark / aléatoire."""
    out = {}
    per_year = 250 / res.horizon  # ~périodes par an
    for key in ("strat", "bench", "rand"):
        rets = res.series(key)
        if not rets:
            out[key] = {}
            continue
        curve = _cum_returns(rets)
        total = curve[-1] - 1.0
        mean = fmean(rets)
        sd = pstdev(rets)
        sharpe = (mean / sd) * (per_year ** 0.5) if sd > 0 else 0.0
        out[key] = {
            "total": total,
            "mean": mean,
            "hit_rate": sum(1 for r in rets if r > 0) / len(rets),
            "sharpe": sharpe,
            "drawdown": _drawdown(curve),
            "n": len(rets),
        }
    out["surperformance_vs_bench"] = out["strat"]["total"] - out["bench"]["total"]
    out["surperformance_vs_rand"] = out["strat"]["total"] - out["rand"]["total"]
    return out


def walk_forward(res: BacktestResult) -> list[tuple[str, float, float]]:
    """Surperformance moyenne par année (stabilité temporelle)."""
    by_year: dict[int, list[float]] = {}
    for d in res.decisions:
        y = d[0].year
        by_year.setdefault(y, []).append(d[1] - d[2])  # strat - bench
    rows = []
    for y in sorted(by_year):
        rows.append((str(y), fmean(by_year[y]), len(by_year[y])))
    return rows


def format_report(res: BacktestResult) -> str:
    s = summarize(res)
    lines = []
    lines.append("=" * 70)
    lines.append(f"BACKTEST DU SCORE — top {res.top}, horizon {res.horizon} séances")
    lines.append(f"Période : {res.start_date} → {res.end_date}  ({res.n_titles} titres)")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"{'':22s} {'Top%+d' % res.top:>10s} {'Marché':>10s} {'Aléatoire':>10s}")
    lines.append("-" * 70)
    lines.append(f"{'Rendement total':22s} {s['strat']['total']*100:9.1f}% {s['bench']['total']*100:9.1f}% {s['rand']['total']*100:9.1f}%")
    lines.append(f"{'Rendement moyen/dec':22s} {s['strat']['mean']*100:9.2f}% {s['bench']['mean']*100:9.2f}% {s['rand']['mean']*100:9.2f}%")
    lines.append(f"{'Hit rate (>0)':22s} {s['strat']['hit_rate']*100:9.0f}% {s['bench']['hit_rate']*100:9.0f}% {s['rand']['hit_rate']*100:9.0f}%")
    lines.append(f"{'Sharpe (annualisé)':22s} {s['strat']['sharpe']:9.2f} {s['bench']['sharpe']:9.2f} {s['rand']['sharpe']:9.2f}")
    lines.append(f"{'Drawdown max':22s} {s['strat']['drawdown']*100:9.1f}% {s['bench']['drawdown']*100:9.1f}% {s['rand']['drawdown']*100:9.1f}%")
    lines.append("")
    lines.append(f"Surperformance vs marché   : {s['surperformance_vs_bench']*100:+.1f}%")
    lines.append(f"Surperformance vs aléatoire: {s['surperformance_vs_rand']*100:+.1f}%")
    lines.append("")
    lines.append("Stabilité par année (surperformance vs marché) :")
    for y, sp, n in walk_forward(res):
        bar = "█" * max(0, int(sp * 1000)) if sp > 0 else "░" * min(0, int(sp * 1000))
        lines.append(f"  {y}: {sp*100:+6.2f}%  ({n} décisions)")
    lines.append("")
    return "\n".join(lines)


def main_backtest(top: int = 10, horizon: int = 20, force: bool = False) -> str:
    t0 = time.time()
    api = BSApi()
    res = run_backtest(api, top=top, horizon=horizon, force=force)
    report = format_report(res)
    report += f"\n(calculé en {time.time()-t0:.1f}s — historique de {res.n_titles} titres)\n"
    return report
