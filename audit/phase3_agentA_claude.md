# Audit phase 3 — Agent A (Claude) — modules sensibles

- **Agent** : A (Claude) — audit indépendant, croisé avec l'agent B
- **Date** : 2026-10-12
- **Périmètre** : `src/strategie/strategie_leo.py` (476 l.), `src/backtesting/challenge_validateur.py` (504 l.), `src/analyse/fondamentaux_historiques.py` (374 l.)
- **Méthode** : lecture intégrale des 3 modules ; lecture de `docs/INVARIANTS-METIER.md`, `IPS.md`, extraits de `CHALLENGE-MULTI-MODELES.md` et `architecture.md` ; lecture partielle de `challenge_indicateurs.py`, `regles.py`, des scripts appelants et de `tests/test_regles_centralisees.py` ; **lecture seule** de `data/fondamentaux_historiques.json` (analyse Python en mémoire, sans écriture). Aucun test lancé, aucun fichier projet modifié.
- **Fait structurant** : `grep` sur `tests/` des noms `strategie_leo`, `MoteurLeo`, `challenge_validateur`, `fondamentaux_historiques`, `evaluer_hypothese`, `bpa_connu`, `extraire_bpa`, `simuler` → **0 occurrence**. Les 338 tests ne couvrent directement aucun des 3 modules ; seuls des scripts (`scripts/tester_*.py`) les exercent.

---

## 1. Synthèse — TOP 5

1. **A3-01 (P1)** — `extraire_bpa` : la branche « on écarte le TTM » est du code mort (la boucle s'arrête avant). Preuve dans les données : **12 titres sur 47 ont BPA 2024 == BPA 2025 au centime** (dont 10 déclarés `bpa_fiable=True`). Années décalées d'un an ⇒ look-ahead dans le module censé le supprimer.
2. **A3-02 (P1)** — `bpa_connu` : un BPA de l'exercice N est « connu » dès le **1er janvier N+1**, alors que la docstring dit « ~avril » (et les comptes BRVM sortent souvent plus tard). Look-ahead de 3 à 6 mois, sur tous les PER/payout du challenge.
3. **A3-03 (P2→P1 pour le jugement)** — le garde-fou « in/out-of-sample » du juge teste `rendement absolu > 0` sur chaque moitié, pas l'avantage vs baseline. Dans un marché à +145 %, il ne rejette quasiment rien : `RETENUE SOUS CONDITION` peut être émis sur des règles sans mérite.
4. **A3-04 (P2)** — `scripts/challenge_multi_modeles.py:465` (le chemin de production du challenge) appelle `evaluer_hypothese(...)` **sans `historique_fond`** : ni les trades ni la baseline ne perçoivent de dividendes — exactement le biais que la docstring dit avoir corrigé (règles de dividende condamnées « par construction »).
5. **A3-05 (P2)** — Aucune correction de comparaisons multiples (20 hypothèses, seuil p ≤ 0,05 ; p-value à 100 tirages, jamais corrigée) + baseline à tirages indépendants alors que les trades de la règle sont corrélés (même régime de marché) ⇒ p-values trop optimistes.

(À suivre en importance : A3-06 invariant A3/C4 contourné — `0.88` en dur ×4 et test aveugle aux sous-paquets ; A3-07 `strategie_leo` paramétré à 15 % de cash vs IPS 30 % ; A3-08 comparaison des variantes biaisée par l'ordre de l'univers.)

---

## 2. Findings détaillés

### A3-01 — P1 — Colonne TTM jamais écartée : BPA décalés d'un an
**Fichier** : `src/analyse/fondamentaux_historiques.py:198-219`

**Description.** La boucle de lecture des cellules s'arrête dès que `len(valeurs) >= len(ordre)`. Le test suivant — « si on a exactement une valeur de plus que d'années, on écarte le TTM » — exige `len(valeurs) == len(ordre) + 1`, ce qui est **impossible** puisque la boucle a coupé à `len(ordre)`. La branche est donc morte. Si la ligne EPS commence par une colonne TTM (ce que le commentaire du code affirme), toutes les valeurs sont associées à l'année précédente-plus-un et la dernière année est perdue. Un cellule non numérique (`-`, `n/a`) est aussi **silencieusement sautée** (`if not mm` → rien n'est ajouté), ce qui décale toutes les valeurs suivantes.

**PREUVE (code)** :
```python
        if len(valeurs) >= len(ordre):
            break
    ...
    # Le premier nombre de la ligne EPS est le TTM : on l'ecarte si on a
    # exactement une valeur de plus que d'annees.
    if len(valeurs) == len(ordre) + 1:
        valeurs = valeurs[1:]
```
**PREUVE (données, `data/fondamentaux_historiques.json`, lecture seule)** : doublons exacts de BPA entre 2024 et 2025 pour ABJC 121.98, BOAB 496.0, CABC 287.91, CFAC 46.4, CIEC 233.93, ORAC 857.1, PALC 1003.19, SIVC 20.53, SOGC 578.31, TTLS 208.09 (tous `bpa_fiable=True`), + NTLC 16698.29, SAFC 2158.25 (False). 12/47 titres : une égalité exacte entre deux exercices consécutifs n'est pas plausible naturellement ; c'est la signature TTM(=dernier FY) + FY2025 lus comme deux exercices.

**Scénario.** FY2025 réel est étiqueté « 2024 », FY2024 réel « 2023 », etc. `bpa_connu(t, "2025-03-01")` renvoie alors un BPA qui en réalité est celui de l'exercice 2025 (publié en 2026) : fuite d'un an. Les PER/payout de 10 titres « fiables » sont faux de ~1 an de croissance ; les règles fondamentales du challenge « RETENUE » reposent dessus. `valider_bpa` ne le détecte pas : il compare uniquement la colonne la plus récente à un PER actuel avec 40 % de tolérance, et le dernier BPA (TTM ≈ FY) est cohérent.

**Recommandation.** Ne pas tronquer la boucle ; lire toute la ligne, puis aligner sur les en-têtes (`TTM` + `FY…`) en détectant explicitement la colonne TTM ; refuser (retourner `{}`) si le nombre de valeurs ≠ nombre d'en-têtes ; traiter `-` comme valeur manquante *à sa position* (None) et non la sauter ; rejeter tout titre où deux exercices consécutifs sont strictement égaux. Ajouter un test sur un HTML-fixture avec colonne TTM.

---

### A3-02 — P1 — Publication du BPA supposée au 1er janvier N+1 (look-ahead de plusieurs mois)
**Fichier** : `src/analyse/fondamentaux_historiques.py:56, 331`

**Description.** Le module annonce « publié vers avril N+1 » mais `bpa_connu` utilise l'année seule : `a + 1 <= annee`. Un BPA FY2024 devient donc visible le 2025-01-01, pas en avril (voire juin/juillet, après assemblées générales BRVM — cf. ex_date de dividendes de mai à septembre dans le cache).

**PREUVE** :
```python
# Un BPA d'exercice N est publie vers avril N+1. On applique ce decalage.
DECALAGE_PUBLICATION_BPA = 1
...
        if a + DECALAGE_PUBLICATION_BPA <= annee:
            candidats.append((a, val))
```
**Scénario.** Une règle « PER < 14 » achète en janvier-mars avec le PER calculé sur des comptes inconnus du marché. Cumulé avec A3-01 (années décalées), l'information employée peut avoir 1 an et 3 mois d'avance. Le docstring du module (« Sans ces règles, on remplace un look-ahead par un autre ») décrit exactement le défaut que le code commet.

**Recommandation.** Comparer des dates, pas des années (`date >= f"{a+1}-06-30"` ou la date réelle de publication/AG si disponible, ou la date de premier dividende de l'exercice). Tester la frontière (31 mars / 1er juillet).

---

### A3-03 — P2 — Garde-fou in/out-of-sample trop faible (critère absolu, pas relatif)
**Fichier** : `src/backtesting/challenge_validateur.py:437-443` ; doc `CHALLENGE-MULTI-MODELES.md:142`

**Description.** Docstring et doc : « un avantage qui n'existe que sur une moitié est de la chance ». Le code ne teste pas l'*avantage* par moitié mais seulement `in_sample_pct <= 0 or out_sample_pct <= 0` (rendement net moyen absolu). Dans un marché ayant fait +145 % et avec dividendes crédités, quasi toute règle a un rendement moyen > 0 sur chaque moitié. La baseline n'est calculée que globalement.

**PREUVE** :
```python
        if r.in_sample_pct <= 0 or r.out_sample_pct <= 0:
            return ("REJETEE — avantage present sur une seule moitie de la "
                    "periode (probable surajustement)")
        if abs(r.in_sample_pct - r.out_sample_pct) > 40:
            return ("FRAGILE — ecart de plus de 40 pts entre les deux moities")
```
**Scénario.** Une règle qui bat la baseline à 100 % grâce à 2017-2021 et fait −3 pts vs hasard sur 2022-2026, mais gagne +12 % en absolu sur chaque moitié, sort « RETENUE SOUS CONDITION — tient sur les deux moitiés ». Le message « avantage présent sur une seule moitié » est aussi trompeur (il s'agit d'un rendement négatif, pas d'un avantage). De plus la coupure `2022-01-01` est fixée par l'appelant ; rien n'empêche de la choisir après avoir vu les résultats, et le « out-of-sample » n'est pas hors échantillon si l'hypothèse a été itérée (doc l. 238-ish : « premier passage »).

**Recommandation.** Calculer la baseline (même méthode) par moitié et exiger `avantage_in > 0` ET `avantage_out > 0` ; figer la date de coupure dans une constante unique ; renommer les verdicts pour dire ce qui est testé.

---

### A3-04 — P2 — Chemin de production du challenge sans dividendes (ni trades ni baseline)
**Fichier** : `scripts/challenge_multi_modeles.py:465` (appelant) / `challenge_validateur.py:216-228, 374-386` (défaut `historique_fond=None`)

**Description.** `historique_fond` est facultatif et silencieux. Le « Round 3 » (jugement final, « validation par le code ») appelle sans lui, alors que `hf` est chargé 20 lignes plus haut et passé à `precalculer_historique`.

**PREUVE** :
```python
    series = precalculer_historique(hist, fond, hf)
    ...
        r = evaluer_hypothese(series, h, date_coupure="2022-01-01")
```
(contraste : `scripts/revalider_regles_challenge.py:74` passe `historique_fond=hf` ; `scripts/tester_le_juge.py:78,84` ne le passe pas non plus.)

**Scénario.** Dans le verdict Round 3, une règle de dividende est jugée sur sa plus-value seule (+15,24 % vs +18,19 % hasard, cas cité dans la docstring de `Trade`) → « NON CONCLUANTE » à tort ; inversement, une règle de croissance n'est pas pénalisée. Deux scripts du même juge donnent des verdicts différents pour la même hypothèse.

**Recommandation.** Rendre `historique_fond` obligatoire (ou le charger automatiquement comme `precalculer_historique` le fait) et lever une alerte si absent.

---

### A3-05 — P2 — Significativité : pas de correction multiple, baseline à tirages indépendants, p-value à granularité 1/100
**Fichier** : `challenge_validateur.py:308-371, 408-410, 429`

**Description.** (a) 20 hypothèses testées, seuil `p > 0.05` rejette ; sous H0 on attend ≈ 1 faux positif sur 20 (3 « retenues » sur 20 sont compatibles avec le hasard) ; aucune correction (Bonferroni/Holm) ni mention. (b) La p-value est `# paniers ≥ rendement / 100` : minimum 0,0000 affiché `p = 0.0000` alors que la vraie borne est < 1/101 ; pas de « +1 ». (c) Les trades de la règle sont corrélés (plusieurs titres entrant le même jour dans le même régime), tandis que les paniers aléatoires tirent des dates indépendantes ⇒ variance du statistique de la règle sous-estimée côté baseline ⇒ p-values trop faibles. (d) Baseline : durée figée à la médiane `duree_med`, alors que la règle sort sur condition (durées variables) ; fenêtre baseline `bornes` peut inclure des séances < 250 que la règle n'a pas le droit de trader (`SEANCES_MIN_INDICATEURS`).

**PREUVE** :
```python
        r.p_value = sum(1 for x in base if x >= r.rendement_net_pct) / len(base)
```
```python
    if r.p_value is not None and r.p_value > 0.05:
```
**Scénario.** Sur 20 règles aléatoires, ≥ 1 passe le filtre p ≤ 0,05 par chance ; si elle franchit aussi A3-03, elle est « retenue ».

**Recommandation.** `p = (1 + #≥)/(1 + N)`, ≥ 1 000 tirages ; seuil ajusté au nombre d'hypothèses ; baseline avec même contrainte `i ≥ 250` et durées rééchantillonnées sur celles de la règle ; bootstrap par date (blocs) pour la corrélation.

---

### A3-06 — P2 — IRVM (0,88) et conservation (0,008) recopiés en dur ; l'invariant A3/C4 est contourné et son test est aveugle
**Fichiers** : `fondamentaux_historiques.py:359` ; `challenge_validateur.py:212` ; `strategie_leo.py:182` ; `challenge_indicateurs.py:~149`

**PREUVE** :
```python
            out["net_yield"] = round(brut * 0.88 - 0.008, 6)       # fondamentaux_historiques
            total += d["montant"] * 0.88      # net d'IRVM          # challenge_validateur
        return sum(d["montant"] * 0.88 for d in t.dividendes       # strategie_leo
```
alors que `src/regles.py` expose `IRVM` et `taxation.py` fournit déjà `net_yield(...)` / `CUSTODY_ANNUAL`. Le test `test_aucune_regle_redefinie_ailleurs` itère sur `SRC.glob("*.py")` : **non récursif**, donc `strategie/`, `backtesting/`, `analyse/` échappent au contrôle. `INVARIANTS-METIER.md` annonce C4 « 5/5 testés ».

**Scénario.** L'IRVM change (l'historique du projet : 10 % → 15 % → 12 %, `regles.py` demande « à revérifier »). `regles.IRVM` est mis à jour ; backtests, juge et net_yield PTI continuent à 12 % en silence, quatre endroits à corriger à la main. De plus `net_yield` du PTI et celui de `taxation.py` peuvent diverger (C4/D5).

**Recommandation.** Importer `IRVM` / `CUSTODY_ANNUAL` de `regles`/`taxation` ; étendre le test à `SRC.rglob("*.py")` et à la recherche des littéraux `0.88` / `0.008`.

---

### A3-07 — P2 — `cash_cible = 0.15` contredit l'IPS (30 %) ; sorties à +15 %/+20 % contredisent l'IPS (+20/+35/+50, stop −15 %)
**Fichier** : `strategie_leo.py:67, 75, 456-459`

**Description.** L'IPS a été corrigé le 12/10/2026 (CONFLIT-01) : liquidités **30 %**, « 15 % était un reste ». Le moteur garde `cash_cible: float = 0.15`. Les paliers sont **volontairement** « réels, plus bas que les documentés » (docstring) — assumé, mais aucun stop-loss −15 % ni palier +35/+50 n'est modélisé alors que l'IPS 4.2 les déclare « non négociables ». Le moteur simule donc un comportement observé, pas l'IPS, et sa description (« stratégie réelle de LEO ») ne dit pas qu'il est exposé à 85 % contre 70 % prévu.

**PREUVE** :
```python
    # 5. Reserve de cash (fraction du capital jamais investie)
    cash_cible: float = 0.15
    seuils_vente: tuple = ((0.15, 1 / 3), (0.20, 1 / 3))
```
**Scénario.** Les rendements/drawdown publiés pour « la stratégie de LEO » sont ceux d'un portefeuille 85 % investi sans stop-loss ; un lecteur les applique à l'allocation IPS (70 % investi, stop −15 %) : rendement surestimé, risque de baisse sous-estimé (aucun stop dans les pertes).

**Recommandation.** Aligner `cash_cible` sur la constante IPS (si elle existe dans `regles.py`) ou documenter l'écart ; modéliser le stop −15 % (variante E) ou signaler « sans stop » dans la sortie.

---

### A3-08 — P2 — « Même capital par titre » faux : le résultat dépend de l'ordre de l'univers et du capital
**Fichier** : `strategie_leo.py:188, 331-352, 445-476`

**Description.** La docstring de `budget_max_ligne` prétend que toutes les variantes engagent le même capital par titre. Or `tranche = budget_max_ligne / nb_tranches` : la variante passive (`nb_tranches=1`, `cash_cible=0`) achète 300 000 F par titre en première entrée ; avec capital 1 M F et 5 titres (valeur utilisée par `tester_strategie_leo.py`/`valider_variantes_strategie.py`), elle épuise le cash après 3 titres (900 k), le 4ᵉ ne passe pas `dispo > tranche*0.5`, le 5ᵉ jamais. La variante complète, elle, ouvre les 5 titres à 100 k. Les variantes ne détiennent donc pas le même ensemble de titres, et le résultat dépend du *premier* titre dans `series` (ordre du dict `univers`).

**PREUVE** :
```python
                tranche = self.p.budget_max_ligne / max(self.p.nb_tranches, 1)
                ...
                if pos is None:
                    if dispo > tranche * 0.5:
                        self._acheter(code, date, cours, tranche, ...
```
**Scénario.** L'« attribution » des composants (entrée progressive, renforcement, paliers) mesure en réalité une différence de composition du portefeuille. Une conclusion « les habitudes de LEO font gagner X pts » peut venir de la sélection de titres, exactement l'effet que la docstring prétend neutraliser. En outre `Parametres.budget_ligne` (100 000) est lu (`budget = ...`) mais jamais utilisé, et `rebalancement_actif`/`seuil_rebalancement` ne sont lus nulle part : le « 5 composants » annoncé n'en implémente que 4.

**Recommandation.** Répartir le capital investi équitablement (budget par titre = capital×(1−cash)/n_titres) ; supprimer ou implémenter les paramètres morts ; imprimer la liste des titres réellement achetés par variante.

---

### A3-09 — P2 — `evaluer_hypothese` / `resume()` : plantage sur résultats sans trade ou sans baseline ; verdict « AUCUN SIGNAL » non protégé
**Fichier** : `challenge_validateur.py:96-114, 391-394`

**Description.** Quand `trades` est vide, `evaluer_hypothese` retourne un `ResultatHypothese` avec `valide=True` et `rendement_net_pct=None`. `resume()` fait ensuite `f"{self.rendement_net_pct:+.2f}"` → `TypeError: unsupported format string passed to NoneType.__format__`. Même chose si `base` est vide (`baseline_mediane_pct` None). La doc (l. 238) souligne déjà qu'il ne faut pas confondre `valide` et « retenue ».

**PREUVE** :
```python
        lignes = [
            f"  {self.id} — {self.nom}",
            f"    trades : {self.nb_trades}   rendement net moyen : "
            f"{self.rendement_net_pct:+.2f} %   median : {self.rendement_median_pct:+.2f} %",
```
**Scénario.** Un appelant (rapport, boucle d'affichage) qui appelle `r.resume()` sur une hypothèse sans signal plante en plein challenge ; au mieux la règle est sautée, au pire le rapport n'est pas écrit. (Je n'ai pas trouvé d'appel `.resume()` dans `scripts/` ; le risque est latent — c'est pourquoi P2 et non P1.) Aucun test n'existe.

**Recommandation.** Gérer `None` dans `resume()` ; ajouter un test « hypothèse sans trade ».

---

### A3-10 — P2 — Exécution au cours de clôture du jour du signal (BRVM : irréalisable) et vente sur dividende à la date `ex`
**Fichier** : `challenge_validateur.py:266-286` ; `strategie_leo.py:309-361`

**Description.** Le signal est calculé avec le close de la séance `i` (rendements r5…r250, prix_vs_mm) et l'ordre exécuté **à ce même close** (`prix_entree = ind["prix"]`). Sur une place à cotation au fixing et liquidité faible, l'ordre ne peut être passé qu'après lecture du close, donc exécuté à `i+1` (ou plus). Pour une règle de rebond/momentum, c'est un avantage systématique (le prix `i+1` reflète souvent la continuation ou le retour). Même construction dans `MoteurLeo` (paliers à +15 % constatés au close, vendus au close). De plus aucun impact de marché/liquidité n'est modélisé.

**PREUVE** :
```python
                if evaluer_compilee(ach, ind):
                    en_position = True
                    i_entree = i
                    prix_entree = ind["prix"]
```
**Scénario.** Résultats surestimés sur les règles de réaction courte (r5, vol_ratio) ; la baseline, tirée au hasard, n'a pas ce biais ⇒ avantage artificiel côté règle. Impact sur la décision à confirmer par un décalage d'une séance.

**Recommandation.** Exécuter à `i+1` (ouverture ou close) pour entrées et sorties, tant dans le juge que dans le moteur ; documenter la limite si conservé.

---

### A3-11 — P2 — Dividende « le plus récent » sans limite d'âge : un dividende supprimé reste dans `net_yield`/`payout`
**Fichier** : `fondamentaux_historiques.py:311-314, 353-359, 371-372`

**Description.** `dernier_dividende_connu` renvoie le dernier détachement ≤ date, sans borne d'ancienneté. Une société qui cesse de payer (ex. BNBC : dernier dividende 2023) conserve `net_yield = DPS/cours` calculé sur un dividende vieux de 3 ans, donc un rendement « 4 % » fictif. De plus, une année avec deux versements (acompte + solde) ne cumule pas : seul le dernier versement est annualisé (sous-estimation), et `payout = dps / bpa` mélange un versement partiel et un BPA annuel.

**PREUVE** :
```python
    connu = [d for d in t.dividendes if d["ex_date"] <= date]
    return connu[-1] if connu else None
...
            out["net_yield"] = round(brut * 0.88 - 0.008, 6)
```
**Scénario.** Règle « rendement net ≥ 4 % » : sélectionne en 2026 un titre dont le dividende a été coupé en 2023 (cf. invariant D1, coupe de dividende = vente totale). Le juge teste une stratégie qui n'achèterait pas dans la réalité de l'IPS (DPS vérifié).

**Recommandation.** Ne retenir que les dividendes des 12–15 derniers mois, sommer les versements d'un exercice, sinon laisser `net_yield` absent (« inconnu », pas zéro).

---

### A3-12 — P2 — Valeur finale/dividendes : dividendes d'une position soldée perdus du compte rendu ; réserve de cash franchie
**Fichier** : `strategie_leo.py:185-206, 235-236, 407`

**Description.** (a) `r.dividendes = sum(p.dividendes for p in self.positions.values())` : une position soldée est supprimée de `self.positions` (`self.positions.pop`), ses dividendes disparaissent du total (le cash, lui, est conservé — valeur finale correcte, mais `dividendes` et `revenu_annuel_pct` sous-estimés). (b) `_acheter` vérifie `dispo > tranche*0.5` mais achète `min(tranche, cash)` : il peut dépasser `cash - cash_cible*capital` de 50 % d'une tranche, donc entamer la réserve. (c) Dividende crédité si le titre est en portefeuille à l'ex-date *après* les ordres du jour : un achat le jour de l'ex-date touche un dividende qu'un détenteur réel n'aurait pas ; une vente ce jour-là en perd un dû. (d) `engage = pos.cout_total` diminue après vente : le plafond `budget_max_ligne` est contournable en réinvestissant le produit de vente.

**PREUVE** :
```python
                    if dispo > tranche * 0.5:
                        self._acheter(code, date, cours, tranche,
...
        r.dividendes = sum(p.dividendes for p in self.positions.values())
```
**Scénario.** Sous le paramétrage par défaut, les positions ne sont jamais intégralement vendues (2 × 1/3) donc (a) est rare ; (b) joue dès que plusieurs titres ouvrent le même jour (cash 150 k, tranche 100 k, dispo 0 → bloqué, mais dispo 60 k → achat de 100 k). Effet de second ordre mais réel sur « exposition moyenne ».

**Recommandation.** Cumuler `dividendes` dans l'objet moteur ; `montant = min(tranche, dispo)` ; ordre dividende avant ordres ; plafond sur capital cumulé acheté.

---

### A3-13 — P3 — Autres constats mineurs
- **`strategie_leo.py:318-328`** : les fractions des paliers s'appliquent à `pos.actions` *restantes* (1/3 puis 1/3 du reste = 2/9 du total, laissant 4/9), alors que la docstring décrit « 3 actions, 2 actions, 1 action » (fractions de l'initial). 
- **`strategie_leo.py:283-307`** : le drawdown est mesuré avant les ordres du jour et jamais après la dernière séance.
- **`strategie_leo.py:390-391`** : si le cours final est 0/None, la position est omise de `valeur_finale` (valeur sous-estimée sans alerte).
- **`strategie_leo.py:419-424`** : `annees` ignore les jours (écart de mois entiers, `max(…, 0.5)`) ; `revenu_annuel_pct` = dividendes/capital initial, pas rendement sur capital investi.
- **`challenge_validateur.py:121-191`** : fonction `indicateurs()` dupliquée de `challenge_indicateurs.precalculer` (`_mm` exclut déjà le jour courant ; deux implémentations à garder cohérentes — D5) ; `sys.path.insert(0, RACINE)` effet de bord à l'import ; `pickle.load` sur `history_clean.pkl` (exécution de code si fichier altéré) ; `charger_fondamentaux` avale toute exception (`except Exception: pass`) et replie silencieusement sur `fundamentals_cache.json` sans contrôle d'unités.
- **`challenge_validateur.py:73-74`** : les frais 2,8 % sont appliqués multiplicativement au total *dividendes inclus* et sans plancher 1 000 F (approximation acceptable, mais le plancher pénalise les petits tickets dans la réalité).
- **`fondamentaux_historiques.py:49, 234`** : `urllib3.disable_warnings()` global + `verify=False` ⇒ aucune authentification de la source (données financières altérables par un intermédiaire) ; `_get` renvoie `None` sur toute erreur et `sauver_cache` écrase le fichier entier : un échec réseau transitoire sur un titre efface ses dividendes précédemment bons (si le script reconstruit tout sans fusion — non vérifié).
- **`fondamentaux_historiques.py:145`** : `html[i:i + 12000]` tronque l'historique des dividendes d'un titre à longue liste, et `devise` est lue mais jamais contrôlée (non-XOF traité comme XOF).
- **`fondamentaux_historiques.py:74, 115`** : tolérance de 40 % sur le PER recalculé (cours actuel / BPA du dernier exercice vs PER de référence) laisse passer un BPA faux de ×1,4.
- **`challenge_indicateurs.py:138-157`** (hors périmètre, observé) : le cache PTI n'est rafraîchi qu'au changement d'année ⇒ un dividende détaché en août n'alimente `net_yield` qu'en janvier suivant (stale, pas de look-ahead).

---

## 3. Vérifié et sain

- **Frais par sens vs aller-retour** : `strategie_leo._cout_ordre` utilise `FRAIS_PAR_SENS` (par ordre, plancher `FRAIS_MINIMUM`) ; `Trade.rendement_net` utilise `FRAIS_ALLER_RETOUR` une fois ; `regles.py` dérive `FRAIS_ALLER_RETOUR = 2 * FRAIS_PAR_SENS`. Pas de double comptage (A1 respecté dans ces modules).
- **CMP** : achat → `cout_total += montant` (frais inclus) ; vente → sortie au prorata du CMP : le CMP reste constant après vente partielle. Cohérent.
- **Palier rejoué** : le marqueur `pos.ventes` empêche de rejouer un palier chaque séance ; la précaution est testée par mesure documentée (1 013 → 4 ventes) mais pas par un test.
- **Forward-fill du drawdown (D2)** : `derniere_cote` reporté pour chaque titre ; `valeur_titres` n'est pas à zéro les jours sans cote. Correct.
- **Pas de look-ahead dans `indicateurs`/`precalculer`** : toutes les fenêtres utilisent les indices ≤ i ; `_mm` exclut même le jour courant.
- **Fenêtre dividende du juge** : `date_entree < ex_date <= date_sortie` — un acheteur du jour de l'ex-date ne perçoit pas le dividende ; baseline et règle utilisent la même fonction `_dividendes_detaches` (symétrie préservée quand `historique_fond` est fourni aux deux).
- **Sécurité du DSL** : le juge ne consomme que `compiler/evaluer_compilee` (hors périmètre ligne à ligne), pas d'`eval` dans le module.
- **Séparation fractions/unités** : `charger_fondamentaux` convertit `rendement_net_pct` et `payout_pct` en fractions (documenté et correct).
- **Seed reproductible** (`graine=12345`) : résultats déterministes.
- **Sorties d'argent** : aucun module n'exécute d'ordre ; ce sont des simulateurs (pas d'impact direct sur le portefeuille réel, seulement sur la décision de l'investisseur).

## 4. Limites de mon audit

- Aucun test lancé (interdit) ; je n'ai pas vérifié le comportement à l'exécution, ni reproduit les chiffres des rapports (`RAPPORT-VALIDATION-28-ANS.md` lu en diagonale).
- A3-01 : l'hypothèse « colonne TTM décale les années » est une **inférence** à partir du code (branche morte) et de 12 doublons exacts ; je n'ai pas refait le scraping (réseau/écriture non autorisés) ni vérifié le HTML source.
- `challenge_schema.py` (DSL/compilation) et `challenge_indicateurs.py` n'ont été lus que partiellement ; le biais de survie (titres radiés absents de `history_clean.pkl`) et la qualité du nettoyage des splits ne sont pas évalués.
- Non vérifié : le script de reconstruction `construire_fondamentaux_historiques.py` (fusion ou écrasement du cache), le comportement de `stockanalysis.com` (colonnes réelles), l'ampleur de l'effet A3-10 (nécessite un rerun).
- Le calcul « 3 hypothèses retenues sur 20 » vient de la doc, pas de mon exécution.
