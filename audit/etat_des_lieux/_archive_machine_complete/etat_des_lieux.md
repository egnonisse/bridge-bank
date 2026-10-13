# État des lieux — agents, modèles, fournisseurs, tâches et config (Bridge Bank / machine)

**Date** : mardi 13/10/2026, 01h25 UTC · **Mode** : LECTURE SEULE (aucune écriture hors de `audit/etat_des_lieux/`)
**Preuves brutes** : `preuves/` (12 fichiers : 11 sorties brutes + le générateur des CSV) — secrets jamais affichés (fragments masqués `***MASQUÉ***`).

---

## a) Ce qui est VÉRIFIÉ

| Sujet | Constat | Source |
|---|---|---|
| Agents/rôles inventoriés | **15** : 1 desktop interactif, 1 délégation, 1 vision, **12 jobs** (5 agents LLM + 7 scriptés) | `inventaire_agents.csv` |
| Tâches planifiées | **12 total, 11 actives, 1 pausée** (Pulse depuis le 22/07) | `cronjob_manage list`, `jobs.json` |
| Modèle par défaut | `deepseek-flash` / provider `deepseek` (api.deepseek.com) | `config.yaml` + session en cours |
| Modèles réellement utilisés | DeepSeek domine : v4-flash (239 sess.), v4-pro (112), flash (3) ; ~380 sessions desktop+cron | `state.db` table `sessions` |
| Délégation | `deepseek-v4-pro`, max_iterations 250 | `config.yaml` section `delegation` |
| Vision | Config `auto` → usage constaté `gemini-2.5-flash` (3 appels) | `state.db` `session_model_usage` |
| Coût cumulé estimé | **69,53 $** (v4-flash 29,02 · v4-pro 31,95 · reste < 9) — coût « réel » non renseigné | `session_model_usage` |
| Clés présentes (doctor OK) | DeepSeek, Anthropic, OpenRouter, Google, Firecrawl, GitHub | `hermes_doctor.txt` |
| OAuth | AUCUN connecté (Nous Portal, Codex, Qwen, MiniMax, xAI ✗) | `hermes_status.txt` |
| Gateway | **Aucune plateforme connectée** (`platforms={}`, Telegram ✗) — service running | `gateway_state.json`, `hermes status` |
| Règles chargées | SOUL.md 525 l · MEMORY.md 44 697 o (**98 %** du plafond) · USER.md 68 % · skill `brvm-value-investing` **978 l** + 38 références | `scan_fichiers.txt`, `skills_scripts_projets.txt` |
| Fichiers de config | 30 listés (chemin, taille, date) : home Hermes (14) + projet Bridge Bank (16) | `inventaire_fichiers_config.csv` |
| Plafonds | max_turns 90 · garde-fous de boucle **warn-only** · code_execution 50 appels max · max_iterations délégation 250 · **aucun plafond $** | `config_masque.yaml` |
| Projets desktop | 9 (dont Bridge Bank → `C:\Users\LEO\projects\Bridge Bank`) | `projects.db` |

## b) Ce qui n'est PAS vérifié (et pourquoi)

1. **Modèle réellement utilisé par job** : `state.db` n'agrège pas par job (les jobs suivent le modèle principal, non pinné) — vérification impossible sans exécution.
2. **Prompts système ~101 000 caractères** (152 stockés en base) : seule l'empreinte est conservée ; une éventuelle troncature du SKILL.md de 978 lignes **n'est pas prouvable** sans rejouer une session.
3. **Livraison effective** des 5 jobs en `deliver: origin` (D2D, gardes, newsletter, GSC, sentry-watch) : sans plateforme connectée, la cible est introuvable côté machine ; je ne peux pas prouver qu'un rapport est arrivé (ni qu'il n'est pas parti — E6).
4. **Quotas restants** (OpenRouter, Firecrawl) : aucun appel réseau autorisé → NON CONSULTÉ.
5. `auth.json` : contenu non lu (fichier sensible) — présence seulement.

## c) Écarts par gravité (15 au total — détail : `ecarts.csv`)

**⚠️ Lecture par projet — ce qui touche la BRVM** : seuls **E4 (backup), E10 (skill 978 l), E12 (radar)** concernent Bridge Bank — et E15 (résolu). Les écarts **E1, E2, E3, E6, E13** concernent **d'autres projets** (PharmaScan, Book, AIWATCH, Broker) : **aucun lien avec la BRVM**. Les écarts **E5, E7, E8, E9, E11, E14** sont des écarts de la **machine/plateforme partagée** (impact indirect sur tous les agents, dont ceux de la BRVM).

**ÉLEVÉE (3 — tous hors BRVM)**
- **E1** — *[PharmaScan]* `pharmascan-sentry-watch` : **échec à CHAQUE run, 89 en 7 jours** — champ `script` invalide (`python scripts/sentry_report.py --check` au lieu d'un chemin). Aucun monitoring Sentry actif.
- **E2** — *[Book]* Job D2D : **HTTP 402 Insufficient Balance** au dernier run (01/10) — suivi des ventes aveugle.
- **E3** — *[PharmaScan]* Job Gardes UNPPCI : **`No module named 'fitz'`** (01/10) — pas d'interpréteur `.venv` déclaré sur ce job scripté ; les gardes du mois ne sont pas collectées.

**MOYENNE (7)** — 🔶 *BRVM* : **E4** backup git (« Repository not found » 05/10 ; credential corrigé le 12/10, prochain run dim 18/10) · **E10** skill 978 lignes. 🔷 *machine (indirect)* : **E5** `providers.default=anthropic` vs `model.default=deepseek-flash` · **E7** clé Anthropic dupliquée · **E8** garde-fous warn-only · **E9** MEMORY.md à 98 %. ↩ *autres projets* : **E6** gateway sans plateforme (5 jobs `deliver: origin` non livrables — aucun BridgeBank concerné) · (E4/E10 détaillés ci-dessus).

**FAIBLE / INFO (5)** — E11 reset de session inopérant (`session_reset` sans plugin) · E12 radar sans rapport depuis le 17/09 (par design : monitor inchangé) · E13 Pulse pausé depuis le 22/07 · E14 vulnérabilités npm (20) · E15 job value : 5 échecs 07→12/10 **résolus le 13/10**.

## d) Décisions que seul LEO peut prendre (options chiffrées)

| # | Décision | Option A | Option B | Option C |
|---|---|---|---|---|
| 1 | **E1 sentry-watch** | Corriger le champ script (~5 min, 0 €) + relancer | Supprimer le job (Sentry reste consultable via le MCP) | Laisser (échec silencieux toléré) |
| 2 | **E2 D2D** | Pinner le job sur DeepSeek (~**0,25 $/mois** d'après l'usage v4-pro) | Recharger OpenRouter (≥ 5 $, montant libre) | Pause du job jusqu'à publication du livre 2 |
| 3 | **E3 gardes** | Ajouter l'interpréteur `.venv` du projet pharmascan au job (5 min) + relancer le mois courant | Convertir en tâche manuelle mensuelle | Laisser (déjà échoué au 01/10) |
| 4 | **E5 providers.default** | Aligner sur `deepseek` (cohérence, 2 min) | Repasser `anthropic` si c'était voulu | Laisser (ambigu) |
| 5 | **E6 livraison origin** | Connecter la passerelle Telegram (~10 min, `hermes gateway`) → 5 jobs livrables d'un coup | Convertir les 5 jobs au notifier interne projet par projet (~30-45 min) | Rien (constat documenté) |
| 6 | **E9 mémoire 98 %** | Consolider MEMORY.md (~30 min, fusionner les entrées anciennes) | Relever `memory_char_limit` (masque le problème) | Attendre l'échec de sauvegarde |
| 7 | **E10 skill 978 l** | Découper : SKILL.md court + références (recommandé, il y a déjà 38 références) | Laisser (troncature non prouvée) | — |
| 8 | **E13 Pulse pausé** | Confirmer la pause | Reprendre | Supprimer le job |

**Ce que je n'ai pas fait** : aucune correction, aucune config modifiée, aucun appel payant ou externe, aucun envoi.
