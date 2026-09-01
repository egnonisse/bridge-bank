"""Monitor du cron de veille radar — sortie DÉTERMINISTE (codes niveau 1 non traités).

Exécuté à chaque tick par le monitor du cron Hermes « BridgeBank veille radar ».
Sortie : codes séparés par des espaces, triés — vide si rien de nouveau.
La sortie ne change QUE lorsqu'un titre entre en niveau 1 pour la première fois
→ l'agent du cron ne se réveille que pour une vraie nouveauté.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest import load_all_history
from src.bsapi import BSApi
from src.radar import load_alerted, scan

hist = load_all_history(BSApi(), force=False)
hits = scan(hist)
alerted = load_alerted()
new = sorted(h["code"] for h in hits if h["level"] == 1 and h["code"] not in alerted)
print(" ".join(new))
