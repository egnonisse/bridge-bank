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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from .backtest import load_all_history
from .bsapi import BSApi
from .spec_fiche import build_fiche

SPAM_DAYS = 7
DATA = Path(__file__).resolve().parents[1] / "data"
STATE_FILE = DATA / "spec_seen_state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")


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
        from .live import live_quotes

        live = live_quotes(codes)
    except Exception:
        live = {}
    fiches = []
    for code in codes:
        bars = hist[code]
        closes = [b.close for b in bars]
        px = live.get(code)
        # Garde-fou : un live aberrant (> ±50 % vs clôture = erreur de
        # parsing du site ou split non traité) est IGNORÉ → clôture.
        if px and px > 0 and 0.5 < px / closes[-1] < 1.5:
            closes = closes + [px]
            source = "live"
        else:
            source = "cloture"
        f = build_fiche(code, code, closes)
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
        state[key] = today
        out.append((f, f.message()))
    save_state(state)
    return out


def main() -> None:
    all_ = "--all" in sys.argv
    res = scan(all_=all_)
    if not res:
        print("Aucun nouveau signal de veille spé aujourd'hui.")
        return
    for f, msg in res:
        print(f"───── {f.code} ({f.verdict}) ─────")
        print(msg)
        print()


if __name__ == "__main__":
    main()
