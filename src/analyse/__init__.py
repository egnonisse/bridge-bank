"""Indicateurs, valorisation et veille.

Modules (déplacés au lot 3 du plan `docs/architecture.md`) : `fondamentaux_historiques.py` ·
`screener.py` · `screening.py` · `bonds.py` · `boc.py` · `news.py` · `radar.py`.

Ce paquet n'importe RIEN : les modules s'importent explicitement entre eux, ce qui garde les
dépendances lisibles d'un seul coup d'œil. Un `__init__.py` qui importe crée des dépendances
implicites que personne ne voit dans le fichier qui appelle.
"""
