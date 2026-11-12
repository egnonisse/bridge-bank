# Impact de la définition d'horizon sur les taux de la veille spéculative

Cas analysés : **1615** · non appariables : 0

Deux définitions, mêmes cas : **A** = 252 séances après le signal (définition publiée jusqu'ici) · **B** = toutes les séances jusqu'à **365 jours calendaires** après le signal.


## 1. Combien de séances tient réellement une année calendaire ?

- médiane **240** séances · min 69 · max 249
- cas où la fenêtre calendaire contient MOINS de 252 séances : **1615** (100.0 %)
- cas où elle en contient PLUS : **0** (0.0 %)

## 2. Taux par schéma — les deux définitions

| Schéma | n | Médiane A (252 séances) | Médiane B (365 j) | Écart | Réussite A | Réussite B | +20 % avant stop A → B | Stop touché A → B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **CASSURE** | 267 | +16.3 % | +17.1 % | +0.8 pt | 65.9 % | 68.2 % | 62 % → 61 % | 38 % → 37 % |
| **EVEIL** | 934 | +5.9 % | +3.5 % | -2.4 pt | 55.6 % | 54.2 % | 52 % → 51 % | 50 % → 49 % |
| **PANIQUE** | 414 | +3.2 % | -0.6 % | -3.8 pt | 52.2 % | 49.3 % | 46 % → 45 % | 56 % → 55 % |

## 3. Écart apparié cas par cas

| Schéma | n | Écart moyen de rendement | Écart médian | Cas où B > A | Cas où B < A | Écart > 5 pts |
|---|---:|---:|---:|---:|---:|---:|
| CASSURE | 267 | +0.30 pt | +0.00 pt | 127 | 125 | 114 |
| EVEIL | 934 | -6.46 pt | +0.00 pt | 440 | 443 | 448 |
| PANIQUE | 414 | -12.34 pt | -0.39 pt | 182 | 213 | 208 |

## 4. Le verdict change-t-il ?

| Schéma | Verdict avec A | Verdict avec B | Stable ? |
|---|---|---|---|
| CASSURE | favorable (+16.3 %) | favorable (+17.1 %) | OUI |
| EVEIL | favorable (+5.9 %) | neutre (+3.5 %) | **NON** |
| PANIQUE | neutre (+3.2 %) | défavorable (-0.6 %) | **NON** |

## 5. Par zone (définition B)

| Schéma | Zone | n | Médiane B | Réussite B | IC 95 % (Wilson) | +20 % avant stop |
|---|---|---:|---:|---:|---|---:|
| CASSURE | 0-20 | 35 | +32.9 % | 77.1 % | [61.0 ; 87.9] | 74 % |
| CASSURE | 20-40 | 51 | +14.0 % | 74.5 % | [61.1 ; 84.5] | 63 % |
| CASSURE | 40-60 | 41 | +13.4 % | 61.0 % | [45.7 ; 74.3] | 49 % |
| CASSURE | 60-80 | 30 | +32.6 % | 73.3 % | [55.6 ; 85.8] | 67 % |
| CASSURE | 80-100 | 110 | +10.1 % | 63.6 % | [54.3 ; 72.0] | 59 % |
| EVEIL | 0-20 | 352 | +1.5 % | 54.0 % | [48.8 ; 59.1] | 52 % |
| EVEIL | 20-40 | 181 | -0.9 % | 49.2 % | [42.0 ; 56.4] | 49 % |
| EVEIL | 40-60 | 146 | +0.0 % | 50.0 % | [42.0 ; 58.0] | 40 % |
| EVEIL | 60-80 | 99 | +8.7 % | 59.6 % | [49.7 ; 68.7] | 58 % |
| EVEIL | 80-100 | 156 | +8.9 % | 60.9 % | [53.1 ; 68.2] | 59 % |
| PANIQUE | 0-20 | 221 | -2.6 % | 47.1 % | [40.6 ; 53.6] | 44 % |
| PANIQUE | 20-40 | 81 | -2.1 % | 48.1 % | [37.6 ; 58.9] | 44 % |
| PANIQUE | 40-60 | 50 | -2.0 % | 50.0 % | [36.6 ; 63.4] | 46 % |
| PANIQUE | 60-80 | 43 | +0.7 % | 51.2 % | [36.8 ; 65.4] | 44 % |
| PANIQUE | 80-100 | 19 | +15.9 % | 73.7 % | [51.2 ; 88.2] | 68 % |

## 6. Ce que ce recalcul ne change pas

- Les **cas** eux-mêmes (1 615) et leur date de signal : inchangés.
- Les **cours** d'entrée : inchangés, concordants à 99,3 % avec l'API indépendante.
- Le **stop** (−15 %) et les **paliers** (+20/+35/+50 %) : inchangés.
- Le **manque de 48 séances** dans le cache : ce recalcul le rend inoffensif sur la date de fin, mais il peut encore décaler le RSI et les fenêtres de création du signal — ce point reste ouvert.