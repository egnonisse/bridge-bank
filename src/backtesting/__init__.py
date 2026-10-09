"""Simulation historique, frais et performances.

Domaine créé au lot 1 du plan `docs/architecture.md`.
Modules prévus : backtest_noyau.py · challenge_validateur.py · challenge_schema.py ·
challenge_indicateurs.py.

NOMMÉ `backtesting` ET NON `backtest` : `src/backtest.py` existe encore, et un paquet du même
nom le MASQUE (l'import résout le dossier d'abord). Mesuré au lot 1 : 7 erreurs de collecte
en test et le contrôle des constantes en échec. `backtest.py` est le CHARGEUR — il rejoindra
`collecte/` ; le dossier garde le nom de la simulation.
"""
