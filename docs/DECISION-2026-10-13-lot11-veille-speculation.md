# DÉCISION — 13/10/2026 — LOT 11 : veille spéculation (B1-10, B1-11, B1-14, B1-15)

Les 4 derniers findings P3 de la phase 3 (`audit/phase3_agentB1_mistral.md`) sur la veille
spéculation, la fiche et les sorties sont corrigés — chacun avec un test gardien.

## B1-10 — le repli silencieux de `spec_profiles` (2 volets)

1. **Le repli est SIGNALÉ.** `load_profiles()` : fichier de calibrage absent ou illisible →
   les stats figées (16-17/09/2026) ne sont plus servies en silence : `log.warning` **et**
   marqueur `"_fallback": True` ; la fiche affiche « ⚠️ STATISTIQUES DE SECOURS : le
   calibrage courant est indisponible — … ne sont PAS re-mesurés ». Avant, un fichier perdu
   faisait passer des chiffres de septembre pour la mesure du jour.
2. **Sans volume réel, pas de confirmation.** `detect_schemas()` : `vol_ok = med > 0 and
   volumes[i] >= med` (avant : `med <= 0` accordait d'office la confirmation de CASSURE à un
   titre illiquide — exactement le faux breakout que la règle volume du 25/09 devait bloquer).

Preuves : `test_b1_10_le_repli_est_journalise_et_marque`,
`test_b1_10_volume_nul_ne_confirme_aucune_cassure`.

## B1-11 — le stop annoncé supposait l'achat au bas de fourchette

`spec_fiche.py` publie désormais les **deux bornes** du stop « −15 % du PRIX PAYÉ » :
`stop` (achat au bas × 0,85) et `stop_hi` (achat plus haut × 0,85), avec le libellé
« Stop −15 % de TON prix payé : entre X F (achat au bas de la fourchette) et Y F (achat
plus haut) ». Avant, « Stop −15 % : X F » ne valait que pour un achat au bas — un achat
plus haut subissait un stop réel allant jusqu'à −19 % de son prix, sans le savoir.

Preuve : `test_b1_11_le_stop_publie_le_prix_paye_aux_deux_bornes`.

## B1-14 — `close_price` ne distinguait pas la DÉTECTION de la VENTE

L'auto-clôture (check dividende `portfolio.py`, stop/palier spé `speculation.py`) écrivait le
**cours de détection** dans `close_price`, et la commande `close` refusait ensuite d'enregistrer
le prix réel (`not p.closed`). Fix en 3 volets :

1. **Modèle** : nouveau champ `close_price_detecte` (positions dividende ET spé) ;
   `close_price` = prix de **VENTE RÉEL**, 0 tant que non confirmé.
2. **Auto-clôture** → écrit `close_price_detecte` uniquement (l'ancien champ ne reçoit plus
   jamais un cours non exécuté) ; la réouverture B1-01 efface les deux.
3. **CLI** : `portf close CODE --price X` et `spec close CODE --price X` acceptent une
   position **déjà clôturée** → enregistrent le prix de vente réel (le message affiche la
   détection conservée à part). Sans `--price`, la commande DIT quoi faire au lieu de
   recopier un cours qui n'est pas une vente.

Preuves : `test_b1_14_l_auto_cloture_note_le_cours_de_detection_pas_une_vente`,
`test_b1_14_portf_close_enregistre_le_prix_reel`.

## B1-15 — l'alerte de plus-value affichait un gain BRUT

`_profit_info_alert` publie « ≈ X nets si tu vendais maintenant (frais de vente ≈ 1,4 %
déduits) » via `_sell_profit_net` — le même net que le chemin jumeau `_double_option_alert`.
Avant : « Tu gagnerais X » — un brut, avec un ton de certitude, contraire au principe NET
de l'IPS §1.

Preuve : `test_b1_15_l_info_plus_value_affiche_un_gain_NET`.

## Référence des sorties régénérée (procédure du lot 5)

`scripts/capturer_sorties.py` : le Namespace simulé de `portf close` fournit `price: None`
(le parser réel le produit toujours). Diff **relu** : **49 sorties modifiées, toutes la ligne
B1-15** (« Tu gagnerais » → « ≈ … nets ») ; 0 disparue, 0 apparue, **398 sorties** (inchangé).

## Vérifications (13/10/2026)

- `pytest` : **517 passed** (511 + 6).
- Filets : constantes **224/224** · chemins **0** · sorties **398/398** (régénérées et relues).
- Aucun chiffre publié modifié → l'audit des preuves (`chiffres_publies_verifies.md`) reste
  valide tel quel.

## Après ce lot

Non statués restants : **B2-08** (6 wrappers de production hors dépôt), **R-002** (tests de
mutation absents — limite assumée), purge d'historique git (décision LEO).
