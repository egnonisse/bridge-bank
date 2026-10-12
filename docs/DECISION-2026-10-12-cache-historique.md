# Décision du 12/10/2026 — Réparation du cache historique (48 → 0 alerte d'intégrité)

**Déclencheur** : l'étape « Intégrité des données » du check quotidien signalait **48 titres
« cache en retard »** (dernières barres au 30/09) — visible grâce à la correction B2-04 du
lot 1, investigué en tant que chantier dédié après le lot 2 (« prochain chantier candidat »).

## Enquête (faits mesurés, pas d'hypothèse)

1. **État** : `data/history_cache.pkl` (48 titres) — dernières barres au **30/09** (12 jours
   de retard) ; mtime du fichier = **09/10 03h36**.
2. **L'API BSTrade était À JOUR** : fetch direct → barres jusqu'au 08/10 (SNTS) / 09/10
   (SGBC, PALC, SLBC, BOAC, SIVC…) — le problème n'était pas la source.
3. **Cause racine** : la logique de cache ne jugeait que le **mtime** du fichier
   (`CACHE_MAX_AGE_DAYS = 7`). Le refresh du 09/10 avait capturé des données **déjà en
   retard** (dernières barres au 30/09) ; ce cache « frais » a été réutilisé tel quel pendant
   7 jours — radar et veille spé compris (analyses techniques sur ~2 semaines de retard).
4. **SEMC / SICC** : aucune transaction depuis le 15/09 — même l'API directe ne fournit rien
   de plus récent. Titres légitimement **dormants** : leurs alertes étaient du bruit permanent.

## Corrections

| # | Correction | Effet |
|---|---|---|
| 1 | **Refresh complet relancé** (`scripts/refresh_history.py`) → 37 titres au 09/10 (dernière séance), 9 aux 07-08/10 | données à jour |
| 2 | **`history_clean.pkl` régénéré** (divisions + nettoyage) puis **`reversal_profiles.json` ré-exporté** | profils « 📜 HISTOIRE » cohérents avec le nouveau cache |
| 3 | **Fraîcheur jugée sur les DONNÉES, plus sur le mtime** (`_donnees_fraiches()` : dernière barre < 4 j) — un cache au fichier récent mais aux données périmées est **ignoré** et re-téléchargé | **auto-réparant** : un refresh raté est retenté chaque jour (l'ancien design figeait 7 jours) |
| 4 | **Registre des titres dormants** (`data/titres_inactifs.json`, écrit à chaque refresh) + `check_freshness` s'en sert (même dernière barre ET vérification < 8 j) | SEMC/SICC : information au lieu d'alerte ; toute nouvelle barre ou vérification périmée **ré-alerte** |

## Preuves

- **Étape Intégrité : 48 → 0 problème** — mesuré avec la même fonction que celle qui alertait
  (`check_all_integrity`) sur le cache réparé.
- Distribution des dernières barres après refresh : **09/10 : 37** · 08/10 : 1 · 07/10 : 8 ·
  15/09 : 2 (dormants vérifiés).
- Suite complète : **361 passed, 1 xfailed** — dont **5 nouveaux tests** :
  `test_donnees_fraiches_juge_sur_la_derniere_barre`,
  `test_cache_fichier_recent_mais_donnees_vieilles_declenche_le_refetch`,
  `test_titre_dormant_verifie_ne_crie_pas`,
  `test_titre_dormant_verification_perimee_realerte`,
  `test_titre_dormant_avec_nouvelle_barre_realerte`.

## Limites (honnêteté)

- Le seuil « données < 4 jours » tolère le week-end (pas de re-fetch inutile si le cache a
  capturé la séance du vendredi) ; si l'API reste muette plusieurs jours, chaque appel
  retente — le retard résiduel est borné par la disponibilité de la source.
- Le registre des dormants porte « vérifié le JJ/MM » : passé **8 jours sans refresh réussi**,
  l'alerte revient — on ne fait pas confiance éternellement à une vérification ancienne.
- Ce chantier était HORS lots 1-2 : il est traité ici comme item distinct (découvert par
  l'outillage réparé au lot 1, résolu après le lot 2).
