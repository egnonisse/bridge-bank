# Chantier « prix des alertes spé » — contrat partagé (02/11/2026)

Ce fichier est la **source commune** des 3 chantiers lancés en parallèle. Lis-le en entier
avant de produire quoi que ce soit.

## Le projet

- Dépôt local : `C:\Users\LEO\projects\Bridge Bank` (branche `main`, remote privé `egnonisse/bridge-bank`).
- Python du projet (le SEUL qui a les dépendances installées) :
  `C:/Users/LEO/AppData/Local/hermes/hermes-agent/venv/Scripts/python`
- Tests : `cd "C:/Users/LEO/projects/Bridge Bank" && "C:/Users/LEO/AppData/Local/hermes/hermes-agent/venv/Scripts/python" -m pytest -q`
- **Ne JAMAIS committer, pousser, ni créer de branche** : le parent (agent principal) commite.

## La question posée par l'utilisateur (verbatim)

« comment savoir qu'on n'achete pas les actions des alertes spe trop cher ? »

## Faits déjà établis — ne pas les re-vérifier, ils sont mesurés dans le code

1. **La fourchette d'achat de la fiche spé est auto-référencée** : dans
   `src/strategie/spec_fiche.py` (vers la ligne 106) :
   `entry_lo = price * 0.985` et `entry_hi = price * 1.05`.
   Elle suit le cours du moment : elle ne mesure PAS la cherté historique.
2. **La zone** = position du dernier cours dans la fourchette des ~5 ans, calculée par
   `spec_profiles.zone_of(closes, years=5)` → flottant de 0 à 1.
   Ses libellés et taux sont **codés en dur** dans `spec_fiche.ZONE_LABELS` :
   FORCE 83 %, BAS_SOLIDE 80 %, MILIEU neutre, HAUT_FRAGILE « 0 gagnant sur 4 »,
   BAS_ECRASE 50 %. **Ces taux ne sont ni datés ni vérifiés.**
3. Le schéma « rebond confirmé » exige **+10 % depuis le creux des 60 séances**.
4. Les fréquences par schéma sont calculées par `src/strategie/spec_profiles.py`
   (« cas observés », jamais « probabilité »).
5. Les données de marché sont dans `data/` (cache JSON) ; le cache des cours se lit avec
   `src/collecte/history_io.charger_cache` et `src/infrastructure/paths.HISTORY_CACHE`.

## Règles du dépôt (non négociables)

1. **AUCUN test ne touche le réseau.** Un appel HTTP dans un test fait passer la suite de
   8 secondes à 278 secondes quand le site ne répond pas (mesuré deux fois). Mocker tout appel.
2. **Aucune règle métier nouvelle sans décision de l'utilisateur.** Un indicateur INFORME ;
   il ne bloque JAMAIS un achat.
3. **Ne jamais inventer un chiffre.** Donnée absente = afficher « indisponible » (abstention),
   jamais une valeur plausible.
4. Français pour les textes visibles et les commentaires ; un commentaire explique le POURQUOI,
   avec la date et la mesure quand c'est une décision.
5. Un fichier = une responsabilité. Seuils numériques dans `src/regles.py` avec provenance
   commentée (date, mesure) — **ne pas modifier `regles.py`** : proposer, ne pas écrire.

## Pièges déjà payés

- Bash MSYS : les binaires natifs refusent `/c/...` → utiliser `C:/...`.
- `PYTHONPATH` est pollué par un venv parasite → préfixer les commandes python par `PYTHONPATH=`.
- `write_file` refuse de réécrire un fichier non relu dans la session → `read_file` d'abord.
- « Terminé, vérifié » ne suffit pas : **prouver par une sortie de test réelle**, collée dans
  le rapport final.

## Vocabulaire imposé (pour que les 3 livrables s'emboîtent)

- `percentile_5ans` : entier 0-100, part des séances des 5 dernières années strictement
  sous le cours actuel. (C'est `zone_of` multiplié par 100, arrondi.)
- `depuis_creux_pct` : pourcentage déjà parcouru entre le creux des 60 dernières séances et
  le cours actuel : `(cours - creux) / creux * 100`.
- `zone` : le flottant 0-1 de `zone_of` (nom existant, ne pas renommer).
- Ces trois noms sont les seuls autorisés dans les livrables.
