# Phase 3 — Brief Agent B (auditeur ADVERSARIAL, famille Mistral)

**Rôle** : Agent B d'un audit technique indépendant à deux agents (protocole d'audit BRVM — Bridge Bank).
**Famille** : Mistral (via OpenRouter) · **Périmètre** : la revue ÉLARGIE (tout sauf le périmètre de l'Agent A).
**Livrable** : `audit/phase3_agentB_mistral.md` · **Interdits** : modifier le projet, exécuter la suite de tests (phase 8).

## Périmètre élargi (exclusif)

Tout `src/` SAUF `strategie/strategie_leo.py`, `backtesting/challenge_validateur.py`,
`analyse/fondamentaux_historiques.py` (réservés à l'Agent A) — notamment :

- alertes (`src/alertes/`, `src/alerts.py`), portefeuille (`src/portfolio.py`, `src/portefeuille/`)
- veille spé (`src/strategie/spec_*.py`), collecte (`src/collecte/`), CLI (`src/main.py`)
- données et caches (`data/*.json` hors gros pkl), scripts d'exploitation (`scripts/`)
- tests (qualité de la couverture, faux positifs)

Lecture recommandée : `docs/IPS.md`, `docs/INVARIANTS-METIER.md`, `audit/phase2_exigences.md`.

## Mission (axes)

1. **Intégrité des données** : caches, historique, faisceau des sources, fraîcheur.
2. **Gestion d'erreurs** : exceptions silencieuses, valeurs par défaut dangereuses.
3. **Cohérence** : seuils/constantes vs décisions documentées ; duplication.
4. **Robustesse opérationnelle** : crons, notifications, idempotence, reprises après échec.
5. **Sécurité** : secrets hors code, appels réseau, entrées non validées.
6. **Qualité des messages** d'alerte (clarté néophyte, absence de promesses).

Pas de généralités — chaque finding porte une preuve citée du code.

## Contraintes

- LECTURE SEULE sur tout le projet ; seul le rapport final est écrit.
- Aucune exécution de la suite de tests ni de commande qui écrit sur disque.
- Rapport en français, format : en-tête · synthèse (TOP 5) · findings (ID B3-01…, fichier:ligne,
  gravité P1/P2/P3, description, preuve, scénario, recommandation) · « vérifié et sain » · limites.
