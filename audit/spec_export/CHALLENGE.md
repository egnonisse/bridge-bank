# CHALLENGE — audit contradictoire des résultats publiés (veille spéculative)

**Auditeur** : CHALLENGE (agent indépendant) · **Date** : 12/11/2026
**Cible** : `audit/spec_export/cas_*.csv`, `resume.json`, `data/spec_profiles.json`,
`src/strategie/spec_fiche.py`, `audit/spec_export/LISEZ-MOI.md`
**Méthode** : mesures exécutées sur le cache propre `data/history_clean.pkl` et sur les
CSV publiés (Python du projet), aucune valeur estimée de tête. Commandes reproductibles en
annexe.

**Chiffres de référence re-vérifiés** : 1 615 cas (PANIQUE 414 · EVEIL 934 · CASSURE 267),
43 titres, signaux du 2018-01-30 au 2025-11-04. Totaux conformes à `resume.json`.

---

## SÉVÉRITÉ CRITIQUE

### C1 — Les alertes envoyées à l'utilisateur affichent les taux BRUTS, pas les taux « avant stop »
**Constat** : la fiche (`src/strategie/spec_fiche.py`, `build_message`, l.374-375) annonce
« Ton palier +20 % : touché dans X % des cas » en lisant `touched["0.20"]` de
`data/spec_profiles.json`, c'est-à-dire le taux **sans contrainte de stop**. Le taux
exécutable (« palier atteint AVANT le stop −15 % ») n'existe que dans `resume.json`, que
**rien ne lit** (vérifié : aucun `avant_stop` ni `resume.json` dans `src/`). L'utilisateur
voit donc le chiffre optimiste, jamais le chiffre du plan qu'on lui vend.

**Mesure** (script `annexe A`, comparaison `spec_profiles.json.touched` vs
`resume.json.*_avant_stop`) :

| Schéma | +20 % annoncé (fiche) | +20 % avant stop (exécutable) | +50 % annoncé | +50 % avant stop |
|---|---:|---:|---:|---:|
| PANIQUE | **59 %** | **46 %** | 32 % | 24 % |
| EVEIL | 61 % | 52 % | 36 % | 30 % |
| CASSURE | 69 % | 62 % | 43 % | 38 % |

**Correction** : `spec_fiche.py` doit lire les taux `avant_stop` (et les afficher comme LA
fréquence qui décide), ou au minimum afficher les deux (« touché dans 59 % des cas, mais
seulement 46 % avant que ton stop −15 % ne coupe »).

### C2 — Le plan de vente par tiers n'est pas ce qui est mesuré — et la règle réelle est pire que la fiche
**Constat** : la fiche annonce « +20 % → vends ⅓ · +35 % → vends ⅓ · +50 % → vends le reste ·
stop −15 % ». Les statistiques publiées mesurent (a) un **rendement buy-and-hold 12 mois**
(`rendement_12m_net`, médianes +16,3 %/+5,9 %/+3,2 %) et (b) la probabilité que chaque palier
soit « touché ». **Ni l'un ni l'autre n'est le P&L du plan à tiers.** En outre la règle de
production `src/strategie/paliers_sortie.py` (l.96-97, 155-159) ajoute deux sorties que la
fiche ne mentionne pas et que l'export ne modélise pas : **stop remonté au break-even après
+20 %**, et **stop suiveur −10 % sous le sommet après +35 %**. Le « avant stop » publié ne
modélise que le stop −15 % : il est donc **encore optimiste** par rapport à la règle réellement
appliquée. Le LISEZ-MOI l'admet (« la rentabilité du plan complet demande un rejeu
chronologique ») — ce qui revient à dire que **rien dans l'export publié ne démontre la
rentabilité du plan vendu**.

**Mesure** : `paliers_sortie.py` l.122-180 (seuils + stop break-even/suiveur) vs
`exporter_cas_spec.py` l.99-108 (seul le stop −15 % est simulé, paliers mesurés isolément).

**Correction** : rejouer le plan complet (P5) et publier le rendement moyen/médian du plan,
net des frais réels (C3/C5), comme seule statistique de rentabilité. Tant que ce chiffre
n'existe pas, la fiche ne doit pas laisser croire que les « touchés dans X % » valident le plan.

### C3 — L'échantillon n'est pas indépendant : l'effectif réel est 2 à 4× plus petit, et PANIQUE cesse d'être rentable
**Constat** : l'espacement de 60 séances est appliqué **par titre ET par schéma**. Or un même
titre déclenche les trois schémas en entrelacé : à l'échelle du titre, l'espacement réel est
en médiane de **45 séances** (quartiles 22 / 45 / 60). **99,9 %** des paires consécutives d'un
même titre ont des fenêtres de 12 mois (252 séances) qui se **chevauchent** ; 64 % sont à moins
de 60 séances. Chaque choc de prix d'un titre est donc compté plusieurs fois comme « cas
indépendants ».

**Mesure** (script `annexe A`, re-tirage glouton à 252 séances par titre, tous schémas) :

| Schéma | publié | indépendant | win publié → indép. | médiane nette publiée → indép. | p20 avant stop pub. → indép. |
|---|---:|---:|---:|---:|---:|
| PANIQUE | 414 | **179** (−57 %) | 0,522 → **0,441** | +3,2 % → **−6,5 %** | 0,461 → **0,397** |
| EVEIL | 934 | **255** (−73 %) | 0,556 → 0,545 | +5,9 % → +4,5 % | 0,517 → 0,498 |
| CASSURE | 267 | **128** (−52 %) | 0,659 → **0,695** | +16,3 % → **+19,4 %** | 0,618 → 0,609 |

Le chevauchement **gonfle PANIQUE** (la médiane passe de +3,2 % à **−6,5 %**, la réussite de
52 % à 44 %) et **masque la force de CASSURE**. La corrélation inter-titres le même jour est,
elle, faible : 6 dates avec ≥5 cas, 31 cas (2 %) — le problème d'indépendance est intra-titre,
pas un choc de marché ponctuel.

**Correction** : publier aussi les taux sur l'échantillon à 252 séances d'espacement par titre
(c'est l'effectif réellement indépendant), et ne conclure la rentabilité d'un schéma que sur
celui-ci.

---

## SÉVÉRITÉ MAJEURE

### M1 — 38 % des cas publiés ne correspondent pas à un signal de production (filtre volume)
**Constat** : en production, `detect_schemas` exige `volume_jour ≥ médiane 60 séances` pour
CASSURE et EVEIL. L'export n'applique pas ce filtre. **41,1 % des cas EVEIL** et **27,0 % des
cas CASSURE** ont un volume du jour inférieur à leur médiane 60 j : ils n'auraient jamais été
signalés. Pour PANIQUE (pas de filtre volume dans `detect_schemas`), **37,0 %** des cas ont
quand même un volume sous leur médiane — l'entrée y est douteuse.

**Mesure** (script `annexe A`) : `volume_jour < volume_median_60j` → PANIQUE 153/414 (37,0 %),
EVEIL 384/934 (41,1 %), CASSURE 72/267 (27,0 %). Le LISEZ-MOI le dit sans chiffrer ; l'écart
d'univers réel est **~38 %**, pas « 1,7 % » (Limite 1, qui ne concerne que le compte PANIQUE).

**Correction** : ré-exporter avec le filtre volume (univers = signaux réellement publiés) et
publier les deux variantes côte à côte.

### M2 — Les frais réels du plan dépassent largement le forfait 2,8 % pour les positions de détail
**Constat** : le plan = 1 achat + 3 ventes = **4 ordres**, chacun avec **minimum 1 000 F**. Le
forfait 2,8 % n'est exact que si aucun minimum ne s'applique, c'est-à-dire **position ≥ 214 286 F**.
En dessous, le minimum domine.

**Mesure** (script `annexe A`) :

| Position | Frais réels du plan (4 ordres, min 1 000 F) | Forfait publié | Écart |
|---:|---:|---:|---:|
| 20 000 F | 20,0 % | 2,8 % | +17,2 pts |
| 50 000 F | 8,0 % | 2,8 % | +5,2 pts |
| 100 000 F | 4,4 % | 2,8 % | +1,6 pts |
| 200 000 F | 2,9 % | 2,8 % | +0,1 pt |
| ≥ 250 000 F | 2,8 % | 2,8 % | 0 |

En outre `paliers_sortie.py` (l.80) ne déduit que `FRAIS × fraction` sur chaque vente : il
**oublie l'achat (1,4 %) et tous les minima**. Conséquence : la médiane nette publiée pour
PANIQUE (+3,2 %) est **négative** pour toute position ≲ 130 000 F une fois les minima comptés.

**Correction** : modéliser les frais par ordre (`max(1,4 % × montant, 1 000 F)`, 4 ordres) et
publier les taux nets pour au moins deux tailles de position (ex. 100 k et 1 M F).

### M3 — Le stop −15 % est atteint souvent et vite : c'est lui qui fait tomber les taux
**Constat** : le stop est touché dans **56 % / 50 % / 38 %** des cas (PANIQUE/EVEIL/CASSURE) ;
parmi les stoppés, **55-61 % le sont dans les 60 premières séances** (délai médian 47-54
séances). La pire baisse à 60 séances atteint −15 % dans **34 % / 28 % / 22 %** des cas. Le
stop n'est pas un garde-fou rare : sur PANIQUE, un cas sur trois est sorti de force en ~2 mois,
et c'est exactement ce mécanisme qui transforme « +20 % touché 59 % » en « avant stop 46 % »
(C1).

**Mesure** (script `annexe B`, `jours_avant_stop` + re-calcul de la pire baisse 60 séances sur
le cache) :

| Schéma | stop touché | dont ≤ 60 s | pire baisse 60 s médiane | ≤ −15 % en 60 s |
|---|---:|---:|---:|---:|
| PANIQUE | 56 % | 61 % | −8,6 % | 34 % |
| EVEIL | 50 % | 55 % | −9,1 % | 28 % |
| CASSURE | 38 % | 57 % | −7,4 % | 22 % |

**Correction** : publier la distribution des délais de stop, et re-tester la robustesse du plan
à un stop plus large (−20 %) : si le plan ne survit qu'à un stop qui n'est jamais touché, il
n'est pas exécutable.

---

## SÉVÉRITÉ MINEURE

### m1 — Biais de survie : réel mais de faible ampleur sur cette fenêtre (la doc le surestime)
Le cache contient **48 titres**. Absents des cas : 5 nouvelles introductions (< 500 séances :
BBGC, BICB, LNBB, ORAC, UNLC) — l'inverse d'un biais de survie — et **1 titre radié en
juin 2017** (SVOC/SIVOA, dernier point `brvm_28ans.json` = 2017-06-30), de toute façon exclu
par le filtre < 500 séances. **Deux titres arrêtés le 2026-09-15** (SEMC, SICC) sont, eux,
**présents** dans l'univers, avec des taux de stop de **61 %** (SEMC) et **81 %** (SICC) : les
perdants sont bien comptés. L'avertissement « titres radiés absents → taux optimistes » est
donc **surdimensionné** ici ; le biais qui fausse réellement les chiffres est le chevauchement
(C3), pas la survie. (`brvm_28ans.json` : 9 codes absents du cache, mais 8 ont disparu avant
2010, hors fenêtre.)

### m2 — Aucune cellule de zone < 10 cas, mais le verdict n'est pas basé sur la bonne métrique
Les 15 cellules schéma×zone publiées ont toutes **n ≥ 19** (le seuil `SEUIL_CAS_ZONE=10` est
donc respecté). Après correction d'indépendance, elles tombent à 13-98 cas — la plus mince,
**PANIQUE 80-100 : 19 → 13 cas**, est précisément celle que `spec_fiche.py` vante comme
« la meilleure zone mesurée ». Surtout, le verdict ✅/🟡/🔴 est dérivé de `win_12m`
(fraction positive à 12 mois), **pas** du taux « palier avant stop » : deux métriques
différentes sont interchangeées au fil de la fiche (l.319 vs l.374). Un titre peut être affiché
« ✅ favorable » sur un chiffre qui ne décrit pas le plan vendu.

### m3 — L'export n'est pas rejouable à l'identique ; doc et CSV divergent du code
`exporter_cas_spec.py` (version disque, l.133-140) écrit des colonnes de maturité
(`date_fin_horizon`, `date_premier_palier`, `date_stop`, `seances_ecoulees`, `horizon_complet`,
`mois_calendaires`) **absentes** des CSV publiés. Rejouer le script produit un schéma différent
de l'export audité : la mention « rejouable » du LISEZ-MOI est fausse en l'état. Le LISEZ-MOI
écrit aussi « cours à J+252 / cours à **J − 1** » alors que le code entre au **cours du signal**
(`closes[i]`) ; et la fiche fixe les paliers sur `entry_lo` (= 0,985 × cours, soit +18,2 % du
cours signal) alors que l'export mesure +20 % du cours signal.

### m4 — Commentaires de code périmés ; dernière année de données invisible
Les commentaires de `spec_fiche.py` (l.67-69, 121-124) citent une calibration antérieure :
« EVEIL 80-100 : 91 cas à 67 %, médiane +18 % » alors que `spec_profiles.json` porte **156 cas
à 63,5 %, médiane +8,8 %** ; « PANIQUE 80-100 : 11 cas à 72,7 % » vs **19 cas à 73,7 %**. La
justification du ✅ repose donc sur des chiffres qui ne sont plus ceux du fichier. Par ailleurs,
la boucle `range(260, len(closes) − HORIZON)` exclut par construction toute la dernière année de
données (post 2025-11-04) : les taux publiés ne couvrent que 2018-2025 (la fiche annonce
« 10 ans ») et n'incorporent pas le régime de marché des 12 derniers mois. Ce n'est pas un bug
de maturité (tous les cas ont bien 252 séances de recul — vérifié, 0 cas immature), mais une
cécité à la période récente qu'il faut dire.

---

## VERDICT

**Ces statistiques démontrent-elles la rentabilité du plan annoncé ? — PARTIELLEMENT, et
tendant vers NON pour ce qui est vendu.**

Aucun chiffre publié ne mesure le P&L du plan à tiers tel qu'annoncé (C2) ; le seul indicateur
« exécutable » produit (palier avant stop) n'est pas celui affiché à l'utilisateur (C1, écart
de 13 points sur PANIQUE), et les frais réels du plan annulent la médiane nette annoncée pour
toute position de détail sous ~214 000 F (M2). Sur l'échantillon strictement non chevauchant,
seul CASSURE reste rentable (médiane +19,4 %, p20 avant stop 61 %), tandis que PANIQUE — le
schéma le plus vendu, 414 cas — bascule à **−6,5 %** de médiane nette avec 44 % de réussite
(C3) : le plan ne démontre sa rentabilité que sur une minorité de ses signaux, et aucun de ces
chiffres n'est net du plan de sortie réellement appliqué.

---

## ANNEXE — commandes exécutées et sorties réelles

Python du projet : `C:/Users/LEO/AppData/Local/hermes/hermes-agent/venv/Scripts/python`.
Scripts de mesure placés dans `C:/Users/LEO/AppData/Local/hermes/cache/scratch/`
(`audit_challenge.py` → `audit_challenge4.py`), sans réseau, sans écriture hors scratch.

**Annexe A — chevauchement, indépendance, volume, frais, zones**
(`audit_challenge2.py` + `audit_challenge3.py`, extraits) :

```
=== 3. INDEPENDANCE / CHEVAUCHEMENT (fenêtre 12 mois = 252 séances) ===
paires consécutives intra-titre : 1547
  dont fenêtres 12m qui se chevauchent (gap < 252) : 1546 (99.9 %)
  gap médian (séances) : 45
  quartiles : [22, 45, 60]
  gaps < 60 : 994 | < 120 : 1529 | < 252 : 1546

[PANIQUE] publié n=414 → indépendant n=179 (réduction 57 %)
  publié           n=414  win=0.522  median=+3.2%  p20_avant_stop=0.461  stop=0.558
  non chevauchant  n=179  win=0.441  median=-6.5%  p20_avant_stop=0.397  stop=0.615
[EVEIL]   publié n=934 → indépendant n=255 (réduction 73 %)
  publié           n=934  win=0.556  median=+5.9%  p20_avant_stop=0.517  stop=0.501
  non chevauchant  n=255  win=0.545  median=+4.5%  p20_avant_stop=0.498  stop=0.529
[CASSURE] publié n=267 → indépendant n=128 (réduction 52 %)
  publié           n=267  win=0.659  median=+16.3% p20_avant_stop=0.618  stop=0.378
  non chevauchant  n=128  win=0.695  median=+19.4% p20_avant_stop=0.609  stop=0.383

=== 8. FILTRE VOLUME (production) PAR SCHÉMA ===
  PANIQUE  n=414  volume_jour < médiane60j : 153 (37.0 %)
  EVEIL    n=934  volume_jour < médiane60j : 384 (41.1 %)
  CASSURE  n=267  volume_jour < médiane60j :  72 (27.0 %)

=== 10. FRAIS : plan 1 achat + 3 ventes, minimum 1 000 F/ordre ===
  position    20,000 F : frais réels plan =  20.0 %  (vs 2.8 %, écart +17.2 pts)
  position    50,000 F : frais réels plan =   8.0 %  (vs 2.8 %, écart +5.2 pts)
  position   100,000 F : frais réels plan =   4.4 %  (vs 2.8 %, écart +1.6 pts)
  position   200,000 F : frais réels plan =   2.9 %  (vs 2.8 %, écart +0.1 pts)
  position   250,000 F : frais réels plan =   2.8 %
  -> position >= 214,286 F pour que les minima ne s'appliquent plus du tout

=== 11. ÉCART annoncé vs mesuré (fiche = touched BRUT, resume = avant_stop) ===
  PANIQUE  +20% : annoncé 59 % vs avant-stop 46 %  | +50% : annoncé 32 % vs avant-stop 24 %
  EVEIL    +20% : annoncé 61 % vs avant-stop 52 %  | +50% : annoncé 36 % vs avant-stop 30 %
  CASSURE  +20% : annoncé 69 % vs avant-stop 62 %  | +50% : annoncé 43 % vs avant-stop 38 %
```

**Annexe B — stop et liquidité** (`audit_challenge2.py`, extraits) :

```
=== 5. STOP −15 % RÉALISME ===
[PANIQUE] n=414 stop touché=56% ; stop ≤ 60 séances : 140/231 (61%) ; délai médian 49
[EVEIL]   n=934 stop touché=50% ; stop ≤ 60 séances : 259/468 (55%) ; délai médian 53.5
[CASSURE] n=267 stop touché=38% ; stop ≤ 60 séances :  58/101 (57%) ; délai médian 47

  Pire baisse dans les 60 SÉANCES suivant le signal (cache propre) :
  [PANIQUE] pire baisse 60s médiane -8.6%  ≤-15% : 34%
  [EVEIL]   pire baisse 60s médiane -9.1%  ≤-15% : 28%
  [CASSURE] pire baisse 60s médiane -7.4%  ≤-15% : 22%

=== 6. LIQUIDITÉ ===
  volume_jour : min=1.0  médiane=1164.0  p10=60
  volume_jour < 100 : 220 (13.6 %)   | < 500 : 553 (34.2 %)
  valeur échangée le jour du signal < 100 k F : 167 (10.3 %) | < 1 M F : 521 (32.3 %)
```

**Annexe C — univers et survie** (`audit_challenge.py` + `audit_challenge4.py`, extraits) :

```
codes cache : 48 | codes dans CSVs : 43
codes ABSENTS des cas : ['BBGC', 'BICB', 'LNBB', 'ORAC', 'UNLC']  (n < 500 séances, introductions récentes)
  SEMC n=1275 ...2026-09-15 (s'arrête)   SICC n=1118 ...2026-09-15 (s'arrête)
  SEMC: 18 cas exportés, stop touché 11 (61 %)
  SICC: 16 cas exportés, stop touché 13 (81 %)
data/brvm_28ans.json: 57 codes ; ABSENTS du cache : CDAC ELFC SACC SCMC SDVC SIMC SRIC SVOC TTRC
  dernière apparition dans brvm_28ans.json : ... SVOC 20170630 (seul radié dans la fenêtre), les 8 autres <= 2010
  dernier signal exporté : 2025-11-04 (données jusqu'au 2026-11-09)
```

