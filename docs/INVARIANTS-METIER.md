# Invariants métier — ce que le système ne doit JAMAIS violer

**Pourquoi ce document existe.** Les invariants étaient dispersés dans les tests : chacun
était prouvé, mais personne ne savait s'il en **manquait** un. Cette liste rend le manque
visible — elle a d'ailleurs immédiatement révélé un trou (voir D2).

**Comment l'utiliser.** Avant de modifier une règle, regardez si elle porte un invariant
ci-dessous. Après la modification, lancez le test cité. Si vous ajoutez une règle métier
qui doit tenir dans le temps, ajoutez son invariant **et** son test ici.

```bash
python -m pytest tests/ -q                        # tous les invariants
python scripts/auditer_constantes.py --comparer   # aucune valeur n'a bougé
```

**Tous les noms de tests ci-dessous ont été vérifiés présents dans `tests/`.**

---

## A. Argent — les frais et la fiscalité

| # | Invariant | Pourquoi (le coût de la violation) | Test |
|---|---|---|---|
| A1 | **Frais par sens et frais aller-retour ne sont jamais confondus** | Le rapport est exactement 2. Les confondre **double les frais, en silence** : le calcul tourne, le résultat est faux. C'est le piège historique du projet (`FRAIS = 0.028` vs `FRAIS_PAR_SENS = 0.014`). | `test_les_frais_ne_sont_pas_confondus` |
| A2 | **Les frais viennent du courtage réel, pas d'une constante inventée** | 0,014 = courtage 0,80 % + TVA 18 % + BRVM 0,456 %, plancher 1 000 F. Si la grille du courtier change, une seule valeur doit bouger. | `test_les_frais_viennent_du_courtage_reel` |
| A3 | **L'IRVM est identique dans tout le code** | Retenue fiscale de 12 % (CI). Deux valeurs divergentes = un rendement net faux, donc des achats à tort. | `test_coherence_fiscale` |
| A4 | **Les objectifs de rendement viennent de `taxation.py`** | Le seuil d'entrée (4 %) et de sortie (2 %) sont des décisions ; recopiés, ils divergent. | `test_seuils_de_rendement_coherents_avec_la_taxation` |

## B. Décisions — ce qui peut déclencher une action

| # | Invariant | Pourquoi | Tests |
|---|---|---|---|
| B1 | **Un seuil non significatif ne déclenche JAMAIS une vente** | Mesuré sur 7 cas, « 86 % de baisses » a une borne basse de 49 % : indiscernable du hasard. Vendre sur cette base coûte 43,1 points de rendement (attribution mesurée). | `test_les_quatre_seuils_sont_informatifs` · `test_alerte_pv_ne_propose_pas_de_vente_si_informatif` · `test_slbc_seuil_5_pct_atteint_mais_informatif` |
| B2 | **Un seuil sans mode est INFORMATIF par défaut** | Choix prudent, et conforme aux données : les 4 titres ont une borne basse sous 50 %. Un défaut inverse ferait vendre sur du bruit. | `test_seuil_ancien_sans_mode_est_informatif` · `test_profit_alert_informative_par_defaut` |
| B3 | **Un mode explicite n'est jamais réécrit par un recalcul** | Un `declencheur` posé volontairement doit survivre à un recalibrage — sinon une décision humaine est effacée en silence. | `test_mode_explicite_est_respecte` |
| B4 | **Un titre sans historique suffisant ne reçoit pas de seuil** | Sous 8 cas, la probabilité est du bruit. On préfère ne rien proposer. | `test_calibrage_insuffisant_renvoie_none` · `test_serie_trop_courte_retourne_none` |

## C. Règles d'architecture — le système informe, jamais ne bloque

| # | Invariant | Pourquoi | Tests |
|---|---|---|---|
| C1 | **Une alerte d'achat ne dépend jamais du cash** | Règle LEO du 08/09/2026 : « comment trouver du cash, j'en fais mon affaire ». Le cash est une **information**, jamais une consigne. | `test_alerte_tresorerie_est_informative` · `test_alerte_tresorerie_nappelle_aucune_fonction_dinvestissement` |
| C2 | **Les limites de concentration informent, elles n'interdisent pas** | Règle LEO du 11/09/2026 : « ne bloque pas ». Un dépassement alerte, il ne refuse pas. | `test_avertit_ligne_buffett_au_dela_de_la_moitie` |
| C3 | **Un indicateur de marché indisponible n'empêche jamais une alerte** | Le régime est un **contexte**, pas une condition. Une panne d'indicateur ne doit pas faire taire le système. | `test_indicateur_indisponible_nempeche_pas_lalerte` · `test_renforcement_part_toujours_regime_absent` |
| C4 | **Aucune règle métier n'est recopiée dans un module** | Une copie diverge en silence des mois plus tard. Le test refuse même une copie **avec la bonne valeur**. | `test_aucune_regle_redefinie_ailleurs` |
| C5 | **Une seule réponse à « combien de cas pour valider un seuil »** | Deux réponses (6 et 8) existaient : un seuil passait un filtre et échouait à l'autre. | `test_une_seule_reponse_au_nombre_de_cas_requis` |

## D. Données — ce qui doit rester fiable

| # | Invariant | Pourquoi | Tests |
|---|---|---|---|
| D1 | **Les sorties fondamentales ne changent jamais sans décision explicite** | Dividende coupé, PER explosé, prix de sortie : ces règles protègent le capital. Une régression ici est un risque **financier** réel. | `test_dividende_coupe_declenche_toujours_la_vente_totale` · `test_per_explose_declenche_toujours_la_vente_totale` · `test_prix_de_sortie_declenche_toujours_la_vente_totale` |
| D2 | **Un titre sans cote ne fabrique pas de drawdown** (forward-fill) | Sur la BRVM, beaucoup de valeurs ne cotent pas tous les jours. Les compter à zéro avait produit **−73 % là où le marché perdait −2,3 %**. ⚠️ Ce test a été **écrit le 08/10/2026** : la correction existait dans le code mais n'était protégée par rien. | `test_un_titre_sans_cote_ne_fabrique_pas_de_drawdown` · `test_le_drawdown_reel_est_bien_mesure` |
| D3 | **Une mesure heuristique de division n'est jamais mélangée à une donnée publiée** | Cas SLBC : un ×50 fabriqué avait produit des rendements absurdes. Une donnée publiée et une estimation ont deux niveaux de confiance. | `test_detect_jumps_ignores_real_splits` · `test_ath_status_ignore_niveaux_pre_division` |
| D4 | **Le journal des seuils est append-only** | Une entrée écrite ne peut plus disparaître. C'est la seule trace de ce qui a bougé **pendant l'exécution**, là où git ne voit rien (réserve LEO du 08/10/2026). | `test_journal_est_append_only` · `test_une_ligne_corrompue_ne_perd_pas_le_reste` |
| D5 | **Deux mesures du même phénomène donnent le même chiffre** | Le seuil de vente et le profil de retournement mesuraient la même chose avec deux définitions : SNTS affichait « 86 % sur 7 cas » puis « 90 % sur 10 cas », et SLBC recevait 39 % (mesuré à +13 %) alors que son seuil de 5 % donne 54 %. **Une notion, un chiffre.** | `test_profil_et_seuil_donnent_le_meme_taux` · `test_chaque_profil_exporte_est_mesure_a_son_seuil` |
| D6 | **Les fenêtres d'épisodes sont disjointes** | Deux épisodes espacés de 10 séances partagent la moitié de leur fenêtre : ils ne sont pas indépendants, et espacer moins gonfle l'effectif (SNTS 7 → 10) sans apporter d'information. **Plus de cas n'est pas une meilleure preuve.** | `test_les_episodes_ne_se_chevauchent_pas` |
| D7 | **Un taux non fondé n'est jamais présenté comme tel** | « 86 % » sur 7 cas se lit comme une probabilité de baisse future alors que sa borne basse est 49 %. Le taux n'est affiché que si `significatif` (≥ 8 cas **et** borne ≥ 50 %). | `test_history_line_sans_taux_quand_non_significatif` · `test_un_taux_eleve_sur_peu_de_cas_n_est_pas_significatif` |

## E. Lecture — compréhensible sans connaissance boursière

| # | Invariant | Pourquoi | Tests |
|---|---|---|---|
| E1 | **Les montants sont au format français** (espace, virgule décimale) | `3,784 F` se lit « trois francs ». Piège de lecture sur un montant. | `test_grand_montant` · `test_aucune_virgule_dans_les_francs` · `test_montant_simple` |
| E2 | **Aucun jargon statistique dans une alerte utilisateur** | « borne basse », « non significatif », « indiscernable » : le lecteur visé n'a jamais touché à la bourse (règle LEO du 03/09/2026). | `test_alerte_pv_explique_en_langage_courant` · `test_messages_du_regime_sans_jargon` |
| E3 | **Le repère du hasard est explicite** | « 46 % » se lit comme un signal ; « trop proche du pile ou face » se comprend. | `test_alerte_pv_explique_en_langage_courant` |

---

## Couverture

| Famille | Invariants | Testés |
|---|---|---|
| A. Argent et fiscalité | 4 | 4 |
| B. Décisions | 4 | 4 |
| C. Architecture | 5 | 5 |
| D. Données | **7** | **7** |
| E. Lecture | 3 | 3 |
| **Total** | **23** | **23** |

### Ce que cette liste a déjà trouvé

**D2 (forward-fill du drawdown)** était documenté dans le code, utilisé dans les mesures
publiées, et **protégé par aucun test**. Un futur « nettoyage » de la boucle aurait recréé
silencieusement un drawdown fabriqué de −73 %. Le test existe désormais
(`tests/test_backtest_invariants.py`).

**Si vous ajoutez une règle métier sans invariant ici, la liste est incomplète.** C'est
précisément le trou que ce document est censé rendre visible.

---

## Contrôle automatique de ce document

Un document qui cite des tests peut **mentir sans le savoir** : un test renommé, et la
référence devient fausse — pire qu'absente, parce qu'elle rassure à tort. C'est arrivé lors
de la rédaction de ce document : 60 % des noms cités avaient été écrits de mémoire.

`tests/test_invariants_documentes.py` relit ce fichier et **vérifie que chaque test cité
existe réellement** dans `tests/`. Le document ne peut plus dériver en silence.
