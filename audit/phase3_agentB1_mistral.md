# Phase 3 — Rapport Agent B1 (auditeur ADVERSARIAL, famille Mistral)

**Date** : 2026-10-12 · **Commit audité** : `b810f7d` (lecture seule — aucune modification du projet)
**Périmètre** : cœur métier hors stratégie-lourde — `src/alertes/`, `src/alerts.py`, `src/portfolio.py`, `src/portefeuille/`, `src/strategie/spec_veille.py`, `spec_fiche.py`, `spec_profiles.py`, `src/notify.py`, `src/ajustement.py`, `src/taxation.py` (+ `src/calibration/seuils_vente.py` lu comme dépendance directe de `portfolio.py` pour l'axe « justesse des seuils »), et les tests associés.
**Hors périmètre** (autre agent) : `strategie_leo.py`, `challenge_validateur.py`, `fondamentaux_historiques.py`, collecte/CLI/scripts (lus uniquement comme appelants, pour prouver l'impact en production).
**Référentiels** : `docs/IPS.md` (v1.2), `docs/INVARIANTS-METIER.md` (23 invariants A1-E3), `audit/phase2_exigences.md` (43 exigences, matrice AL-*/EX-*/SP-*).
**Contraintes respectées** : lecture seule, aucune exécution de la suite de tests, aucune écriture hors ce rapport.

---

## Synthèse — TOP 5

1. **B1-01 (P1)** — Une sortie fondamentale « VENDS TOUT » est envoyée **une seule fois**, l'état étant persisté **avant** l'envoi et le résultat de l'envoi **ignoré** : un échec Telegram (transitoire) fait perdre l'alerte définitivement, et la position est clôturée dans `data/portfolio.json` sans que LEO ne l'ait vue ni vendue.
2. **B1-02 (P2)** — Invariant **E1 violé en production** : les alertes Telegram « live » (sortie, moins-value, renforcements avec montant conseillé, fiches spé) formatent les francs avec une **virgule** de milliers (`39,000 F`) — le piège de lecture que le projet documente lui-même — parce que seul le chemin « info » utilise `format_fr.fcfa`.
3. **B1-03 (P2)** — Le **DRIP comptabilise le dividende brut** : l'IRVM 12 % (retenue à la source) n'est jamais déduit dans `record_dividend` → cash, actions rachetées, `dividends_earned` surévalués de ~13,6 % à chaque versement ; le portefeuille enregistré diverge du compte réel.
4. **B1-04 (P2)** — `load_portfolio` retourne `[]` **en silence** sur fichier illisible, et le cron quotidien sauvegarde sans condition : un `portfolio.json` corrompu (écriture non atomique) est **effacé** au passage suivant. Le projet sait pourtant faire mieux (`seuils_vente.charger` lève `SeuilsInvalides`).
5. **B1-07 (P2)** — Le **cooldown du moteur d'alertes est inefficace** : la clé d'état contient le prix du message, donc chaque nouveau cours crée une nouvelle clé → re-notification toutes les 300 s tant que la condition tient (pire avec la règle `change_pct`).

---

## Findings

### B1-01 — Sortie « VENDS TOUT » : envoi unique, état persisté avant l'envoi, aucune reprise sur échec
**Fichier** : `src/portfolio.py:491-509` · `src/main.py:512-541` · gravité **P1**

**Description.** La détection d'une sortie fondamentale marque la position `closed = True` dans `check_dividend_position`, puis `cmd_portf check` sauvegarde le portefeuille **avant** d'envoyer Telegram, ignore la valeur de retour de `notifier.send()`, et le lendemain la position clôturée est sautée (`if p.closed: continue`). Un envoi qui échoue (panne réseau, rate-limit Telegram, token expiré, Telegram non configuré) n'est **jamais** réémis : l'alerte de sortie — la plus grave que le système émet — est perdue définitivement. Or le cron quotidien (`cmd_daily`, étape « Déclencheurs de sortie ») envoie les alertes dans `logs/daily.log` redirigé, canal que LEO ne surveille pas : Telegram est le seul canal de delivery.

**Preuve citée.**
- `src/portfolio.py:491-497` : `pos.closed = True; pos.close_reason = "dividende suspendu"` (idem :492-497, 500-503, 506-509 pour PER > 40 et prix de sortie).
- `src/main.py:523` : `alerts = check_dividend_position(p, quote.last, fund.get("dps"), fund.get("per"))`.
- `src/main.py:527-531` : `if p.closed: events.extend(...)` — la sortie ignore le cooldown (conforme à AL-05), **mais** `save_portfolio(positions)` (ligne 532) précède l'envoi.
- `src/main.py:539-541` : `print(a.message); notifier.send(f"🏦 Noyau :\n{a.message}")` — retour ignoré.
- `src/main.py:517` : `if p.closed: continue` — aucune réévaluation ensuite.
- `scripts/daily_check.py:23-30` : stdout/stderr redirigés vers `logs/daily.log` → le `print` n'est pas un canal pour LEO.
- `src/notify.py:46-69` : `send()` retourne `envoye` (booléen) et l'inscrit au journal (`envoye: false`) — **mais rien dans le projet ne relit ce champ pour relancer**.

**Scénario.** Mardi 09:00, dividende de SNTS coupé de 60 % → alerte « 🔴 VENDS TOUT ». Coupure réseau de 30 s au moment de l'envoi : `requests.post` lève, `send()` retourne `False`, seule une ligne `log.error` et une entrée `envoye: false` au journal. `portfolio.json` contient déjà `closed: true`. Mercredi, idem : la position est sautée. LEO n'a jamais reçu l'alerte, n'a pas vendu, et le système ne le lui dira plus jamais — le titre reste pourtant dans son portefeuille réel, non surveillé (plus de soutenabilité, plus de cooldown, plus de rapport de performance sur cette ligne).

**Recommandation.** (1) Ne persister `closed` qu'après un envoi réussi (ou tracer `alerte_envoyee` et rémettre les sorties non confirmées au prochain run). (2) Relire le journal (`envoye: false` sur un message contenant « VENDS TOUT ») au démarrage du check quotidien et réémettre. (3) Poser `notifier.send(...)` avant `save_portfolio(...)`, ou rendre la clôture conditionnelle au retour d'envoi. (4) Ajouter un test : échec d'envoi → la position n'est pas marquée clôturée / l'alerte est réémise.

---

### B1-02 — Invariant E1 violé : séparateur de milliers à la virgule dans les alertes Telegram « live »
**Fichier** : `src/portfolio.py:293-294, 358-360, 509, 585-628` · `src/strategie/spec_fiche.py:152, 171-178, 190-195` · `src/alerts.py:96-100` · gravité **P2**

**Description.** L'invariant E1 (« Les montants sont au format français — espace, virgule décimale ») est **non tenu dans les messages effectivement envoyés**. La plupart des constructeurs d'alertes formattent les francs avec `:,.0f` (virgule de milliers : `39,000`), alors que `src/portefeuille/format_fr.py` existe précisément pour ce piège et n'est utilisé que par `_profit_info_alert` (le chemin « info », `portfolio.py:316`) et `_history_line`. Les chemins **live** — sortie fondamentale, moins-value, renforcements (avec le montant conseillé `~{max_qty*price:,.0f} F`), fiches spé, moteur d'alertes watchlist — envoient tous des virgules.

**Preuve citée.**
- `src/portfolio.py:509` : `f"... prix de sortie atteint ({current_price:,.0f} ≥ {pos.exit_price:,.0f})"` → « 39,546 ≥ 38,995 ».
- `src/portfolio.py:603-604` : `f"   (~{max_qty*price:,.0f} F), pour ne pas faire de ce titre plus de..."` — montant conseillé en virgule.
- `src/strategie/spec_fiche.py:152` : `f"Cours de référence : {f.price:,.0f} F "`; lignes 190-195 : `"   • Achat : entre {b['entry_lo']:,.0f} et {b['entry_hi']:,.0f} F — jamais plus cher"`.
- `src/alerts.py:96` : `f"Prix atteint {last:,.0f} FCFA (seuil haut {float(rules['max']):,.0f})"`.
- Garde-fou inefficace : `tests/test_format_fr.py` ne teste que la fonction `fcfa` (8 tests sur le helper), jamais le contenu des messages ; `docs/INVARIANTS-METIER.md` E1 cite `test_grand_montant` / `test_aucune_virgule_dans_les_francs` — qui valident `fcfa(699718) == "699 718 F"`, pas les alertes.
- Le projet documente lui-même le risque : `src/portefeuille/format_fr.py:10-12` — « un lecteur lit `3,784 F` comme trois francs [...] c'est un piège de lecture qui peut faire prendre une décision sur un chiffre mal compris ».

**Scénario.** Le cron quotidien envoie « 💪 RENFORCE LIMITÉ SNTS [...] au plus 2 action(s) (~78,000 F) ». LEO, néophyte, lit « 78,000 F » comme « soixante-dix-huit francs » (ou hésite) — le montant conseillé d'un ordre d'achat est exactly le chiffre à ne pas mal lire.

**Recommandation.** Remplacer tous les `:,.0f` des messages par `fcfa()` (import local comme en `portfolio.py:316`) dans `portfolio.py`, `spec_fiche.py`, `alerts.py` ; ajouter un test qui scanne les messages construits (ou une fonction de formatage unique) — le test E1 actuel ne protège que le helper, pas son usage.

---

### B1-03 — DRIP : le dividende brut est comptabilisé, l'IRVM 12 % n'est jamais déduit
**Fichier** : `src/portfolio.py:546-559` (`record_dividend`) · gravité **P2**

**Description.** `pos.dps` est le dividende **brut** (table IPS §3.3 « DPS brut » ; `yield_pct` est brut, `net_yield_pct` applique l'IRVM). `record_dividend` calcule `cash = pos.dps * pos.quantity` — le montant **brut** — puis achète `int(cash // price)` actions et crédite `dividends_earned` du brut. Or l'IRVM de 12 % est une **retenue à la source** (IPS §7, `taxation.py:52`) : le cash réellement crédité est `dps × 0,88 × quantité`. Le mécanisme DRIP — l'objectif central de la stratégie (IPS §1 « Revenu dividende réinvesti (DRIP) ») — surévalue le cash réinvesti de 13,6 % à chaque versement, donc le nombre d'actions achetées, donc `dividends_earned`, `cash_residual`, et la base de tous les calculs futurs. Le portefeuille enregistré diverge du compte-titres réel, par composition.

**Preuve citée.**
- `src/portfolio.py:553` : `cash = pos.dps * pos.quantity` (aucun `* (1 - IRVM_DIVIDEND_TAX)`).
- `src/portfolio.py:554-558` : `new_shares = int(cash // price) if price > 0 else 0; pos.quantity += new_shares; pos.dividends_earned += cash`.
- `src/portfolio.py:195` : `_dividend_annual_net` applique, lui, `(1 - IRVM_DIVIDEND_TAX)` — la retenue est connue du module, juste pas appliquée ici.
- `src/main.py:561` : `print(f"✓ Dividende versé : {cash:,.0f} FCFA ...")` — présente le brut comme « versé ».
- Ancrage du défaut : `tests/test_portfolio.py:494-520` assert `cash == 5220.0` (1740 × 3, brut) ; `tests/fixtures/sorties_reference.json:1263-1303` (`record_dividend|*`) idem.

**Scénario.** SNTS, 3 actions, dps 1 740 F brut. Le vrai encaissement est 4 594 F (IRVM 12 % retenu) ; le système enregistre 5 220 F, calcule un achat d'actions sur 5 220 F et crédite 5 220 F de « dividendes encaissés ». Au fil des exercices, la quantité enregistrée (base des dividendes futurs, du poids de la ligne, des alertes) dépasse la quantité réelle d'environ 13,6 % par an composé.

**Recommandation.** `cash = pos.dps * (1 - IRVM_DIVIDEND_TAX) * pos.quantity` ; distinguer « dividende brut » et « cash net reçu » dans le message CLI ; mettre à jour les tests et fixtures en conséquence. Vérifier au passage si `pos.dps` devrait être le dps **payé** (avis réel) plutôt que le dps de l'ouverture (voir B1-05).


---

### B1-04 — `load_portfolio` : valeur par défaut dangereuse — un fichier illisible devient un portefeuille vide, puis est écrasé
**Fichier** : `src/portfolio.py:563-577` · `src/main.py:512-532, 463-476` · gravité **P2**

**Description.** `load_portfolio()` retourne `[]` **en silence** sur `OSError`, `JSONDecodeError` **et `TypeError`** (ligne 568). Or `DividendPosition(**d)` lève `TypeError` sur toute dérive de schéma (clé inconnue, type inattendu), et `save_portfolio()` réécrit le fichier intégralement. Conséquence : un `data/portfolio.json` corrompu (écriture non atomique — `write_text` direct, crash, disque plein) ou simplement incompatible avec une évolution du dataclass est lu comme « portefeuille vide », puis **écrasé** par le prochain `save_portfolio`. Pire : le cron quotidien (`cmd_portf check`) sauvegarde **sans condition** (même avec zéro position chargée), donc le check de 09:00 est le vecteur d'effacement. Le projet sait pourtant faire autrement : `seuils_vente.charger()` refuse un fichier illisible (`SeuilsInvalides`, « on refuse de détruire ce qu'on ne sait pas relire », `src/calibration/seuils_vente.py:214-222`) — le même garde n'existe pas pour le portefeuille, qui est pourtant la source de vérité des décisions.

**Preuve citée.**
- `src/portfolio.py:566-569` : `try: return [DividendPosition(**d) for d in json.loads(...)] except (OSError, json.JSONDecodeError, TypeError): return []` — aucune distinction « absent » / « illisible », aucun log.
- `src/portfolio.py:572-577` : `save_portfolio` → `PORTFOLIO_FILE.write_text(json.dumps([asdict(p) ...]))` — réécriture intégrale, non atomique.
- `src/main.py:512-532` : `positions = load_portfolio()` … `save_portfolio(positions)` — inconditionnel, dans le cron quotidien (`cmd_daily`, étape « Déclencheurs de sortie », `src/main.py:1253`).
- `src/main.py:463-476` (`portf open`) : `positions = load_portfolio()` → `append` → `save_portfolio` — une dérive de schéma efface toutes les positions existantes et n'enregistre que la nouvelle.

**Scénario.** Un crash pendant l'écriture de `portfolio.json` (ou un champ renommé dans `DividendPosition` lors d'une prochaine évolution) laisse un fichier tronqué. Au prochain `portf open` ou au check quotidien de 09:00, `load_portfolio()` retourne `[]` sans un mot, `save_portfolio([])` remplace le fichier : **tout l'historique de positions est perdu**, et le système cesse de surveiller des titres que LEO détient réellement.

**Recommandation.** Distinguer « fichier absent » (`[]` légitime) et « fichier illisible » (lever, ou conserver + alerter, comme `lire_et_valider`) ; écrire de façon atomique (fichier temporaire + `os.replace`) ; ne jamais sauvegarder une liste vide issue d'une erreur de lecture ; ajouter un test : fichier corrompu → exception (ou quarantaine), pas `[]`.

---

### B1-05 — Le dps n'est jamais rafraîchi : rendement net affiché et prix de sortie calculés sur le dividende de l'ouverture
**Fichier** : `src/portfolio.py:158-169, 489-509` · `src/main.py:523` · gravité **P2**

**Description.** `pos.dps` est fixé à l'ouverture (`portfolio.py:845`) et **aucun chemin de code ne le met à jour**. Pourtant le check quotidien reçoit le dps courant (`current_dps`, `main.py:523`) — mais `check_dividend_position` ne l'utilise que pour détecter une coupe > 50 % (lignes 489-497). Le « Rendement net actuel » de l'alerte (`pos.net_yield_pct`, ligne 169), le dividende annuel net (`_dividend_annual_net`, ligne 195) et surtout le **prix de sortie** (`pos.exit_price`, calculé une fois dans `__post_init__`, testé ligne 506) restent fondés sur le dps de l'ouverture. Or l'IPS §3.2 définit le prix de sortie comme « rendement net tombé à 2 % » — un rendement qui se mesure sur le **dividende courant**. Après une hausse de dividende, `exit_price` est trop bas → « VENDS TOUT — prix de sortie atteint » se déclenche alors que le rendement net réel est encore supérieur à 2 % (vente prématurée, contraire à l'IPS). Après une coupe < 50 %, `exit_price` est trop haut → sortie tardive. Dans les deux cas, le « Rendement net actuel : X % » affiché à LEO est faux. `record_dividend` réinvestit également sur le dps de l'ouverture, pas sur le montant réellement payé.

**Preuve citée.**
- `src/portfolio.py:158-162` : `if self.dps > 0: if self.exit_price <= 0: self.exit_price = round(self.dps / DIV_YIELD_EXIT, 2)` — calculé une fois, sur le dps d'ouverture.
- `src/portfolio.py:506` : `if not pos.closed and pos.exit_price > 0 and current_price >= pos.exit_price:` — test sur la valeur périmée.
- `src/portfolio.py:489-497` : `current_dps` n'est utilisé que pour `current_dps <= 0` et `current_dps < pos.dps * DIV_CUT_RATIO`.
- `src/main.py:523` : `check_dividend_position(p, quote.last, fund.get("dps"), fund.get("per"))` — la donnée fraîche est disponible et ignorée pour le rendement/la sortie.
- Aucun `pos.dps = ...` hors constructeur (grep : seule affectation `dps=dps`, `portfolio.py:845`).

**Scénario.** LEO ouvre SNTS avec dps 1 977 F → `exit_price` = 62 073 F. L'exercice suivant, Sonatel relève le dividende à 2 300 F : le rendement net réel au cours de 55 000 F est ~3,3 %, encore au-dessus du plancher de 2 %, mais le prix de sortie enregistré reste 62 073 F — atteint **avant** que le rendement réel ne tombe à 2 % → alerte « VENDS TOUT » prématurée. À l'inverse, après une coupe de 30 % (sous le seuil de coupe de 50 %), `exit_price` trop haut → la sortie « rendement à 2 % » arrive en retard, alors que le rendement réel est déjà sous 2 % depuis des semaines.

**Recommandation.** Recalculer le prix de sortie sur le dps courant quand il est fourni (`exit_price_courant = current_dps / DIV_YIELD_EXIT`) ; afficher le rendement net sur le dps courant ; documenter la règle « prix de sortie = f(dps courant) » dans l'IPS §3.2 si c'est le choix retenu (sinon, mettre à jour l'IPS).

---

### B1-06 — Fiche spé : fiscalité recopiée en dur (`0,88`, `0,8`), invisible au test gardien C4
**Fichier** : `src/strategie/spec_fiche.py:170` · `tests/test_regles_centralisees.py:76-86` · gravité **P2**

**Description.** La ligne « dividende net » de la fiche spéculative calcule `net = b["dps"] * 0.88 / f.price * 100 - 0.8` — `0,88` est `1 − IRVM` et `0,8` la conservation annuelle en %, **recopiés en dur** au lieu d'importés de `taxation`. C'est exactement ce que l'invariant C4 interdit (« le test refuse même une copie avec la bonne valeur »). Le test gardien `test_aucune_regle_redefinie_ailleurs` a **deux angles morts** qui rendent cette copie invisible : (1) il ne balaie que `SRC.glob("*.py")` — les **sous-dossiers** (`src/strategie/`, `src/calibration/`, `src/alertes/`, `src/portefeuille/`) ne sont pas scannés ; (2) il ne détecte que les `ast.Assign` nommés, pas les **littéraux dans les expressions**. Si l'IRVM change (l'historique 10 % → 15 % → 12 % montre que ce taux vit), le « ≈ X % net » de la fiche est faux tandis que tout le reste du projet s'actualise.

**Preuve citée.**
- `src/strategie/spec_fiche.py:170` : `net = b["dps"] * 0.88 / f.price * 100 - 0.8 if f.price else 0`.
- `src/taxation.py:52,61` : `IRVM_DIVIDEND_TAX = 0.12` ; `net_yield(g) = g * (1 - IRVM_DIVIDEND_TAX) - CUSTODY_ANNUAL` — la source existe.
- `tests/test_regles_centralisees.py:79` : `for f in sorted(SRC.glob("*.py")):` — top-level uniquement. Lignes 60-64 : `if not isinstance(noeud, ast.Assign)` — les littéraux en expression sont ignorés.

**Scénario.** Décret 2027 : IRVM passe à 10 %. `taxation.py` et `regles.py` sont mis à jour ; la fiche spé continue d'afficher un rendement net calculé avec 12 % — une erreur d'environ 2,3 points sur le « ≈ X % net » présenté à LEO dans une alerte Telegram.

**Recommandation.** Utiliser `net_yield(dps / price) * 100` (import `taxation`) ; faire scanner le test C4 récursivement (`rglob`) et/ou ajouter un test « aucun littéral 0,88 / 0,008 / 0,12 hors `taxation.py`/`regles.py` ».

---

### B1-07 — Moteur d'alertes (watchlist) : le cooldown est inefficace, la clé d'état contient le prix
**Fichier** : `src/alerts.py:81-87, 95-100, 128-131` · gravité **P2**

**Description.** L'anti-spam de `AlertEngine` mémorise `state[key] = now` avec `key = f"{code}:{cond}"` — et `cond` **contient le prix courant** (`f"Prix atteint {last:,.0f} FCFA..."`) ou la variation (`f"Variation {var:+.2f}%..."`). À chaque nouveau cours, la clé change → le cooldown de 30 min ne s'applique **jamais** : tant qu'un titre reste au-dessus de son seuil `max`, LEO reçoit un Telegram **toutes les 300 s** (boucle documentée `alert --loop --interval 300`, README ligne 29). Avec la règle `change_pct`, `var` change à chaque tick → notification à **chaque cycle**, cooldown ou non. Trois défauts liés : (1) cooldown inefficace ; (2) `data/alerts_state.json` croît sans borne (une clé par prix distinct, jamais purgée) ; (3) `run_loop` ignore le retour de `notifier.send()` — un envoi échoué est perdu jusqu'à la prochaine clé (même schéma que B1-01). Accessoire : `rules.get("max")` / `rules.get("min")` testés par truthiness (lignes 95-99) — un seuil de `0` est silencieusement ignoré.

**Preuve citée.**
- `src/alerts.py:81-86` : `for cond in self._check_rules(quote, rules): key = f"{code}:{cond}"; if self.state.get(key, 0) > now - self.cooldown: continue; self.state[key] = now`.
- `src/alerts.py:96-100` : `out.append(f"Prix atteint {last:,.0f} FCFA (seuil haut {float(rules['max']):,.0f})")` — le prix est dans la clé.
- `src/alerts.py:99` : `out.append(f"Variation {var:+.2f}% (seuil ±{float(rules['change_pct']):.0f}%)")` — la variation à 2 décimales change à chaque tick.
- `src/alerts.py:128-131` : `messages = engine.check_once(); for msg in messages: ... notifier.send(msg)` — retour ignoré ; `check_once` sauvegarde l'état (`self._save_state()`, ligne 87) avant tout envoi.
- `config.yaml:19-23` : `interval_seconds: 300`, `cooldown_minutes: 30` — le cooldown est bien invoqué, mais vidé de son effet.

**Scénario.** LEO surveille SIVC `--max 2600`. Le titre passe à 2 610 F à 10:00 et cote 2 610-2 640 F toute la matinée : LEO reçoit ~7 messages Telegram (« Prix atteint 2 610 FCFA », « 2 615 », « 2 622 »…) en 35 minutes, là où le cooldown de 30 min devait le rendre muet. Le fichier d'état grossit d'autant.

**Recommandation.** Clé de cooldown = `f"{code}:{type}:{seuil}"` (sans le prix), pas `f"{code}:{cond}"` ; purger les entrées plus vieilles que le cooldown à chaque sauvegarde ; relancer l'envoi sur échec (file de retry) ; tester `rules["max"] = 0`.

---

### B1-08 — Deux « prix d'entrée net 4 % » divergent d'environ 1,4 % ; l'alerte de renforcement contredit l'IPS
**Fichier** : `src/portfolio.py:162, 679` · `src/taxation.py:69-78` · `docs/IPS.md §3.2-3.3` · gravité **P3**

**Description.** Le projet porte **deux formules** du « prix d'entrée garantissant 4 % net » : (a) `DividendPosition.entry_price_ref = dps / DIV_YIELD_ENTRY` (`portfolio.py:162`) — la formule de l'IPS §3.2 (`dps × (1 − 12 %) / (4 % + 0,80 %)`), ancrée par `tests/test_portfolio.py:35` à 31 900 F pour dps 1 740 ; (b) `taxation.entry_price_for_net(dps)` (`taxation.py:78`), qui divise **en plus** par `(1 + BROKERAGE_FEE)` ≈ 1,014 — soit ~1,4 % plus bas — et qui est celle utilisée par l'alerte quotidienne de renforcement : `portfolio.py:679` `entry_ref = entry_price_for_net(p.dps)`, affiché comme « sous ton seuil de X F » (`_msg_renfort_*`, lignes 585-628). Pour SNTS (dps 1 977) : l'IPS §3.3 publie **36 245 F**, `entry_price_ref` vaut 36 245 F, mais l'alerte dit **35 745 F**. La divergence n'est documentée ni dans l'IPS ni dans une décision datée ; la hiérarchie des sources (décision du 12/10) ne peut pas trancher, les deux valeurs vivant dans le code. La version « frais inclus » est arguably plus juste économiquement, mais elle contredit la référence publiée et le champ du même nom dans le dataclass.

**Preuve citée.**
- `src/taxation.py:76-78` : `return dps / gross_yield_for_net(target_net) / (1 + BROKERAGE_FEE)` (commentaire : « le prix de marché doit être plus bas pour que le rendement net sur COÛT (CMP, frais inclus) atteigne la cible »).
- `src/portfolio.py:679` : `entry_ref = entry_price_for_net(p.dps)` ; `src/portfolio.py:587-588` : `f"💪 RENFORCE {p.code} ... sous ton seuil de {entry_ref:,.0f} F."`
- `src/portfolio.py:161-162` : `self.entry_price_ref = round(self.dps / DIV_YIELD_ENTRY, 2)` — l'autre formule, sans les frais.
- `docs/IPS.md:86` (table) : SNTS « Entrée (4 % net) **10 450** / 36 245 » — la valeur de l'IPS. Vérification numérique : 1977 × 0,88 / 0,048 = 36 245,0 ; `entry_price_for_net(1977)` = 35 744,58.
- `tests/test_portfolio.py:35, 490` : `assert abs(p.entry_price_ref - 31900.0) < 0.01` — seul le variant « sans frais » est testé contre l'IPS.

**Scénario.** Le renforcement est un ordre limite « achète si le prix revient à X F ». LEO compare X à la table de l'IPS (36 245) ou au `portf open` (qui affiche `entry_price_ref` = 36 245, `main.py:480`) : l'alerte Telegram dit 35 745. 500 F d'écart sur un seuil de décision, sans aucune note disant lequel est la référence.

**Recommandation.** Choisir une formule, la documenter (IPS §3.2 ou décision datée), et n'en garder qu'une en code — ou afficher les deux avec leurs libellés (« seuil IPS » / « seuil frais inclus »).

---

### B1-09 — Veille spé : « 2 stop-outs consécutifs » (documenté) vs comptage cumulatif (implémenté) ; date extraite d'une chaîne de caractères
**Fichier** : `src/strategie/spec_veille.py:22-24, 73-86` · gravité **P3**

**Description.** Le commentaire et la constante disent « 2 stop-outs **consécutifs** = suspension 60 j » (`STOPOUT_SUSPEND_DAYS = 60 # 2 stop-outs consécutifs = suspension 60 j`, ligne 23 ; « 2 stop-outs consécutifs = suspension longue », ligne 84). Mais le code compte **tous les stop-outs de l'historique** du titre (`stop_counts[code] = stop_counts.get(code, 0) + 1` pour chaque position clôturée portant « stop » dans la raison) — aucune notion de conséquence. Un titre stoppé deux fois à deux ans d'intervalle (avec des gains entre les deux) est suspendu 60 jours au lieu de 30. Par ailleurs, la date du dernier stop est extraite de la **chaîne** `close_reason` par `split(" ")[-1][:10]` (ligne 78) : si le format de la raison change (ou ne se termine pas par une date), le `except` bascule sur `opened_at` — la date d'**ouverture**, qui peut fausser le cooldown dans les deux sens.

**Preuve citée.**
- `src/strategie/spec_veille.py:23` : `STOPOUT_SUSPEND_DAYS = 60   # 2 stop-outs consécutifs = suspension 60 j`.
- `src/strategie/spec_veille.py:73-76` : `for p in spec_pos: if p.closed and "stop" in (p.close_reason or "").lower(): stop_counts[code] = stop_counts.get(code, 0) + 1` — cumul, pas de séquence.
- `src/strategie/spec_veille.py:77-80` : `d = date.fromisoformat((p.close_reason or "").split(" ")[-1][:10])` … `except Exception: d = date.fromisoformat(p.opened_at[:10])`.

**Scénario.** BICB est stoppé en janvier 2025 (−15 %), repris, stoppé une seconde fois en septembre 2026 : `stop_counts` = 2 → suspension 60 j, alors que la règle écrite prévoit 60 j pour deux stop-outs **à la suite** (le même faux breakout répété). La fiche est muette 2 mois pour un titre qui n'a commis aucune faute récente.

**Recommandation.** Compter les stop-outs consécutifs (réinitialiser le compteur sur une clôture non liée à un stop) ; stocker la date de clôture dans un champ structuré (`closed_at`) au lieu de la parser dans `close_reason`.

---

### B1-10 — Profils spé : fallback silencieux sur des statistiques figées ; confirmation volume contournée par des volumes nuls
**Fichier** : `src/strategie/spec_profiles.py:117-138, 72-86` · gravité **P3**

**Description.** Deux valeurs par défaut dangereuses. (1) `load_profiles()` : si `data/spec_profiles.json` est absent ou illisible, elle retourne **en silence** les statistiques figées des épreuves du 16-17/09 (`except Exception: pass` → fallback) — la fiche affiche alors « FRÉQUENCES HISTORIQUES (10 ans…) » avec les valeurs de septembre 2026, sans aucune mention qu'elles sont un fallback périmé. (2) `detect_schemas()` : la confirmation volume exige `volumes[i] >= med` — **mais** `vol_ok = med <= 0 or volumes[i] >= med` : si la médiane des 60 séances est nulle (titre illiquide, trou de données, volume à 0), la confirmation est **accordée d'office**, exactement le « faux breakout » que la règle du 25/09 devait bloquer.

**Preuve citée.**
- `src/strategie/spec_profiles.py:119-123` : `if PROFILES_FILE.exists(): try: return json.loads(...) except Exception: pass` puis `return {"CASSURE": {"n": 10, "win_12m": 0.70, ...}}` — fallback muet.
- `src/strategie/spec_fiche.py:156-160` : le message affiche `f"{b['win_12m']*100:.0f} % de {b['n']} cas OBSERVÉS..."` — aucune distinction « calibré » / « figé ».
- `src/strategie/spec_profiles.py:73-74` : `med = statistics.median(volumes[-61:-1]); vol_ok = med <= 0 or volumes[i] >= med` (idem ligne 84-85 pour EVEIL) — le contournement par `med <= 0`.

**Scénario.** Le fichier `spec_profiles.json` est supprimé (ou corrompu) lors d'un nettoyage de `data/` : le lendemain, les fiches spé affichent « 70 % de réussite sur 10 cas » — chiffres de 2026-09 — comme s'ils étaient le calibrage courant. Un titre sans volume (med = 0) déclenche une « CASSURE confirmée » sur un simple print, sans aucune demande réelle.

**Recommandation.** Logger un avertissement au chargement du fallback et l'afficher dans la fiche (« statistiques de secours, non recalibrées ») ; pour le volume, exigeant `med > 0` **et** `volumes[i] >= med` (un titre sans volume ne confirme pas).

---

### B1-11 — Fiche spé : le « stop −15 % » est calculé sur le bas de la fourchette, pas sur le prix d'achat réel
**Fichier** : `src/strategie/spec_fiche.py:100-106, 190-195` · `docs/IPS.md §4.2` · gravité **P3**

**Description.** Le filet annoncé est « Stop −15 % », mais il est calculé `stop = entry_lo * 0.85` — c'est-à-dire −15 % par rapport au **bas de la fourchette d'achat**, pas par rapport au prix auquel LEO achète. Pour une CASSURE, la fourchette est `[plafond, plafond × 1,05]` : un achat au haut de la fourchette place le stop à −19 % du prix payé. Pour EVEIL/PANIQUE, `entry_lo = prix × 0,985` → stop = prix × 0,837, soit −16,3 % du cours de référence — alors que le message dit « Stop −15 % : X F → tu vends tout, sans discuter ». L'IPS §4.2 (« Stop-loss initial : −15 % ») est présenté comme mécanique « non négociable » : le pourcentage annoncé ne correspond pas au risque réel si l'achat n'est pas exactement au bas de la fourchette.

**Preuve citée.**
- `src/strategie/spec_fiche.py:100-106` : `if main == "CASSURE": plafond = max(closes[-251:-1]); entry_lo, entry_hi = plafond, plafond * 1.05` … `stop = entry_lo * 0.85`.
- `src/strategie/spec_fiche.py:191` : `f"   • Stop −15 % : {b['stop']:,.0f} F → tu vends tout, sans discuter\n"`.
- `docs/IPS.md:176` : « **Stop-loss initial : −15 %**. »

**Scénario.** Cassure sur BICB à 5 720 F (plafond), fiche envoyée : « Achat entre 5 720 et 6 006 F — Stop −15 % : 4 862 F ». LEO achète à 5 990 F (dans la fourchette, « jamais plus cher » respecté) : son stop réel est à −18,8 %, pas −15 %. S'il ancre son risque sur « −15 % », il sous-estime la perte maximale d'environ 4 points.

**Recommandation.** Calculer le stop sur le prix d'achat effectif (ou afficher « stop à −15 % du prix payé, soit X F à ajuster selon ton prix d'entrée ») ; aligner le libellé sur l'IPS.

---

### B1-12 — Duplications en dur autour des seuils : `PROFIT_DOWN_PROB` figé, `PROFIT_ALERT_THRESHOLD` importé mais mort, défaut `0.13` recopié
**Fichier** : `src/portfolio.py:34, 69, 280-282` · `src/calibration/seuils_vente.py:263-268` · `src/regles.py:86` · gravité **P3**

**Description.** Trois duplications autour du même objet (le seuil de vente), toutes invisibles au test C4 (qui ne balaie que `src/*.py` et les assignments nommés). (1) `PROFIT_DOWN_PROB = {"SNTS": 86, "SGBC": 63, "SLBC": 54, "PALC": 45}` (`portfolio.py:69`) recopie les `down_prob` de `data/profit_thresholds.json` (86/63/54/46 — **PALC y vaut 46, pas 45** : la copie diverge déjà) et sert de fallback muet dans `_double_option_alert` (lignes 280-282) si le fichier calibré est perdu. (2) `PROFIT_ALERT_THRESHOLD` est importé en tête de `portfolio.py` (ligne 34) **et jamais utilisé** — la valeur cataloguée (`regles.py:86`, « défaut pour un titre sans historique suffisant ») est morte. (3) Le défaut réellement appliqué vit dans `seuils_vente.pour(code, defaut=0.13)` (ligne 263) — un **littéral** qui duplique `regles.PROFIT_ALERT_THRESHOLD` sans le nommer ; le test `test_aucune_regle_redefinie_ailleurs` ne le voit pas (sous-dossier + argument par défaut, pas un `Assign`).

**Preuve citée.**
- `src/portfolio.py:69` : `PROFIT_DOWN_PROB = {"SNTS": 86, "SGBC": 63, "SLBC": 54, "PALC": 45}  # affichage`.
- `data/profit_thresholds.json` (PALC) : `"down_prob": 46` — divergence de 1 point déjà actée entre la copie et la source.
- `src/portfolio.py:280-282` : `prob = load_profit_thresholds().get(pos.code, {}).get("down_prob"); if prob is None: prob = PROFIT_DOWN_PROB.get(pos.code)`.
- `src/portfolio.py:34` : import de `PROFIT_ALERT_THRESHOLD` ; grep : aucune autre occurrence dans `portfolio.py` (hors commentaire ligne 70).
- `src/calibration/seuils_vente.py:263` : `def pour(code: str, defaut: float = 0.13) -> float:` ; `src/regles.py:86` : `PROFIT_ALERT_THRESHOLD = 0.13`.

**Scénario.** Le fichier `profit_thresholds.json` est perdu : `_double_option_alert` affiche « l'historique ne montre une baisse que dans 45 % des cas » pour PALC, alors que la mesure calibrée dit 46 %. Si LEO remonte un jour le défaut à 0,15 dans `regles.py`, `pour()` continue de rendre 0,13 — deux réponses à « quel est le seuil par défaut », le défaut historique de l'audit du 08/10 (C5).

**Recommandation.** Supprimer `PROFIT_DOWN_PROB` (ou le dériver du fichier chargé) ; utiliser `regles.PROFIT_ALERT_THRESHOLD` comme défaut de `pour()` ; étendre le test C4 aux sous-dossiers.

---

### B1-13 — Veille spé : l'anti-spam est consommé avant la livraison — une fiche OUI peut être muette 7 jours sans jamais avoir été envoyée
**Fichier** : `src/strategie/spec_veille.py:116-127` · `src/main.py:1124-1151` · gravité **P3**

**Description.** `scan()` marque `state[key] = today` pour **chaque fiche générée** (ligne 125), y compris les fiches « NON » (documenté) — mais la livraison Telegram est en aval et partielle : `cmd_specveille` n'envoie que les verdicts OUI/PRUDENCE, **plafonnés à 3 fiches par jour** (`keep = keep[:3]`, `main.py:1129`), et seulement si `notifier.enabled`. Une fiche OUI générée un jour où 3 autres fiches ont pris les slots (ou Telegram non configuré) est marquée « vue » → **muette 7 jours** → LEO ne la verra jamais, et aucun log ne le signale (le plafond anti-flood « avale » la fiche en silence). L'anti-spam devrait être consommé à l'envoi, pas à la génération.

**Preuve citée.**
- `src/strategie/spec_veille.py:125-126` : `state[key] = today; out.append((f, f.message()))` — état écrit avant toute livraison.
- `src/main.py:1124-1129` : `# Plafond anti-flood : max 3 fiches par jour` … `keep = keep[:3]`.
- `src/main.py:1147-1150` : `for f in keep: if notifier.enabled: notifier.send(...)` — les fiches hors `keep` ne sont jamais envoyées.
- `src/main.py:1151` : `print(f"[specveille] {len(res)} fiche(s) générée(s) · {n_sent} envoyée(s)...")` — le compteur est imprimé dans le log du cron, pas remonté à LEO.

**Scénario.** Quatre fiches OUI un même matin (marée haussière). Trois partent sur Telegram. La quatrième — disons une CASSURE, le schéma « rare » — est marquée vue et disparaît ; le lendemain, `SPAM_DAYS = 7` la rend muette. LEO n'a jamais vu la fiche, et le heartbeat ne mentionne que le nombre de fiches générées.

**Recommandation.** Ne marquer l'état anti-spam que pour les fiches effectivement envoyées (déplacer la mise à jour d'état côté livraison), ou logger « générée mais non envoyée (plafond) » dans le heartbeat ; exempter le schéma CASSURE du plafond de 3.

---

### B1-14 — Après une sortie auto, aucun moyen d'enregistrer le prix de vente réel : `close_price` reste un cours de détection
**Fichier** : `src/portfolio.py:541-542` · `src/main.py:569-585, 440-451` · gravité **P3**

**Description.** Quand une sortie fondamentale est détectée, `check_dividend_position` marque la position clôturée, et `portfolio.py:541-542` renseigne `pos.close_price = current_price` — le **cours de détection**, pas un prix de vente (LEO exécute manuellement, peut-être des jours plus tard, à un autre cours). Or `cmd_portf close` ne s'applique qu'aux positions **ouvertes** (`if p.code == code and not p.closed`, `main.py:575`) : après une sortie auto, la commande répond « aucune position ouverte » — **il n'existe aucun moyen d'enregistrer le prix de vente réel**. Le `close_price` « hypothétique » sert ensuite aux calculs de performance (rapports) : la performance d'une ligne sortie est chiffrée sur une transaction qui n'a jamais eu lieu à ce prix.

**Preuve citée.**
- `src/portfolio.py:541-542` : `if pos.closed and not pos.close_price: pos.close_price = current_price` — prix de détection, pas de vente.
- `src/main.py:574-585` : `for p in positions: if p.code == code and not p.closed: ...` — une position auto-clôturée est invisible pour `portf close`.
- `src/main.py:440-448` (clôture manuelle de la poche spé, même pattern) : `p.close_price = quote.last if quote else p.entry_price` — le CLI *peut* enregistrer un prix de clôture manuel, mais pas pour une position déjà `closed` par le check.

**Scénario.** SNTS déclenche « prix de sortie atteint » à 62 100 F (enregistré comme `close_price`). LEO vend une semaine plus tard à 60 800 F. Le rapport de performance de la ligne SNTS affiche le rendement calculé sur 62 100 F — un prix auquel aucune vente n'a été exécutée — et l'écart est invisible.

**Recommandation.** Ajouter une commande `portf sold CODE --price X` (ou autoriser `portf close` sur les positions auto-clôturées) pour enregistrer le prix réel ; distinguer dans le modèle `close_price_detecte` / `close_price_reel`.

---

### B1-15 — Alerte info : « Tu gagnerais X en vendant maintenant » affiche un gain brut, contraire au principe NET de l'IPS
**Fichier** : `src/portfolio.py:319-332` (`_profit_info_alert`) · `docs/IPS.md §1` · gravité **P3**

**Description.** Le chemin d'alerte **actuellement live** pour les plus-values (les 4 seuils étant `informatif`, c'est `_profit_info_alert` qui produit le message Telegram, `portfolio.py:527`) affiche « Tu gagnerais {fcfa(gain_fcfa)} en vendant maintenant » avec `gain_fcfa = (price − entry_price) × quantity` — un gain **brut** : ni les ~1,4 % de frais de vente, ni le courtage d'achat déjà payé (l'entrée réelle est `entry_price + commission`) ne sont déduits. Le chemin jumeau `_double_option_alert` (ligne 294) affiche « bénéfice net ≈ … (après frais ~1,4 %) » — la norme. L'IPS §1 pose le principe : « le rendement se mesure en NET (après impôt + frais) ». « Tu gagnerais » est en outre une formulation de gain certain, pour un chiffre qui ne l'est pas (exécution à ce prix non garantie).

**Preuve citée.**
- `src/portfolio.py:320` : `gain_fcfa = (price - pos.entry_price) * pos.quantity`.
- `src/portfolio.py:332` : `f"   Tu gagnerais {fcfa(gain_fcfa)} en vendant maintenant.\n"`.
- `src/portfolio.py:294` (chemin jumeau) : `f"      bénéfice net ≈ {profit_net:,.0f} F (après frais ~1,4 %)\n"` — le net existe, via `_sell_profit_net` (lignes 185-190).
- `docs/IPS.md:27-28` : « **Principe fondamental :** le rendement se mesure en **NET** (après impôt + frais). »

**Scénario.** SNTS +13 % : « Tu gagnerais 39 000 F en vendant maintenant. » Le gain net après frais de vente est ~38 500 F ; après prise en compte du courtage d'achat, un peu moins. LEO ancre « 39 000 F » — le chiffre le plus visible de l'alerte — alors que le projet lui-même interdit de présenter un brut comme un net.

**Recommandation.** Réutiliser `_sell_profit_net(pos, price, 1.0)` pour ce chiffre et libeller « gain net après frais » ; ou « tu vendrais pour ≈ X F » (prix brut de la vente) en complément.

---

## Vérifié et sain

- **`src/taxation.py`** — conforme à l'IPS §7 : courtage 0,80 % (min 1 000 F) + TVA 18 % + BRVM 0,456 % = `BROKERAGE_FEE` ≈ 1,40 % (vérifié : 0,008 × 1,18 + 0,00456 = 0,0140) ; conservation 0,20 %/trim (min 2 500 F) ; IRVM 12 % unique (`test_coherence_fiscale`) ; `net_yield = brut × 0,88 − 0,80 %` conforme à l'IPS ; `gross_yield_for_net(0,04)` = 5,4545 % conforme au « brut ≥ 5,45 % » de l'IPS §3.1. Invariants A1-A4 tenus.
- **`src/notify.py`** — point de passage unique, journal de l'envoi **après** tentative avec `envoye` vrai/faux, empreinte complète, `enregistrer` ne lève jamais (ceinture et bretelles côté appelant). `_origine()` par `sys._getframe(2)` correcte (caller de `send`). Le journal des alertes (`src/alertes/journal_alertes.py`) est append-only, tolérant aux lignes corrompues, testé (12 tests) — conforme à D4.
- **`src/calibration/seuils_vente.py`** — la significativité (Wilson, `EPISODES_MIN = 8`, `BORNE_BASSE_MIN = 0,50`) est conforme à B1/B2 ; `charger()` refuse un fichier illisible (le bon pattern, cf. B1-04) ; `enregistrer()` valide + protège les décisions explicites (B3) + écriture atomique ; journal append-only des changements (D4). Les 4 seuils en vigueur (`data/profit_thresholds.json`) sont bien `informatif`, cohérents avec la décision du 08/10 et l'IPS révisée du 12/10 (CONFLIT-03 résolu côté code).
- **`src/portfolio.py` — sorties fondamentales** — les trois règles (dividende suspendu/coupé > 50 %, PER > 40, prix de sortie) sont câblées comme l'IPS §3.4, une baisse de cours seule ne déclenche rien (`test_price_drop_does_not_trigger`), la soutenabilité (payout > 80 % / > 100 %) est un niveau 3 informatif (C2), les renforcements informent sans bloquer (C1/C2), le régime de marché est un contexte (C3, `try/except` autour de `regime_du_jour`). Le message info est honnête (taux affiché seulement si `significatif`, repère « pile ou face », « RIEN À FAIRE » explicite) — E2/E3 tenus sur ce chemin.
- **`src/alertes/journal_alertes.py`** — robuste : n-raise jamais, une ligne illisible n'invalide pas le journal, l'origine tracée, le rappel d'empreinte optionnel et désactivé par défaut (le message reste inchangé).
- **`src/ajustement.py`** — module d'audit correctement déclassé : docstring explicite (« ne doit JAMAIS servir à ajuster l'historique »), seul consommateur = `scripts/diagnostic_anomalies_residuelles.py` (audit) ; la référence officielle est `src/collecte/divisions_officielles.py`. Conforme à D3 (pas de mélange heuristique/publié dans les calculs).
- **`src/strategie/spec_fiche.py` — pédagogie** — la fiche sépare fait/hypothèse/décision, rappelle le biais de survie (« PAS une probabilité »), la règle d'or « un pari perdant ne devient JAMAIS un loyer », « ta décision, jamais automatique » ; le verdict NON existe et est câblé (zone DANGER/PIÈGE). Le garde-fou de cours live aberrant (> ±50 %) est présent (`spec_veille.py:96`).
- **Cohérence des paliers spé** — `spec_fiche.py:123-125` (paliers +20/+35/+50 % sur `entry_lo`) conforme à l'IPS §4.2 ; `spec_profiles.py` CASSURE = plus haut 250 séances, conforme à la docstring.
- **Anti-spam renforcements** — `check_reinforcements` (`portfolio.py:722-783`) : cooldown 7 j par titre, re-signal si le prix baisse de ≥ 3 % pendant le cooldown, double format d'état rétrocompatible — conforme à AL-05 pour les niveaux 2-3.
- **Session BRVM** — `_in_session()` (`alerts.py:104-110`) utilise l'heure locale ; le poste cron est à Abidjan (UTC, pas de DST), donc la fenêtre 08:30-16:00 couvre la séance ~09:00-15:00 — correct sur ce host.

## Limites de cet audit

- **Lecture seule, pas d'exécution** : aucune suite de tests lancée (phase 8), aucune exécution du code en production — les preuves sont statiques (citations de code) + quelques exécutions Python **purement calculatoires** (formules de `taxation`, formatage) qui ne touchent ni le projet ni les données.
- **Périmètre** : `strategie_leo.py`, `challenge_validateur.py`, `fondamentaux_historiques.py`, la collecte, la CLI et les scripts n'ont été lus que comme **appelants** (pour prouver l'impact en production) — leurs propres défauts ne sont pas audités ici. `src/strategie/speculation.py`, `paliers_sortie.py`, `noyau_check.py`, `src/report.py`, `src/analyse/*` sont hors périmètre ; B1-14 touche à `report.py` sans l'avoir audité.
- **Hypothèses de déploiement** : le cron quotidien (`cmd_daily` 09:00) et le cron veille spé 16h sont supposés actifs comme documenté (README §« Automatisation quotidienne ») ; B1-01/B1-13 dépendent de Telegram étant le seul canal de delivery (console = `logs/daily.log`).
- **B1-05** suppose que `current_dps` (source `collecte.fundamentals`) reflète le dividende de l'exercice courant — la fraîcheur de cette source n'a pas été auditée (collecte, hors périmètre).
- Les findings P3 n'ont pas tous été re-vérifiés ligne à ligne dans les tests associés ; l'absence de test citée est une constatation statique (`grep` des `def test*`).

---

## Bilan

| Gravité | Nombre | IDs |
|---|---|---|
| **P1** | **1** | B1-01 |
| **P2** | **6** | B1-02, B1-03, B1-04, B1-05, B1-06, B1-07 |
| **P3** | **8** | B1-08, B1-09, B1-10, B1-11, B1-12, B1-13, B1-14, B1-15 |
| **Total** | **15** | |

**Rapport** : `C:\Users\LEO\projects\Bridge Bank\audit\phase3_agentB1_mistral.md`
