"""Monitor du cron de veille radar — sortie DÉTERMINISTE (codes à veiller).

Exécuté à chaque tick par le monitor du cron Hermes « BridgeBank veille radar ».
Sortie :
  L1: <codes niveau 1>   — SORTIE DE FOND (veille complète + analyse du pourquoi)
  L2: <codes niveau 2>   — ACCUMULATION (veille douce : mention brève, pas d'analyse poussée)
Vide si rien de nouveau. Ne change QUE lorsqu'un titre entre dans un niveau pour la
première fois OU y RÉ-ENTRE après >= 5 jours d'absence (veille permanente par cycle).
"""
import json
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

SEEN2_FILE = ROOT / "data" / "radar_seen2_state.json"  # *_state.json exclu par .gitignore

hist = load_all_history(BSApi(), force=False)
hits = scan(hist)
level1 = [h["code"] for h in hits if h["level"] == 1]
level2 = [h["code"] for h in hits if h["level"] == 2 and h["code"] not in level1]
alerted = load_alerted()

# Niveau 1 : SORTIE DE FOND (veille complète)
seen = load_seen_state()
codes1, seen_new = monitor_output(level1, alerted, seen, date.today().isoformat())
save_seen_state(seen_new)

# Niveau 2 : ACCUMULATION (veille douce, même règle de cycle, état séparé)
try:
    seen2 = json.loads(SEEN2_FILE.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    seen2 = {}
codes2, seen2_new = monitor_output(level2, alerted, seen2, date.today().isoformat())
SEEN2_FILE.write_text(json.dumps(seen2_new, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"L1: {' '.join(codes1)}")
print(f"L2: {' '.join(codes2)}")
