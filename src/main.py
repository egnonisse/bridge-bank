"""CLI BS Trade Analyzer — screening BRVM + alertes Telegram.

Usage:
    python -m src.main screen [--top N] [--min-vol V]
    python -m src.main analyze CODE
    python -m src.main top
    python -m src.main watch add CODE [--max X] [--min X] [--var X]
    python -m src.main watch remove CODE
    python -m src.main watch list
    python -m src.main alert --once
    python -m src.main alert --loop [--interval S]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import yaml

from .bsapi import BSApi
from .notify import TelegramNotifier
from .screening import analyze as analyze_stock
from .screening import screen

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"


def load_dotenv() -> None:
    """Charge ROOT/.env dans os.environ (si non déjà défini)."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get_notifier(cfg: dict) -> TelegramNotifier:
    tg = cfg.get("telegram", {})
    token = os.getenv("TELEGRAM_BOT_TOKEN") or tg.get("bot_token", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or tg.get("chat_id", "")
    return TelegramNotifier(token, chat_id)


def cmd_screen(args: argparse.Namespace) -> None:
    api = BSApi()
    print(f"Screening marché BRVM (top {args.top})…\n")
    results = screen(api, top=args.top, min_volume=args.min_vol)
    print(f"{'CODE':8s} {'NOM':28s} {'COURS':>10s} {'VAR5J':>8s} {'VAR20J':>8s} {'RSI':>5s} {'VOLRAT':>6s} {'SCORE':>6s}")
    print("-" * 95)
    for a in results:
        rsi = f"{a.rsi:.0f}" if a.rsi is not None else "-"
        name = a.quote.name[:27]
        print(
            f"{a.quote.code:8s} {name:28s} {a.quote.last:10,.0f} "
            f"{a.change_5d:7.1f}% {a.change_20d:7.1f}% {rsi:>5s} {a.volume_ratio:6.1f} {a.score:6.1f}"
        )
    print("\nScore = tendance (EMA50) + RSI + momentum 20j + volumes. Recherche d'achat : score élevé sans RSI >70.")


def cmd_analyze(args: argparse.Namespace) -> None:
    api = BSApi()
    a = analyze_stock(api, args.code)
    if a is None:
        print(f"Titre {args.code} introuvable.")
        sys.exit(1)
    q = a.quote
    print(f"=== {q.name} ({q.code}) ===")
    print(f"Cours: {q.last:,.0f} FCFA   Var jour: {q.change_pct:+.2f}%")
    print(f"Ouverture: {q.open:,.0f}   +Haut: {q.high:,.0f}   +Bas: {q.low:,.0f}   Volume: {q.volume:,}")
    print(f"Range 52 sem: {q.low_52w:,.0f} – {q.high_52w:,.0f} (position: {q.range_52w*100:.0f}%)")
    if q.vwap:
        print(f"Prix moyen jour: {q.vwap:,.2f} FCFA")
    print()
    print(f"RSI(14): {a.rsi:.1f}" if a.rsi is not None else "RSI(14): n/a")
    print(f"EMA20: {a.ema20:,.0f}   EMA50: {a.ema50:,.0f}" if a.ema20 else "EMA: n/a")
    print(f"Var 5j: {a.change_5d:+.2f}%   Var 20j: {a.change_20d:+.2f}%")
    print(f"Volume: {q.volume:,}  (moy 20j: {a.avg_volume_20:,.0f}, ratio {a.volume_ratio:.1f}x)")
    print(f"Score: {a.score}/7")
    print("\nSignaux:")
    for s in a.signals:
        print(f"  • {s}")
    if not a.signals:
        print("  (aucun signal particulier)")


def cmd_top(args: argparse.Namespace) -> None:
    api = BSApi()
    snap = api.market_snapshot()
    stocks = [q for q in snap.stocks if q.last > 0 and not q.is_obligation]
    hausses = sorted(stocks, key=lambda q: q.change_pct, reverse=True)[:args.n]
    baisses = sorted(stocks, key=lambda q: q.change_pct)[:args.n]
    print("=== TOP HAUSSES DU JOUR ===")
    for q in hausses:
        print(f"  {q.code:8s} {q.name[:26]:26s} {q.last:10,.0f}  {q.change_pct:+.2f}%")
    print("\n=== TOP BAISSES DU JOUR ===")
    for q in baisses:
        print(f"  {q.code:8s} {q.name[:26]:26s} {q.last:10,.0f}  {q.change_pct:+.2f}%")


def load_watchlist(cfg: dict) -> dict:
    return cfg.get("watchlist", {}) or {}


def save_watchlist(cfg: dict, watchlist: dict) -> None:
    cfg["watchlist"] = watchlist
    with CONFIG_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)


def cmd_watch(args: argparse.Namespace) -> None:
    cfg = load_config()
    watchlist = load_watchlist(cfg)
    code = args.code.strip().upper() if args.code else ""

    if args.action == "add":
        rules = {k: v for k, v in (("max", args.max), ("min", args.min), ("change_pct", args.var)) if v is not None}
        if not rules:
            print("Au moins un seuil requis : --max, --min ou --var")
            sys.exit(1)
        watchlist[code] = rules
        save_watchlist(cfg, watchlist)
        print(f"✓ {code} surveillé : {rules}")
    elif args.action == "remove":
        if code in watchlist:
            del watchlist[code]
            save_watchlist(cfg, watchlist)
            print(f"✓ {code} retiré de la watchlist")
        else:
            print(f"{code} n'est pas dans la watchlist")
    elif args.action == "list":
        if not watchlist:
            print("Watchlist vide. Ajoutez: watch add CODE --max X --min X --var X")
        for code, rules in watchlist.items():
            print(f"  {code}: {rules}")


def cmd_alert(args: argparse.Namespace) -> None:
    from .alerts import AlertEngine, run_loop

    cfg = load_config()
    watchlist = load_watchlist(cfg)
    if not watchlist:
        print("Watchlist vide — rien à surveiller. Ajoutez d'abord des titres :")
        print("  python -m src.main watch add SIVC --max 2600 --min 2200 --var 5")
        sys.exit(1)

    notifier = get_notifier(cfg)
    if not notifier.enabled:
        print("⚠️  Telegram non configuré — les alertes ne seront PAS envoyées.")
        print("   1. Créez un bot avec @BotFather → obtenez le token")
        print("   2. Mettez TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans config.yaml (ou .env)")
        print("   3. Envoyez un message au bot puis récupérez votre chat_id")

    api = BSApi()
    interval = args.interval or cfg.get("alerts", {}).get("interval_seconds", 300)
    cooldown = cfg.get("alerts", {}).get("cooldown_minutes", 30)
    session_only = cfg.get("alerts", {}).get("session_only", True)

    if args.once:
        # Vérification manuelle : toujours répondre, même hors séance
        engine = AlertEngine(api, notifier, watchlist, cooldown, session_only, respect_session=False)
        messages = engine.check_once()
        if not messages:
            print("Aucun seuil franchi.")
        for msg in messages:
            print("🔔", msg)
            notifier.send(msg)
    else:
        run_loop(api, notifier, watchlist, interval, cooldown, session_only)


def main() -> None:
    # Console Windows : forcer UTF-8 pour les caractères spéciaux (⅓, ≥, emojis)
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    parser = argparse.ArgumentParser(prog="bstrade", description="BS Trade Analyzer — BRVM")
    sub = parser.add_subparsers(dest="command", required=True)

    p_screen = sub.add_parser("screen", help="Classement screening du marché")
    p_screen.add_argument("--top", type=int, default=15)
    p_screen.add_argument("--min-vol", type=int, default=100)
    p_screen.set_defaults(func=cmd_screen)

    p_an = sub.add_parser("analyze", help="Fiche détaillée d'un titre")
    p_an.add_argument("code")
    p_an.set_defaults(func=cmd_analyze)

    p_top = sub.add_parser("top", help="Top hausses/baisses du jour")
    p_top.add_argument("-n", type=int, default=10)
    p_top.set_defaults(func=cmd_top)

    p_watch = sub.add_parser("watch", help="Gérer la watchlist")
    p_watch.add_argument("action", choices=["add", "remove", "list"])
    p_watch.add_argument("code", nargs="?")
    p_watch.add_argument("--max", type=float, help="Seuil haut (prix >=)")
    p_watch.add_argument("--min", type=float, help="Seuil bas (prix <=)")
    p_watch.add_argument("--var", type=float, help="Seuil variation du jour (%%)")
    p_watch.set_defaults(func=cmd_watch)

    p_alert = sub.add_parser("alert", help="Vérifier les alertes")
    p_alert.add_argument("--once", action="store_true", help="Vérification unique")
    p_alert.add_argument("--loop", action="store_true", help="Boucle continue")
    p_alert.add_argument("--interval", type=int, help="Secondes entre vérifications")
    p_alert.set_defaults(func=cmd_alert)

    p_bt = sub.add_parser("backtest", help="Valider le score par backtest")
    p_bt.add_argument("--top", type=int, default=10)
    p_bt.add_argument("--horizon", type=int, default=20)
    p_bt.add_argument("--force", action="store_true", help="Re-télécharger l'historique")
    p_bt.set_defaults(func=cmd_backtest)

    p_spec = sub.add_parser("spec", help="Spéculation (signaux + positions)")
    p_spec.add_argument("action", choices=["screen", "open", "status", "check", "alert", "close"])
    p_spec.add_argument("code", nargs="?")
    p_spec.add_argument("--amount", type=float, default=100000, help="Montant à investir (FCFA)")
    p_spec.add_argument("--min", type=int, default=3, help="Confluence minimale de signaux")
    p_spec.set_defaults(func=cmd_spec)

    p_portf = sub.add_parser("portf", help="Noyau dividende (positions long terme)")
    p_portf.add_argument("action", choices=["open", "status", "check", "dividend", "close"])
    p_portf.add_argument("code", nargs="?")
    p_portf.add_argument("--amount", type=float, default=100000, help="Montant à investir (FCFA)")
    p_portf.add_argument("--dps", type=float, help="Dividende par action (FCFA)")
    p_portf.add_argument("--per", type=float, help="PER à l'ouverture")
    p_portf.set_defaults(func=cmd_portf)

    p_report = sub.add_parser("report", help="Rapport mensuel de santé du portefeuille")
    p_report.add_argument("action", choices=["show", "cash"], nargs="?", default="show")
    p_report.add_argument("--amount", type=float, help="Solde de liquidités (FCFA)")
    p_report.set_defaults(func=cmd_report)

    p_boc = sub.add_parser("boc", help="BOC : dividendes + rectificatifs (source complète)")
    p_boc.set_defaults(func=cmd_boc)

    p_div = sub.add_parser("div", help="Dividendes encaissés (avis BSTrade) — suivi réel + IRVM")
    p_div.add_argument("action", choices=["list", "add"], nargs="?", default="list")
    p_div.add_argument("code", nargs="?")
    p_div.add_argument("--amount", type=float, help="Montant NET encaissé (FCFA)")
    p_div.add_argument("--actions", type=int, default=0, help="Nombre d'actions détenues")
    p_div.add_argument("--date", help="Date d'encaissement (AAAA-MM-JJ)")
    p_div.set_defaults(func=cmd_div)

    p_fund = sub.add_parser("fund", help="Screener fondamentaux (value+dividende, magic formula)")
    p_fund.add_argument("mode", choices=["value", "magic", "traps"])
    p_fund.add_argument("--force", action="store_true", help="Re-scraper les fondamentaux")
    p_fund.add_argument("--alert", action="store_true", help="Détecter les NOUVEAUX titres value + alerte Telegram")
    p_fund.set_defaults(func=cmd_fund)

    p_limits = sub.add_parser("limits", help="Ordres limites du noyau dividende (prix d'achat net 4 %%)")
    p_limits.add_argument("--target", type=float, default=4.0, help="Rendement net cible en %% (défaut 4)")
    p_limits.set_defaults(func=cmd_limits)

    p_radar = sub.add_parser("radar", help="Radar de veille : titres en sortie de fond (zéro trading)")
    p_radar.add_argument("--alert", action="store_true", help="Alerte Telegram des NOUVEAUX titres de niveau 1 (anti-spam : chaque titre une seule fois)")
    p_radar.add_argument("--mark", nargs="+", help="Marquer des codes comme veille FAITE (anti-spam du cron de veille)")
    p_radar.set_defaults(func=cmd_radar)

    p_noyau = sub.add_parser("noyau-check", help="Filtres noyau sur un candidat (alerte d'achat QUALIFIÉE — jamais sans les 4 filtres)")
    p_noyau.add_argument("code", nargs="+", help="Code(s) BRVM à évaluer")
    p_noyau.set_defaults(func=cmd_noyau_check)

    p_sustain = sub.add_parser("sustain", help="Soutenabilité des dividendes du noyau (payout, anti value-trap)")
    p_sustain.set_defaults(func=cmd_sustain)

    p_news = sub.add_parser("news", help="Annonces officielles BRVM sur les titres du noyau")
    p_news.add_argument("--check", action="store_true", help="Détecter les nouveautés + alerte Telegram")
    p_news.set_defaults(func=cmd_news)

    p_live = sub.add_parser("live", help="Cours temps réel BRVM (brvm.org) + état de la séance")
    p_live.set_defaults(func=cmd_live)

    p_integrity = sub.add_parser("integrity", help="Contrôle d'intégrité des données (cache, cassures, profils)")
    p_integrity.set_defaults(func=cmd_integrity)

    p_bond = sub.add_parser("bond", help="Obligations BRVM (hors stratégie depuis 03/09/2026 — manuel uniquement)")
    p_bond.add_argument("action", choices=["list", "ytm", "buy", "show"], nargs="?", default="list")
    p_bond.add_argument("code", nargs="?")
    p_bond.add_argument("--qty", type=int, help="Nombre de titres (buy)")
    p_bond.add_argument("--price", type=float, help="Prix en %% du nominal (ytm, buy)")
    p_bond.set_defaults(func=cmd_bond)

    p_daily = sub.add_parser("daily", help="Check quotidien complet (annonces + noyau + spéculation)")
    p_daily.set_defaults(func=cmd_daily)

    args = parser.parse_args()
    args.func(args)


def cmd_backtest(args: argparse.Namespace) -> None:
    from .backtest import main_backtest

    print(main_backtest(top=args.top, horizon=args.horizon, force=args.force))


def cmd_spec(args: argparse.Namespace) -> None:
    from .speculation import (
        check_all,
        load_positions,
        open_position,
        save_positions,
        screen_speculation,
    )

    api = BSApi()
    if args.action == "screen":
        print("Screening spéculatif (≥3 signaux)…\n")
        results = screen_speculation(api, min_signals=args.min)
        if not results:
            print("Aucun titre avec la confluence requise.")
            return
        print(f"{'Code':7s} {'Nom':26s} {'Cours':>9s} {'Sig':>3s}  Signaux")
        print("-" * 72)
        for r in results:
            print(
                f"{r['code']:7s} {r['name'][:25]:26s} {r['last']:>9,.0f} "
                f"{r['count']:>3d}  {', '.join(r['signals'])}"
            )
    elif args.action == "open":
        positions = load_positions()
        if any(p.code == args.code.upper() and not p.closed for p in positions):
            print(f"Position déjà ouverte sur {args.code}.")
            return
        try:
            pos = open_position(api, args.code, args.amount)
        except ValueError as e:
            print(f"⛔ {e}")
            return
        positions.append(pos)
        save_positions(positions)
        print(f"✓ Position ouverte : {pos.name} ({pos.code})")
        print(f"  {pos.quantity} actions à {pos.entry_price:,.0f} = {pos.quantity * pos.entry_price:,.0f} FCFA")
        print(f"  Stop-loss −15 % : {pos.stop_loss:,.0f}")
        print("  Paliers : +20 % (vendre ⅓), +35 % (vendre ⅓), +50 % (clôture)")
    elif args.action == "status":
        from .speculation import ZONE_DEAD_INFO_DAYS, zone_morte_status

        positions = load_positions()
        snap = api.market_snapshot()
        if not positions:
            print("Aucune position. Ouvrez-en une : spec open CODE --amount 100000")
            return
        print(f"{'Code':7s} {'Nom':22s} {'Entrée':>8s} {'Cours':>8s} {'Perf':>7s} {'Stop':>8s}  État")
        print("-" * 78)
        for p in positions:
            quote = snap.by_code(p.code)
            cur = quote.last if quote else p.entry_price
            perf = (cur / p.entry_price - 1) * 100
            etat = "CLÔTURÉ" if p.closed else "ouverte"
            print(
                f"{p.code:7s} {p.name[:21]:22s} {p.entry_price:>8,.0f} {cur:>8,.0f} "
                f"{perf:>+6.1f}% {p.stop_loss:>8,.0f}  {etat}"
            )
        for p in positions:
            if p.closed:
                continue
            zm = zone_morte_status(p, api)
            if zm and zm[1] and zm[0] >= ZONE_DEAD_INFO_DAYS:
                print(f"   ⏳ {p.code} : zone morte depuis {zm[0]} séances "
                      f"(ni +20 % ni stop −15 %). Histoire : conserver reste positif ; "
                      f"revue automatique à ~120 séances.")
    elif args.action == "check":
        events = check_all(api)
        notifier = get_notifier(load_config())
        if not events:
            print("Aucun événement (stops/paliers non déclenchés).")
            return
        for e in events:
            print(e)
            notifier.send(f"🎲 Spéculation : {e}")
    elif args.action == "alert":
        from .live import ORDER_CUTOFF_BSTRADE
        from .speculation import STOP_LOSS, TAKE_1, TAKE_2, TAKE_3, detect_new_candidates

        new = detect_new_candidates(api, min_signals=args.min)
        notifier = get_notifier(load_config())
        if not new:
            print("Aucun nouveau candidat spéculatif.")
            return
        for c in new:
            last = c["last"]
            qty = max(1, int(args.amount // last)) if last > 0 else 1
            limit = round(last * 1.03)
            stop = round(last * (1 - STOP_LOSS))
            t1 = round(last * (1 + TAKE_1))
            t2 = round(last * (1 + TAKE_2))
            t3 = round(last * (1 + TAKE_3))
            msg = (
                f"🎲 SPÉCULATION — NOUVEAU CANDIDAT\n\n"
                f"🟢 ACHÈTE {c['name']} ({c['code']})\n"
                f"   Signaux ({c['count']}) : {', '.join(c['signals'])}\n"
                f"   Cours (clôture veille) : {last:,.0f} F\n\n"
                f"   📋 Ordre : ACHAT {qty} act. {c['code']} à ≤ {limit:,.0f} F (limite +3 %)\n"
                f"      → investi ≈ {qty * last:,.0f} F\n\n"
                f"   🛑 Stop −15 % : {stop:,.0f} F → vends tout\n"
                f"   🎯 Paliers : +20 % ({t1:,.0f}) vends ⅓ → stop remonte à {last:,.0f}\n"
                f"               +35 % ({t2:,.0f}) vends ⅓ → stop suiveur\n"
                f"               +50 % ({t3:,.0f}) clôture\n\n"
                f"   ⏰ Passe l'ordre sur BSTrade avant {ORDER_CUTOFF_BSTRADE:%Hh%M} "
                f"(courriel avant 11h).\n"
                f"   ⚠️ Vérifie le cours du jour (brvm.org) avant d'envoyer l'ordre."
            )
            print(msg)
            notifier.send(msg)
    elif args.action == "close":
        positions = load_positions()
        code = args.code.upper()
        found = False
        snap = api.market_snapshot()
        for p in positions:
            if p.code == code and not p.closed:
                p.closed = True
                p.close_reason = "clôture manuelle"
                quote = snap.by_code(code)
                p.close_price = quote.last if quote else p.entry_price
                found = True
        if found:
            save_positions(positions)
            print(f"✓ {code} clôturé manuellement.")
        else:
            print(f"{code} : aucune position ouverte.")


def cmd_portf(args: argparse.Namespace) -> None:
    from .portfolio import (
        load_portfolio,
        open_dividend_position,
        save_portfolio,
    )

    api = BSApi()
    if args.action == "open":
        positions = load_portfolio()
        if any(p.code == args.code.upper() and not p.closed for p in positions):
            print(f"Position déjà ouverte sur {args.code}.")
            return
        if args.dps is None or args.per is None:
            print("--dps et --per sont requis (dividende/action et PER à l'ouverture).")
            return
        try:
            pos = open_dividend_position(api, args.code, args.amount, args.dps, args.per)
        except ValueError as e:
            print(f"⛔ {e}")
            return
        positions.append(pos)
        save_portfolio(positions)
        print(f"✓ Position ouverte : {pos.name} ({pos.code})")
        print(f"  {pos.quantity} actions à {pos.entry_price:,.0f} = {pos.invested:,.0f} FCFA")
        print(f"  Dividende : {pos.dps:,.0f} FCFA/action (brut {pos.yield_pct(pos.entry_price):.2f}%, net {pos.net_yield_pct(pos.entry_price):.2f}%)")
        print(f"  Prix d'entrée (net 4 %) : {pos.entry_price_ref:,.0f} | Prix de sortie (net 2 %) : {pos.exit_price:,.0f}")
    elif args.action == "status":
        from .portfolio import status_level

        positions = load_portfolio()
        snap = api.market_snapshot()
        if not positions:
            print("Aucune position. Ouvrez-en une : portf open CODE --dps X --per Y")
            return
        print(f"{'Code':7s} {'Nom':20s} {'Entrée':>8s} {'Cours':>8s} {'Perf':>7s} {'Net%':>6s} {'Sortie':>9s} {'Durée':>6s}  Niveau")
        print("-" * 100)
        for p in positions:
            quote = snap.by_code(p.code)
            cur = quote.last if quote else p.entry_price
            perf = (cur / p.entry_price - 1) * 100
            yld = p.net_yield_pct(cur)
            _, label = status_level(p, cur)
            print(
                f"{p.code:7s} {p.name[:19]:20s} {p.entry_price:>8,.0f} {cur:>8,.0f} "
                f"{perf:>+6.1f}% {yld:>5.2f}% {p.exit_price:>9,.0f} {p.years_held:>5.1f}a  {label}"
            )
    elif args.action == "check":
        from datetime import datetime

        from .fundamentals import get_fundamentals
        from .portfolio import (
            check_dividend_position,
            is_cooldown_active,
            load_alert_state,
            save_alert_state,
        )

        positions = load_portfolio()
        snap = api.market_snapshot()
        alert_state = load_alert_state()
        events: list[tuple[str, object]] = []
        for p in positions:
            if p.closed:
                continue
            quote = snap.by_code(p.code)
            if quote is None or quote.last <= 0:
                continue
            fund = get_fundamentals(p.code)
            alerts = check_dividend_position(p, quote.last, fund.get("dps"), fund.get("per"))
            # Niveau 1 (info) jamais envoyé. Sorties (EXIT) toujours envoyées.
            # Niveaux 2-3 (décision/fondamental) soumis au cooldown 7 jours.
            actionable = [a for a in alerts if a.level > 1]
            if p.closed:
                events.extend((p.code, a) for a in actionable)
            elif actionable and not is_cooldown_active(alert_state, p.code):
                events.extend((p.code, a) for a in actionable)
                alert_state[p.code] = datetime.now().isoformat()
        save_portfolio(positions)
        save_alert_state(alert_state)
        if not events:
            print("Aucune alerte actionnable (niveaux 2-3) ni sortie fondamentale.")
            return
        notifier = get_notifier(load_config())
        actions = getattr(args, "_actions", None)
        for code, a in events:
            print(a.message)
            notifier.send(f"🏦 Noyau :\n{a.message}")
            if actions is not None:
                if "VENDS TOUT" in a.message:
                    actions.append("VENDS TOUT " + code)
                elif "VENDS" in a.message:
                    actions.append("Vends 1 sur 3 de " + code)
                else:
                    actions.append("Décision sur " + code)
    elif args.action == "dividend":
        from .portfolio import record_dividend

        positions = load_portfolio()
        code = args.code.upper()
        snap = api.market_snapshot()
        found = False
        for p in positions:
            if p.code == code and not p.closed:
                quote = snap.by_code(code)
                price = quote.last if quote else p.entry_price
                cash, shares, residual = record_dividend(p, price)
                print(f"✓ Dividende versé : {cash:,.0f} FCFA ({p.dps:,.0f} × {p.quantity - shares} actions)")
                print(f"  Réinvesti : {shares} actions à {price:,.0f} (résidu {residual:,.0f} FCFA)")
                print(f"  Nouvelle quantité : {p.quantity} | Total reçu : {p.dividends_earned:,.0f} FCFA")
                found = True
        if found:
            save_portfolio(positions)
        else:
            print(f"{code} : aucune position ouverte.")
    elif args.action == "close":
        positions = load_portfolio()
        code = args.code.upper()
        found = False
        snap = api.market_snapshot()
        for p in positions:
            if p.code == code and not p.closed:
                p.closed = True
                p.close_reason = "clôture manuelle"
                quote = snap.by_code(code)
                p.close_price = quote.last if quote else p.entry_price
                found = True
        if found:
            save_portfolio(positions)
            print(f"✓ {code} clôturé manuellement.")
        else:
            print(f"{code} : aucune position ouverte.")


def cmd_report(args: argparse.Namespace) -> None:
    from .report import build_report, set_cash

    if args.action == "cash":
        if args.amount is None:
            print("Usage : report cash --amount 118261")
            return
        set_cash(args.amount)
        print(f"✓ Liquidités enregistrées : {args.amount:,.2f} F")
        return

    api = BSApi()
    message = build_report(api, record=True)
    print(message)
    notifier = get_notifier(load_config())
    if notifier.enabled:
        notifier.send(message)
        print("\n✅ Rapport envoyé sur Telegram")


def cmd_boc(args: argparse.Namespace) -> None:
    from .boc import detect_events, fetch_latest_boc
    from .portfolio import load_portfolio

    result = fetch_latest_boc()
    if result is None:
        print("BOC indisponible (site down ou jours fériés).")
        return
    text, date, source = result
    codes = [p.code for p in load_portfolio() if not p.closed]
    events = detect_events(text, date, codes)

    if not events:
        print(f"BOC {date.strftime('%d/%m/%Y')} ({source}) : aucun événement dividende sur le noyau.")
        return

    notifier = get_notifier(load_config())
    for e in events:
        if e["action"] == "RECTIFIÉ":
            msg = (f"📢 BOC {date.strftime('%d/%m')} — {e['code']} : dividende RECTIFIÉ "
                   f"{e['ancien']:,.0f} → {e['montant']:,.0f} F (payé le {e['date']})")
        else:
            msg = (f"📢 BOC {date.strftime('%d/%m')} — {e['code']} : dividende "
                   f"{e['montant']:,.0f} F payé le {e['date']}")
        if "cross_sika" in e:
            msg += f" ⚠️ sikafinance indique {e['cross_sika']:,.0f} F (à vérifier)"
        print(msg)
        if notifier.enabled:
            notifier.send(msg)


def cmd_reinforcements(args: argparse.Namespace) -> None:
    """Étape quotidienne : titres du noyau redescendus sous leur seuil d'achat."""
    from .portfolio import check_reinforcements

    actions = getattr(args, "_actions", None)
    api = BSApi()
    hits = check_reinforcements(api)
    if not hits:
        print("Aucun titre à renforcer aujourd'hui.")  # texte silencieux (marker du heartbeat)
        return
    notifier = get_notifier(load_config())
    for code, msg in hits:
        print(msg)
        if notifier.enabled:
            notifier.send(f"🏦 Noyau :\n{msg}")
        if actions is not None:
            if "CONCENTRATION" in msg:
                actions.append(f"🚫 {code} : renforcement BLOQUÉ (plafond 35 % — diluer en priorité)")
            else:
                actions.append(f"RENFORCE {code} (prix sous ton seuil)")


def cmd_fund(args: argparse.Namespace) -> None:
    from .screener import screen_magic_formula, screen_value_dividend

    api = BSApi()
    if args.mode == "value":
        if getattr(args, "alert", False):
            from .screener import detect_new_value_opportunities

            new = detect_new_value_opportunities(api, force=args.force)
            if not new:
                print("Aucun nouveau titre value+dividende (rien n'a changé).")
                return
            notifier = get_notifier(load_config())
            actions = getattr(args, "_actions", None)
            for r in new:
                msg = (
                    f"🔎 NOUVELLE opportunité value : {r['code']} ({r['name']})\n"
                    f"   cours {r['last']:,.0f} F · PER {r['per']:.1f} · "
                    f"rend. net {r['net_yield']:.2f} %\n"
                    f"   → analyser (payout + fondamentaux) avant d'acheter"
                )
                print(msg)
                if notifier.enabled:
                    notifier.send(f"🏦 Nouvelle opportunité value :\n{msg}")
                if actions is not None:
                    actions.append(f"NOUVEAU CANDIDAT {r['code']} (à analyser : payout + fondamentaux)")
            return
        print("Screener value+dividende (PER ≤ 14, rendement NET ≥ 4 %)…\n")
        results = screen_value_dividend(api, force=args.force)
        if not results:
            print("Aucun titre ne remplit les critères.")
            return
        print(f"{'Code':7s} {'Nom':22s} {'Cours':>8s} {'PER':>6s} {'Div/act':>8s} {'Brut':>5s} {'Net':>5s}")
        print("-" * 66)
        for r in results:
            print(
                f"{r['code']:7s} {r['name'][:21]:22s} {r['last']:>8,.0f} "
                f"{r['per']:>6.2f} {r['dps']:>8,.0f} {r['yield']:>5.2f}% {r['net_yield']:>5.2f}%"
            )
    elif args.mode == "magic":
        print("Magic Formula BRVM (rang PER + rang rendement)…\n")
        results = screen_magic_formula(api, force=args.force)
        print(f"{'Code':7s} {'Nom':20s} {'Cours':>8s} {'PER':>6s} {'Brut':>5s} {'Net':>5s} {'Score':>5s}")
        print("-" * 62)
        for r in results[:15]:
            print(
                f"{r['code']:7s} {r['name'][:19]:20s} {r['last']:>8,.0f} "
                f"{r['per']:>6.2f} {r['yield']:>5.2f}% {r['net_yield']:>5.2f}% {r['score']:>5d}"
            )
    elif args.mode == "traps":
        from .screener import flag_value_traps

        print("Titres suspects de value trap (⚠️ à vérifier par le fondamental)…\n")
        results = flag_value_traps(api, force=args.force)
        if not results:
            print("Aucun titre suspect.")
            return
        print(f"{'Code':7s} {'Nom':22s} {'PER':>6s} {'Rend.':>6s}  Raisons")
        print("-" * 72)
        for r in results:
            print(
                f"{r['code']:7s} {r['name'][:21]:22s} {r['per']:>6.1f} "
                f"{r['yield']:>5.1f}%  {'; '.join(r['reasons'])}"
            )


def cmd_limits(args: argparse.Namespace) -> None:
    from .orders import build_limit_orders

    cfg = load_config()
    codes = cfg.get("noyau", {}).get("codes", [])
    if not codes:
        print("Aucun code dans config.yaml (section `noyau.codes`).")
        return
    api = BSApi()
    target_net = args.target / 100.0
    orders = build_limit_orders(api, codes, target_net=target_net)

    print(f"Ordres limites du noyau dividende (rendement NET cible {args.target:.0f} %)…\n")
    print(f"{'Code':7s} {'Nom':20s} {'Cours':>8s} {'Div/act':>8s} {'Entrée':>8s} {'Net':>6s} {'Payout':>7s}  Action")
    print("-" * 86)
    for o in orders:
        if "error" in o:
            print(f"{o['code']:7s}  ⚠ {o['error']}")
            continue
        payout_str = f"{o['payout']}%" if o.get("payout") is not None else "-"
        print(
            f"{o['code']:7s} {o['name'][:19]:20s} {o['last']:>8,.0f} {o['dps']:>8,.0f} "
            f"{o['entry_price']:>8,.0f} {o['net_yield']:>5.2f}% {payout_str:>7s}  {o['action']}"
        )


def cmd_div(args: argparse.Namespace) -> None:
    """Saisit et suit les encaissements réels de dividendes (avis BSTrade)."""
    from .dividends import add_dividend, load_dividends
    from .portfolio import load_portfolio

    if args.action == "add":
        if not args.code or args.amount is None:
            print("Usage : div add CODE --amount NET [--actions N] [--date AAAA-MM-JJ]")
            return
        entry = add_dividend(args.code, args.amount, args.actions, args.date)
        print(f"✓ Encaissement {entry['code']} : {entry['montant_net']:,.2f} F net ({entry['date']})")
        if entry["actions"] > 0:
            pos = next((p for p in load_portfolio() if p.code == entry["code"]), None)
            brut = pos.dps * entry["actions"] if pos else 0.0
            if brut > 0:
                tax = (1 - entry["montant_net"] / brut) * 100
                print(f"   brut attendu {brut:,.0f} F → imposition implicite {tax:.1f} % (attendu 12 %)")
        return

    items = load_dividends()
    if not items:
        print("Aucun dividende encaissé enregistré.")
        print("Usage : div add CODE --amount NET (montant net crédité par BSTrade)")
        return
    print(f"{'Code':7s} {'Date':12s} {'Net':>10s} {'Act.':>5s}")
    print("-" * 38)
    for d in items:
        print(f"{d['code']:7s} {d['date']:12s} {d['montant_net']:>10,.0f} {d.get('actions', 0):>5d}")
    print("-" * 38)
    print(f"Total encaissé : {sum(d['montant_net'] for d in items):,.2f} F net")


def cmd_bond(args: argparse.Namespace) -> None:
    """Obligations BRVM : carnet achetables, YTM précis, positions, coupons."""
    from .bonds import (
        NOMINAL,
        add_bond_position,
        buyable_lines,
        coupons_per_year,
        current_yield,
        issuer_risk,
        load_bond_positions,
        market_line,
        ytm,
    )

    if args.action == "list":
        lines = buyable_lines()
        if not lines:
            print("Aucune offre vendeur dans le référentiel (carnet du 20/08/2026).")
            return
        print("Obligations achetables immédiatement (offre vendeur), triées par rendement actuariel :\n")
        print(f"{'Code':10s} {'Obligation':33s} {'Prix':>5s} {'Qté':>5s} {'Coupon':>7s} {'Éch.':>5s} {'YTM':>7s}  Risque")
        print("-" * 92)
        for r in lines:
            y = f"{r['ytm']:.2f}%" if r["ytm"] is not None else "n/a"
            print(
                f"{r['code']:10s} {r['label'][:32]:33s} {r['bid']:>5.0f} {r['qty_bid']:>5d} "
                f"{r['coupon']:>6.2f}% {r['maturity']:>5d} {y:>7s}  {r['risk']}"
            )
        print(f"\nNominal : {NOMINAL:,.0f} F/titre — prix en % du nominal (100 = {NOMINAL:,.0f} F).")
        print("Frais Bridge et fiscalité des coupons : à confirmer avant tout ordre.")
    elif args.action == "ytm":
        if not args.code:
            print("Usage : bond ytm CODE [--price P]")
            return
        line = market_line(args.code)
        if line is None:
            print(f"{args.code} : ligne inconnue du référentiel.")
            return
        price = args.price if args.price is not None else (line.get("bid") or line.get("prev_close") or 100)
        y = ytm(price, line["coupon"], line["maturity"])
        cy = current_yield(price, line["coupon"])
        print(f"{line['label']} ({line['code']})")
        print(f"   Prix {price:.2f} % · coupon {line['coupon']:.2f} % · échéance {line['maturity']} · risque {issuer_risk(args.code)}")
        if cy is not None:
            print(f"   Rendement courant : {cy:.2f} %/an")
        if y is not None:
            print(f"   Rendement actuariel : {y:.2f} %/an (coupons + remboursement)")
        else:
            print("   Rendement actuariel : n/a (échéance dépassée)")
        if price > 100:
            print(f"   ⚠️ Acheté au-dessus du pair : perte de {price - 100:.2f} points au remboursement.")
    elif args.action == "buy":
        if not args.code or not args.qty or args.price is None:
            print("Usage : bond buy CODE --qty N --price P   (ex. bond buy TPCI.O87 --qty 10 --price 98)")
            return
        try:
            entry = add_bond_position(args.code, args.qty, args.price)
        except ValueError as e:
            print(f"⛔ {e}")
            return
        cost = entry["qty"] * NOMINAL * entry["price"] / 100.0
        y = ytm(entry["price"], entry["coupon"], entry["maturity"])
        print(f"✓ Achat enregistré : {entry['label']} ({entry['code']})")
        print(f"   {entry['qty']} titres @ {entry['price']:.2f} % = {cost:,.0f} FCFA (hors frais)")
        print(f"   Coupons annuels attendus : {entry['qty'] * NOMINAL * entry['coupon'] / 100.0:,.0f} F bruts")
        print(f"   YTM à l'achat : {y:.2f} %/an" if y is not None else "   YTM : n/a")
        print("   N'oublie pas : confirmer nominal + frais avec Bridge Securities.")
    elif args.action == "show":
        positions = load_bond_positions()
        if not positions:
            print("Aucune position obligataire enregistrée.")
            print("Usage : bond buy CODE --qty N --price P")
            return
        print(f"{'Code':10s} {'Obligation':33s} {'Qté':>4s} {'Prix':>6s} {'Valeur':>10s} {'Coupons/an':>10s}")
        print("-" * 80)
        for p in positions:
            line = market_line(p["code"])
            price = line["prev_close"] if line and line.get("prev_close") else p["price"]
            val = p["qty"] * NOMINAL * price / 100.0
            cpn = p["qty"] * NOMINAL * p["coupon"] / 100.0
            print(
                f"{p['code']:10s} {p['label'][:32]:33s} {p['qty']:>4d} {p['price']:>6.2f} "
                f"{val:>10,.0f} {cpn:>10,.0f}"
            )
        print("-" * 80)
        print(f"Total valeur (cours veille) : {sum(p['qty'] * NOMINAL * (market_line(p['code'])['prev_close'] if market_line(p['code']) and market_line(p['code']).get('prev_close') else p['price']) / 100.0 for p in positions):,.0f} F")
        print(f"Coupons annuels attendus : {coupons_per_year(positions):,.0f} F bruts")


def cmd_sustain(args: argparse.Namespace) -> None:
    """Vérifie la soutenabilité (payout) des titres du noyau + alerte Telegram."""
    from datetime import datetime

    from .portfolio import (
        check_sustainability,
        is_cooldown_active,
        load_alert_state,
        save_alert_state,
    )

    cfg = load_config()
    codes = cfg.get("noyau", {}).get("codes", [])
    if not codes:
        print("Aucun code dans config.yaml (section `noyau.codes`).")
        return
    api = BSApi()
    alerts = check_sustainability(api, codes)
    alert_state = load_alert_state()
    events = []
    for a in alerts:
        if a.code and not is_cooldown_active(alert_state, a.code):
            events.append(a)
            alert_state[a.code] = datetime.now().isoformat()
    save_alert_state(alert_state)
    if not events:
        print("Soutenabilité noyau : tous les dividendes sont couverts (payout sain).")
        return
    notifier = get_notifier(cfg)
    for a in events:
        print(a.message)
        notifier.send(f"🏦 Noyau :\n{a.message}")


def _news_action(a: dict) -> str:
    """Traduit une annonce BRVM en instruction claire (compréhensible par un néophyte)."""
    code = a["code"]
    if a["type"] == "dividendes":
        return f"🟡 CONSERVE {code} — dividende annoncé. Vérifie le montant (coupé ou augmenté ?)"
    if a["type"] == "ag":
        return f"🟡 CONSERVE {code} — assemblée générale annoncée. À surveiller."
    if a["type"] == "dirigeants":
        return f"📢 À SURVEILLER {code} — changement de direction."
    if a["type"] == "notations":
        return f"📢 À SURVEILLER {code} — notation financière publiée."
    return f"📢 INFO {code} — communiqué publié ({a['date']})."


def cmd_radar(args: argparse.Namespace) -> None:
    """Radar de veille « sortie de fond » — détection précoce, ZÉRO trading.

    --alert : n'affiche que les niveau 1 et alerte Telegram sur les NOUVEAUX
    (un titre alerté une fois n'est plus jamais re-alerté — anti-spam).
    """
    from .backtest import load_all_history
    from .bsapi import BSApi
    from .radar import filter_new_level1, format_radar, scan

    api = BSApi()
    hist = load_all_history(api, force=False)
    hits = scan(hist)
    try:
        snap = api.market_snapshot()
        names = {q.code.strip().upper(): q.name for q in snap.stocks}
        for h in hits:
            h["name"] = names.get(h["code"], "")
    except Exception:
        pass  # le radar reste utile sans les noms

    if getattr(args, "mark", None):
        from datetime import datetime

        from .radar import load_alerted, save_alerted

        state = load_alerted()
        today = datetime.now().strftime("%Y-%m-%d")
        for c in args.mark:
            state.setdefault(c.upper(), today)
        save_alerted(state)
        print(f"✓ {len(args.mark)} code(s) marqué(s) comme veille faite : "
              f"{', '.join(c.upper() for c in args.mark)}")
        return

    if getattr(args, "alert", False):
        level1 = [h for h in hits if h["level"] == 1]
        if not level1:
            return  # silencieux : aucun événement
        new = filter_new_level1(level1)
        if new:
            notifier = get_notifier(load_config())
            for h in new:
                msg = (
                    f"📡 RADAR — NOUVELLE SORTIE DE FOND (veille, PAS un ordre)\n\n"
                    f"{h['name'] or h['code']} ({h['code']}) — {h['last']:,.0f} F\n"
                    f"   {h['r60']:+.0f} % sur 60 séances · {h['r120']:+.0f} % sur 120\n"
                    f"   {h['pct_ath']:+.0f} % vs plus haut historique\n\n"
                    f"   ❓ La question : qu'est-ce qui a changé dans les fondamentaux ?\n"
                    f"   (résultats, contrat, restructuration) — jamais un signal d'achat."
                )
                print(msg)
                if notifier.enabled:
                    notifier.send(msg)
        new_codes = {h["code"] for h in new}
        for h in level1:  # contexte dans le log quotidien, sans re-spam
            print(f"   [radar] {h['code']} niveau 1 — déjà alerté" if h["code"] not in new_codes
                  else f"   [radar] {h['code']} niveau 1 — NOUVEAU")
        return

    format_radar(hits)


def cmd_noyau_check(args: argparse.Namespace) -> None:
    """Évalue des candidats contre les filtres noyau → alerte d'achat qualifiée.

    Cours : live brvm.org en priorité, sinon snapshot BSTrade (clôture veille).
    """
    from .bsapi import BSApi
    from .live import live_quotes
    from .noyau_check import evaluate_noyau_candidate

    api = BSApi()
    snap = api.market_snapshot()
    found = False
    for raw in args.code:
        code = raw.strip().upper()
        price = None
        try:
            lq = live_quotes([code])
            price = lq.get(code)
        except Exception:
            price = None
        quote = snap.by_code(code)
        if price is None and quote is not None:
            price = quote.last
        if not price or price <= 0:
            print(f"{code} : cours indisponible — ignoré.")
            continue
        name = quote.name if quote else code
        res = evaluate_noyau_candidate(code, price, name)
        if res:
            print(res["message"])
            print()
            found = True
    if not found:
        print("Aucun candidat ne passe les filtres noyau — silence (le radar reste de la veille).")


def cmd_news(args: argparse.Namespace) -> None:
    from .news import detect_new, fetch_announcements, filter_codes

    cfg = load_config()
    codes = cfg.get("noyau", {}).get("codes", [])
    if not codes:
        print("Aucun code dans config.yaml (section `noyau.codes`).")
        return

    anns = fetch_announcements()

    if args.check:
        new = detect_new(anns, codes)
        if not new:
            print("Aucune nouvelle annonce sur le noyau.")
            return
        notifier = get_notifier(cfg)
        for a in new:
            msg = _news_action(a)
            print(msg)
            notifier.send(f"🏦 Noyau : {msg}\n{a['url']}")
        return

    focus = filter_codes(anns, codes)
    if not focus:
        print("Aucune annonce récente sur les titres du noyau.")
        return
    print(f"Annonces officielles BRVM — titres du noyau ({len(focus)})…\n")
    for a in focus[:20]:
        print(f"{a['date']}  {a['code']:6s} {a['type']:12s} {a['society']}")
        print(f"    {a['url']}")


def cmd_live(args: argparse.Namespace) -> None:
    """Affiche les cours temps réel BRVM (brvm.org) + l'état de la séance."""
    from .bsapi import BSApi
    from .live import live_quotes, session_open

    api = BSApi()
    snap = api.market_snapshot()
    codes = [q.code.strip() for q in snap.stocks if not q.is_obligation and q.last > 0]
    etat = "OUVERTE" if session_open() else "fermée"
    print(f"État séance : {etat} (09h00-15h00, Abidjan) — cours temps réel brvm.org\n")
    try:
        quotes = live_quotes(codes)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ Échec du scraping brvm.org : {e}")
        return
    if not quotes:
        print("Aucun cours récupéré.")
        return
    print(f"{'Code':7s} {'Nom':22s} {'Temps réel':>10s} {'Veille':>8s} {'Var':>7s}")
    print("-" * 58)
    for code in sorted(quotes):
        q = snap.by_code(code)
        name = q.name if q else code
        prev = q.last if q and q.last > 0 else 0.0
        var = f"{(quotes[code] / prev - 1) * 100:+.1f}%" if prev else "—"
        prev_s = f"{prev:,.0f}" if prev else "—"
        print(f"{code:7s} {name[:21]:22s} {quotes[code]:>10,.0f} {prev_s:>8s} {var:>7s}")


def cmd_integrity(args: argparse.Namespace) -> None:
    """Contrôle d'intégrité des données : cache, cassures, profils dérivés."""
    from .backtest import load_all_history
    from .cache_integrity import check_all_integrity

    api = BSApi()
    hist = load_all_history(api)
    problems = check_all_integrity(hist, api.market_snapshot())
    if not problems:
        print("Intégrité des données : OK (cache cohérent, profils à jour).")
        return
    print(f"{len(problems)} problème(s) d'intégrité détecté(s) :")
    for p in problems[:12]:
        print(f"  ⚠ {p}")


def cmd_daily(args: argparse.Namespace) -> None:
    """Check quotidien complet : annonces + déclencheurs de sortie + stops + heartbeat."""
    from datetime import datetime
    from io import StringIO

    print("=" * 62)
    print(f"Check quotidien Bridge Bank — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 62)

    actions: list[str] = []  # plan d'action du jour (résumé « AUJOURD'HUI »)
    steps = [
        ("BOC", cmd_boc, {}, "aucun événement dividende"),
        ("Annonces BRVM", cmd_news, {"check": True}, "Aucune nouvelle annonce"),
        ("Soutenabilité", cmd_sustain, {}, "tous les dividendes sont couverts"),
        ("Opportunités value", cmd_fund, {"mode": "value", "alert": True, "force": False, "_actions": actions}, "Aucun nouveau titre value"),
        ("Renforcements noyau", cmd_reinforcements, {"_actions": actions}, "Aucun titre à renforcer"),
        ("Déclencheurs de sortie", cmd_portf, {"action": "check", "code": None, "amount": 100000, "dps": None, "per": None, "_actions": actions}, "Aucune alerte actionnable"),
        # Spéculation SUSPENDUE (décision LEO 26/08/2026, épreuve H2/H4) :
        # volume ≥2× = placebo prédictif (p=0,44) et frais réels min 1 000 F
        # annulent l'espérance sous 150 000 F/position. Modules conservés,
        # disponibles en CLI manuelle (`spec screen` / `spec check`).
        # Réactivée « en conscience » le 03/09 : alertes via le cron 16h dédié.
        ("Intégrité des données", cmd_integrity, {}, "cache cohérent"),
        # Le radar est géré par le cron dédié « BridgeBank veille radar »
        # (monitor + agent) — un seul flux, pas de double alerte ici.
    ]
    summaries: list[tuple[str, bool]] = []
    for label, func, kwargs, quiet_marker in steps:
        print(f"\n— {label} —")
        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            func(argparse.Namespace(**kwargs))
        except Exception as e:
            print(f"⚠ échec : {e}")
        finally:
            sys.stdout = old_stdout
        text = buf.getvalue()
        print(text, end="")
        summaries.append((label, quiet_marker in text))

    print("\n✓ Check quotidien terminé.")
    heartbeat = _build_heartbeat(summaries, actions)
    print(heartbeat)
    notifier = get_notifier(load_config())
    if notifier.enabled:
        notifier.send(heartbeat)


def _build_heartbeat(summaries: list[tuple[str, bool]],
                     actions: list[str] | None = None) -> str:
    """Message quotidien de clôture : résumé par étape + plan d'action « AUJOURD'HUI »."""
    from datetime import datetime

    parts = []
    for label, quiet in summaries:
        parts.append(f"{label} : {'✅ rien à signaler' if quiet else '🔔 événement (alerte ci-dessus)'}")
    msg = (
        f"✅ Check quotidien Bridge Bank — {datetime.now().strftime('%d/%m %H:%M')}\n"
        + "\n".join(f"   {p}" for p in parts)
    )
    if actions:
        plan = "\n".join(f"   • {a}" for a in actions)
        msg += f"\n\n🎯 AUJOURD'HUI POUR TON NOYAU :\n{plan}"
        msg += "\n\n   Détails et montants : dans les alertes ci-dessus."
    else:
        msg += "\n\n🎯 AUJOURD'HUI POUR TON NOYAU : ne touche à rien —"
        msg += "\n   le système n'a rien vu qui vaille un ordre."
    return msg


if __name__ == "__main__":
    main()
