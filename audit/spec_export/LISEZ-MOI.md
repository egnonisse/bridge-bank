# Export des cas de la veille spéculative — pour audit externe

**Date de production** : 12/11/2026 · **Script** : `scripts/exporter_cas_spec.py` (rejouable)
**Producteur** : `scripts/calibrate_spec_profiles.py` (les mêmes règles, univers légèrement différent)

## Ce que contient ce dossier

| Fichier | Contenu |
|---|---|
| `cas_PANIQUE.csv` | 414 cas, une ligne par épisode |
| `cas_EVEIL.csv` | 934 cas |
| `cas_CASSURE.csv` | 267 cas |
| `resume.json` | agrégats par schéma et par zone, **avec la contrainte de stop** |

## Les règles exactes du signal

Toutes sont dans `src/strategie/spec_profiles.py`, fonction `detect_schemas(closes, volumes=None)`.
Elles s'évaluent sur la **dernière séance** d'une série ; un titre peut déclencher **plusieurs**
schémas le même jour.

### CASSURE — cassure du plus haut des 250 séances
```python
if closes[i] > max(closes[i - 250 : i]):        # i = dernière séance
    # confirmée par le volume (uniquement si `volumes` est fourni) :
    #   médiane des 60 séances précédentes > 0 ET volume du jour >= cette médiane
```
- **Fenêtre** : 250 séances (≈ 1 an de bourse).
- **Filtre volume** : appliqué **en production**, **pas dans cet export** (voir « Limites »).

### EVEIL — rebond confirmé de +10 % depuis le creux des 60 séances
```python
creux60 = min(closes[i - 60 : i])
if closes[i] / creux60 - 1 >= 0.10:
    # confirmée par le volume, même règle que la cassure
```

### PANIQUE — RSI 14 sous 30
```python
if rsi(closes)[i] is not None and rsi(closes)[i] < 30:
```
RSI = Relative Strength Index sur 14 séances (moyenne des hausses / moyenne des baisses).

### Le classement de zone — attention au vocabulaire
```python
def zone_of(closes, years=5):
    window = closes[-n-1 : -1] + [closes[-1]]     # ~1260 séances
    return (closes[-1] - min(window)) / (max(window) - min(window))
```
C'est une **position entre le minimum et le maximum de la fenêtre** (0 à 100 %), **PAS un
percentile de rang**. Les deux diffèrent sensiblement : sur ORGT à 2 550 F, la position min-max
vaut **35,7 %** alors que la part des séances sous ce prix vaut **46,2 %**.

Les colonnes `zone_minmax` et `percentile_rang` sont toutes deux exportées pour que l'écart
soit contrôlable. **Le backtest classe avec `zone_minmax`** (les tranches 0-20, 20-40… sont
des intervalles de position min-max).

### Échantillonnage : épisodes non chevauchants
- Espacement de **60 séances par titre ET par schéma** : deux signaux du même schéma sur le
  même titre à moins de 60 séances d'intervalle ne comptent qu'une fois.
- **Horizon** : 252 séances (12 mois) après le signal.
- **Frais** : 2,8 % aller-retour déduits du rendement 12 mois.

## Les colonnes du CSV

| Colonne | Sens |
|---|---|
| `code`, `date_signal`, `cours_signal` | identification du cas |
| `zone_minmax` | position dans la fourchette 5 ans (0-1) — **celle utilisée par le backtest** |
| `zone_tranche` | 0-20 · 20-40 · 40-60 · 60-80 · 80-100 |
| `percentile_rang` | part des séances sous le cours (le vrai percentile, pour comparaison) |
| `rendement_12m_net` | cours à J+252 / cours à J − 1 − 2,8 % |
| `pic_max_12m` | plus haut atteint sur 12 mois (en %) |
| `creux_min_12m` | plus bas atteint sur 12 mois (en %) |
| `stop_15_touche` | le cours a-t-il touché −15 % **à un moment** des 12 mois |
| `jours_avant_stop` | au bout de combien de séances (vide si jamais touché) |
| `p20/p35/p50_touche` | le palier a-t-il été touché **un jour** (mesure brute, optimiste) |
| **`p20/p35/p50_avant_stop`** | **le palier a-t-il été touché AVANT que le stop ne le soit** |
| `p20/p35/p50_jour` | date du premier franchissement (en séances) |
| `volume_jour`, `volume_median_60j` | liquidité — une sortie n'est possible que s'il y a une contrepartie |

**La distinction `touche` / `avant_stop` est l'apport principal de cet export** : la fiche
publiée annonçait « +20 % touché dans 59 % des cas » pour PANIQUE ; le plan exécutable, stop
compris, donne **46 %**.

## Résultats — ce que l'export démontre

| Schéma | Cas | Médiane nette 12 mois | Stop touché | +20 % brut | **+20 % avant stop** |
|---|---:|---:|---:|---:|---:|
| CASSURE | 267 | +16,3 % | 38 % | 69 % | **62 %** |
| EVEIL | 934 | +5,9 % | 50 % | 61 % | **52 %** |
| PANIQUE | 414 | +3,2 % | 56 % | 59 % | **46 %** |

**Pour PANIQUE par zone** — la zone 20-40, que la fiche annonçait « favorable », est en réalité
la plus défavorable avec la 0-20 :

| Zone | n | % de cas positifs | Médiane nette | +20 % avant stop |
|---|---:|---:|---:|---:|
| 0-20 | 221 | 51,1 % | +1,6 % | 43,9 % |
| **20-40** | **81** | **49,4 %** | **−2,8 %** | **44,4 %** |
| 40-60 | 50 | 52,0 % | +2,9 % | 48,0 % |
| 60-80 | 43 | 53,5 % | +4,8 % | 44,2 % |
| 80-100 | 19 | 73,7 % | +18,0 % | 78,9 % |

## Limites — à lire avant de conclure

1. **Univers légèrement différent du calibrage publié** : cet export lit `data/history_clean.pkl`
   via `charger_cache`, alors que `calibrate_spec_profiles.py` passe par `load_all_history(BSApi())`.
   Écart mesuré : **414 cas PANIQUE ici, 421 au calibrage** (1,7 %). Les taux ne sont donc pas
   identiques au centième près ; l'ordre de grandeur et les conclusions, oui.
2. **Les volumes ne filtrent pas ces cas** : `detect_schemas` est appelé **sans** la liste de
   volumes, exactement comme le calibrage. En production, la fiche applique le filtre volume —
   les cas exportés sont donc plus nombreux que les signaux réellement publiés.
3. **Biais de survie** : seuls les titres encore présents dans le cache apparaissent. Un titre
   radié, suspendu ou liquidé est absent — et c'est précisément dans les zones basses qu'ils se
   trouvent. Les taux sont **optimistes**.
4. **Pas d'indépendance stricte** : l'espacement de 60 séances réduit la redondance sans
   l'éliminer. Plusieurs cas peuvent refléter le même choc de marché sur des titres différents.
5. **Aucune exécution réelle n'est simulée** : le stop est supposé rempli à −15 % au cours de
   clôture. Une exécution partielle, un cours en gap ou une séance sans contrepartie donnent un
   résultat différent — la colonne `volume_jour` permet de majorer ce risque.
6. **Les frais sont forfaitaires** (2,8 % aller-retour). Les ventes fractionnées en trois fois
   coûtent davantage (minimum de courtage de 1 000 F par ordre).

## Ce qui n'est PAS prouvé par cet export

- **La rentabilité du plan complet** (entrée + stop + trois ventes partielles) : elle demande un
  rejeu chronologique avec les règles de sortie réellement appliquées.
- **La robustesse hors période** : aucun test sur une fenêtre postérieure n'est fourni ici.
- **L'absence de surapprentissage** : les tranches de zone (0-20, 20-40…) n'ont pas été validées
  sur une période indépendante, et le nombre de découpages essayés avant de retenir ceux-ci n'est
  pas documenté.
