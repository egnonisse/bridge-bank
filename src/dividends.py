"""Suivi des encaissements RÉELS de dividendes (avis BSTrade).

Contrairement au calcul théorique (dps × quantité × (1 − IRVM)), ce module
enregistre les montants NET réellement crédités sur le compte, lus sur l'« avis
d'encaissement de dividendes » de BSTrade. Il permet de :
  - confirmer le taux d'IRVM réel (12 % attendu, à re-vérifier) ;
  - tracer le cash réellement disponible pour le DRIP.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from .infrastructure.paths import DATA_DIR  # chemins centralisés (lot 0 du plan docs/architecture.md)

DIVIDENDES_FILE = DATA_DIR / "dividendes.json"


def load_dividends() -> list[dict]:
    if not DIVIDENDES_FILE.exists():
        return []
    try:
        data = json.loads(DIVIDENDES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_dividends(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DIVIDENDES_FILE.write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def add_dividend(code: str, montant_net: float, actions: int = 0,
                 date: str | None = None) -> dict:
    """Enregistre un encaissement réel (montant NET crédité par BSTrade)."""
    items = load_dividends()
    entry = {
        "code": code.upper(),
        "montant_net": round(float(montant_net), 2),
        "actions": int(actions),
        "date": date or datetime.now().strftime("%Y-%m-%d"),
    }
    items.append(entry)
    save_dividends(items)
    return entry


def total_encaissé() -> float:
    """Total net réellement encaissé (FCFA)."""
    return round(sum(d.get("montant_net", 0.0) for d in load_dividends()), 2)
