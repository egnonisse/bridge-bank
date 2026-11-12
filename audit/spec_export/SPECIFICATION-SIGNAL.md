# Spécification exacte du signal de veille spéculative

**Objet** : rendre le signal reproduisible par un tiers qui ne lit pas le code.
Chaque règle cite le fichier et la ligne qui l'implémente (format `chemin:ligne`).
Toute valeur absente du code est écrite « non spécifié dans le code ».

**Fichiers sources du signal** (lus en entier, version du 12/11/2026) :

| Fichier | Rôle |
|---|---|
| `src/strategie/spec_profiles.py` | le détecteur `detect_schemas`, le RSI, `zone_of`, les profils |
| `src/regles.py` + `src/taxation.py` | la valeur des frais (`FRAIS_ALLER_RETOUR`) |
| `scripts/calibrate_spec_profiles.py` | comment les cas sont comptés et agglomérés |
| `scripts/exporter_cas_spec.py` | comment un cas est exporté, le parcours stop/paliers |
| `src/strategie/spec_fiche.py` | la production (filtre volume réellement appliqué, seuils d'affichage) |

---

## 1. La formule EXACTE du RSI

Implémentée par `rsi(vals, n=14)` — `src/strategie/spec_profiles.py:40-57`.

- **Période** : `n = 14` (paramètre par défaut) — `spec_profiles.py:40`.
- **Méthode de Wilder** (pas une moyenne simple glissante) :
  - **Amorçage** : sur les 14 premières variations, moyenne **arithmétique simple**
    des gains et des pertes — `avg_g, avg_l = gains / n, losses / n`
    (`spec_profiles.py:47-51`, à l'index `i == n`).
  - **Lissage** : pour chaque barre suivante, lissage de Wilder
    `avg_g = (avg_g * (n - 1) + g) / n` et `avg_l = (avg_l * (n - 1) + l) / n`
    (`spec_profiles.py:53-55`).
- **Valeur** : `100.0 si avg_l == 0 sinon 100 - 100 / (1 + avg_g / avg_l)`
  (`spec_profiles.py:52` et `:56`).
  - **Aucune perte** (`avg_l == 0`) → RSI = **100,0**.
  - **Aucun gain** (`avg_g == 0`, `avg_l > 0`) → RSI = **0,0**.
  - **Série plate** (toutes variations nulles) → `avg_l == 0` est testé en premier → RSI = **100,0** (pas 50).
- **Arrondi** : **aucun** — la fonction renvoie un flottant brut (aucun `round`).
- **Première valeur valide** : l'index `n` = **14** ; `out[0..13]` restent `None`
  (`spec_profiles.py:44-51`). Le RSI lu pour le signal est `r[i]` avec `i` = dernière
  barre, donc un RSI **lissé Wilder** (toute série réelle dépasse 14 barres).

> La description de `LISEZ-MOI.md:41` (« moyenne des hausses / moyenne des baisses »)
> est **imprécise** : elle omet l'amorçage + lissage de Wilder et les cas limites
> 100/0. Voir §9.

---

## 2. Les trois schémas — conditions exactes

Tout est dans `detect_schemas(closes, volumes=None)` — `src/strategie/spec_profiles.py:60-103`.
Les trois conditions s'évaluent sur la **dernière séance** de la série (`i = len(closes) - 1`,
`spec_profiles.py:72`). Un titre peut déclencher **plusieurs** schémas le même jour
(`found` est une liste cumulée).

**Garde d'entrée** (avant tout test) : `if len(closes) < 260 or closes[-1] <= 0: return []`
— `spec_profiles.py:70`. Il faut **≥ 260 clôtures** et une **dernière clôture strictement
positive** ; sinon aucun signal.

### CASSURE — cassure du plus haut des 250 séances

```
if closes[i] > max(closes[i - 250 : i]):        # spec_profiles.py:75
```

- **Comparaison EXCLUSIVE** : `>` strict. Le dernier cours doit être **strictement
  supérieur** au maximum des 250 précédents. Un cours **égal** au plus haut ne déclenche **pas**.
- **Fenêtre** : indices `[i-250, i-1]` inclus, soit **250 séances** immédiatement avant la
  dernière (la dernière est exclue du max). Source : `spec_profiles.py:75`.
- Filtre volume : voir §3.

### EVEIL — rebond ≥ +10 % depuis le creux des 60 séances

```
creux60 = min(closes[i - 60 : i])               # spec_profiles.py:88
if closes[i] / creux60 - 1 >= 0.10:             # spec_profiles.py:89
```

- **Comparaison INCLUSIVE** : `>=` supérieur ou égal. Un rebond **exactement** de +10,00 %
  (ratio `closes[i]/creux60 - 1 == 0.10`) déclenche.
- **Fenêtre du creux** : indices `[i-60, i-1]` inclus, soit **60 séances** avant la dernière
  (`spec_profiles.py:88`).
- Aucun test `creux60 > 0` ici : la garde de la ligne 70 (`closes[-1] <= 0`) filtre la
  **dernière** clôture mais **pas** le creux. Une clôture à **0 dans la fenêtre des 60
  séances précédentes** (`min(closes[i-60:i]) == 0`) fait lever une **`ZeroDivisionError`**
  à la ligne 89 (vérifié par exécution : `[50.0]*260 + [55.0]` avec `c[220] = 0.0` →
  `ZeroDivisionError: float division by zero`). Les données du backtest ne sont pas filtrées
  sur `close > 0` (`exporter_cas_spec.py:56-59`) : ce cas dépend donc des données.
- Filtre volume : voir §3.

### PANIQUE — RSI 14 sous 30

```
r = rsi(closes)                                 # spec_profiles.py:100
if r[i] is not None and r[i] < 30:              # spec_profiles.py:101
```

- **Comparaison EXCLUSIVE** : `<` strict. RSI **égal** à 30,0 ne déclenche **pas**.
- **Aucun filtre volume** (contrairement à CASSURE et EVEIL).
- `r[i] is not None` : sécurité contre une série trop courte (jamais atteinte ici,
  car la garde de la ligne 70 exige déjà ≥ 260 barres).

---

## 3. Le filtre de volume

Identique pour CASSURE et EVEIL ; **absent pour PANIQUE**.

```
if volumes and len(volumes) == len(closes):     # spec_profiles.py:77 (CASSURE) / :91 (EVEIL)
    med = statistics.median(volumes[-61:-1])    # spec_profiles.py:78 / :92
    vol_ok = med > 0 and volumes[i] >= med      # spec_profiles.py:82 / :96
```

- **Quand il s'applique** : seulement si `volumes` est fourni **et** `len(volumes) == len(closes)`.
  Sinon (`volumes=None` ou longueur différente), le filtre est **sauté** : le schéma se
  déclenche sur le prix seul (`vol_ok` reste `True`).
- **Fenêtre de la médiane** : `volumes[-61:-1]` = les **60 séances** qui se terminent à la
  séance **précédant** la dernière (indices `[len-61, len-2]`). Le volume du jour du signal
  n'est **pas** inclus dans la médiane.
- **Condition** : `med > 0` **et** `volumes[i] >= med` (comparaison **INCLUSIVE** sur le
  volume du jour). Une **médiane nulle** (titre illiquide, trou de données) **refuse** la
  confirmation : `med > 0` est faux, donc `vol_ok = False` — même si le volume du jour est
  positif. C'est la règle « B1-10 (13/10/2026) » commentée aux lignes 79-81 et 93-95.
- **En production** (là où le filtre compte) : `build_fiche` appelle
  `detect_schemas(closes, volumes)` — `src/strategie/spec_fiche.py:177` ; les volumes sont
  extraits et transmis par `src/strategie/spec_veille.py:113` et `:125`.
- **Dans les backtests, le filtre est DÉSACTIVÉ** : `calibrate_spec_profiles.py:75` et
  `exporter_cas_spec.py:66` appellent `detect_schemas(closes[: i + 1])` **sans** volumes.
  Les cas exportés/calibrés sont donc **plus nombreux** que les signaux réellement publiés.

---

## 4. La position de zone (et ce qu'elle n'est pas)

`zone_of(closes, years=5)` — `src/strategie/spec_profiles.py:106-113`.

- `n = min(len(closes) - 1, years * 252)` = au plus **1260** séances (`:108`).
- Fenêtre : `closes[-n-1:-1] + [closes[-1]]` = jusqu'à **1261** séances (`:109`).
- Résultat : `(closes[-1] - min) / (max - min)` (`:113`), `0.0` si `max <= min` (`:111-112`).
- **C'est une position min-max** dans la fourchette 5 ans (0 à 1), **PAS un percentile de
  rang** (part des séances sous le cours). Aucun arrondi dans la fonction ; l'arrondi à 4
  décimales n'a lieu qu'à l'export CSV (`exporter_cas_spec.py:94`), **après** le classement.

Libellés (`zone_label`, `spec_profiles.py:116-125`) : `< 0.20` BAS_ECRASE · `< 0.40`
BAS_SOLIDE · `< 0.60` MILIEU · `< 0.80` HAUT_FRAGILE · sinon FORCE.

Tranches du backtest (`calibrate_spec_profiles.py:51-52`, `exporter_cas_spec.py:35-36`) :
0-20 / 20-40 / 40-60 / 60-80 / 80-100, classées par `lo <= zone < hi`
(`tranche_de`, `calibrate_spec_profiles.py:56-60`). La borne haute de la dernière tranche est
`1.01`, donc une zone = 1,0 tombe bien dans 80-100.

---

## 5. Ordre de sélection des cas

Un « cas » = (titre, date, schéma) retenu par le backtest. Boucle dans
`calibrate_spec_profiles.py:69-89` et `exporter_cas_spec.py:55-112`.

1. **Univers** : un titre est traité si `len(closes) >= 500` **et** `closes[0] > 0`
   (`calibrate_spec_profiles.py:71`, `exporter_cas_spec.py:62`). Sinon le titre entier est
   écarté.
2. **Boucle** : `for i in range(260, len(closes) - HORIZON)` (`calibrate:74`, `exporter:65`).
   Chaque `i` est une « journée de signal » candidate. Le détecteur n'est **jamais** évalué
   sur les 260 premières séances, et jamais sur les 252 dernières (il faut 252 séances de
   futur).
3. **Détection** : `detect_schemas(closes[: i + 1])` **sans volumes** (`calibrate:75`,
   `exporter:66`) — cf. §3.
4. **Espacement de 60 séances, par titre ET par schéma** :
   - `last_entry = {s: -10**9 for s in SCHEMAS}` est **réinitialisé pour chaque titre**
     (`calibrate:73`, `exporter:64`).
   - Pour chaque schéma détecté : `if i - last_entry[s] < ESPACEMENT: continue`
     (`calibrate:82`, `exporter:86`) puis `last_entry[s] = i` (`calibrate:89`, `exporter:88`).
   - Un cas n'est retenu que s'il est **≥ 60 séances** après le dernier cas **retenu** du
     **même schéma sur le même titre**. « ≥ 60 » et non « > 60 » : le test est `< 60`, donc
     exactement 60 séances d'écart est retenu.
   - L'espacement est **indépendant par schéma** : un CASSURE et un EVEIL le même jour sont
     tous deux retenus (compteurs distincts).

**Pourquoi le premier cas d'une série peut être écarté** — trois mécanismes, à ne pas
confondre :

1. L'**espacement n'écarte jamais le premier cas** : `last_entry = -10**9` rend
   `i - (-10**9)` énorme, donc la première détection d'un titre/schéma est **toujours**
   conservée (preuve §8.4).
2. Le **premier cas d'un titre peut l'être pour d'autres raisons** :
   - le détecteur n'est appelé qu'à partir de `i = 260` (`calibrate:74`, `exporter:65`) —
     un signal actif pendant les 260 premières séances n'est jamais vu ;
   - `detect_schemas` refuse `len(closes) < 260` (`spec_profiles.py:70`) — 259 clôtures
     → aucun signal (preuve §8.4) ;
   - le garde-fou titre `len(closes) < 500 or closes[0] <= 0` écarte le titre entier
     (`calibrate:71`, `exporter:62`) ;
   - une clôture du jour ≤ 0 écarte le cas (`closes[-1] <= 0`, `spec_profiles.py:70`).

---

## 6. Rendement 12 mois, frais, et « palier touché avant le stop »

### Rendement net à 12 mois

- `HORIZON = 252` — `spec_profiles.py:27` (252 séances = 12 mois de bourse).
- `rendement = closes[i + HORIZON] / closes[i] - 1 - FRAIS`
  (`calibrate_spec_profiles.py:78` ; idem `exporter_cas_spec.py:82` sous la forme
  `futur[-1] / closes[i] - 1 - FRAIS` où `futur[-1] = closes[i + 252]`).
- Le **pic** (mesure « touché » brute du calibrage) :
  `peak = max(closes[i + 1 : i + HORIZON + 1]) / closes[i] - 1`
  (`calibrate_spec_profiles.py:79`) — les 252 séances **après** le signal, jour du signal exclu.

### Les frais

- `FRAIS = FRAIS_ALLER_RETOUR` — import `spec_profiles.py:26` ; valeur `2 * FRAIS_PAR_SENS`
  = **0,028** (2,8 % aller-retour) — `src/regles.py:57` ; `FRAIS_PAR_SENS = BROKERAGE_FEE`
  = **0,014** — `src/regles.py:56`.
- Décomposition de `BROKERAGE_FEE` : `BROKERAGE_RATE * (1 + TVA_RATE) + BRVM_FEES_RATE`
  = `0,008 × (1 + 0,18) + 0,00456` = 0,014 — `src/taxation.py:29` (avec `:24`, `:26`, `:27`).
- `FRAIS_MINIMUM = 1 000 F` par ordre — `src/regles.py:58` (`BROKERAGE_MIN = 1000.0`,
  `src/taxation.py:25`).
- **Attention** : le backtest déduit un **forfait de 2,8 %** et ignore le minimum de
  1 000 F par ordre. Sous ~125 000 F par ordre, le taux effectif dépasse 2,8 %
  (commentaire `src/taxation.py:28`). Le forfait est donc **optimiste** pour les petites
  lignes.

### « Palier touché avant le stop » — définition exacte

Uniquement dans `exporter_cas_spec.py` (le calibrage ne simule pas le stop) :

- `STOP = 0.15` — `exporter_cas_spec.py:32`. `PALIERS = (0.20, 0.35, 0.50)` — `:33`.
- Parcours séance par séance des 252 séances **après** le signal
  (`futur = closes[i + 1 : i + HORIZON + 1]`, `:71`) :
  - `r = c / closes[i] - 1` (`:76`) ;
  - **stop** : première séance `j` où `r <= -STOP` (`:77`), i.e. `r <= -0.15` — **inclusif** ;
    seule la **première** occurrence est mémorisée (`if jour_stop is None and …`, `:77`) ;
  - **palier** : première séance `j` où `r >= p` (`:80`) — **inclusif** — pour chaque palier.
- **« palier avant stop »** : `atteint and (jour_stop is None or jours_palier[p] < jour_stop)`
  (`:108`) — le palier doit être atteint à une séance **strictement antérieure** à celle du
  stop. Si le stop n'est jamais touché, tout palier touché compte. Si palier et stop sont
  touchés **le même jour**, ce n'est **pas** « avant ».
- Colonnes exportées : `p{20,35,50}_touche` (brut), `p{20,35,50}_avant_stop` (exécutable),
  `p{20,35,50}_jour`, `stop_15_touche`, `jours_avant_stop` (`:106-111`).
- **Cas limite flottant** (à connaître, pas un bug intentionnel) : `120.0/100.0 - 1 =
  0.19999999999999996 < 0.20` → un palier touché **exactement** à +20,00 % n'est **pas**
  compté ; en revanche `85.0/100.0 - 1 = -0.15000000000000002 <= -0.15` → un stop
  **exactement** à −15,00 % **est** compté. Voir §8.5.

---

## 7. Tableau de traçabilité

| Règle | Où |
|---|---|
| RSI période 14 (paramètre par défaut) | `src/strategie/spec_profiles.py:40` |
| RSI amorçage moyenne simple sur 14 variations | `src/strategie/spec_profiles.py:47-52` |
| RSI lissage de Wilder | `src/strategie/spec_profiles.py:53-56` |
| RSI = 100 si aucune perte (`avg_l == 0`) | `src/strategie/spec_profiles.py:52` et `:56` |
| RSI = 0 si aucun gain (conséquence `avg_g/avg_l = 0`) | `src/strategie/spec_profiles.py:52` et `:56` |
| RSI non arrondi (flottant brut) | `src/strategie/spec_profiles.py:52` et `:56` |
| RSI première valeur valide à l'index 14 | `src/strategie/spec_profiles.py:44-51` |
| Garde `len(closes) < 260` ou `closes[-1] <= 0` | `src/strategie/spec_profiles.py:70` |
| CASSURE : `closes[i] > max(closes[i-250:i])` (strict) | `src/strategie/spec_profiles.py:75` |
| EVEIL : `creux60 = min(closes[i-60:i])` | `src/strategie/spec_profiles.py:88` |
| EVEIL : `closes[i]/creux60 - 1 >= 0.10` (inclusif) | `src/strategie/spec_profiles.py:89` |
| PANIQUE : `rsi(closes)[i] < 30` (strict) | `src/strategie/spec_profiles.py:100-101` |
| PANIQUE sans filtre volume | `src/strategie/spec_profiles.py:99-102` |
| Filtre volume : `med = median(volumes[-61:-1])` | `src/strategie/spec_profiles.py:78` et `:92` |
| Filtre volume : `med > 0 and volumes[i] >= med` | `src/strategie/spec_profiles.py:82` et `:96` |
| Filtre volume sauté si `volumes` absent/désaligné | `src/strategie/spec_profiles.py:77` et `:91` |
| Filtre volume appliqué en production | `src/strategie/spec_fiche.py:177` ; `src/strategie/spec_veille.py:113,125` |
| Filtre volume absent des backtests | `scripts/calibrate_spec_profiles.py:75` ; `scripts/exporter_cas_spec.py:66` |
| `zone_of` : fenêtre ≤ 1260 séances + position min-max | `src/strategie/spec_profiles.py:106-113` |
| `zone_label` seuils 0,20/0,40/0,60/0,80 | `src/strategie/spec_profiles.py:116-125` |
| Tranches 0-20…80-100 et `lo <= zone < hi` | `scripts/calibrate_spec_profiles.py:51-60` ; `scripts/exporter_cas_spec.py:35-43` |
| `HORIZON = 252` | `src/strategie/spec_profiles.py:27` |
| `FRAIS = FRAIS_ALLER_RETOUR` (import) | `src/strategie/spec_profiles.py:26` |
| `FRAIS_ALLER_RETOUR = 2 * FRAIS_PAR_SENS` = 0,028 | `src/regles.py:57` |
| `FRAIS_PAR_SENS = BROKERAGE_FEE` = 0,014 | `src/regles.py:56` |
| `BROKERAGE_FEE = 0,008 × 1,18 + 0,00456` | `src/taxation.py:29` |
| `FRAIS_MINIMUM = 1 000 F` | `src/regles.py:58` ; `src/taxation.py:25` |
| Univers : `len(closes) < 500 or closes[0] <= 0` écarté | `scripts/calibrate_spec_profiles.py:71` ; `scripts/exporter_cas_spec.py:62` |
| Boucle `range(260, len - HORIZON)` | `scripts/calibrate_spec_profiles.py:74` ; `scripts/exporter_cas_spec.py:65` |
| Espacement `ESPACEMENT = 60` | `scripts/calibrate_spec_profiles.py:53` ; `scripts/exporter_cas_spec.py:34` |
| Espacement par titre ET par schéma (`last_entry` par titre) | `scripts/calibrate_spec_profiles.py:73,82,89` ; `scripts/exporter_cas_spec.py:64,86,88` |
| Rendement 12 m net `closes[i+252]/closes[i] - 1 - FRAIS` | `scripts/calibrate_spec_profiles.py:78` ; `scripts/exporter_cas_spec.py:82` |
| Pic (mesure « touché » brute) sur les 252 séances après signal | `scripts/calibrate_spec_profiles.py:79` ; `scripts/exporter_cas_spec.py:83` |
| `STOP = 0.15`, `PALIERS = (0.20, 0.35, 0.50)` | `scripts/exporter_cas_spec.py:32-33` |
| Stop : première séance `r <= -0.15` (inclusif) | `scripts/exporter_cas_spec.py:77` |
| Palier : première séance `r >= p` (inclusif) | `scripts/exporter_cas_spec.py:80` |
| « avant le stop » = séance strictement antérieure | `scripts/exporter_cas_spec.py:108` |
| `SEUIL_CAS_ZONE = 10` (aucune conclusion sous 10 cas) | `src/strategie/spec_fiche.py:40` |
| Couleur du verdict : ≥ 60 % ✅ · ≥ 50 % 🟡 · sinon 🔴 | `src/strategie/spec_fiche.py:98-104` |
| Schéma « principal » de la fiche : CASSURE > EVEIL > PANIQUE | `src/strategie/spec_fiche.py:27` et `:180-186` |

---

## 8. Preuves d'exécution (sorties réelles du Python du projet)

Python : `C:/Users/LEO/AppData/Local/hermes/hermes-agent/venv/Scripts/python`.
Toutes les sorties ci-dessous sont copiées telles quelles des exécutions de ce jour.

### 8.1 RSI — valeur sans perte et série plate

```
FRAIS (aller-retour): 0.028
HORIZON: 252
serie monotone croissante (aucune perte) -> rsi[14] = 100.0 (index 14 )
serie plate -> rsi[-1] = 100.0 (plate => 100.0 aussi, pas 50)
```

### 8.2 CASSURE (`>`) et EVEIL (`>=`) — inclusive ou exclusive

```
dernier close == max(250 precedentes) -> []
dernier close 50.01 > max 50.0        -> ['CASSURE']
creux60=100, dernier=110 (ratio==0.10 exact) -> ['EVEIL']
creux60=100, dernier=109.99 (ratio 0.0999)    -> []
```

→ CASSURE **exclusive** (égal → rien) ; EVEIL **inclusive** (+10,00 % exact → EVEIL).

### 8.3 PANIQUE (`< 30` strict)

```
CROISEMENT ASCENDANT: x=84.30589 RSI=29.999965 | x=84.30590 RSI=30.000013
  RSI< 30 -> detect: ['PANIQUE']
  RSI>=30 -> detect: []
```

→ RSI 29,999965 (< 30) déclenche ; RSI 30,000013 (≥ 30) ne déclenche pas : **strict**.

### 8.4 Volume, espacement, garde de longueur

```
vol jour 500 < mediane 1000 -> []
vol jour 1000 == mediane    -> ['CASSURE', 'EVEIL']
mediane nulle (illiquide)    -> []
sans volumes (None)          -> ['CASSURE', 'EVEIL']

indices ou le schema est actif : [260, 261, 262, 300, 320, 380, 381]
cas RETENUS (espaces de >=60)   : [260, 320, 380]

len 260 -> ['CASSURE', 'EVEIL']
len 259 -> []
```

→ volume du jour = médiane **passe** (`>=`) ; médiane nulle **refuse** ; sans volumes,
**aucun filtre**. Espacement : le **premier cas (260) est gardé** ; 320 est gardé car
`320 - 260 == 60` (pas `< 60`) ; 300 et 381 écartés. Garde : 259 clôtures → rien.

### 8.5 Stop / palier, « avant le stop », et cas limite flottant

```
A: [105.0, 121.0, 95.0, 85.0, 90.0] -> stop j= 4 paliers j= {0.2: 2} | p20_avant_stop = True
B: [85.0, 121.0] -> stop j= 1 paliers j= {0.2: 2} | p20_touche = True | p20_avant_stop = False
D: [121.0, 85.0] -> stop j= 2 paliers j= {0.2: 1} | p20_avant_stop = True

120.0/100.0 - 1 = 0.19999999999999996 >= 0.20 ? False
135.0/100.0 - 1 = 0.3500000000000001 >= 0.35 ? True
85.0/100.0 - 1 = -0.15000000000000002 <= -0.15 ? True
```

→ « avant le stop » = séance **strictement** antérieure (B : palier j2 après stop j1 → non).
Stop −15 % **inclusif** (exactement −15 % est compté). Palier +20 % : un cours **exactement**
à +20,00 % n'est pas compté (flottant `0.19999… < 0.20`) alors que +35,00 % l'est.

---

## 9. Divergences relevées avec `LISEZ-MOI.md`

1. **`LISEZ-MOI.md:106-109` (Limite 1) — CORRECTION.** Il affirme que l'export lit
   `data/history_clean.pkl` via `charger_cache` **alors que** le calibrage passe par
   `load_all_history(BSApi())`, avec un écart « 414 vs 421 ». C'est **périmé** : le calibrage
   lit désormais `charger_historique_propre()` (`calibrate_spec_profiles.py:31`), qui renvoie
   `charger_cache(HISTORY_CACHE)` (`src/collecte/preparation.py:91`) — **le même cache propre**
   que l'export (`exporter_cas_spec.py:52`). Les deux univers sont identiques (414 cas PANIQUE,
   cf. `CONTRAT-7-AGENTS.md:15`). Idem pour « univers légèrement différent » en
   `LISEZ-MOI.md:4`.
2. **`LISEZ-MOI.md:41` — imprécis** : « RSI = moyenne des hausses / moyenne des baisses »
   omet l'amorçage + lissage de Wilder et les cas limites (aucune perte → 100, aucun gain → 0,
   série plate → 100). Voir §1.
3. **`LISEZ-MOI.md:32-33` — à préciser** : EVEIL est « +10 % » **inclusif** (`>= 0.10`) ;
   un rebond exactement de +10,00 % déclenche. La fenêtre du creux est les 60 séances
   précédant la dernière (indices `[i-60, i-1]`).
4. **`LISEZ-MOI.md:28` — correct** : le filtre volume n'est appliqué ni dans l'export ni
   dans le calibrage ; il ne l'est qu'en production (`spec_fiche.py:177`).

---

## 10. Ce que ce signal ne dit pas (lectures trompeuses à écarter)

- **Ce n'est pas une stratégie d'exécution.** `detect_schemas` détecte une situation sur la
  **dernière** séance. Il ne définit ni le prix d'entrée, ni la taille de position, ni
  l'ordre de sortie. Le stop −15 % et les paliers +20/+35/+50 % n'existent **que** dans
  `exporter_cas_spec.py` : ce sont des **seuils de mesure du backtest**, pas des ordres
  réellement passés.
- **« Touché » ≠ « gagné ».** La colonne `pXX_touche` (et le `touched` du calibrage,
  `calibrate_spec_profiles.py:101`) mesure le pic atteint **un jour** sur 12 mois, sans stop.
  La mesure exécutable est `pXX_avant_stop` (`exporter_cas_spec.py:108`), toujours plus basse.
- **Le filtre volume est absent du backtest.** Les cas exportés/calibrés sont détectés sur le
  **prix seul** ; la production, elle, exige le volume (`spec_fiche.py:177`). Le nombre de cas
  backtestés surestime le nombre de signaux réellement publiés.
- **`zone_minmax` n'est pas un percentile.** Position dans la fourchette min-max 5 ans
  (`spec_profiles.py:113`) ; la colonne `percentile_rang` (`exporter_cas_spec.py:46-49`) est
  un autre nombre, exporté pour comparaison, non utilisé pour classer.
- **Biais de survie.** Seuls les titres présents dans le cache apparaissent ; les radiés/
  suspendus/liquidés sont absents. Les taux sont optimistes (source : `spec_fiche.py:33-35`).
- **Pas d'indépendance.** L'espacement de 60 réduit la redondance sans l'éliminer ; plusieurs
  cas peuvent refléter le même choc de marché.
- **Les frais sont forfaitaires** (2,8 %) et ignorent le minimum de 1 000 F par ordre
  (`src/regles.py:58`) : sous ~125 000 F par ordre, le coût réel dépasse 2,8 %.
- **Le RSI a deux cas limites contre-intuitifs** : aucune perte → 100,0 ; aucune variation
  (série plate) → 100,0 (pas 50) ; aucun gain → 0,0.
- **Sous 10 cas (`SEUIL_CAS_ZONE = 10`), aucune conclusion chiffrée** n'est tirée d'une zone
  ou d'un schéma (`spec_fiche.py:40`, `:98-104`) : un « 100 % sur 2 cas » ne vaut rien.
- **Le schéma « principal » affiché sur une fiche** n'est pas le détecteur : c'est une
  priorité d'affichage CASSURE > EVEIL > PANIQUE (`spec_fiche.py:27`, `:180-186`), alors
  qu'un titre peut cocher les trois le même jour.
- **Aucune exécution réelle simulée** : le stop est supposé rempli à −15 % au cours de
  clôture ; gap, séance sans contrepartie ou exécution partielle donnent un autre résultat.
- **Le paramétrage des tranches de zone** (0-20, 20-40…) n'est pas documenté comme validé
  hors période ; le risque de surapprentissage n'est pas exclu par ces fichiers.
