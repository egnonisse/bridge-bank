# Phase 3 — Matériel récupéré du run B avorté (12/10/2026)

**Contexte.** Le premier run de l'Agent B (Mistral Large 4-0, `audit/phase3_brief_agentB.md`,
périmètre élargi entier) a travaillé 47 minutes (74 appels d'outils) puis a été **coupé par une
panne de connexion au moment d'écrire son rapport** — le rapport n'a jamais été écrit. Ce fichier
consigne, honnêtement, les **pistes que ce run avait confirmées par exécution** avant sa coupure
(extraits de son transcript `deleg_3821ba96/task-0.log`), **re-vérifiées indépendamment** par
l'auditeur principal ci-dessous. Elles seront **croisées** avec les rapports des agents B1/B2 qui
reprennent la revue élargie.

Statut de traçabilité : ces findings sont réels et vérifiés, mais ils proviennent d'un run dont le
rapport formel n'existe pas — à confronter aux rapports B1/B2 avant intégration finale.

---

## Piste B0-01 — Le cooldown « 30 jours après stop-out » de la veille spé est inopérant (P1)

**Ce qu'il a vu** : `src/strategie/spec_veille.py:78` essaie de lire la date du stop dans
`close_reason` via `date.fromisoformat((p.close_reason or "").split(" ")[-1][:10])`.

**Vérification indépendante (auditeur principal, exécutée)** :

```
close_reason réel = 'STOP déclenché à 29,745 (stop 25,283)'    (produit par speculation.py:183)
token extrait     = '25,283)'
parse → ValueError SYSTÉMATIQUE → repli sur `opened_at` (date d'OUVERTURE)
```

**Conséquence** : `stopout_last[code]` = date d'ouverture, pas la date du stop. Pour toute position
gardée > 30 jours avant d'être stoppée, le cooldown est **déjà expiré au jour du stop** → le garde-
fou anti-faux-breakout (30 j après un stop, 60 j après deux) **ne filtre rien dans le cas courant**.

**Correction à prévoir** (phase 9-11) : horodater le stop dans `close_reason` (ou un champ dédié
`closed_at`) plutôt que d'extraire une date d'une chaîne destinée à l'affichage.

---

## Piste B0-02 — Les fiches de la veille spé affichent des montants à la VIRGULE anglaise (P2)

**Ce qu'il a vu** : formatage `f"{39500:+,.0f}"` → `+39,500`, qu'un lecteur francophone peut lire
« 39,5 » ; alors que le projet possède un helper dédié (`src/portefeuille/format_fr.py`) dont le
test verrouille explicitement « aucune virgule dans les francs » (« Python écrit 3,784… un
francophone y lit trois francs »).

**Vérification indépendante** :

```
→ tests/test_format_fr.py EXISTE et documente ce piège exact.
→ src/strategie/spec_fiche.py utilise encore `:,.0f` (virgule) dans ~8 endroits,
  dont « Cours de référence : {x:,.0f} F » et chaque niveau du filet (stop, paliers).
→ Les fiches envoyées quotidiennement à LEO ne sont PAS passées au format FR.
```

**Correction à prévoir** : remplacer par `format_fr.fcfa()/nombre()` dans `spec_fiche.py`
(et vérifier les autres modules affichant des montants).

---

## Piste B0-03 — `verify=False` sur tous les appels HTTPS sortants (P3, assumé mais à documenter)

**Ce qu'il a vu** : appels `requests.get(..., verify=False)` dans : `analyse/boc.py`,
`analyse/news.py`, `analyse/fondamentaux_historiques.py`, `collecte/dividend_history.py`,
`collecte/live.py`, `collecte/bsapi.py`.

**Vérification indépendante** : `bsapi.py` documente le choix (« certificat SSL du serveur
invalide → verify=False, données publiques »). Le risque (MITM sur des données publiques) est
faible mais réel ; l'idéal serait de limiter `verify=False` aux domaines réellement à certificat
invalide (brvm.org) et de garder la vérification ailleurs (sources société, Telegram, etc.).

**Statut** : constat d'hygiène sécurité — à prioriser avec les autres findings de sécurité.

---

## Piste B0-04 — Écart de définition du prix d'entrée : IPS vs code (P3, documentaire)

**Ce qu'il a vu** : `gross_yield_for_net(4 %) = 0,054545` alors que l'IPS §3.2 écrit
`dps × (1 − 12 %) / (4 % + 0,80 %)` = division par **0,048**. Les deux sont **mathématiquement
équivalents** (0,88/0,048 = 1/0,054545), mais le code applique en plus les **frais d'achat**
(÷1,014) : `entry code = 35 744,58` vs `36 245` (IPS). Écart = définition « frais inclus ou non ».

**Statut** : incohérence documentaire mineure — préciser la définition dans l'IPS (frai inclus).

---

*Fin du matériel récupéré. Les rapports B1 (`phase3_agentB1_mistral.md`) et B2
(`phase3_agentB2_mistral.md`) reprennent la revue élargie en écriture incrémentale.*
