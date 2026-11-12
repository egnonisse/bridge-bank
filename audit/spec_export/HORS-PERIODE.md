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
- **Validation** (à partir du 2023-01-01) : **637** cas
- Total : 1615 cas (doit égaler 1 615)


## 2. Statistiques par schéma et par période

Taux de réussite = cas finissant **plus haut 12 mois après**, net de frais
(2,8 % aller-retour). Médiane nette = médiane du rendement 12 mois net.
« +20 % avant stop » = le palier +20 % est atteint avant le stop −15 %.


| Schéma | Période | n | Réussite 12 m | IC 95 % (Wilson) | Médiane nette | +20 % avant stop | Stop −15 % touché |

|---|---|---:|---:|---:|---:|---:|---:|
| CASSURE | dév. | 136 | 55.1 % | [46.8 % ; 63.2 %] | 4.51 % | 52.2 % | 44.1 % |
| CASSURE | valid. | 131 | 77.1 % | [69.2 % ; 83.5 %] | 27.30 % | 71.8 % | 31.3 % |
| EVEIL | dév. | 574 | 47.2 % | [43.2 % ; 51.3 %] | -2.43 % | 44.8 % | 58.4 % |
| EVEIL | valid. | 360 | 68.9 % | [63.9 % ; 73.5 %] | 22.63 % | 62.8 % | 36.9 % |
| PANIQUE | dév. | 268 | 44.8 % | [38.9 % ; 50.8 %] | -6.97 % | 40.3 % | 61.2 % |
| PANIQUE | valid. | 146 | 65.8 % | [57.7 % ; 73.0 %] | 13.43 % | 56.8 % | 45.9 % |

*Garde-fou* : effectifs globaux mesurés CASSURE=267 / EVEIL=934 / PANIQUE=414 (attendu 267 / 934 / 414).


## 3. Statistiques par zone (position min-max 5 ans)

Diagnostic par cellule : ✅ favorable (≥60 %), 🟡 neutre (50–60 %),
🔴 défavorable (<50 %), ⚪ non conclu (n<10).


### CASSURE

| Zone | n dév. | réussite dév. | n valid. | réussite valid. | annoncé (plein) | +20 % av. stop dév. | +20 % av. stop valid. | Diagnostic dév. → valid. |

|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0-20 | 32 | 75.0 % | 3 | 100.0 % | 77 % (n=35) | 71.9 % | 100.0 % | ✅ favorable → ⚪ (n<10) |
| 20-40 | 41 | 56.1 % | 10 | 90.0 % | 63 % (n=51) | 61.0 % | 70.0 % | 🟡 neutre → ✅ favorable |
| 40-60 | 22 | 40.9 % | 19 | 84.2 % | 61 % (n=41) | 36.4 % | 63.2 % | 🔴 défavorable → ✅ favorable |
| 60-80 | 11 | 45.5 % | 19 | 89.5 % | 73 % (n=30) | 45.5 % | 78.9 % | 🔴 défavorable → ✅ favorable |
| 80-100 | 30 | 46.7 % | 80 | 70.0 % | 64 % (n=110) | 33.3 % | 71.2 % | 🔴 défavorable → ✅ favorable |

### EVEIL

| Zone | n dév. | réussite dév. | n valid. | réussite valid. | annoncé (plein) | +20 % av. stop dév. | +20 % av. stop valid. | Diagnostic dév. → valid. |

|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0-20 | 301 | 53.5 % | 51 | 70.6 % | 56 % (n=352) | 49.8 % | 68.6 % | 🟡 neutre → ✅ favorable |
| 20-40 | 117 | 41.0 % | 64 | 65.6 % | 50 % (n=181) | 44.4 % | 57.8 % | 🔴 défavorable → ✅ favorable |
| 40-60 | 66 | 33.3 % | 80 | 65.0 % | 51 % (n=146) | 30.3 % | 50.0 % | 🔴 défavorable → ✅ favorable |
| 60-80 | 47 | 36.2 % | 52 | 80.8 % | 60 % (n=99) | 44.7 % | 69.2 % | 🔴 défavorable → ✅ favorable |
| 80-100 | 43 | 53.5 % | 113 | 67.3 % | 64 % (n=156) | 32.6 % | 69.0 % | 🟡 neutre → ✅ favorable |

### PANIQUE

| Zone | n dév. | réussite dév. | n valid. | réussite valid. | annoncé (plein) | +20 % av. stop dév. | +20 % av. stop valid. | Diagnostic dév. → valid. |

|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0-20 | 192 | 48.4 % | 29 | 69.0 % | 51 % (n=221) | 41.1 % | 62.1 % | 🔴 défavorable → ✅ favorable |
| 20-40 | 41 | 29.3 % | 40 | 70.0 % | 49 % (n=81) | 34.1 % | 55.0 % | 🔴 défavorable → ✅ favorable |
| 40-60 | 19 | 36.8 % | 31 | 61.3 % | 52 % (n=50) | 36.8 % | 54.8 % | 🔴 défavorable → ✅ favorable |
| 60-80 | 10 | 50.0 % | 33 | 54.5 % | 54 % (n=43) | 50.0 % | 42.4 % | 🟡 neutre → 🟡 neutre |
| 80-100 | 6 | 50.0 % | 13 | 84.6 % | 74 % (n=19) | 50.0 % | 92.3 % | ⚪ (n<10) → ✅ favorable |

### Cellules dont le diagnostic change entre développement et validation

**13 cellule(s) instable(s)** (diagnostic différent entre les deux
périodes, avec au moins 10 cas de chaque côté) :

- **CASSURE / zone 20-40** : 🟡 neutre (56 %, n=41) → ✅ favorable (90 %, n=10)

- **CASSURE / zone 40-60** : 🔴 défavorable (41 %, n=22) → ✅ favorable (84 %, n=19)

- **CASSURE / zone 60-80** : 🔴 défavorable (45 %, n=11) → ✅ favorable (89 %, n=19)

- **CASSURE / zone 80-100** : 🔴 défavorable (47 %, n=30) → ✅ favorable (70 %, n=80)

- **EVEIL / zone 0-20** : 🟡 neutre (53 %, n=301) → ✅ favorable (71 %, n=51)

- **EVEIL / zone 20-40** : 🔴 défavorable (41 %, n=117) → ✅ favorable (66 %, n=64)

- **EVEIL / zone 40-60** : 🔴 défavorable (33 %, n=66) → ✅ favorable (65 %, n=80)

- **EVEIL / zone 60-80** : 🔴 défavorable (36 %, n=47) → ✅ favorable (81 %, n=52)

- **EVEIL / zone 80-100** : 🟡 neutre (53 %, n=43) → ✅ favorable (67 %, n=113)

- **PANIQUE / zone 0-20** : 🔴 défavorable (48 %, n=192) → ✅ favorable (69 %, n=29)

- **PANIQUE / zone 20-40** : 🔴 défavorable (29 %, n=41) → ✅ favorable (70 %, n=40)

- **PANIQUE / zone 40-60** : 🔴 défavorable (37 %, n=19) → ✅ favorable (61 %, n=31)

- **PANIQUE / zone 80-100** : ⚪ (n<10) (50 %, n=6) → ✅ favorable (85 %, n=13)


1 cellule(s) non concluante(s) en validation (n<10) : CASSURE/0-20 (n=3)


## 4. Benchmark : acheter au hasard

Base du marché = tenir 12 mois (net de frais) un titre éligible à une date
éligible, **sans aucun signal**. C'est la performance de fond du marché sur les
mêmes fenêtres — le niveau que le signal doit dépasser pour « apporter quelque
chose ».


| Période | n | Réussite 12 m | IC 95 % (Wilson) | Médiane nette |

|---|---:|---:|---:|---:|
| Base du marché — dév. | 41197 | 48.1 % | [47.6 % ; 48.6 %] | -1.61 % |
| Base du marché — valid. | 26794 | 69.7 % | [69.2 % ; 70.3 %] | 21.85 % |

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
| CASSURE | dév. | 136 | -10.78 % | 54 % (74/136) |
| CASSURE | valid. | 131 | +0.41 % | 49 % (64/131) |
| EVEIL | dév. | 574 | -0.51 % | 48 % (273/574) |
| EVEIL | valid. | 360 | +0.41 % | 50 % (181/360) |
| PANIQUE | dév. | 268 | +4.45 % | 47 % (126/268) |
| PANIQUE | valid. | 146 | -6.21 % | 49 % (72/146) |

## 5. Significativité

Méthodes (conservatrices, formules ci-dessous) : intervalle de Wilson à 95 %,
test de deux proportions (écart-type non poolé), Mann-Whitney U avec correction
des ex æquo. Aucune significativité n'est revendiquée au-delà de ce que les
effectifs permettent.


### 5.1 Stabilité : développement vs validation (le cœur de la question)


| Schéma | réussite dév. | réussite valid. | z (2 prop.) | p | même distribution des rendements ? (Mann-Whitney p) |

|---|---:|---:|---:|---:|---:|
| CASSURE | 55.1 % | 77.1 % | -3.90 | 9.58e-05 | 0.000818 |
| EVEIL | 47.2 % | 68.9 % | -6.76 | 1.42e-11 | 8.11e-12 |
| PANIQUE | 44.8 % | 65.8 % | -4.23 | 2.39e-05 | 4.64e-05 |

> Lecture : ces écarts dév./valid. sont tous significatifs, mais ils reflètent d'abord
> le changement de régime (la base passe de 48,1 % à 69,7 %). La stabilité qu'il faut
> surveiller n'est pas le taux brut du signal, mais son ÉCART à la base — c'est l'objet
> de 5.2.


### 5.2 Le signal bat-il la base du marché ? (par période)


| Schéma | Période | réussite signal | réussite base | z (2 prop.) | p | médianes (Mann-Whitney p) |

|---|---|---:|---:|---:|---:|---:|
| CASSURE | dév. | 55.1 % | 48.1 % | +1.65 | 0.0993 | 0.0251 |
| CASSURE | valid. | 77.1 % | 69.7 % | +2.01 | 0.0446 | 0.19 |
| EVEIL | dév. | 47.2 % | 48.1 % | -0.43 | 0.67 | 0.581 |
| EVEIL | valid. | 68.9 % | 69.7 % | -0.33 | 0.739 | 0.781 |
| PANIQUE | dév. | 44.8 % | 48.1 % | -1.09 | 0.275 | 0.165 |
| PANIQUE | valid. | 65.8 % | 69.7 % | -1.00 | 0.315 | 0.253 |

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
passe de **48.1 %** de réussite (médiane -1.61 %)
sur 2018-2022 à **69.7 %** (médiane +21.85 %) sur
2023-2025 : un marché en hausse de +21.6 points,
indépendamment de tout signal. Les 13 cellules par zone qui changent de diagnostic le
font toutes dans le même sens (🔴/🟡 → ✅) : ce n'est pas du bruit qui va dans les deux
sens, c'est la signature d'un marché globalement haussier sur 2023-2025. Toute hausse
du taux du signal doit être lue CONTRE cette hausse de fond.

**CASSURE** — annoncé 267 cas sur le plein échantillon. Sur la période
indépendante (2023-2025, n=131) : réussite 77.1 % contre
69.7 % pour la base « achat au hasard » → +7.4 points,
un avantage limite (z significatif, médianes non confirmées) (z p = 0.0446 ; Mann-Whitney p = 0.19). Excès moyen sur
le même titre : +0.41 %.

**EVEIL** — annoncé 934 cas sur le plein échantillon. Sur la période
indépendante (2023-2025, n=360) : réussite 68.9 % contre
69.7 % pour la base « achat au hasard » → -0.8 points,
légèrement EN DESSOUS de la base (z p = 0.739 ; Mann-Whitney p = 0.781). Excès moyen sur
le même titre : +0.41 %.

**PANIQUE** — annoncé 414 cas sur le plein échantillon. Sur la période
indépendante (2023-2025, n=146) : réussite 65.8 % contre
69.7 % pour la base « achat au hasard » → -4.0 points,
légèrement EN DESSOUS de la base (z p = 0.315 ; Mann-Whitney p = 0.253). Excès moyen sur
le même titre : -6.21 %.

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

