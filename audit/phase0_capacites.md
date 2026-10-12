# AUDIT BRVM — Phase 0 : capacités réellement disponibles

**Statut** : constat, aucune conclusion d'audit. **Date** : 2026-10-09. **Commit** : `b810f7d`.
Règle appliquée : *ne jamais supposer qu'un outil existe sans l'avoir vérifié* — chaque ligne
porte la commande ou le fichier de preuve qui l'établit.

## Capacités vérifiées comme DISPONIBLES

| Capacité | Ce qui a été constaté | Preuve |
|---|---|---|
| Exécution Python | **3.11.15**, interpréteur `…\hermes-agent\venv\Scripts\python.exe` | `preuves/git_etat.txt` + mesure directe |
| Exécution des tests | **pytest 9.1.1**, **336 tests collectés dans 39 fichiers `.py`** (= 38 fichiers `test_*.py` + `conftest.py` — d'où l'écart apparent avec le « 38 » de la Phase 2) | `preuves/tests_collecte.txt` |
| Bibliothèques du projet | `requests 2.33.0`, `PyYAML 6.0.3`, `numpy 2.4.3`, `pymupdf 1.28.2`, `urllib3 2.7.0`, `rich 14.3.3` | `pip list` |
| Git | branche `main` ; au contrôle final : **2 fichiers de données modifiés** (`data/per_cache.json`, `data/reinf_alert_state.json` — écrits par le check de production du 09/10 entre 09:12 et 09:13, origine établie par rapprochement du planificateur) et 2 éléments non suivis (`audit/`, `data/alertes_journal.jsonl`) | `preuves/git_etat_final.txt` |
| Analyse statique | `ast` (stdlib) — graphe d'imports construit et vérifié à la main | `preuves/phase1_inventaire.json` |
| Création d'une branche / espace isolé | possible (git), **non utilisé** : l'audit reste en lecture seule | — |
| Réseau | `brvm.org` 1,9 s · `api.telegram.org` 0,8 s · `github.com` 0,4 s — **IPv4 forcé** (l'IPv6 de cette machine ne route pas) | mesure directe |
| Données de marché locales | `data/history_clean.pkl` (7,0 Mo, 48 titres), `data/reversal_profiles.json` (14,8 Ko) | `ls -la data/` |
| Génération PDF | `pymupdf` présent (peut écrire un PDF) — **non encore exercé** | `pip list` |
| Machine | 4 cœurs · 17,1 Go RAM (3,0 Go libres) · 295 Go de disque libre | `preuves/anomalie_sustain_sans_fondamentaux.txt` (dernière ligne) |

## Capacités vérifiées comme INDISPONIBLES

| Capacité | Constat | Conséquence pour l'audit |
|---|---|---|
| **Couverture de code** (`coverage`) | **absent** (`import coverage` → ModuleNotFoundError) | Phase 10 : la couverture LIGNES/BRANCHES **ne peut pas être mesurée** sans installer l'outil. Je ne produirai aucun taux inventé. |
| **Tests de mutation** (`mutmut`) | **absent** | Phase H **impossible** en l'état. Une mesure de couverture ne remplace pas cette information. |
| **Tests de propriétés** (`hypothesis`) | **absent** | Phase G limitée à des jeux d'entrées écrits à la main (bien reproductibles, moins larges). |
| Outils de lint (ruff/flake8/mypy) | **non vérifiés** — je ne les ai pas testés, je ne les déclare donc ni présents ni absents | À vérifier si la Phase 10 doit les inclure |

## Modèles d'IA : capacité ÉTABLIE (preuve d'exécution dans `preuves/modeles_verifies.txt`)

| Élément | Constat vérifié |
|---|---|
| Fournisseur par défaut de Hermes | `anthropic` — **mais sa clé directe est invalide** : `hermes doctor` répond « ✗ Anthropic API (invalid API key) » |
| Fournisseurs sains | **✓ OpenRouter · ✓ DeepSeek · ✓ gemini** (rapport officiel de `hermes doctor`) |
| Délégation | **configurée** : `delegation.provider = openrouter`, `delegation.model = anthropic/claude-sonnet-5.5` (via `hermes config set`, jamais par édition du fichier) |
| Deux modèles distincts, **vérifié de bout en bout** | **OUI** — un sous-agent réel a exécuté une tâche et la base de sessions enregistre `model = anthropic/claude-sonnet-5.5`, `billing_provider = openrouter`, alors que la session parente est `deepseek-v4-flash` / `deepseek` |

**Pourquoi OpenRouter plutôt qu'un fournisseur direct** (choix corrigé en cours de phase, sur
remarque de LEO) : la clé Anthropic directe étant morte, OpenRouter **rouvre la famille Claude**
(génération réelle obtenue), donne accès à **458 modèles** de familles différentes avec **une seule
clé**, et son solde est consultable — **4,82 $ disponibles** au moment de l'audit.

**Duo proposé pour la Phase 3**, deux familles réellement différentes :

| Rôle | Modèle | Prix (entrée / sortie par million de jetons) |
|---|---|---|
| Agent A — auditeur fonctionnel | `anthropic/claude-sonnet-5.5` (via OpenRouter) | 2,00 $ / 10,00 $ |
| Agent B — auditeur adversaire | `mistralai/mistral-large-2512` ou `qwen/qwen3.5-plus` | 0,50/1,50 ou 0,30/1,80 |

**Contrainte budgétaire à respecter** : avec 4,82 $ de crédit, un audit mené largement sur Claude
épuiserait le solde. Le Claude doit donc être réservé à un **périmètre borné** — les points
sensibles identifiés en Phase 1 (moteur de stratégie, validateur statistique, fondamentaux
historiques) — le second auditeur, dix à vingt fois moins cher, couvrant la revue élargie.

## Contraintes connues qui pèsent sur l'audit

- **Aucun outil de couverture ni de mutation** → la Phase 10 sera partielle, et je le dirai.
- **Windows/MSYS** : les binaires natifs refusent les chemins `/c/...` (constaté deux fois pendant
  cette phase : lecture de `config.yaml` échouée puis réussie avec un chemin natif).
- **Réseau disponible mais non utilisé** : l'audit s'interdit tout test qui frappe un service
  externe (BRVM, BSTrade, Telegram) sans autorisation explicite. Les caches locaux suffisent.
- **Écritures** : l'audit n'exécute, pendant les phases 0-1, que des commandes en lecture ; les
  fichiers de données du projet portent tous des dates antérieures à l'audit (vérifié).

## Limites explicites de cette phase

- Les capacités sont celles de la machine de LEO ; je n'ai pas testé d'environnement de secours
  (VPS, CI) autrement qu'en lisant la configuration de la CI.
- Je n'ai pas mesuré les durées de la suite de tests ni sa consommation mémoire : ce sont des
  mesures de la Phase 8, pas de la Phase 0.
