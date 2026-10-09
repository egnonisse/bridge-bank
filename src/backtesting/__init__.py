"""Simulation historique, frais et performances.

Modules (déplacés au lot 3 du plan `docs/architecture.md`) : `backtest_noyau.py` ·
`challenge_validateur.py` · `challenge_schema.py` · `challenge_indicateurs.py`.

NOMMÉ `backtesting` ET NON `backtest` : `src/backtest.py` existe encore, et un paquet du même
nom le MASQUE (l'import résout le dossier d'abord). Mesuré au lot 1 : 7 erreurs de collecte
en test et le contrôle des constantes en échec. `backtest.py` est le CHARGEUR — il rejoindra
`collecte/` au lot 4 ; le dossier garde le nom de la simulation.

Ce paquet n'importe RIEN : `challenge_validateur` importe `challenge_schema` explicitement.
"""
