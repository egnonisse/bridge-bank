# RECONCILIATION-BOC — cours et volumes du cache local vs Bulletins Officiels de la Cote

> Contrôle exécuté le **jeudi 12 novembre 2026, ~22:11 UTC**.
> Périmètre : cache historique du projet (`data/history_clean.pkl` + `data/history_cache.pkl`)
> vs sources officielles BRVM (BOC PDF et page « cours-actions » de brvm.org).
> Script : `scripts/reconcilier_boc.py` (hors ligne, lit le cache, injecte les références).

**Conclusion en une phrase** : le cache n'est **pas faux**, il est **en retard de 3 séances**
(dernière barre au 09/11 pour 46 titres sur 48) ; les 4 chiffres cités par l'auditeur sont
**tous confirmés** par les sources officielles, mais ils concernent des séances (10, 11 et
12/11) que le cache ne contient pas encore.

---

## 1. Ce qui est MESURÉ localement (le cache, hors réseau)

### 1.1 Origine des fichiers

| Fichier | Rôle | mtime (dernière écriture) |
|---|---|---|
| `data/history_cache.pkl` | cache BRUT (collecte API BSTrade) | 2026-11-10 09:01:38 UTC |
| `data/history_clean.pkl` | cache PROPRE (divisions ajustées — source des décisions) | 2026-11-10 09:01:42 UTC |
| `data/history_clean.pkl.sha256` | empreinte de provenance | 2026-11-10 09:01:42 UTC |

Le cache a donc été écrit le **matin du 10/11**, avant la clôture de la séance du 10/11 :
sa barre la plus récente est celle du **09/11** (clôture publiée en fin de séance du 09/11).
Lecture faite via `history_io.charger_cache()`, empreinte SHA-256 **vérifiée conforme**.

### 1.2 Décalage réel (dernière séance du cache vs date du jour) — TOUS les titres

| Dernière barre du cache | Retard vs 12/11 | Nb de titres |
|---|---|---|
| 2026-11-09 | **3 jours** | **46** |
| 2026-09-15 | **58 jours** | **2** (SEMC, SICC) |

- **46 titres** : dernière barre au lundi 09/11. Les séances du 10, 11 et 12/11 manquent.
- **SEMC et SICC** : dernière transaction réelle au 15/09 (SEMC 1495 F / 12 827 titres ;
  SICC 8 400 F / 72 titres). Depuis, la BRVM les cote encore à **prix indicatif**
  (volume 0 sur la page officielle du 12/11 : SEMC 1 495, SICC 8 400) — la source
  ne renvoie plus de barre sans transaction, donc le cache s'arrête à leur dernier échange.

### 1.3 Pourquoi 3 séances de retard (mécanisme, lu dans le code)

`src/collecte/backtest.py` :

- `CACHE_MAX_AGE_DAYS = 7` : re-téléchargement si le **fichier** a plus d'une semaine ;
- `CACHE_STALE_DATA_DAYS = 4` : re-téléchargement dès que la **dernière barre** a plus de 4 jours
  (`_donnees_fraiches`, ligne 55) ;
- au 12/11 : dernière barre = 09/11 → (12 − 9) = **3 jours < 4** → le cache est jugé « frais »,
  `load_all_history()` le réutilise **sans re-télécharger**.

Le décalage est donc **borné par conception** (≈ 3-4 séances, pas « un jour ») et **auto-réparant** :
au 13/11, (13 − 9) = 4 jours → re-téléchargement déclenché. Le contexte du litige
(« peuvent avoir un jour de retard ») **sous-estime** le retard réel constaté.

### 1.4 Sortie réelle du script (titres par défaut)

```
$ python scripts/reconcilier_boc.py
Titre | Dernière séance (cache) | Clôture | Volume | Valeur éch.≈ | Réf. clôture (même date) | Δ clôture | Réf. volume | Δ volume | Retard (j) | Réf. la + récente
------------------------------------------------------------------------------------------------------------------------------------------------------
ORGT  | 2026-11-09 | 2 650 | 646 | 1 711 900 | 2 650 | +0.00 % | 646 | +0.00 % | 3 | 2026-11-12 (plus récente que le cache)
TTLC  | 2026-11-09 | 3 030 | 4 470 | 13 544 100 | 3 030 | +0.00 % | 4 470 | +0.00 % | 3 | 2026-11-12 (plus récente que le cache)
SNTS  | 2026-11-09 | 4 150 | 105 946 | 439 675 900 | 4 150 | +0.00 % | 105 946 | +0.00 % | 3 | 2026-11-12 (plus récente que le cache)
PALC  | 2026-11-09 | 7 600 | 13 342 | 101 399 200 | 7 600 | +0.00 % | 13 342 | +0.00 % | 3 | 2026-11-12 (plus récente que le cache)
SGBC  | 2026-11-09 | 39 000 | 6 089 | 237 471 000 | 39 000 | +0.00 % | 6 089 | +0.00 % | 3 | 2026-11-12 (plus récente que le cache)
```

```
$ python scripts/reconcilier_boc.py --distribution
=== Distribution du retard (dernière barre vs aujourd'hui, 2026-11-12) ===
48 titres dans le cache ; retard max 58 j.
  retard   3 j : 46 titre(s)
  retard  58 j :  2 titre(s)

Détail par date de dernière barre :
  2026-09-15 : 2 titre(s) — SEMC, SICC
  2026-11-09 : 46 titre(s) — ABJC, BBGC, BICB, BICC, BNBC, BOAB, BOABF, BOAC, BOAM, BOAN, BOAS, CABC, CBIBF, CFAC, CIEC, ECOC, ETIT, FTSC, LNBB, NEIC, NSBC, NTLC, ONTBF, ORAC, ORGT, PALC, PRSC, SAFC, SCRC, SDCC, SDSC, SGBC, SHEC, SIBC, SIVC, SLBC, SMBC, SNTS, SOGC, SPHC, STAC, STBC, TTLC, TTLS, UNLC, UNXC
```

(Option d'injection testée : `--no-defaults --ref "ORGT|2026-11-10|2505|1466" --ref "ORGT|2026-11-11|2550|284"`
→ le script signale correctement « Réf. la + récente 2026-11-11 (plus récente que le cache) ».)

---

## 2. Nature de chaque observation (ce que le code importe réellement)

Lecture de `src/collecte/bsapi.py` (client API BSTrade) :

| Observation | Ce qu'elle est réellement | Où elle vit |
|---|---|---|
| **Barres du cache d'historique** | **Clôture officielle de séance** (OHLCV **journalier**). `history()` → `GetDataStockByCodeAndInterval2`, champs `CurrentDate` (ts ms → date de séance), `OpenP/HighP/LowP/CloseP`, `Volume`. Chaque barre est datée au **jour de séance** (00:00:00), **pas** à l'instant de la transaction. | `data/history_cache.pkl` puis `data/history_clean.pkl` (les 2 caches ont la **même** dernière barre pour les 48 titres : vérifié, 0 différence) |
| **Cotation « live » (snapshot)** | **Dernière transaction** horodatée : `Quote.traded_at` = `_parse_date(parts[-1])` (`%d/%m/%Y %H:%M:%S`). C'est le seul endroit où un horodatage intra-séance existe. | `market_snapshot()` — **non persisté** dans le cache d'historique |
| **Titre sans transaction (SEMC, SICC)** | **Prix indicatif** : la BRVM publie un cours de référence sans échange (volume 0). Le cache s'arrête à la **dernière transaction** (15/09) car l'API ne renvoie plus de barre à volume nul. | registre `titres_inactifs.json` (`INACTIF_APRES_JOURS = 8`) |

En clair : **la veille décide sur des clôtures de séance**, datées au jour, jamais horodatées à la
transaction. Le grief « les cours ne sont pas horodatés dans les fiches » est donc structurellement
juste sur la forme (pas d'horodatage intra-séance dans l'historique), mais **faux sur le fond**
quant à la valeur des cours : ils sont datés au jour de séance et, pour la séance qu'ils couvrent,
**exacts** (cf. §3).

---

## 3. Ce qui est VÉRIFIÉ auprès d'une source externe

Le réseau a répondu. Sources consultées :

1. **BOC PDF officiels brvm.org** (téléchargés et dépouillés) :
   - `https://www.brvm.org/sites/default/files/boc_20261109_2.pdf` (séance 09/11) ✓
   - `https://www.brvm.org/sites/default/files/boc_20261110_2.pdf` (séance 10/11) ✓
   - `https://www.brvm.org/sites/default/files/boc_20261111_2.pdf` (séance 11/11) ✓
2. **BOC 12/11** : `boc_20261112_2.pdf` → **HTTP 404, non encore publié** au moment du contrôle.
   La séance du 12/11 est donc vérifiée via la **page officielle « cours-actions » de brvm.org**
   (mise à jour « Jeudi 12 novembre 2026 ») et recoupée avec richbourse.com, bifinances.com,
   thecapitalinvest.app (chiffres identiques).
3. waramina.com, westcapbi.com, richbourse.com : confirmations secondaires des 11/11.

### 3.1 Valeurs officielles relevées (clôture / volume)

| Titre | 09/11 (BOC) | 10/11 (BOC) | 11/11 (BOC) | 12/11 (brvm.org live) |
|---|---|---|---|---|
| ORGT | 2 650 / 646 | **2 505 / 1 466** | **2 550 / 284** | **2 560 / 1 542** |
| TTLC | 3 030 / 4 470 | 3 030 / 7 127 | 3 015 / 1 644 | 3 095 / **2 656** |
| SNTS | 4 150 / 105 946 | 4 000 / 270 403 | 4 190 / 85 624 | 4 195 / 231 018 |
| PALC | 7 600 / 13 342 | 7 595 / 5 782 | 7 590 / 635 | 7 645 / 7 679 |
| SGBC | 39 000 / 6 089 | 38 900 / 2 721 | 38 600 / 1 126 | 38 890 / 3 570 |

(Clôture en FCFA / volume en titres. Les 4 cellules en gras sont les chiffres cités par l'auditeur.)

### 3.2 Les 4 affirmations de l'auditeur — verdict

| Affirmation | Verdict | Source |
|---|---|---|
| ORGT clôture **2 505 F le 10/11** | ✅ CONFIRMÉ | BOC 10/11 (PDF) : clôture 2 505, −5,47 % |
| ORGT clôture **2 550 F le 11/11** | ✅ CONFIRMÉ | BOC 11/11 (PDF) : clôture 2 550, +1,80 % (+ waramina, westcapbi, richbourse) |
| ORGT clôture **2 560 F le 12/11** | ✅ CONFIRMÉ | brvm.org « cours-actions » 12/11 : clôture 2 560, +0,39 % (BOC PDF non encore publié) |
| TTLC **2 656 actions échangées le 12/11** | ✅ CONFIRMÉ | brvm.org « cours-actions » 12/11 : volume 2 656 (+ richbourse, bifinances, thecapitalinvest) |

**L'auditeur a raison sur ses relevés.** La divergence n'est pas une erreur de données de son
côté ni du nôtre : c'est un **décalage de séance** (§4).

---

## 4. Écarts constatés et explication

### 4.1 Écart principal : staleness (3 séances), pas d'erreur de valeur

La dernière séance du cache (09/11) confrontée au **BOC de la même séance** :

| Titre | Cache 09/11 | BOC 09/11 | Écart clôture | Écart volume |
|---|---|---|---|---|
| ORGT | 2 650 / 646 | 2 650 / 646 | **0,00 %** | **0,00 %** |
| TTLC | 3 030 / 4 470 | 3 030 / 4 470 | **0,00 %** | **0,00 %** |
| SNTS | 4 150 / 105 946 | 4 150 / 105 946 | **0,00 %** | **0,00 %** |
| PALC | 7 600 / 13 342 | 7 600 / 13 342 | **0,00 %** | **0,00 %** |
| SGBC | 39 000 / 6 089 | 39 000 / 6 089 | **0,00 %** | **0,00 %** |

**Le cache est exact à 0,00 % sur la séance qu'il couvre** (clôture ET volume, 5 titres sur 5).
Les chiffres de l'auditeur (2 505 / 2 550 / 2 560 pour ORGT, 2 656 titres pour TTLC) portent sur
les séances **postérieures** au 09/11 — séances **absentes du cache**. L'écart qu'il constate
est donc un **écart de couverture (retard), pas un écart de valeur**. Cause : le cache n'a pas été
re-téléchargé depuis le matin du 10/11, et le seuil de fraîcheur de 4 jours (`CACHE_STALE_DATA_DAYS`)
ne le déclenchera que le 13/11 (§1.3).

### 4.2 Écart secondaire : « valeur échangée » calculée vs publiée

Le script calcule `valeur ≈ clôture × volume`. Le BOC publie une colonne « Valeur » = somme des
transactions réellement exécutées. Comparaison sur la séance 09/11 :

| Titre | clôture × volume (script) | Valeur BOC | Écart |
|---|---|---|---|
| ORGT | 1 711 900 | 1 716 730 | +0,28 % |
| TTLC | 13 544 100 | 13 447 340 | −0,71 % |
| SNTS | 439 675 900 | 434 835 775 | −1,10 % |
| PALC | 101 399 200 | 100 861 175 | −0,53 % |
| SGBC | 237 471 000 | 237 893 585 | +0,18 % |

Explication : le prix moyen pondéré des transactions diffère légèrement de la clôture ; l'écart
est de l'ordre de 1 %, sans signification pour le litige. À noter : `HistoryBar` ne porte **pas**
de champ « valeur » — la valeur exacte échangée n'est pas stockée dans le cache, seule clôture et
volume le sont.

### 4.3 Anomalie d'affichage sur la page live brvm.org (sans impact sur le fond)

Sur la page « cours-actions » du 12/11, la colonne « Cours veille » affiche **3 095** pour TTLC
alors que le BOC du 11/11 fixe la clôture à **3 015** (la variation +2,65 % du 12/11 se calcule
bien sur 3 015 → 3 095). La colonne « veille » du flux live recopie visiblement le cours de
référence, pas la clôture de veille. **Le BOC PDF fait foi** : TTLC 11/11 = 3 015. Signalé ici car
une réconciliation automatisée sur la page live seule introduirait un écart fantôme de 80 F.

### 4.4 Hypothèses classées par plausibilité (si un écart résiduel était invoqué)

1. **Très probable — retard de collecte** : le cache s'arrête au 09/11 (écrit le 10/11 au matin),
   l'auditeur compare avec des séances plus récentes. C'est le cas démontré ici.
2. **Plausible — division non ajustée** : pour un titre ayant subi une division récente (ex. SNTS
   26/10/2026, nominal 500→50, ×10), un cours **brut** pré-division diffère d'un facteur entier du
   cours **propre** ; mais sur la **dernière** séance les deux caches sont identiques (vérifié).
3. **Possible — prix indicatif** : un titre sans transaction garde son dernier cours ; SEMC/SICC
   sont à 58 jours de la dernière transaction réelle.
4. **Improbable — corruption du cache** : contredit par la vérification SHA-256 et par l'égalité
   stricte cache/BOC sur les 5 titres.

---

## 5. Ce que ce contrôle ne prouve pas

- **La séance du 12/11 n'est pas vérifiée contre le BOC PDF** : le bulletin `boc_20261112_2.pdf`
  n'était pas publié au moment du contrôle (HTTP 404). Les valeurs du 12/11 reposent sur la page
  live officielle brvm.org et des relais secondaires concordants, **pas** sur le bulletin officiel.
- **La série historique ajustée des divisions n'est pas re-confrontée au BOC** : on n'a vérifié que
  la **dernière** barre. Le retro-ajustement des divisions (37 titres sur 48 touchés, facteurs ×2
  à ×100) reste hors périmètre de ce contrôle.
- **Rien sur l'exhaustivité de l'API BSTrade** au-delà de la dernière barre : un titre absent du
  cache ou une barre manquante en milieu d'historique ne serait pas détecté ici.
- **L'horodatage des « fiches »** (le grief de forme initial) : les fiches sont produites par un
  autre chantier ; ce contrôle ne fait que documenter que l'historique du projet est daté au jour
  de séance et non horodaté à la transaction (§2).
- **La cause exacte de l'absence de re-téléchargement les 11 et 12/11** : le mécanisme de
  fraîcheur explique pourquoi le cache n'est *pas* re-téléchargé (données jugées fraîches < 4 j),
  mais ce contrôle n'établit pas si le job quotidien a effectivement tourné ou échoué ces jours-là.

---

## Annexe — méthode

- Lecture du cache : `history_io.charger_cache()` (empreinte SHA-256 vérifiée), caches propre et brut.
- Références : BOC PDF brvm.org (curl → extraction PyMuPDF, colonnes « Cours »/« Volume » de la
  table de cotation) pour les 09, 10, 11/11 ; page live brvm.org « cours-actions » pour le 12/11.
- Le script `scripts/reconcilier_boc.py` lit le cache **sans réseau** et compare aux références
  injectées (`--ref`, `--ref-file`, ou les références embarquées `--no-defaults` pour les ignorer).
