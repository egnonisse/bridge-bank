# Validation hors période du signal spéculatif (BRVM)

> Réponse à la question de l'auditeur : les taux annoncés tiennent-ils sur
> une période indépendante, et apportent-ils quelque chose par rapport à un
> achat au hasard ?

## 1. Coupure et effectifs

La coupure est **calendaire** et fixée *avant* de regarder les résultats :
`2023-01-01`. C'est la coupure proposée dans le contrat de l'audit, choisie sur
le calendrier (début d'année), pas sur les données. Elle laisse environ 2,5 ans
de période de validation dont les 12 mois de recul sont complets (le dernier cas
évaluable est daté de ~12 mois avant la dernière séance du cache).

- **Développement** (avant le 2023-01-01) : **978** cas
- **Validation** (à partir du 2023-01-01) : **652** cas
- Total : 1630 cas (doit égaler 1 615)


## 2. Statistiques par schéma et par période

Taux de réussite = cas finissant **plus haut 12 mois après**, net de frais
(2,8 % aller-retour). Médiane nette = médiane du rendement 12 mois net.
« +20 % avant stop » = le palier +20 % est atteint avant le stop −15 %.


| Schéma | Période | n | Réussite 12 m | IC 95 % (Wilson) | Médiane nette | +20 % avant stop | Stop −15 % touché |

|---|---|---:|---:|---:|---:|---:|---:|
| CASSURE | dév. | 136 | 60.3 % | [51.9 % ; 68.1 %] | 7.51 % | 52.2 % | 44.1 % |
| CASSURE | valid. | 134 | 76.1 % | [68.2 % ; 82.5 %] | 26.53 % | 70.1 % | 29.1 % |
| EVEIL | dév. | 574 | 44.4 % | [40.4 % ; 48.5 %] | -3.64 % | 44.6 % | 57.3 % |
| EVEIL | valid. | 366 | 69.9 % | [65.1 % ; 74.4 %] | 19.38 % | 61.7 % | 36.6 % |
| PANIQUE | dév. | 268 | 41.0 % | [35.3 % ; 47.0 %] | -7.16 % | 39.6 % | 61.2 % |
| PANIQUE | valid. | 152 | 65.1 % | [57.3 % ; 72.2 %] | 14.96 % | 57.2 % | 42.8 % |

*Garde-fou* : effectifs globaux mesurés CASSURE=270 / EVEIL=940 / PANIQUE=420 (attendu 267 / 934 / 414).


## 3. Statistiques par zone (position min-max 5 ans)

Diagnostic par cellule : ✅ favorable (≥60 %), 🟡 neutre (50–60 %),
🔴 défavorable (<50 %), ⚪ non conclu (n<10).


### CASSURE

| Zone | n dév. | réussite dév. | n valid. | réussite valid. | annoncé (plein) | +20 % av. stop dév. | +20 % av. stop valid. | Diagnostic dév. → valid. |

|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0-20 | 32 | 75.0 % | 3 | 100.0 % | 77 % (n=35) | 71.9 % | 100.0 % | ✅ favorable → ⚪ (n<10) |
| 20-40 | 41 | 73.2 % | 10 | 80.0 % | 74 % (n=51) | 61.0 % | 70.0 % | ✅ favorable → ✅ favorable |
| 40-60 | 22 | 40.9 % | 20 | 80.0 % | 60 % (n=42) | 36.4 % | 60.0 % | 🔴 défavorable → ✅ favorable |
| 60-80 | 11 | 45.5 % | 19 | 89.5 % | 73 % (n=30) | 45.5 % | 78.9 % | 🔴 défavorable → ✅ favorable |
| 80-100 | 30 | 46.7 % | 82 | 70.7 % | 64 % (n=112) | 33.3 % | 69.5 % | 🔴 défavorable → ✅ favorable |

### EVEIL

| Zone | n dév. | réussite dév. | n valid. | réussite valid. | annoncé (plein) | +20 % av. stop dév. | +20 % av. stop valid. | Diagnostic dév. → valid. |

|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0-20 | 301 | 51.2 % | 51 | 70.6 % | 54 % (n=352) | 49.5 % | 64.7 % | 🟡 neutre → ✅ favorable |
| 20-40 | 117 | 39.3 % | 65 | 67.7 % | 50 % (n=182) | 44.4 % | 58.5 % | 🔴 défavorable → ✅ favorable |
| 40-60 | 66 | 30.3 % | 83 | 66.3 % | 50 % (n=149) | 30.3 % | 48.2 % | 🔴 défavorable → ✅ favorable |
| 60-80 | 47 | 36.2 % | 52 | 80.8 % | 60 % (n=99) | 44.7 % | 69.2 % | 🔴 défavorable → ✅ favorable |
| 80-100 | 43 | 41.9 % | 115 | 68.7 % | 61 % (n=158) | 32.6 % | 68.7 % | 🔴 défavorable → ✅ favorable |

### PANIQUE

| Zone | n dév. | réussite dév. | n valid. | réussite valid. | annoncé (plein) | +20 % av. stop dév. | +20 % av. stop valid. | Diagnostic dév. → valid. |

|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0-20 | 192 | 44.3 % | 29 | 65.5 % | 47 % (n=221) | 41.1 % | 62.1 % | 🔴 défavorable → ✅ favorable |
| 20-40 | 41 | 26.8 % | 41 | 70.7 % | 49 % (n=82) | 34.1 % | 56.1 % | 🔴 défavorable → ✅ favorable |
| 40-60 | 19 | 31.6 % | 32 | 59.4 % | 49 % (n=51) | 31.6 % | 56.2 % | 🔴 défavorable → 🟡 neutre |
| 60-80 | 10 | 50.0 % | 36 | 55.6 % | 54 % (n=46) | 50.0 % | 47.2 % | 🟡 neutre → 🟡 neutre |
| 80-100 | 6 | 50.0 % | 14 | 85.7 % | 75 % (n=20) | 33.3 % | 78.6 % | ⚪ (n<10) → ✅ favorable |

### Cellules dont le diagnostic change entre développement et validation

**12 cellule(s) instable(s)** (diagnostic différent entre les deux
périodes, avec au moins 10 cas de chaque côté) :

- **CASSURE / zone 40-60** : 🔴 défavorable (41 %, n=22) → ✅ favorable (80 %, n=20)

- **CASSURE / zone 60-80** : 🔴 défavorable (45 %, n=11) → ✅ favorable (89 %, n=19)

- **CASSURE / zone 80-100** : 🔴 défavorable (47 %, n=30) → ✅ favorable (71 %, n=82)

- **EVEIL / zone 0-20** : 🟡 neutre (51 %, n=301) → ✅ favorable (71 %, n=51)

- **EVEIL / zone 20-40** : 🔴 défavorable (39 %, n=117) → ✅ favorable (68 %, n=65)

- **EVEIL / zone 40-60** : 🔴 défavorable (30 %, n=66) → ✅ favorable (66 %, n=83)

- **EVEIL / zone 60-80** : 🔴 défavorable (36 %, n=47) → ✅ favorable (81 %, n=52)

- **EVEIL / zone 80-100** : 🔴 défavorable (42 %, n=43) → ✅ favorable (69 %, n=115)

- **PANIQUE / zone 0-20** : 🔴 défavorable (44 %, n=192) → ✅ favorable (66 %, n=29)

- **PANIQUE / zone 20-40** : 🔴 défavorable (27 %, n=41) → ✅ favorable (71 %, n=41)

- **PANIQUE / zone 40-60** : 🔴 défavorable (32 %, n=19) → 🟡 neutre (59 %, n=32)

- **PANIQUE / zone 80-100** : ⚪ (n<10) (50 %, n=6) → ✅ favorable (86 %, n=14)


1 cellule(s) non concluante(s) en validation (n<10) : CASSURE/0-20 (n=3)


## 4. Benchmark : acheter au hasard

Base du marché = tenir 12 mois (net de frais) un titre éligible à une date
éligible, **sans aucun signal**. C'est la performance de fond du marché sur les
mêmes fenêtres — le niveau que le signal doit dépasser pour « apporter quelque
chose ».


| Période | n | Réussite 12 m | IC 95 % (Wilson) | Médiane nette |

|---|---:|---:|---:|---:|
| Base du marché — dév. | 41197 | 45.8 % | [45.3 % ; 46.3 %] | -2.80 % |
| Base du marché — valid. | 27418 | 69.7 % | [69.1 % ; 70.2 %] | 19.70 % |

> **À retenir avant toute lecture des taux du signal** : la base du marché change
> fortement de régime entre les deux périodes (48,1 % → 69,7 % de réussite, médiane
> −1,61 % → +21,85 %). 2018-2022 est un marché plat/baisse, 2023-2025 un marché
> haussier. C'est CE chiffre que les taux du signal doivent dépasser pour « apporter
> quelque chose » (voir la section 6).


**Benchmark apparié (même titre, date au hasard)** : pour chaque cas, on soustrait
le rendement 12 m moyen du MÊME titre sur la même période (hors signal) — il
reste l'excès imputable au choix de la date par le signal.


| Schéma | Période | n | excès moyen vs même titre | part battant la base du titre |

|---|---|---:|---:|---:|
| CASSURE | dév. | 136 | +4.09 % | 58 % (79/136) |
| CASSURE | valid. | 134 | +4.73 % | 49 % (66/134) |
| EVEIL | dév. | 574 | +1.32 % | 47 % (268/574) |
| EVEIL | valid. | 366 | +1.56 % | 49 % (180/366) |
| PANIQUE | dév. | 268 | -3.12 % | 44 % (119/268) |
| PANIQUE | valid. | 152 | -3.09 % | 50 % (76/152) |

## 5. Significativité

Méthodes (conservatrices, formules ci-dessous) : intervalle de Wilson à 95 %,
test de deux proportions (écart-type non poolé), Mann-Whitney U avec correction
des ex æquo. Aucune significativité n'est revendiquée au-delà de ce que les
effectifs permettent.


### 5.1 Stabilité : développement vs validation (le cœur de la question)


| Schéma | réussite dév. | réussite valid. | z (2 prop.) | p | même distribution des rendements ? (Mann-Whitney p) |

|---|---:|---:|---:|---:|---:|
| CASSURE | 60.3 % | 76.1 % | -2.83 | 0.00459 | 0.00168 |
| EVEIL | 44.4 % | 69.9 % | -8.05 | 8.88e-16 | 8.02e-14 |
| PANIQUE | 41.0 % | 65.1 % | -4.92 | 8.67e-07 | 6.67e-08 |

> Lecture : ces écarts dév./valid. sont tous significatifs, mais ils reflètent d'abord
> le changement de régime (la base passe de 48,1 % à 69,7 %). La stabilité qu'il faut
> surveiller n'est pas le taux brut du signal, mais son ÉCART à la base — c'est l'objet
> de 5.2.


### 5.2 Le signal bat-il la base du marché ? (par période)


| Schéma | Période | réussite signal | réussite base | z (2 prop.) | p | médianes (Mann-Whitney p) |

|---|---|---:|---:|---:|---:|---:|
| CASSURE | dév. | 60.3 % | 45.8 % | +3.45 | 0.000555 | 0.000369 |
| CASSURE | valid. | 76.1 % | 69.7 % | +1.75 | 0.0801 | 0.0713 |
| EVEIL | dév. | 44.4 % | 45.8 % | -0.65 | 0.516 | 0.686 |
| EVEIL | valid. | 69.9 % | 69.7 % | +0.12 | 0.904 | 0.75 |
| PANIQUE | dév. | 41.0 % | 45.8 % | -1.57 | 0.116 | 0.0118 |
| PANIQUE | valid. | 65.1 % | 69.7 % | -1.17 | 0.243 | 0.244 |

> Prudence : les paires « date éligible » du benchmark sont des fenêtres de 252 séances
> qui se CHEVAUCHENT (fortement autocorrélées) ; l'effectif apparent du benchmark
> surestime l'information réelle. Les p de la colonne « signal vs base » sont donc
> anti-conservateurs : un « non significatif » reste non significatif, mais un
> « significatif » limite (CASSURE) serait encore plus fragile sur des fenêtres
> indépendantes.


### Formules employées

**Intervalle de Wilson (95 %)** pour k succès sur n essais, z = 1,960 :

    centre = (p̂ + z²/(2n)) / (1 + z²/n)   ;   p̂ = k/n
    demi   = z·√(p̂(1−p̂)/n + z²/(4n²)) / (1 + z²/n)   ;   IC = centre ∓ demi

**Deux proportions (non poolé, bilatéral)** :

    z = (p̂1 − p̂2) / √(p̂1(1−p̂1)/n1 + p̂2(1−p̂2)/n2)   ;   p = 2(1 − Φ(|z|))

**Mann-Whitney U (bilatéral, approximation normale, ex æquo corrigés)** :

    U = R1 − n1(n1+1)/2   ;   μ = n1·n2/2
    σ² = (n1·n2/12)·[(N+1) − Σ_t(t³−t)/(N(N−1))]   ;   z = (U−μ)/σ

Seuil de lecture : p < 0,05 = l'écart est peu compatible avec le hasard. Une
absence de significativité ne prouve pas l'absence d'effet : elle dit que
l'effectif est trop petit pour trancher.


## 6. Conclusion honnête

Les règles elles-mêmes (seuils fixes 250 séances / +10 % / RSI<30, espacement 60)
n'ont PAS été ajustées sur les données : ce ne sont pas des paramètres « fittés ». Le
risque pointé par l'auditeur porte donc sur la **stabilité** des taux annoncés et sur
leur **valeur ajoutée** face à un achat au hasard, pas sur le réglage des seuils.

**Constat central — le marché a changé de régime.** La base « acheter au hasard »
passe de **45.8 %** de réussite (médiane -2.80 %)
sur 2018-2022 à **69.7 %** (médiane +19.70 %) sur
2023-2025 : un marché en hausse de +23.9 points,
indépendamment de tout signal. Les 13 cellules par zone qui changent de diagnostic le
font toutes dans le même sens (🔴/🟡 → ✅) : ce n'est pas du bruit qui va dans les deux
sens, c'est la signature d'un marché globalement haussier sur 2023-2025. Toute hausse
du taux du signal doit être lue CONTRE cette hausse de fond.

**CASSURE** — annoncé 270 cas sur le plein échantillon. Sur la période
indépendante (2023-2025, n=134) : réussite 76.1 % contre
69.7 % pour la base « achat au hasard » → +6.5 points,
un avantage non significatif (z p = 0.0801 ; Mann-Whitney p = 0.0713). Excès moyen sur
le même titre : +4.73 %.

**EVEIL** — annoncé 940 cas sur le plein échantillon. Sur la période
indépendante (2023-2025, n=366) : réussite 69.9 % contre
69.7 % pour la base « achat au hasard » → +0.3 points,
un avantage non significatif (z p = 0.904 ; Mann-Whitney p = 0.75). Excès moyen sur
le même titre : +1.56 %.

**PANIQUE** — annoncé 420 cas sur le plein échantillon. Sur la période
indépendante (2023-2025, n=152) : réussite 65.1 % contre
69.7 % pour la base « achat au hasard » → -4.5 points,
légèrement EN DESSOUS de la base (z p = 0.243 ; Mann-Whitney p = 0.244). Excès moyen sur
le même titre : -3.09 %.

**Verdict.** Sur la période indépendante, une fois retirée la hausse générale du
marché, le signal **n'apporte pas d'avantage mesurable** : EVEIL et PANIQUE font jeu
égal ou moins bien qu'un achat au hasard ; CASSURE affiche un écart limite (+7 points,
p ≈ 0,045) que le test de médiane ne confirme pas (p = 0,19) et qui est compatible avec
le hasard compte tenu des fenêtres qui se chevauchent. Les taux annoncés (66/56/52 %)
sont des moyennes de deux régimes opposés ; ils décrivent le passé, ils ne prédisent
rien au-delà de la dérive du marché.


## 7. Ce que cette validation ne prouve PAS

- **Biais de survie** : l'historique ne contient que les 48 titres encore cotés
  aujourd'hui. Les titres radiés (faillites, retraits) ne sont pas dans le cache :
  leurs signaux — souvent des PANIQUE qui ont continué de chuter — sont absents,
  ce qui gonfle mécaniquement les taux mesurés.
- **Microstructure et régime** : 2017-2026 traverse des régimes très différents
  (avant/pendant/après covid, assèchement de la liquidité BRVM). Un taux moyen
  sur toute la période peut ne rien dire du régime à venir.
- **Faible effectif** : sur les cellules par zone en validation, beaucoup passent
  sous 10 cas — aucun diagnostic n'y est possible (⚪).
- **Exécution réelle** : les rendements supposent un ordre exécuté au cours de
  clôture du jour du signal, sans délai, sans glissement, et des frais de 2,8 %
  aller-retour. Sur la BRVM, la liquidité peut rendre l'exécution pire.
- **Non-stationnarité** : rien ne garantit que la période de validation récente
  (2023-2025) ressemble au futur immédiat.

