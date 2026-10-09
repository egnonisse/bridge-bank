"""Seuils calibrés et régimes de marché.

Modules (déplacés au lot 3 du plan `docs/architecture.md`) : `seuils_vente.py` ·
`regime_marche.py` · `schema_seuils.py`.

`schema_seuils.py` est le 42e module de `src/` : il est **né après la carte du plan** (durcissement
des seuils du 09/10) et rattaché ici parce qu'il porte le vocabulaire et la protection des seuils
calibrés — la même responsabilité que `seuils_vente`, dont il est la source. Le plan est mis à jour
en conséquence (§4).

Ce paquet n'importe RIEN : `seuils_vente` réexporte `schema_seuils` pour ses appelants, mais
l'import est écrit dans `seuils_vente`, pas ici.
"""
