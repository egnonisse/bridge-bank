"""Catalogue des règles métier de Bridge Bank — une valeur, un endroit, une provenance.

POURQUOI CE MODULE
------------------
Un audit du 08/10/2026 a trouvé 194 définitions de constantes pour 159 notions, dont
plusieurs recopiées d'un module à l'autre : le PER maximum dans 4 fichiers, le payout
dans 3, l'IRVM sous 2 noms. Deux conséquences réelles, pas théoriques :

  - « combien de cas faut-il pour valider un seuil » avait DEUX réponses (6 et 8) ;
  - `FRAIS = 0.028` (aller-retour) et `FRAIS_PAR_SENS = 0.014` portent le même mot
    « FRAIS » avec des sens OPPOSÉS — les confondre double les frais, en silence.

CE MODULE EST UN CATALOGUE, PAS UNE USINE
-----------------------------------------
Il ne contient QUE des valeurs, aucune logique, et n'importe rien d'autre que
`taxation` (qui est lui-même sans dépendance). Il n'introduit donc aucun cycle d'import.

Il ne redéfinit PAS la fiscalité : `taxation.py` en est déjà la source correcte (taux de
courtage, TVA, frais BRVM, conservation, IRVM). Ce module la RÉEXPORTE sous les noms
attendus par le reste du code. Une seule valeur, un seul endroit — le reste s'y réfère.

RÈGLE DE PROVENANCE (demande LEO du 08/10/2026)
-----------------------------------------------
**Chaque règle dit d'où vient son chiffre.** Sans cela, un seuil devient un nombre
magique : personne ne sait s'il repose sur une mesure, sur une loi, ou sur une intuition
recopiée trois fois.

Une date n'est écrite que lorsqu'elle PORTE l'information (un taux fiscal change par
décret ; « PER ≤ 14 » ne change pas par date). Une date qui ne sert à rien devient fausse
en vieillissant — pire que pas de date.

COMMENT L'UTILISER
------------------
Les modules existants gardent leurs noms locaux, ce qui évite de toucher leur logique :

    from .regles import PER_MAX as PER_MAX_NOYAU

Vérification de non-régression (aucune valeur ne doit avoir bougé) :

    python scripts/auditer_constantes.py --comparer
"""
from __future__ import annotations

from .taxation import (BROKERAGE_FEE, BROKERAGE_MIN, IRVM_DIVIDEND_TAX,
                       TARGET_NET_YIELD_ENTRY, TARGET_NET_YIELD_EXIT)

# ══════════════════════════════════════════════════════════════════════════════
#  1. FISCALITÉ ET FRAIS
#  PROVENANCE : grille tarifaire Bridge Securities (courtage) + Code général des
#  impôts de Côte d'Ivoire (retenue sur dividende). Ces valeurs sont IMPOSÉES :
#  elles ne se discutent pas, elles se vérifient auprès du courtier et de la DGI.
# ══════════════════════════════════════════════════════════════════════════════

IRVM = IRVM_DIVIDEND_TAX          # 0,12 — retenue à la source, CI (BOC du 15/06/2026 ;
                                  #        10 % en 2019, 15 % en 2025 → à revérifier)
FRAIS_PAR_SENS = BROKERAGE_FEE    # 0,014 — courtage 0,80 % + TVA 18 % + BRVM 0,456 %
FRAIS_ALLER_RETOUR = 2 * FRAIS_PAR_SENS   # 0,028 — DÉRIVÉ, jamais recopié
FRAIS_MINIMUM = BROKERAGE_MIN     # 1 000 F — plancher de courtage par ordre

# ══════════════════════════════════════════════════════════════════════════════
#  2. FILTRES D'ENTRÉE DU NOYAU  (les 4 conditions pour acheter un loyer)
#  PROVENANCE : IPS (Investment Policy Statement) de LEO — stratégie value héritée de
#  Graham/Buffett/Greenblatt. Aucune n'a été optimisée sur le passé : ce sont des
#  EXIGENCES d'acheteur, pas des paramètres ajustés.
# ══════════════════════════════════════════════════════════════════════════════

PER_MAX = 14.0            # au-delà : l'action coûte trop cher ses bénéfices
PAYOUT_MAX = 0.80         # au-delà : le dividende est tendu, la coupe se rapproche
PAYOUT_TIGHT = PAYOUT_MAX  # nom historique (portfolio.py, noyau_check.py) — même règle
PAYOUT_CRITICAL = 1.00    # au-delà : elle paie plus qu'elle ne gagne — non soutenable
PER_ABSURD = 50.0         # au-delà : le bénéfice est quasi nul, le PER n'informe plus
RENDEMENT_NET_ENTREE = TARGET_NET_YIELD_ENTRY   # 0,04 — le loyer minimum acceptable
RENDEMENT_NET_SORTIE = TARGET_NET_YIELD_EXIT    # 0,02 — en dessous, on vend
RENDEMENT_NET_MIN = RENDEMENT_NET_ENTREE        # nom historique (backtest_noyau.py)

# ══════════════════════════════════════════════════════════════════════════════
#  3. SEUILS DE VENTE SUR GAIN  (un signal doit être prouvé, sinon il informe)
#  PROVENANCE : MESURÉE — 179 détachements de dividende et 5 196 observations sur
#  29 ans (scripts/validation_longue.py, scripts/mesurer_detachements.py). Le test de
#  Wilson (src/seuils_vente.py) montre qu'aucun seuil de vente sur gain n'atteint 50 %
#  de borne basse : le mode informatif est la RÈGLE, pas l'exception.
# ══════════════════════════════════════════════════════════════════════════════

EPISODES_MIN = 8          # en dessous, une probabilité est du bruit (voir seuils_vente)
BORNE_BASSE_MIN = 0.50    # un seuil ne déclenche que si sa borne basse bat le hasard
PROFIT_ALERT_THRESHOLD = 0.13   # défaut pour un titre sans historique suffisant
SELL_FRACTION = 1 / 3     # fraction vendue à un palier (1/3 = 33 %)

# ══════════════════════════════════════════════════════════════════════════════
#  4. LIMITES DE CONCENTRATION  (informatives : elles n'interdisent jamais)
#  PROVENANCE : IPS de LEO — règles de risque personnel (« ligne Buffett » : jamais
#  plus de la moitié dans un seul titre). Elles INFORMENT, elles ne bloquent pas
#  (règle LEO du 11/09/2026 : le système informe, il n'empêche jamais une alerte).
# ══════════════════════════════════════════════════════════════════════════════

MAX_POSITION_WEIGHT = 0.35   # poids marché libre sous 35 % ; au-delà, l'alerte est graduée
MAX_BUY_WEIGHT = 0.40        # poids d'ACHAT maximum après un renforcement « limité »
MAX_MARKET_WEIGHT = 0.50     # ligne Buffett : jamais plus de la moitié dans un seul titre

# ══════════════════════════════════════════════════════════════════════════════
#  5. SEUILS D'ALERTE
#  PROVENANCE : convention d'affichage, sans effet sur une décision d'achat ou de
#  vente. Modifiable sans rejouer le passé.
# ══════════════════════════════════════════════════════════════════════════════

LOSS_ALERT_THRESHOLD = 0.10  # moins-value ≥ −10 % : alerte de couverture par les dividendes

# ══════════════════════════════════════════════════════════════════════════════
#  6. POINT D'ENTRÉE — position du prix dans l'HISTORIQUE du titre
#  PROVENANCE : constat du 30/10/2026. PALC acheté au 78e percentile d'un titre PLAT
#  (+1,3 %/an, −44 % sous son ATH) : les 8 filtres du noyau vérifiaient tous le
#  DIVIDENDE, aucun le PRIX. Coût mesuré : avec le même capital, 36 actions au prix
#  médian (6 200 F) au lieu de 26 → +4 518 F/an de loyer (+39 %).
#  Ces seuils INFORMENT (verdict publié dans l'alerte) ; ils ne bloquent JAMAIS un
#  achat — même doctrine que les limites de concentration (11/09/2026 : le système
#  informe, LEO décide).
#  NUANCE FONDATRICE : sur un titre en CROISSANCE, un percentile élevé est NORMAL —
#  c'est la signature d'un titre qui monte (SGBC 98e à +11,2 %/an, SNTS 99e à
#  +6,0 %/an). Le signal n'existe que sur un titre PLAT/CYCLIQUE (PALC +1,3 %/an).
# ══════════════════════════════════════════════════════════════════════════════

POINT_ENTREE_CROISSANCE_AN = 6.0        # ≥ 6 %/an = croissance : percentile non pertinent
POINT_ENTREE_PERCENTILE_PRUDE = 70.0    # titre plat : au-delà, point d'entrée moyen-haut
POINT_ENTREE_PERCENTILE_CHER = 85.0     # titre plat : au-delà, achat tardif dans le cycle
