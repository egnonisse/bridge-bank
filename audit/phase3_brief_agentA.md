# Phase 3 — Brief Agent A (auditeur fonctionnel, famille Claude)

**Rôle** : Agent A d'un audit technique indépendant à deux agents (protocole d'audit BRVM — Bridge Bank).
**Famille** : Claude (via OpenRouter) · **Périmètre** : les 3 modules « sensibles » désignés par la Phase 1.
**Livrable** : `audit/phase3_agentA_claude.md` · **Interdits** : modifier le projet, exécuter la suite de tests (phase 8).

## Périmètre borné (exclusif)

1. `src/strategie/strategie_leo.py` — moteur de stratégie
2. `src/backtesting/challenge_validateur.py` — validateur statistique
3. `src/analyse/fondamentaux_historiques.py` — fondamentaux historiques

Lecture recommandée : tests couvrant ces modules, `docs/INVARIANTS-METIER.md`,
`docs/architecture.md`, `docs/CHALLENGE-MULTI-MODELES.md`, `docs/RAPPORT-VALIDATION-28-ANS.md`.

## Mission

Trouver les défauts RÉELS et VÉRIFIABLES : bugs de logique, erreurs de calcul, biais
(look-ahead, survivance, multiplicité), cas limites, incohérences avec la documentation,
fragilités. Pas de généralités — chaque finding porte une preuve citée du code.

## Contraintes

- LECTURE SEULE sur tout le projet ; seul le rapport final est écrit.
- Aucune exécution de la suite de tests ni de commande qui écrit sur disque.
- Rapport en français, format : en-tête · synthèse (TOP 5) · findings (ID A3-01…, fichier:ligne,
  gravité P1/P2/P3, description, preuve, scénario, recommandation) · « vérifié et sain » · limites.
