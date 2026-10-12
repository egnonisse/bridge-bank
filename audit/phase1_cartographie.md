# AUDIT BRVM — Phase 1 : cartographie intégrale (lecture seule)

**Date** : 2026-10-09 · **Commit audité** : `b810f7d93db6ab8d9dc11b77f0d7e7adb6c1d5c0` (`main`)
**Périmètre** : `C:\Users\LEO\projects\Bridge Bank` · **Méthode** : lecture statique (AST) + git +
lecture du code. Aucune exécution de test, aucune modification du projet.

Tags utilisés : **[FV]** fait vérifié · **[AR]** anomalie reproduite · **[RI]** risque identifié ·
**[H]** hypothèse · **[NT]** non testé · **[NC]** non concluant.

---

## 1. État initial du dépôt

| Constat | Valeur | Preuve |
|---|---|---|
| Arbre de travail | **propre**, aucun fichier modifié | `preuves/git_etat.txt` |
| Fichiers non suivis | **0** avant l'audit (puis `audit/`, créé par l'audit) | `preuves/git_etat.txt` |
| Fichiers suivis | 298 | `preuves/git_fichiers_suivis.txt` |
| Branche / HEAD | `main` / `b810f7d` | `preuves/git_etat.txt` |

### Les sept fichiers cités par la mission — vérifiés un par un

| Cité comme | Réalité au commit audité | Verdict |
|---|---|---|
| `src/regles.py` | **présent** — `src/regles.py`, 106 lignes | conforme |
| `src/seuils_vente.py` | **déplacé** → `src/calibration/seuils_vente.py`, 348 lignes | **chemin de la mission périmé** |
| `src/paths.py` | **déplacé** → `src/infrastructure/paths.py`, 92 lignes | **chemin de la mission périmé** |
| `profit_thresholds.json` | présent sous `data/profit_thresholds.json` (840 octets) | conforme, chemin à préciser |
| `data/seuils_journal.jsonl` | **présent** — 5 lignes | conforme |
| `portfolio.py` | présent sous `src/portfolio.py`, 847 lignes | conforme, chemin à préciser |
| `main.py` | présent sous `src/main.py`, 1 313 lignes | conforme, chemin à préciser |

**[FV]** Deux des sept chemins cités dans la mission sont périmés : ils ont été réorganisés les
mêmes jours (lots 2 et 3 du plan `docs/architecture.md`). La consigne « ne présume pas que ces
fichiers existent ou possèdent encore le même contenu » s'est révélée utile.

**Aucun secret suivi par git** **[FV]** : `git ls-files` ne trouve que `.env.example` ;
`config.yaml` porte `telegram.bot_token` et `chat_id` **vides** (longueur 0).

---

## 2. Volumes

| Zone | Contenu | Lignes |
|---|---|---|
| `src/` | **55 fichiers .py** (42 modules + 13 `__init__`), 11 paquets | **10 461** |
| `scripts/` | **90 scripts** | **11 843** |
| `tests/` | **39 fichiers, 336 tests** | **4 198** |
| `docs/` | **15 documents .md** (IPS, INVARIANTS-METIER, 5 décisions, 2 anomalies, 1 rapport de validation 28 ans…) | — |
| `data/` | 76 fichiers suivis par git, 51 fichiers de données sur le disque (json/jsonl/pkl) | — |
| CI | `.github/workflows/ci.yml` (1 workflow, 4 étapes) | — |
| Crochet local | `.githooks/pre-push` | — |

Détail module par module : **`audit/inventaire_modules.csv`** (55 lignes, une par module : domaine,
lignes, fonctions publiques/privées, classes, dépendances entrantes/sortantes, tests qui le citent,
présence d'une docstring). Source : `preuves/phase1_inventaire.json`.

---

## 3. Arborescence (à la date de l'audit)

```
Bridge Bank/
├── src/
│   ├── regles.py (106)  taxation.py  portfolio.py (847)  main.py (1313)
│   ├── alerts.py  report.py  notify.py  ajustement.py
│   ├── domaine/          regles et modèles ............ models.py
│   ├── collecte/         accès aux données ............ bsapi, live, backtest,
│   │                                                   cache_integrity, fundamentals,
│   │                                                   dividends, dividend_history,
│   │                                                   divisions_officielles,
│   │                                                   nettoyage_aberrantes
│   ├── analyse/          indicateurs et veille ........ fundamentaux_historiques, screener,
│   │                                                   screening, bonds, boc, news, radar
│   ├── strategie/        décisions .................... strategie_leo, noyau_check, orders,
│   │                                                   speculation, spec_profiles, spec_fiche,
│   │                                                   spec_veille, paliers_sortie
│   ├── calibration/      seuils et régimes ............ seuils_vente, schema_seuils,
│   │                                                   regime_marche
│   ├── portefeuille/     présentation ................. format_fr
│   ├── alertes/          transport et trace ........... journal_alertes
│   ├── backtesting/      simulation ................... backtest_noyau, challenge_schema,
│   │                                                   challenge_indicateurs, challenge_validateur
│   ├── cli/              (vide — cible du lot 5)
│   └── infrastructure/   plomberie .................... paths, empreinte
├── scripts/ (90)   tests/ (39)   docs/ (15)   data/   audit/ (ce dossier)
```

**[FV]** L'arborescence par domaines est celle du plan `docs/architecture.md`, lots 0 à 4 (faits).
Les paquets `domaine/`, `collecte/`, `analyse/`, `strategie/`, `calibration/`, `backtesting/`
contiennent leurs modules ; `cli/` et `alertes/` restent partiellement cibles du lot 5.

---

## 4. Graphe de dépendances

**108 arêtes d'import** entre modules du projet. Extrait des sommets :

| Module | Importé par | Dépend de | Rôle dans le graphe |
|---|---|---|---|
| `src.infrastructure.paths` | **23** | 0 | **socle gelé** : aucun module ne le remplace |
| `src.collecte.bsapi` | 10 | 0 | point d'accès unique aux données de marché |
| `src.regles` | 10 | 1 | catalogue des règles métier |
| `src.collecte.fundamentals` | 6 | 0 | fondamentaux par titre |
| `src.taxation` | 5 | 0 | fiscalité et frais |
| `src.portfolio` | 4 | 11 | agrégateur du noyau dividende |
| `src.main` | **0** | **21** | nœud terminal (CLI) : rien ne l'importe |

**Strates observées** **[FV, par lecture du graphe]** :
`paths` / `regles` / `taxation` (socle, sans dépendance interne) → `collecte` →
`analyse` / `calibration` → `strategie` → `portfolio` → `main`. Aucun cycle détecté dans le
graphe d'imports statique.

---

## 5. Flux de données **[FV par lecture du code — non exercé à l'exécution en phases 0-1]**

```
BSTrade (API) ─┐
brvm.org ──────┼─→ collecte/ ─→ data/*.pkl|json (caches) ─→ analyse/ ─→ strategie/
PDF UNPPCI/BOC ┘        │                                                      │
                        ▼                                                      ▼
              data/*_state.json (anti-doublon)                         portfolio/ (noyau)
                                                                               │
                     prompts / cron (6 tâches) ──→ main.py (22 sous-commandes) ┘
                                                                               │
                                             ┌─────────────────────────────────┴────────┐
                                             ▼                                          ▼
                                    notify.py → Telegram                    data/*.jsonl (traces)
                                                                      seuils_journal · alertes_journal
```

Trois journaux/traces coexistent : `data/seuils_journal.jsonl` (5 lignes — décisions de seuil),
`data/alertes_journal.jsonl` et les `data/*_state.json` (anti-doublon, non versionnés).

**État du journal des alertes — mis à jour le 09/10 à 09h13 (fait postérieur à ma première
observation, que je consigne plutôt que de l'effacer)** : il était **absent** lors de la collecte
de preuves à 07h17 ce jour-là (`preuves/alertes_journal.txt`), puis le **check quotidien de
production** a tourné à 09h12-09h13 et l'a créé avec **5 envois réels** :

| Heure | Message (extrait) | Empreinte |
|---|---|---|
| 09:12:32 | 🟠 FONDAMENTAL — BOAS — payout 84 % — dividende tendu | `code=b810f7d*` · `seuils=e4fe39cdb73c` |
| 09:12:33 | 🟠 FONDAMENTAL — SOGC — payout 99 % | idem |
| 09:12:50 | 📉 LE PRIX S'EST ENCORE AMÉLIORÉ — renforcement PALC | idem |
| 09:13:01 | ⚡ DÉCISION — PALC −10,3 % — CONSERVE | idem |
| 09:13:04 | ✅ Check quotidien Bridge Bank — 09/10 09:13 | idem |

**[FV] La traçabilité fonctionne en production** : chaque alerte réelle porte son empreinte de
version, et le drapeau `*` signale correctement que l'arbre de travail différait du commit. C'est
le dispositif décrit en `docs/DECISION-2026-10-09-empreinte-des-alertes.md`, **constaté à
l'œuvre** — pas seulement testé.

**[RI] Écritures concurrentes pendant l'audit** : la production écrit dans `data/` (ici
`per_cache.json` et `reinf_alert_state.json`, modifiés à 09h13) **pendant que l'audit est en
cours**. Aucune de ces écritures n'est imputable à l'audit (dates et contenus vérifiés), mais
cela impose de **figer les fichiers de `data/` avant la Phase 8**, sinon un test pourrait lire un
état modifié sous ses pieds.

**[RI] Ces modifications ne sont pas commitées** : le dépôt local et le dépôt distant divergent
d'état de données depuis le 09/10 (la sauvegarde automatique est en échec — anomalie A-001).

---

## 6. Décisions métier identifiées dans le code

| Règle | Où | Valeur effective constatée | Exigence écrite ? |
|---|---|---|---|
| Sortie totale (4 motifs) : dividende suspendu/coupé > 50 %, PER > 40, prix de sortie atteint | `portfolio.py:485-509` | `DIV_CUT_RATIO 0.5`, `PER_EXPLODE 40.0` **[FV]** | `docs/IPS.md` (à confronter en Phase 2) |
| Seuil de vente ⅓ **par titre**, avec garde de significativité statistique | `calibration/seuils_vente.py` + `portfolio.py:517-527` | SNTS 13 %, SGBC 10 %, SLBC 5 %, PALC 5 % **[FV — `preuves/seuils_actuels.txt`]** | `docs/DECISION-2026-10-08-seuils-vente.md` |
| Un seuil ne propose une vente que s'il est **fondé** (`borne_basse ≥ 50 %`) | `seuils_vente.est_declencheur` | les 4 seuils en vigueur sont `informatif` **[FV — journal des seuils]** | oui |
| Verrou de concentration **informe, ne bloque jamais** | `portfolio.py:654-708` | 35 % / 50 % / plafond d'achats | `docs/DECISION-*` |
| Poches étanches (un spéculatif ne devient jamais un investissement) | `portfolio.py:828-836` | lève une `ValueError` explicite | `docs/IPS.md` |
| Échéance 3 ans = réévaluation, jamais clôture auto | `portfolio.py:534-535` | `HOLDING_YEARS 3` | oui |

**Aucun de ces seuils n'a été modifié par l'audit** **[FV]** : `data/profit_thresholds.json` et
`data/seuils_journal.jsonl` portent des dates antérieures à l'audit.

---

## 7. Points d'entrée

| Type | Nombre | Détail |
|---|---|---|
| Sous-commandes CLI exposées | **22** | screen, analyze, top, watch, alert, backtest, spec, portf, report, boc, div, fund, limits, radar, noyau-check, sustain, news, live, integrity, bond, daily, specveille |
| Fonctions `cmd_*` | **25** | 3 d'entre elles ne sont **pas** exposées : `cmd_reinforcements`, `cmd_watchlist`, `cmd_filet` — **[FV]** ce sont des étapes internes appelées par `cmd_daily` (`main.py:1245-1265`) |
| Tâches planifiées Hermes (Bridge Bank) | **6** | check quotidien 09:00 · analyse value 09:30 · radar 09:45 · veille spé 09:50 · rapport mensuel (1er, 09:00) · sauvegarde git hebdo (dimanche 09:00) |
| Scripts | 90 | usage ponctuel ou épreuve statistique ; non exposés comme interface |

### État des tâches planifiées **[FV — `cronjob_manage`]**

| Tâche | Dernière exécution | État | Constat |
|---|---|---|---|
| check quotidien 09:00 | 08/10 09:34 | **ok** | script `bridgebank_daily.py`, sans agent |
| rapport mensuel | 01/10 09:01 | **ok** | — |
| veille radar 09:45 | 08/10 09:45 | **ok** | livraison Telegram, surveillée par un *monitor* |
| veille spé 09:50 | 08/10 09:58 | **ok** | — |
| **analyse value 09:30** | 08/10 09:30 | **`blocked_config`** | « delivery platform 'telegram' has no gateway credentials configured » → la tâche s'exécute mais **sa sortie ne peut pas être livrée** |
| **sauvegarde git hebdo** | 05/10 13:01 | **erreur** | `remote: Repository not found` sur `github.com/egnonisse/bridge-bank` → **la sauvegarde automatique ne fonctionne pas** |

Ces deux derniers points sont des **anomalies reproduites par la plateforme** (voir
`audit/registre_anomalies.csv`, identifiants A-001 et A-002).

---

## 8. Modules sans aucun test qui les cite — le point le plus sérieux de cette phase

**[FV]** 12 modules (hors `__init__`) ne sont cités par **aucun** fichier de test :

| Module | Lignes | Ce que c'est |
|---|---|---|
| `src.strategie.strategie_leo` | **476** | **le moteur de stratégie** (`MoteurLeo`) |
| `src.backtesting.challenge_validateur` | **504** | le validateur des hypothèses statistiques |
| `src.analyse.fondamentaux_historiques` | **374** | les fondamentaux à la date (anti-lookahead) |
| `src.backtesting.challenge_schema` | 290 | schéma et évaluation des hypothèses |
| `src.collecte.backtest` | 268 | chargement de l'historique |
| `src.collecte.divisions_officielles` | 234 | divisions de nominal |
| `src.strategie.paliers_sortie` | 243 | paliers de sortie |
| `src.backtesting.challenge_indicateurs` | 256 | indicateurs du challenge |
| `src.collecte.bsapi` | 189 | **accès aux données de marché** |
| `src.ajustement` | 162 | ajustement CLI |
| `src.alerts` | 134 | moteur d'alertes de watchlist |
| `src.collecte.nettoyage_aberrantes` | 101 | nettoyage des cours aberrants |

**Lecture prudente** : « aucun test ne le cite » n'est pas « non testé » — un module peut être
couvert indirectement. Mais **quatre** d'entre eux sont des pièces maîtresses (moteur de stratégie,
validateur statistique, fondamentaux historiques, accès aux données) et méritent une vérification
explicite en Phase 4. C'est une liste de travail, pas un verdict.

---

## 9. Risques immédiats liés à l'exécution des tests **[RI — à confirmer en Phase 8]**

| Risque | Constat | Mitigation proposée |
|---|---|---|
| Appels réseau | 3 fichiers citent `requests`/`urlopen` (`test_live`, `test_news`, `test_journal_alertes`) ; la lecture montre qu'ils posent un bouchon | exécuter chaque fichier isolément et surveiller les accès sortants |
| Écritures | 8 fichiers citent une écriture (`save_*`, `.write_text`, `.unlink`) ; la lecture montre `tmp_path` | exécuter avec un relevé des dates des fichiers de `data/` avant/après |
| Données réelles | `data/portfolio.json`, `data/*_state.json`, journaux | **jamais** exécuter la suite avant d'avoir figé ces fichiers ; un test qui écrirait dans `data/` serait une anomalie en soi |

---

## 10. Informations manquantes qui empêchent de définir le comportement attendu (Phase 2)

1. **Aucune spécification formelle unique** : les règles vivent dans `docs/IPS.md`,
   `docs/INVARIANTS-METIER.md`, cinq documents de décision et les commentaires du code. Savoir
   laquelle fait autorité en cas de contradiction n'est pas établi → **décision humaine requise**
   (l'audit ne choisira pas arbitrairement).
2. **La provenance des données de fondamentaux** n'est pas documentée à ma connaissance
   (`collecte/fundamentals.py` : à examiner en Phase 5) — sa fraîcheur conditionne tout payout.
3. **Le décompte exact des coûts réels** (courtage, TVA, BRVM, conservation) doit être confronté au
   relevé Bridge Bank ; je ne l'ai pas encore fait.
4. **L'usage attendu des scripts d'épreuve** (90 scripts) : certains sont des épreuves statistiques
   qui fondent des décisions (`docs/RAPPORT-VALIDATION-28-ANS.md`) — leur reproductibilité doit
   être vérifiée avant de s'appuyer sur leurs conclusions.

---

## 11. Plan d'exécution des phases suivantes

| Phase | Contenu | Dépendance | Preuve attendue |
|---|---|---|---|
| **2** | Registre des exigences (source exacte, module, test, statut) | décision sur la hiérarchie des sources (§10.1) | `audit/matrice_exigences_tests.csv` |
| **3** | Deux agents indépendants sur les points sensibles | **décision sur le second modèle** (Phase 0) | `audit/registre_desaccords.md` |
| **4** | Matrice de tests (nominaux, limites, invalides, adversariaux, robustesse) | Phase 2 | tests ajoutés + journal d'exécution |
| **5** | Audit financier : formules, recalculs indépendants, déclencheurs, calibration, biais temporels | Phase 2 | `audit/preuves/phase5_*.txt` |
| **6** | Contrats entre modules et chaînes complètes | Phases 4-5 | matrice de traçabilité |
| **7** | Sécurité, intégrité, fiabilité opérationnelle | — | rapport dédié |
| **8** | **Exécution contrôlée** des tests (avec relevé avant/après des fichiers de `data/`) | autorisation de LEO | journaux bruts |
| **9-11** | Corrections (si autorisées), couverture, rapport final + PDF | Phases précédentes | `audit/rapport_final.md` |

**Rappel du protocole** : les phases 0 et 1 sont **terminées** ; aucune correction, aucun
déploiement, aucun test n'a été exécuté. Le présent document ne conclut rien sur la fiabilité du
système — il décrit ce qui existe.
