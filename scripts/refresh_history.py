"""Re-télécharge l'historique complet de toutes les actions BRVM (cache force).

Utile quand des titres manquent au cache (nouvelle cotation, échec API ponctuel).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bsapi import BSApi
from src.backtest import load_all_history

if __name__ == "__main__":
    api = BSApi()
    hist = load_all_history(api, force=True)
    print(f"Cache régénéré : {len(hist)} titres")
