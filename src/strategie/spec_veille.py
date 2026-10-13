"""Veille spé quotidienne — scan des titres et génération des fiches.

Anti-spam : un titre déjà signalé avec le même schéma est muet pendant
SPAM_DAYS jours (état dans data/spec_seen_state.json). Une fiche qui dit
NON est aussi mémorisée (elle ne re-viendra pas chaque matin).

Usage : python -m src.spec_veille [--all]   (—all : sans filtre anti-spam)
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from ..infrastructure.paths import DATA_DIR as DATA  # chemins centralisés (lot 0 du plan docs/architecture.md)
from ..infrastructure.ecriture import ecrire_json_atomique  # P7-01 : ecriture atomique

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ..collecte.backtest import load_all_history
from ..collecte.bsapi import BSApi
from .spec_fiche import build_fiche

SPAM_DAYS = 7
STOPOUT_COOLDOWN_DAYS = 30  # un titre stoppé ne re-entre pas en fiche avant 30 j
STOPOUT_SUSPEND_DAYS = 60   # 2 stop-outs consécutifs = suspension 60 j
STOPOUT_SUSPEND_COUNT = 2
STATE_FILE = DATA / "spec_seen_state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    ecrire_json_atomique(STATE_FILE, state)  # P7-01 : écriture atomique


def stopout_cooldowns(spec_pos) -> tuple[dict, dict]:
    """Cooldowns par titre après stop-out (B0-01 + B1-09).

    - `stopout_last[code]` : date du DERNIER stop-out (SUSPEND_DAYS de repli si illisible).
    - `stopout_days[code]` : STOPOUT_SUSPEND_DAYS si ≥ 2 stop-outs RAPPROCHÉS (dans la
      fenêtre de suspension précédant le dernier = « échecs répétés dans une tendance
      baissière »), sinon STOPOUT_COOLDOWN_DAYS.
      B1-09 (lot 2) : avant, TOUS les stop-outs historiques étaient comptés cumulativement —
      deux stop-outs espacés de deux ans déclenchaient la suspension de 60 j à tort.
    """
    stop_dates: dict[str, list[date]] = {}
    for p in spec_pos:
        if not (p.closed and "stop" in (p.close_reason or "").lower()):
            continue
        code = p.code.upper()
        try:
            if getattr(p, "closed_at", ""):
                d = date.fromisoformat(p.closed_at[:10])
            else:
                d = date.fromisoformat((p.close_reason or "").split(" ")[-1][:10])
        except Exception:
            try:
                d = date.fromisoformat(p.opened_at[:10])
            except Exception:
                continue
        stop_dates.setdefault(code, []).append(d)

    stopout_last: dict[str, date] = {}
    stopout_days: dict[str, int] = {}
    for code, ds in stop_dates.items():
        ds.sort()
        dernier = ds[-1]
        stopout_last[code] = dernier
        rapproches = [d for d in ds if (dernier - d).days <= STOPOUT_SUSPEND_DAYS]
        stopout_days[code] = (STOPOUT_SUSPEND_DAYS if len(rapproches) >= STOPOUT_SUSPEND_COUNT
                              else STOPOUT_COOLDOWN_DAYS)
    return stopout_last, stopout_days


def scan(all_: bool = False) -> list:
    """Retourne [(fiche, message)] pour les titres à signaler aujourd'hui.

    Règle LEO 19/09 : chaque fiche est régénérée au COURS DU MOMENT
    (live brvm.org) avant l'envoi — jamais envoyée sur des données
    périmées du cache. Fallback : dernière clôture connue, mentionnée
    dans la fiche (« cours de référence »).
    """
    state = load_state()
    today = date.today().isoformat()
    out = []
    hist = load_all_history(BSApi(), force=False)
    codes = [c for c, bars in hist.items() if len(bars) >= 500]
    try:
        from ..collecte.live import live_quotes

        live = live_quotes(codes)
    except Exception:
        live = {}
    fiches = []
    # cooldown après stop-out : un titre stoppé ne re-entre pas en fiche
    # avant STOPOUT_COOLDOWN_DAYS jours (faux breakout → rachat = perte
    # répétée — règle du challenge croisé 25/09)
    try:
        from .speculation import load_positions

        stopout_last, stopout_days = stopout_cooldowns(load_positions())
    except Exception:
        stopout_last, stopout_days = {}, {}
    for code in codes:
        bars = hist[code]
        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]
        px = live.get(code)
        # Garde-fou : un live aberrant (> ±50 % vs clôture = erreur de
        # parsing du site ou split non traité) est IGNORÉ → clôture.
        if px and px > 0 and 0.5 < px / closes[-1] < 1.5:
            closes = closes + [px]
            volumes = volumes + [volumes[-1] if volumes else 0]
            source = "live"
        else:
            source = "cloture"
        if code in stopout_last and (date.today() - stopout_last[code]).days < stopout_days.get(code, STOPOUT_COOLDOWN_DAYS):
            continue  # stop-out récent (ou suspension) : pas de nouvelle fiche
        f = build_fiche(code, code, closes, volumes)
        if f is None:
            continue
        f.blocks["cours_source"] = source
        fiches.append(f)

    # contexte de marée : combien de titres cochent le même schéma aujourd'hui
    from collections import Counter

    maree = Counter(f.blocks["main"] for f in fiches)
    for f in fiches:
        f.blocks["nb_meme_schema"] = maree[f.blocks["main"]]
        key = f"{f.code}:{f.blocks['main']}"
        seen = state.get(key, "")
        if not all_ and seen:
            try:
                d = date.fromisoformat(seen)
                if (date.today() - d).days < SPAM_DAYS:
                    continue
            except ValueError:
                pass
        out.append((f, f.message(), key))
        # B1-13 (lot 2) : seules les fiches NON décidables (NON) sont marquées ici — c'est
        # le filtre anti-bruit local, pas un envoi. Les fiches décidables (OUI/PRUDENCE)
        # sont marquées par l'APPELANT après livraison réussie (`mark_delivered`) : un envoi
        # échoué (Telegram en panne) ne consomme plus les 7 jours — la fiche revient demain,
        # et une fiche écartée par le plafond 3/j n'est plus perdue non plus.
        if f.verdict not in ("OUI", "PRUDENCE"):
            state[key] = today
    save_state(state)
    return out


def mark_delivered(keys: list[str]) -> None:
    """Marque des fiches comme LIVRÉES (anti-spam 7 j) — appelé APRÈS livraison (B1-13)."""
    if not keys:
        return
    state = load_state()
    today = date.today().isoformat()
    for k in keys:
        state[k] = today
    save_state(state)


def main() -> None:
    all_ = "--all" in sys.argv
    res = scan(all_=all_)
    if not res:
        print("Aucun nouveau signal de veille spé aujourd'hui.")
        return
    for f, msg, _key in res:
        print(f"───── {f.code} ({f.verdict}) ─────")
        print(msg)
        print()
    # affichage local = livraison : on marque les fiches montrées (B1-13)
    mark_delivered([k for _f, _m, k in res])


if __name__ == "__main__":
    main()
