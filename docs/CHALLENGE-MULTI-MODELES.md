# Challenge multi-modèles — Bridge Bank

> **⚠️ ADDENDUM du 13/10/2026 — LE JUGE A ÉTÉ DURCI (audit A3) ET LES 6 RÈGLES
> RE-JUGÉES : 1/6.**
> Exécution à **J+1**, **p = (1+#≥)/(1+N)** sur **1 000 tirages**, baseline bornée à
> la fenêtre éligible (durées rééchantillonnées, **bootstrap conditionnel aux dates de
> la règle**), robustesse par l'**avantage vs baseline par moitié**, seuil
> **Bonferroni**. Résultat : seule `gemini-2.5-fla-H3` survit (+2,07 pt, p=0,005) ;
> les 5 autres sont dans le bruit (p 0,10 à 0,92). L'ancien « 6/6 tiennent
> (+5 à +19,5 pts, p=0,000) » est l'état ANTÉRIEUR, conservé daté.
> Détail : `docs/DECISION-2026-10-13-lot8-chantier-challenge.md`.

Faire challenger le système BRVM par les meilleurs modèles du marché, sans
jamais leur laisser le dernier mot.

---

## 1. Le principe

> **Les modèles génèrent. Le code valide. L'humain arbitre.**

Un modèle de langage ne valide **rien**. Il ne connaît pas les données, invente
des chiffres plausibles, et partage avec ses concurrents les mêmes biais de
formation. Six modèles d'accord sur un seuil ne prouvent pas plus qu'un seul —
c'est même souvent le signe qu'ils ont appris la même chose.

Ce dispositif retourne la logique : les modèles sont des **générateurs
d'hypothèses**, et le juge est le **backtest du projet**, sur des données
vérifiées.

### La règle anti-triche

**Les modèles ne voient JAMAIS un résultat de backtest.** Ni en génération, ni
en critique. S'ils voyaient les scores, ils apprendraient à viser le test au
lieu de raisonner — et leur production ne vaudrait plus rien.

---

## 2. Architecture en 4 rounds

| Round | Acteur | Ce qui se passe | Coût |
|---|---|---|---|
| **R1 — Génération** | 6 modèles | Reçoivent les statistiques descriptives du marché + le langage autorisé. Produisent 5 hypothèses chacun, à l'aveugle. | ~0,03 $ |
| **R2 — Critique** | 6 modèles | Reçoivent les hypothèses des **autres**, anonymisées. Disent lesquelles sont fragiles. | ~0,03 $ |
| **R3 — Validation** | **le code** | Backtest de tout, comparaison au panier aléatoire, découpage in/out-of-sample. Aucun appel API. | 0 $ |
| **R4 — Verdict** | le code | Classement par ce qui a été MESURÉ. Les avis ne comptent pas. | 0 $ |

### Modèles retenus (familles différentes)

Six variantes du même raisonnement n'apporteraient rien : on prend des
**familles distinctes**, pas six tailles du même modèle.

| Modèle | Famille |
|---|---|
| `anthropic/claude-haiku-5.5` | Anthropic |
| `openai/gpt-5.6-luna-pro` | OpenAI |
| `google/gemini-2.5-flash` | Google |
| `~deepseek/deepseek-pro-latest` | DeepSeek |
| `meta-llama/llama-3.3-70b-instruct` | Meta |
| `mistralai/mistral-large-4-0` | Mistral |

---

## 3. Le langage d'hypothèses (DSL)

Une hypothèse est une règle d'achat et une règle de vente, écrites dans un
langage **fermé** :

```
<indicateur> <comparateur> <nombre>  [et|ou]  <indicateur> <comparateur> <nombre>
```

**Pourquoi un langage plutôt que du code ?** Parce que le texte vient d'un
modèle : l'exécuter directement (`eval`) ouvrirait la porte à l'injection,
à l'accès disque et aux boucles infinies. Le DSL n'accepte ni parenthèses, ni
fonctions, ni guillemets, ni mots réservés — vérifié par un test dédié
(CTRL-4 tente une injection : elle est refusée sans qu'une ligne s'exécute).

### Indicateurs disponibles

| Indicateur | Sens |
|---|---|
| `r5` `r20` `r60` `r120` `r250` | rendement sur N séances (fraction : 0.15 = +15 %) |
| `vol60` | volatilité annualisée sur 60 séances |
| `dd250` | distance au plus haut des 250 séances (négatif) |
| `dd_atl` | chute depuis le plus haut historique (négatif) |
| `pos5a` | position dans la fourchette 5 ans (0 = plus bas, 1 = plus haut) |
| `prix_vs_mm50` / `prix_vs_mm200` | cours / moyenne mobile − 1 |
| `vol_ratio` | volume du jour / volume médian 60 séances − 1 |
| `per` `net_yield` `payout` | ✅ **fondamentaux RECONSTITUÉS historiquement** (voir ci-dessous) |

### ✅ Les fondamentaux sont désormais point-in-time (corrigé le 07/10/2026)

**Le problème qui existait.** `per`, `net_yield` et `payout` étaient les valeurs
**d'aujourd'hui** appliquées à tout l'historique. Une règle « acheter les PER < 15 »
ne testait donc pas « était-ce bon à l'époque ? » mais « est-ce bon **maintenant** ? » :
une fuite du futur qui rendait ces règles intestables.

**La correction.** `src/fondamentaux_historiques.py` reconstitue, pour chaque titre,
les dividendes avec leur **date de détachement** et le BPA par exercice, puis
`fondamentaux_a_la_date()` ne retourne que ce qui était **réellement connu** ce
jour-là :

| Donnée | Devient connue à |
|---|---|
| Dividende de l'exercice N | sa **date de détachement** (ex-date) |
| BPA de l'exercice N | **année N+1** (publication des comptes, ~avril) |

**Vérification (3 tests, `scripts/tester_anti_lookahead.py`)** :
190 transitions de dividende et 105 couples (titre, exercice) testés, **0 violation**.
Les indicateurs varient bien avec la date (SGBC : 404 valeurs distinctes de
`net_yield` entre 2023 et 2026).

**Couverture mesurée** : 42/47 titres avec dividendes datés, **25/47 avec un BPA
vérifié**. Fenêtre exploitable : **2022 → 2026**. Les 4 titres sans historique
daté n'ont simplement pas d'indicateurs fondamentaux — le juge refuse alors de
trancher dessus plutôt que de trancher faux.

**Contrôle croisé obligatoire du BPA.** Le parseur peut se tromper du tout au tout :
mesuré sur 16 titres, 10 corrects, **2 franchement faux** (NTLC 20,7× trop grand —
exactement le ratio de sa division de 2017 ; BICC 2,3× trop petit) et 4 sans donnée.
Le PER de référence sert donc de juge : au-delà de 40 % d'écart, le BPA du titre est
**écarté** et ses règles fondamentales désactivées (`valider_bpa`).

### ⚠️ Les dividendes sont crédités dans le rendement (corrigé le 07/10/2026)

`Trade.rendement_net` ne comptait **que la plus-value**. Une stratégie de dividende
était donc jugée avec 5 à 7 points de handicap par an — un biais structurel contre
le style même qu'on cherchait à évaluer.

Corrigé : les dividendes détachés pendant la détention sont crédités (nets d'IRVM
12 %), **des deux côtés** — dans la simulation de l'hypothèse **et** dans les paniers
aléatoires. Ne corriger qu'un côté créerait le biais inverse.

**Effet mesuré** : la règle « rendement net ≥ 4 % » passe de +15,24 % à +18,02 %, et
le hasard de +18,19 % à +20,79 %. Le verdict ne change pas, mais la comparaison est
désormais honnête.

---

## 4. Le juge — trois garde-fous

### a) Baseline aléatoire obligatoire

Dans un marché qui a fait **+145 %** entre 2017 et 2026, n'importe quelle règle
gagne de l'argent. La référence n'est donc jamais zéro : on tire **100 paniers
achetés au hasard**, de même taille et de même durée, sur la même plage de dates.
Une hypothèse ne compte que si elle **bat ce tirage**.

### b) In / out-of-sample

La période est coupée en deux (coupure 2022-01-01). Un avantage qui n'existe que
sur une moitié est de la chance, pas une découverte.

### c) Net de frais

**2,8 % par aller-retour** (1,4 % par sens, courtage réel). Aucun résultat brut
n'est affiché.

### Verdicts produits

| Verdict | Signification |
|---|---|
| `RETENUE SOUS CONDITION` | bat le hasard, tient sur les deux moitiés |
| `FRAGILE` | bat le hasard mais écart > 40 pts entre les moitiés |
| `NON CONCLUANTE` | p > 0,05 — le hasard n'est pas écarté |
| `REJETEE` | ne bat pas le hasard, ou une seule moitié |
| `PREUVE INSUFFISANTE` | moins de 10 trades |
| `AUCUN SIGNAL` | la règle ne se déclenche jamais |

---

## 5. Faire tourner le juge d'abord

**On ne dépense pas un centime avant d'avoir prouvé que le juge est fiable.**
Le script `scripts/tester_le_juge.py` soumet 4 hypothèses de contrôle dont la
réponse est connue d'avance :

| Contrôle | Attendu | Rôle |
|---|---|---|
| CTRL-1 rebond confirmé | retenue | le juge sait reconnaître un signal réel |
| CTRL-2 acheter la faiblesse | **rejetée** | témoin volontairement faux |
| CTRL-3 toujours vrai | avantage ≈ 0 | la baseline est bien centrée |
| CTRL-4 injection de code | **refusée** | la sécurité est effective |

**Si CTRL-2 passe ou si CTRL-4 s'exécute : le juge est en cause, pas les
modèles. On corrige avant de lancer quoi que ce soit.**

---

## 6. Utilisation

```bash
# 1. Vérifier le juge (obligatoire, gratuit)
python scripts/tester_le_juge.py

# 2. Simuler sans dépenser
python scripts/challenge_multi_modeles.py --dry-run

# 3. Lancer
python scripts/challenge_multi_modeles.py --all --plafond 4.5
```

**Prérequis** : `OPENROUTER_API_KEY` active dans `%HERMES_HOME%\.env`
(ligne décommentée — un `#` en tête la rend inerte).

**Budget** : le script cumule les tokens réellement consommés et **refuse tout
appel** qui ferait dépasser le plafond. Le coût réel du premier passage complet :
**0,0525 $** pour 12 appels sur 6 modèles.

---

## 7. Résultats du premier passage (07/10/2026)

**20 hypothèses**, 3 retenues, **0,0525 $**.

| Hypothèse | Règle d'achat | net | vs hasard | p | trades |
|---|---|---|---|---|---|
| Rebond après effondrement | `dd_atl < -0.80 et r60 > 0.10 et r250 > 0` | +72,9 % | +43,1 | 0,020 | 34 |
| Tendance proche des plus hauts | `prix_vs_mm200 > 0.10 et dd250 > -0.10` | +9,0 % | +4,8 | 0,000 | 431 |
| Tendance modérée | `r60 > 0.05 et r250 > 0.05 et prix_vs_mm200 > 0 et vol60 < 0.60` | +4,0 % | +3,2 | 0,010 | 636 |

### Ce que ça dit

1. **Les deux règles robustes sont des règles de TENDANCE** — le momentum bat le
   retour à la moyenne sur la BRVM, ce que les épreuves internes avaient déjà
   montré. Convergence entre deux méthodes indépendantes.
2. **Le signal « rebond après effondrement » ressort une nouvelle fois**
   (+72,9 %) — troisième confirmation, et il correspond au signal « rebond
   confirmé » déjà suivi par le radar.
3. **Les avis des modèles étaient incohérents** : GPT jugeait 0 hypothèse solide
   sur 8, Gemini en jugeait 5. Un vote n'aurait rien valu — le code a tranché.

---

## 8. Pièges rencontrés (à ne pas répéter)

| Piège | Conséquence | Correctif |
|---|---|---|
| Recalculer les indicateurs à chaque séance | 7 min pour 4 hypothèses | **précalcul en une passe** (22 s pour 47 titres) |
| Parser les expressions à chaque évaluation | ×4000 plus lent | `compiler()` une fois, puis `evaluer_compilee()` |
| Reconstruire les index de dates dans la baseline | interminable | bornes précalculées par titre |
| Noms de champs différents entre dataset et DSL | **7 hypothèses déclarées « aucun signal » à tort** | conversion dans `charger_fondamentaux()` |
| `payout_pct` calculé comme `dps / cours` | c'est le **rendement**, pas le payout — ABJC affichait 5,5 % au lieu de 150 % | `dps × per / cours` |
| Fondamentaux actuels appliqués à tout l'historique | fuite du futur | `src/fondamentaux_historiques.py` : reconstitution point-in-time (dates de détachement + publication des comptes) |
| Dividendes absents du rendement des trades | stratégie de dividende handicapée de 5-7 pts/an | `Trade.dividendes` crédité dans la simulation **et** dans la baseline |
| Parseur de BPA lisant la mauvaise colonne | NTLC 20,7× trop grand → PER 0,90 | contrôle croisé par le PER de référence (`valider_bpa`, tolérance 40 %) |
| `r.valide` confondu avec « règle retenue » | faux succès annoncé | `valide` = conformité au DSL ; le verdict est dans `r.verdict` |

---

## 9. Scripts

| Fichier | Rôle |
|---|---|
| `scripts/challenge_multi_modeles.py` | orchestrateur R1→R4 |
| `scripts/tester_le_juge.py` | contrôle du juge avant dépense |
| `src/challenge_schema.py` | DSL : validation, compilation, évaluation |
| `src/challenge_indicateurs.py` | précalcul des indicateurs (une passe) |
| `src/challenge_validateur.py` | backtest, baseline, verdicts |
| `data/hypotheses_controle.json` | les 4 hypothèses de contrôle |
| `data/challenge_resultats.json` | résultats et journal de dépense |

---

## 10. Ce que ce dispositif ne fait pas

- Il ne **prouve** pas qu'une règle gagnera demain : il élimine celles qui
  n'ont jamais eu d'avantage. C'est tout, et c'est déjà beaucoup.
- Il ne remplace pas le jugement sur les **frais réels, la liquidité et
  l'exécution** : un backtest suppose qu'on achète au cours de clôture, ce qui
  est impossible sur les petites capitalisations BRVM.
- Les règles retenues ne sont **pas** des ordres d'achat. Le noyau reste régi
  par les 4 filtres du projet (dividende couvert, PER, payout, régularité).
