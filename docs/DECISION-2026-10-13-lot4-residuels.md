# Décision du 13/10/2026 — LOT 4 : résiduels de l'audit (C7, C8, C9) et moteur A3-12

## Contexte

Suite des lots 1-3 (12/10). Ce lot ferme les résiduels P2/P3 de l'audit :
**B2-07** (livraison des jobs agents), **B2-05/B2-06/B2-12** (silences de la collecte, drapeau
dilué), **A3-11** (dividende courant, C7) et **A3-12** (4 défauts du moteur de simulation).
Chaque correction suit le protocole établi : test qui verrouille → correction → preuve en réel
→ re-mesure des chiffres publiés si le moteur change.

## 1. Livraison des jobs agents (B2-07 + radar) — commit `160e53e`

**Constat en réel** : le job value (`9bf21948f66b`) échouait à CHAQUE run depuis ≥ le 07/10
(`[blocked_config] platform 'telegram' has no gateway credentials`) et le radar était en
`delivery: suppressed` sur tous ses runs — aucun rapport de ces 2 jobs n'atteignait LEO.
Cause : la passerelle Telegram d'Hermes n'est pas connectée sur cette machine (règle du
18/09 : les crons livrent par le **notifier interne** du projet).

**Correction** : découpage des messages > 4 096 caractères dans `src/notify.py` (un rapport
long était *perdu* à l'envoi) ; `scripts/notifier_envoyer.py` (pont CLI agent → notifier) ;
les 2 jobs en `deliver=local` + étape d'ENVOI explicite dans le prompt.
**Preuves** : message de test reçu ; run value `completed` avec la réponse conforme ; run radar
`completed` ; plus aucun `failed`/`blocked_config`.

## 2. Silences de la collecte et drapeau d'empreinte (C9 partiel, C8/B2-12) — commits `fe94aa7`, `0dc4b9b`

- **B2-05** : `ajuster_historique` LÈVE si le fichier des divisions manque (plus jamais un
  historique brut non ajusté en silence — classe de l'incident du 21/08).
- **B2-06** : repli d'historique journalisé + titres en échec comptés (`backtest.py`) ; barre
  sans horodatage ÉCARTÉE (plus de date « maintenant » fabriquée) ; valeur illisible signalée
  vs champ absent muet (`bsapi.py`).
- **B2-12** : le drapeau `*` exclut les 14 fichiers d'état écrits par le fonctionnement normal
  (caches, états de veille, snapshots suivis) ; `profit_thresholds.json`, `regles.py`,
  `config.yaml` restent surveillés — un vrai changement de règles porte toujours l'étoile.

## 3. Dividende courant point-in-time (A3-11, C7) — commit `2d81f73`

- **Péremption** : `dernier_dividende_connu` retourne « inconnu » au-delà de 456 jours
  (15 mois) — plus de rendement fictif d'un dividende coupé (scénario BNBC).
- **Cumul** : le dps point-in-time est la SOMME des versements de l'année écoulée
  (acompte + solde) ; le payout dps/BPA redevient annuel/annuel.
- **Preuve** : 6 tests ; **rejeu complet des chiffres publiés : EXIT 0, aucun écart**.

## 4. Moteur de simulation : 4 corrections (A3-12) — ce commit

| Défaut | Correction |
|---|---|
| (a) dividendes d'une position soldée perdus du compte-rendu | cumul moteur `dividendes_encaisses` — le revenu réel reste compté |
| (b) réserve de cash franchie d'une demi-tranche | le montant acheté est borné par le disponible (`min(tranche, dispo)`) |
| (c) dividende crédité APRÈS les ordres du jour (achat à l'ex-date rémunéré à tort) | section dividende AVANT les ordres — le droit va aux détenteurs d'avant l'ex-date |
| (d) plafond de ligne contournable en réinvestissant le produit d'une vente | le plafond se mesure sur le cumul investi (`investi_total`), plus sur `cout_total` |

## 5. Impact sur les chiffres publiés (re-mesure du 13/10)

Preuve brute : `audit/preuves/attribution_remesuree_2026-10-13.txt`.

| Mesure (attribution 2022-2026, 5 titres réels) | 12/10 | **13/10 (moteur corrigé)** |
|---|---|---|
| Noyau passif (A) | 232,2 % · expo 94,9 % | **233,0 % · expo 94,9 %** |
| Renforcement (C) | +26,2 pt | **+26,7 pt** |
| Paliers (D) | −45,4 pt | **−49,0 pt** |
| Stratégie complète (B) | −31,2 pt | **−43,0 pt** |

**Le sens est intact, le constat renforcé** : les paliers coûtent davantage (le fix (d) retire
un « gain » de réinvestissement qui n'aurait pas dû être compté), le renforcement apporte
légèrement. Référence mise à jour (`audit/preuves/chiffres_reference.json`, provenance 13/10)
et documents alignés : `docs/INVARIANTS-METIER.md` (B1), `docs/RAPPORT-VALIDATION-28-ANS.md`,
`audit/chiffres_publies_verifies.md`. Jamais de réécriture silencieuse : les anciennes valeurs
restent datées dans l'historique.

## Preuves d'ensemble

- Suite de tests : **484 passed, 0 xfailed** (12 tests neufs dans ce lot : 6 collecte, 2
  empreinte, 6 A3-11, 4 A3-12 — et alignements des tests existants du moteur).
- Rejeu des chiffres publiés : EXIT 0 avant A3-12 (aucun écart) ; re-testé après mise à jour
  de la référence (voir rapport daté dans `audit/preuves/`).
- Épreuves hors référence (`tester_noyau`, `tester_revenu_vs_hasard`) : exécutées après A3-11,
  exit 0, conclusions inchangées (« le noyau apporte du revenu mais l'avantage n'est pas
  établi »).

## Ce qui reste

- **Phases 6-7 de l'audit** (contrats inter-modules, sécurité et intégrité).
- **Résiduels P3** : B2-10 (trois caches d'historique, le backtest de validation lit le brut),
  B2-09 (paths), C7 partiel (fraîcheur des deux caches fondamentaux — à re-cartographier).
- **Phase 8** : exécution contrôlée (autorisation LEO).
