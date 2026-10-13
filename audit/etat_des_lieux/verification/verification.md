# Vérification ciblée de l'état des lieux Bridge Bank — 8 points

**Date** : mardi 13/10/2026, 01h50–02h20 UTC · **Mode** : lecture seule · **Preuves brutes** : `preuves/` (15 fichiers)
**Périmètre** : les 8 points ouverts de `audit/etat_des_lieux/etat_des_lieux.md`. Rien n'a été corrigé (voir `corrections_au_rapport.md` pour les reformulations).

---

## V1 — Composition du prompt système · **CONFIRMÉ** (le risque de troncature est écarté au niveau du prompt)

`hermes prompt-size` (préuve `V1_prompt_size.txt`) : prompt système total **99 601 B** (97,3 KB) = identity/guidance 17 791 B (stable) + **mémoire 44 888 B** + **profil utilisateur 19 940 B** + index des skills 13 458 B (volatile 81 808 B) ; **schémas d'outils : 67 967 B (38 outils, dont kanban 24,5 KB)**.

**Le skill `brvm-value-investing` : 96 308 B sur disque — mais son INDEX dans le prompt = 87 B.** Il n'est donc **PAS intégré en entier au prompt système : il est chargé à la demande** (`skill_view`). La crainte « skill tronqué dans le prompt » est écartée ; le risque résiduel se déplace sur la lecture au moment de l'appel.
**Limites** : mesure `platform=cli` (session interactive) — **la mesure pour un job cron n'est PAS VÉRIFIÉE** (aucune commande équivalente sans exécuter un job). La taille de lecture du skill à l'appel n'est pas mesurable sans rejouer une session.

## V2 — Clé Anthropic et fournisseur par défaut · **CONTREDIT** (le rapport déclarait la clé valide — elle est INVALIDE)

`hermes doctor` du 13/10 01h51 (preuve `V2_doctor.txt`, ligne 95) : **`✗ Anthropic API (invalid API key)`** — et le doctor du 13/10 01h10 utilisé pour l'inventaire disait **déjà** la même chose (ligne 94) : **mon rapport d'inventaire a eu tort d'écrire « doctor OK »** (voir `corrections_au_rapport.md`).
`%HERMES_HOME%\.env` (preuve `V2_env_noms.txt`) : 21 lignes, 20 noms ; **`ANTHROPIC_API_KEY` ×2, longueurs [108, 108], valeurs DIFFÉRENTES** (booléen d'égalité testé sans jamais lire les valeurs).
Config : `providers.default = anthropic` MAIS `model.default = deepseek-flash` / `model.provider = deepseek`.
`hermes fallback list` (preuve `V2_fallback.txt`) : **« No fallback providers configured »** → **si le modèle principal échoue, AUCUN repli automatique n'est configuré** ; et tout usage qui retomberait sur le provider par défaut (anthropic) échouerait (clé invalide).
**Limite** : impossible de dire laquelle des deux occurrences du `.env` est lue (ordre de chargement) — les valeurs n'ont pas été affichées.

## V3 — Mixture of Agents (`moa`) · **CONFIRMÉ** (activé, agrégateur sur fournisseur NON connecté, jamais utilisé)

Config (preuve `V3_V4_moa_delegation.txt`) : **`moa.enabled: true`**, agrégateur **claude-opus-5 / anthropic** (⇒ **clé invalide**, cf. V2), presets `default` identiques, `degraded_reference_policy: loud`, `fanout: per_iteration`. Identique dans les deux backups (14/09 et 29/09).
**Aucun job BRVM n'appelle MoA (constaté)** : aucune référence `moa`/`mixture` dans `cron/jobs.json` ni dans les prompts des 6 jobs. Dans `state.db` : **aucune session ni modèle contenant « moa »** ; tâches connues : `''`, `approval`, `background_review`, `compression`, `title_generation`, `vision`.
**Limite** : MoA s'active par session (interactive) ; on ne peut pas prouver qu'il ne sera jamais invoqué — s'il l'était, l'agrégateur anthropic invalide produirait un échec ou une dégradation (bruyante, `loud`).

## V4 — Historique de la délégation · **NON VÉRIFIABLE** (date exacte) — intervalle borné

config **actuelle** : `delegation = deepseek-v4-pro / deepseek` (max_iterations 250). Backups : **29/09 et 14/09 : AUCUN model/provider de délégation** (⇒ modèle par défaut de l'époque). Le passage à DeepSeek explicite a donc eu lieu **entre le 29/09 et le 13/10** — indice : mtime de `config.yaml` = **12/10 03:39** ; pas de backup intermédiaire pour trancher.
`session_model_usage` : `anthropic/claude-sonnet-5.5` (openrouter) first_seen **11/10 ~23h59 UTC**, last_seen **12/10 ~01h26** ; `claude-opus-5.5` (openrouter) 12/10 ~03h11 — ces sessions correspondent aux **audits multi-modèles du 12/10**, pas nécessairement à la délégation.
**Verdict** : NON VÉRIFIABLE pour la date exacte ; intervalle (29/09 → 13/10], indice fort au 12/10.

## V5 — Livraison réelle des alertes BRVM · **CONFIRMÉ** (tout est expliqué par le code ou les données)

15 derniers runs × 6 jobs listés avec `scheduled_instant`/start/finish/status/delivery/error (preuve `V5_livraison.txt`). Valeurs distinctes de `delivery_outcome` (toutes jobs) : `not_configured` 313 · `None` 177 · `suppressed_acked` 149 · `suppressed` 121 · `failed` 3 — sémantique lue dans le code (`cron/scheduler.py`, `_classify_delivery_outcome`, preuve `V5_code_delivery2.txt`) :
- **`suppressed`** = `deliver=local` (nominal, rien à envoyer par le gateway) ;
- **`not_configured`** = une livraison était demandée vers « origin » mais **aucune plateforme connectée** : **la livraison n'a PAS eu lieu** (313 runs concernés — dont le backup BridgeBank `c3a1…`, deliver=origin) ;
- **`suppressed_acked`** = échec connu déjà acquitté (pas de re-notification) ;
- **`failed`** = 3 erreurs d'envoi réelles.
- **Runs `unknown`** (1 par job, le 11/10) = « Scheduler restarted after this execution's owner exited before a durable terminal state » → **runs interrompus par un redémarrage du scheduler (tous réclamés ~11/10 16h42, fin 19h02)** : ni succès ni échec.
- **Check du 12/10 fini 17h05** : run **MANUEL** (`source=direct`, `scheduled_instant` NULL — déclenché pendant les travaux du 12/10) ; le run planifié du jour avait été **rattrapé** 16:43→16:49 (`builtin`).
Jobs.json : les 3 jobs scriptés (check, mensuel, backup) ont **`workdir=None`** (leurs scripts résolvent le projet en absolu) ; les 2 jobs agents + spé ont le workdir correct ; aucun job n'est épinglé à un modèle.
**Limite** : les 15 runs par job couvrent ~2-3 semaines ; au-delà non consulté.

## V6 — Canal de notification du projet · **CONFIRMÉ**

- **Où** : `config.yaml` du projet → `telegram: {bot_token:'', chat_id:''}` (vides) ; **`.env` du projet → `TELEGRAM_BOT_TOKEN` (longueur 46) + `TELEGRAM_CHAT_ID` (longueur 10)** ; rien en variable d'environnement système hors `.env` (chargé par `load_dotenv` local).
- **`session_only`** : garde dans `src/alerts.py:68` (`respect_session and session_only and not _in_session()`), `_in_session` = lundi-vendredi **8h30–16h00** (UTC) (`src/alerts.py:111-117`). **Le check quotidien passe `respect_session=False`** (`src/main.py:182`) → **`session_only: true` N'EMPÊCHE PAS ses envois**, y compris hors 16h00 (constaté : envois journalisés à 16:48–17:05 le 12/10). Il ne s'applique qu'au mode « boucle » (`AlertEngine` avec `respect_session=True`, `src/main.py:130`).
- **`empreinte_dans_message`** : lue à `src/main.py:59-62`, suffixe géré dans `src/notify.py:67/101` ; actuellement **false** (pas de suffixe).
- **Envoi par le notifier du projet, PAS par le gateway** : chaîne lue dans le code — cron Hermes → `~/hermes/scripts/bridgebank_daily.py` → `scripts/daily_check.py` → `src.main.cmd_daily` → `get_notifier()` (`src/main.py:55-62, 168`) → `TelegramNotifier.send()`. Preuves : fichiers cités (lecture, sans exécution).
- **Journal** (`data/alertes_journal.jsonl`, 12 lignes) : dernier envoi **2026-10-13 00:19:44** (origine `__main__`, 299 car. — le message de test du 13/10) ; dernier envoi **métier** : **2026-10-12 17:05:50** (origine `src.main`). Tous `envoye: true`.

## V7 — Mémoire et contexte partagés · **CONFIRMÉ** (classification heuristique)

`MEMORY.md` : **73 entrées, 43 131 caractères**. Répartition (motifs précis par ordre de priorité — preuve `V7_memoire.txt`) :

| Catégorie | Entrées | Caractères | Part |
|---|---|---|---|
| AIWATCH | 19 | 12 270 | 28 % |
| Hermes / machine | 14 | 8 539 | 20 % |
| Zariamall / BotWhatsApp | 15 | 7 929 | 18 % |
| PharmaScan | 13 | 7 723 | 18 % |
| Book / TapyCash / ShopMa / Broker | 4 | 3 185 | 7 % |
| Général / divers | 5 | 1 957 | 5 % |
| **BRVM (Bridge Bank)** | **3** | **1 528** | **4 %** |

Bridge Bank = **3 entrées dédiées (IRVM, radar/veille, Bridge Bank elle-même)** ≈ 4 % — plus des parcelles dans des entrées mixtes (2 entrées mentionnent `bridge-bank`, dont la règle GitHub partagée). La mémoire est donc **majoritairement e-commerce/pharma**.
**Limite** : les jobs cron chargent MEMORY.md — **NON VÉRIFIÉÉ** (la mesure `prompt-size` est `platform=cli` ; pas d'équivalent cron sans exécution). La classification est heuristique (frontières approximatives).

## V8 — État du budget · **CONFIRMÉ** — avec ÉCART entre deux sources (signalé, non tranché)

- **OpenRouter (ESTIMATION locale)** : **4,0531 $** cumulés (preuve `V8_budget.txt`) — mistral-large-4-0 2,06 $ (133 appels), claude-opus-5.5 0,85 $, claude-sonnet-5.5 0,66 $, gemini-3.1-pro 0,48 $. **L'annonce du 09/10 (manifest d'audit) disait 4,82 $** → **écart entre les deux sources ; je ne tranche pas** (l'annonce venait probablement de l'API, l'estimation d'ici ne compte que les sessions conservées). **Le solde réel n'a PAS été consulté.**
- **Coût des sessions cron (6 derniers jours)** : **0,0185 $ au total** (08/10 : 0,0141 — probablement la newsletter AIWATCH du jeudi ; 13/10 : 0,0044 — runs de cette nuit) → **ordre de grandeur : moins d'un centime par jour d'activité** ; les jobs BRVM scriptés ne consomment AUCUN LLM.
- **`hermes usage`** : son aide (lue, `V8_usage_help.txt`) dit « **Fetch the configured provider's account limits** … OpenRouter credits » → **OUI, il consulte le réseau. NON exécuté** (pas d'accord demandé).

---

**Contrôle final** : aucun secret dans les fichiers produits (scan `sk-`/`Bearer`/chaînes > 30 car. : AUCUN) · 8 verdicts = 8 lignes du CSV · `git status` : voir compte rendu.
