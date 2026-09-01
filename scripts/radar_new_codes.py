"""Monitor du cron de veille radar — sortie DÉTERMINISTE (codes niveau 1 à veiller).

Exécuté à chaque tick par le monitor du cron Hermes « BridgeBank veille radar ».
Sortie : codes séparés par des espaces, triés — vide si rien de nouveau.
Ne change QUE lorsqu'un titre entre en niveau 1 pour la première fois OU y
RÉ-ENTRE après >= 5 jours d'absence (veille permanente par cycle, anti-spam).
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest import load_all_history
from src.bsapi import BSApi
from src.radar import (
    load_alerted,
    load_seen_state,
    monitor_output,
    save_seen_state,
    scan,
)

hist = load_all_history(BSApi(), force=False)
hits = scan(hist)
level1 = [h["code"] for h in hits if h["level"] == 1]
alerted = load_alerted()
seen = load_seen_state()
codes, seen_new = monitor_output(level1, alerted, seen, date.today().isoformat())
save_seen_state(seen_new)
print(" ".join(codes))
