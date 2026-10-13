# État des lieux — système d'alerte Bridge Bank (périmètre BRVM uniquement)

**Date** : mardi 13/10/2026, ~02h10 UTC · **Mode** : LECTURE SEULE (seule exception : ce dossier)
**Périmètre** : **Bridge Bank uniquement** (précision LEO du 13/10 — la mission sert à décider l'orchestration du système d'alerte BRVM). L'inventaire machine complet (tous projets) est conservé pour référence dans `_archive_machine_complete/`.
**Preuves brutes** : `preuves/` (12 fichiers) — secrets jamais affichés (fragments masqués `***MASQUÉ***`).

---

## a) Ce qui est VÉRIFIÉ — le système d'alerte BRVM tel qu'il tourne

**La chaîne du matin** (workdir `C:\Users\LEO\projects\Bridge Bank`, livraison par le **notifier interne** du projet) :

| Heure | Job | Type | État |
|---|---|---|---|
| 09h00 | check quotidien | script (`.venv` projet) | ✅ completed (12/10 17:05) |
| 09h30 | analyse value | agent LLM | ✅ completed — **réparé le 13/10** (5 échecs avant) |
| 09h45 | veille radar | agent LLM + monitor (gating) | ✅ completed (no_change) — livraison réparée le 13/10 |
| 09h50 | veille spé | script | ✅ completed |
| 1er du mois | rapport mensuel | script | ✅ completed (01/10) |
| dimanche | backup git | script | ⚠️ dernier échec (05/10, repo introuvable) — credential corrigé le 12/10, **à confirmer dim 18/10** |

**Modèles et fournisseurs des agents BRVM** : **DeepSeek est LE fournisseur** (défaut `deepseek-flash`, usage réel `deepseek-v4-flash` 239 sessions ; délégation `deepseek-v4-pro`, 250 itérations) · vision `gemini-2.5-flash` (lecture des avis/captures) · clés présentes et valides : DeepSeek, Gemini, GitHub, OpenRouter (⚠️ plafond 5 $ atteint), Anthropic (⚠️ dupliquée dans `.env`).

**Plafonds** : `max_turns=90` · garde-fous de boucle **warn-only** · code_execution 50 appels · max_iterations délégation 250 · **aucun plafond de dépense**.

**Règles chargées** : SOUL.md (525 l) + MEMORY.md (**98 %** du plafond) + USER.md + skill `brvm-value-investing` (**978 l** + 38 références).

**Fichiers** : 24 inventoriés (config Hermes, scripts des 5 jobs, skill, config/.env du projet, docs de règles). **Coût** : 69,53 $ cumulés sur la machine (non isolable par projet — les sessions Bridge Bank y sont incluses).

## b) Ce qui n'est PAS vérifié (et pourquoi)

1. **Modèle réellement utilisé par job** : les jobs suivent le modèle principal (non pinnés) ; `state.db` n'agrège pas par job — vérification impossible sans exécution.
2. **Troncature éventuelle** du skill de 978 lignes / du prompt système (~101 000 car.) : seul le hash est conservé — non prouvable sans rejouer une session.
3. **Quotas restants** (OpenRouter, Gemini) : aucun appel réseau autorisé par la mission → NON CONSULTÉ.
4. **Résultat du backup git de dimanche** : pas encore eu lieu.

## c) Écarts qui concernent Bridge Bank (10 — **aucun élevé**)

**Moyens (6)** — 🔶 *directs* :
- **E1** Backup git : dernier échec « Repository not found » (05/10) ; credential corrigé le 12/10 → **vérifier le run de dimanche 18/10**.
- **E2** Skill `brvm-value-investing` : **978 lignes** — risque de troncature des règles à l'exécution.
🔷 *plateforme partagée (impact indirect)* :
- **E4** `providers.default=anthropic` vs `model.default=deepseek-flash` (le réel = DeepSeek).
- **E5** `ANTHROPIC_API_KEY` **dupliquée** dans `%HERMES_HOME%\.env`.
- **E6** Garde-fous de boucle : `hard_stop_enabled=false` (avertissent, n'arrêtent jamais).
- **E7** `MEMORY.md` à **98 %** du plafond — elle porte tout le contexte Bridge Bank.

**Faibles (3)** : **E3** radar sans rapport depuis le 17/09 (par design : monitor inchangé = aucun code L1/L2) · **E8** reset de session inopérant · **E9** vulnérabilités npm (outils locaux).
**Info (1)** : **E10** jobs value + radar réparés le 13/10 (les 5 échecs du 07→12/10 sont clos).

> Les 3 écarts « élevés » de l'inventaire machine (`sentry-watch` PharmaScan, D2D Book, gardes UNPPCI) **ne concernent pas la BRVM** — ils restent documentés dans `_archive_machine_complete/`.

## d) Décisions que seul LEO peut prendre (options chiffrées)

| # | Sujet | Option A (recommandée) | Option B | Option C |
|---|---|---|---|---|
| 1 | **E2 skill 978 l** | Découper : SKILL.md < 300 l (l'essentiel), le reste déjà en 38 références — **~1 session de travail, 0 €** | Laisser tel quel (risque non prouvé) | — |
| 2 | **E7 mémoire 98 %** | Consolider MEMORY.md (fusionner les entrées anciennes) — **~30 min** | Relever `memory_char_limit` | Attendre l'échec de sauvegarde |
| 3 | **E4 providers.default** | Aligner sur `deepseek` — **2 min** | Laisser (ambigu) | Repasser `anthropic` si voulu |
| 4 | **E6 garde-fous** | `hard_stop_enabled: true` — **1 min** | Laisser en warn-only | — |
| 5 | **E5 clé dupliquée** | Supprimer la ligne obsolète du `.env` — **2 min (toi)** | Laisser | — |
| 6 | **OpenRouter 5 $** | Repointer les futurs audits multi-modèles sur DeepSeek — **0 €** | Recharger (≥ 5 $) | Ne plus faire d'audit multi-modèles |
| 7 | **E1 backup** | Rien à faire — vérifier le run du **dim 18/10** | Relancer à la main | — |

**Ce qui n'a pas été fait** : aucune correction, aucune config modifiée, aucun appel payant ou externe, aucun envoi.
