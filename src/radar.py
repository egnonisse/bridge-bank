"""Radar « sortie de fond » — veille des transitions de régime. ZÉRO trading.

Seuils calibrés le 01/09/2026 sur les 65 triplements BRVM 2017-2026
(scripts/test_momentum_hypotheses.py) :
  - les futurs triplements partent à -94 % de leur ATH (médiane) ;
  - au premier +30 % sur 120j, le titre fait déjà +31 % sur 60j (médiane) ;
  - le triplement survient ~76 séances plus tard (médiane) -> ~3 mois d'avance.

Niveaux :
  NIVEAU 1 « SORTIE DE FOND » : r60 >= +15 % ET r120 >= +30 % ET cours <= 20 % ATH
  NIVEAU 2 « ACCUMULATION »    : r60 >= +10 % ET r120 >= +20 % ET cours <= 50 % ATH

Rôle : watchlist de VEILLE FONDAMENTALE (« pourquoi ça bouge ? »), jamais un
signal d'achat — l'épreuve du momentum extrême a démontré que suivre ces
mouvements net de frais ne bat pas le hasard.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ALERT_STATE_FILE = DATA_DIR / "radar_alert_state.json"


def load_alerted() -> dict:
    """Codes déjà alertés en niveau 1 (anti-spam permanent : on n'alerte que les nouveautés)."""
    if ALERT_STATE_FILE.exists():
        try:
            return json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_alerted(state: dict) -> None:
    ALERT_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


SEEN_STATE_FILE = DATA_DIR / "radar_seen_state.json"  # exclu par .gitignore (*_state.json)
REENTER_GAP_DAYS = 5  # absence minimale hors du radar avant re-signal (absorbe les vacillements)


def load_seen_state() -> dict:
    """Dernière date de présence en niveau 1, par code."""
    if SEEN_STATE_FILE.exists():
        try:
            return json.loads(SEEN_STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_seen_state(state: dict) -> None:
    SEEN_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def monitor_output(level1: list[str], alerted: dict, seen: dict,
                   today: str) -> tuple[list[str], dict]:
    """Codes à veiller + état de présence mis à jour.

    Veille PERMANENTE par cycle : un titre est signalé quand il est NOUVEAU
    (jamais traité) OU quand il RÉ-ENTRE en niveau 1 après >= 5 jours d'absence
    (les vacillements niveau 1<->2 de quelques jours n'alertent pas). Un titre
    présent en continu n'est jamais re-spammé.
    """
    from datetime import date

    s1 = set(level1)
    first_tick = not seen
    old = dict(seen)
    day = date.fromisoformat(today)

    reentrants = set()
    for c in s1:
        if c not in alerted:
            continue
        if c in old:
            gap = (day - date.fromisoformat(old[c])).days
            if gap >= REENTER_GAP_DAYS:
                reentrants.add(c)
        elif not first_tick:
            # marqué mais jamais enregistré par ce monitor : vrai retour
            reentrants.add(c)

    for c in s1:
        seen[c] = today
    # purge des codes disparus depuis > 180 jours (dette de données bénigne)
    for c in list(seen):
        if c not in s1 and (day - date.fromisoformat(seen[c])).days > 180:
            del seen[c]

    return sorted(set(s1) - set(alerted) | reentrants), seen


def filter_new_level1(hits: list[dict]) -> list[dict]:
    """Hits de niveau 1 JAMAIS alertés ; les marque comme alertés."""
    state = load_alerted()
    new = [h for h in hits if h["level"] == 1 and h["code"] not in state]
    for h in new:
        state[h["code"]] = h["date"]
    save_alerted(state)
    return new


def _safe_ret(closes: list[float], offset: int) -> float | None:
    """Rendement sur `offset` séances jusqu'à la dernière clôture (>0)."""
    if len(closes) <= offset:
        return None
    past, now = closes[-1 - offset], closes[-1]
    if past <= 0 or now <= 0:
        return None
    return now / past - 1.0


def ath_status(closes: list[float]) -> tuple[float, float]:
    """(ATH, cours actuel en % de l'ATH)."""
    valid = [c for c in closes if c > 0]
    ath = max(valid) if valid else 0.0
    now = valid[-1] if valid else 0.0
    pct = (now / ath - 1.0) * 100 if ath > 0 else 0.0
    return ath, pct


def scan(hist_all: dict, min_bars: int = 260) -> list[dict]:
    """Titres en mouvement naissant depuis le fond. Triés par score décroissant."""
    hits = []
    for code, bars in hist_all.items():
        if len(bars) < min_bars:
            continue
        closes = [float(b.close) for b in bars]
        r60 = _safe_ret(closes, 60)
        r120 = _safe_ret(closes, 120)
        ath, pct_ath = ath_status(closes)
        if r60 is None or r120 is None or ath <= 0:
            continue
        level = None
        if r60 >= 0.15 and r120 >= 0.30 and pct_ath <= -80:
            level = 1
        elif r60 >= 0.10 and r120 >= 0.20 and pct_ath <= -50:
            level = 2
        if level is None:
            continue
        vols = [float(b.volume) for b in bars[-20:]]
        vol20 = statistics.mean(vols) if vols else 0.0
        # score : force du mouvement × profondeur du fond (veille, pas trading)
        score = r60 * 100 * (-pct_ath / 100)
        hits.append({
            "code": code,
            "name": "",  # enrichi par la commande via market_snapshot()
            "last": closes[-1],
            "date": str(bars[-1].date)[:10],
            "r60": r60 * 100,
            "r120": r120 * 100,
            "ath": ath,
            "pct_ath": pct_ath,
            "vol20": vol20,
            "level": level,
            "score": score,
        })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits


def format_radar(hits: list[dict]) -> None:
    """Affichage lisible + rappel du rôle de veille."""
    if not hits:
        print("Radar : aucun titre en sortie de fond aujourd'hui.")
        return
    print(f"{'Code':<7}{'Nom':<22}{'Cours':>10}{'r60':>8}{'r120':>8}"
          f"{'% ATH':>8}{'Vol20':>9}  Niveau")
    print("-" * 82)
    for h in hits:
        label = "1 SORTIE DE FOND" if h["level"] == 1 else "2 ACCUMULATION"
        print(f"{h['code']:<7}{h['name']:<22}{h['last']:>10,.0f}{h['r60']:>+7.1f}%"
              f"{h['r120']:>+7.1f}%{h['pct_ath']:>+7.0f}%{h['vol20']:>9,.0f}  {label}")
    print(f"\nDonnées au {hits[0]['date']} (dernière barre du cache).")
    print("⚠️  Radar = VEILLE : « qu'est-ce qui a changé dans les fondamentaux ? » — jamais un ordre.")
