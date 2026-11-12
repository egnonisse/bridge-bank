# PLAN COMPLET — ce que la veille spéculative encaisse réellement

Audit produit par `scripts/rejouer_plan_complet.py` (12/11/2026). Tous les chiffres
ci-dessous sont la **sortie réelle du script** sur le cache PROPRE (divisions ajustées),
rejoué en lecture seule. Aucun chiffre n'est inventé ; aucun fichier n'a été écrit par
le script.

---

## 1. Le problème que ce rejeu tranche

Jusqu'ici le projet publie des taux du type « ton palier +20 % est touché dans 59 % des
cas ». C'est une mesure du **PLUS HAUT atteint dans les 12 mois** : elle ignore (a) le
stop −15 %, (b) le plan de vente par tiers, (c) les frais réels avec minimum par ordre,
(d) la capacité réelle du marché à absorber l'ordre. Un auditeur externe a relevé que ces
chiffres ne démontrent pas la rentabilité du plan.

Ce rejeu simule le **plan annoncé dans les fiches** (`src/strategie/spec_fiche.py`),
séance par séance, sur le même univers que l'export (1 615 cas à horizon complet) :

- achat au cours du signal (dernière clôture connue) ;
- **stop −15 % du prix payé** → vente de tout, sans discuter ;
- **+20 %** du prix payé → vente d'⅓ du titre initial ;
- **+35 %** → ⅓ ; **+50 %** → le dernier tiers ;
- reliquat (tiers jamais vendus) sorti au close de la dernière séance de l'horizon.

## 2. Hypothèses explicites (et leur sens pessimiste/optimiste)

| # | Hypothèse | Biais |
|---|---|---|
| 1 | Exécution au **CLOSE** (comme l'export et le calibrage ; pas de données intraday) | **OPTIMISTE** : un stop intraday aurait touché plus tôt, à un prix pire |
| 2 | **Ordre des événements le même jour** : stop et paliers vivent de part et d'autre de l'entrée (−15 % vs ≥ +20 %), ils ne peuvent pas partager un même close. Cas résiduel = gap qui traverse un palier → la tranche se remplit **AU NIVEAU du palier** (ordre limite), jamais au-dessus. S'il fallait trancher « stop ou palier le même jour », on retient **le stop d'abord** (le plan dit « vends tout, sans discuter ») | **PESSIMISTE** (on ne crédite jamais l'excédent d'une gap, on renonce au palier le jour d'un stop) |
| 3 | « ⅓ » = tiers du **nombre de titres initial**, pas du reliquat | conforme au texte de la fiche |
| 4 | Frais = `commission()` de `src/taxation.py` : courtage 0,80 % (**min 1 000 F**) + TVA 18 % + BRVM 0,456 % | **réaliste** — le minimum mord sous ~125 000 F |
| 5 | Taille de position explicite : 50 000 / 100 000 / 500 000 F (défaut **100 000 F**) | nécessaire pour lire le minimum de frais |
| 6 | Contrainte de volume : un ordre ne peut absorber plus de **10 %** du volume de la séance (unité : titres, champ `volume` du cache) | hypothèse de participation annoncée |

## 3. Univers rejoué (sortie réelle)

```
cache PROPRE lu en lecture seule : 48 titres
cas à horizon COMPLET : 1615   CASSURE 267, EVEIL 934, PANIQUE 414
cas récents NON MATURES : 292   CASSURE 82, EVEIL 160, PANIQUE 50
diagnostic volume des séances suivies : 100.0 % avec volume > 0, volume médian 846 titres
```

Les 1 615 cas reproduisent exactement l'univers publié (contrat : 267 / 934 / 414).
Le « naïf +20 % » re-mesuré ici (69,3 % / 60,6 % / 58,9 %) est **identique** au calibrage
publié (0,693 / 0,606 / 0,589) : même univers, deux mesures, écart net attribuable au seul
plan de vente.

## 4. Frais réels par ordre — le minimum de 1 000 F ne pardonne pas

```
taille de position |  achat (1 ordre) |      tiers vendu +20 %
             50000 F |            2.82 % |                6.36 % (tranche 20000 F)
            100000 F |            1.64 % |                3.41 % (tranche 40000 F)
            500000 F |            1.40 % |                1.40 % (tranche 200000 F)
```

Lecture : le « 1,4 % par sens » annoncé n'est vrai qu'à partir de ~125 000 F par ordre.
À **100 000 F de position**, l'achat paie 1,64 % et chaque tiers revendu au palier +20 %
(= 40 000 F) paie **3,41 %**. À **50 000 F**, le tiers revendu paie **6,36 %**. Le plan
vend par tiers → il **découpe ses ordres en petits montants** et maximise l'impact du
minimum : c'est structurellement défavorable aux petites positions.

## 5. Plan complet par schéma — position 100 000 F

```
   schéma     n  net moyen    médian  % perdants  perte moy.  gain moy.  espérance  net total
  CASSURE   267     +7.1 %   +15.0 %       36.7 %     -20.1 %    +22.9 %     +7.1 %     +7.1 %
    EVEIL   934     +2.2 %    -1.5 %       50.7 %     -18.0 %    +23.1 %     +2.2 %     +2.2 %
  PANIQUE   414     -1.2 %   -10.2 %       57.0 %     -18.4 %    +21.7 %     -1.2 %     -1.2 %
```

(`rendement net = P&L encaissé / capital investi`, frais achat + vente inclus, minimum
1 000 F par ordre. `net total = Σ P&L / Σ capital investi` — égal à la moyenne ici car
les positions sont de taille égale, ce n'est pas un rendement composé.)

Trois constats :

1. **La panique est perdante nette.** Espérance **−1,2 %**, médiane **−10,2 %**, 57 % de
   cas perdants, perte moyenne −18,4 %. Le schéma le plus fréquent en bas de fourchette
   encaisse moins que zéro une fois le stop et les frais appliqués.
2. **L'éveil est au point mort.** Médiane **−1,5 %** : un cas sur deux perd de l'argent ;
   le gain moyen des gagnants (+23,1 %) ne compense que de justesse la perte moyenne des
   perdants (−18,0 %).
3. **Seule la cassure reste nettement positive** (+7,1 % d'espérance, médiane +15,0 %,
   36,7 % de perdants) — le schéma rare.

## 6. Le chiffre naïf vs le plan complet — l'écart demandé

```
   schéma     n naïf +20 % plan +20 % naïf +50 % plan +50 %  naïf médian  plan médian
  CASSURE   267      69.3 %      61.8 %      43.4 %      37.8 %      +16.3 %      +15.0 %
    EVEIL   934      60.6 %      51.7 %      35.8 %      30.3 %       +5.9 %       -1.5 %
  PANIQUE   414      58.9 %      46.4 %      32.1 %      24.2 %       +3.2 %      -10.2 %
```

- « ton palier +20 % est touché dans 59 % des cas » (PANIQUE) : c'est le **plus haut
  atteint**. Le plan ne vend réellement son premier tiers que dans **46,4 %** des cas —
  dans les 12,5 points restants, le titre a touché +20 % **après** avoir enfoncé le stop
  (le plan était déjà sorti, à perte).
- Le stop −15 % mord dans **55,8 %** des cas PANIQUE (50,1 % EVEIL, 37,8 % CASSURE,
  re-mesuré ici). Plus de la moitié des rachats de panique sortent à perte avant d'avoir
  vendu un seul tiers.
- **L'écart le plus parlant est la médiane** : l'EVEIL passe de **+5,9 %** naïf (ce que le
  calibrage publie) à **−1,5 %** encaissé ; la PANIQUE de **+3,2 %** à **−10,2 %**. Le
  plan par tiers vend trop tôt les gagnants (un tiers à +20 % seulement) et garde trop
  longtemps les perdants (reliquat revalorisé au close final).

## 7. Par zone × schéma — position 100 000 F

```
  CASSURE — n=267
      zone     n  net moyen    médian  % perdants  stop touché  +20 vendu
      0-20    35    +14.2 %   +28.7 %       28.6 %        22.9 %      74.3 %
     20-40    51     +5.7 %    +3.3 %       41.2 %        37.3 %      62.7 %
     40-60    41     +2.4 %    -3.9 %       51.2 %        48.8 %      48.8 %
     60-80    30    +10.6 %   +25.2 %       33.3 %        30.0 %      66.7 %
    80-100   110     +6.3 %   +15.5 %       32.7 %        37.3 %      60.9 %

  EVEIL — n=934
      zone     n  net moyen    médian  % perdants  stop touché  +20 vendu
      0-20   352     +2.5 %    -6.3 %       51.7 %        50.3 %      52.6 %
     20-40   181     +1.2 %    -5.8 %       54.1 %        49.7 %      49.2 %
     40-60   146     -1.6 %   -17.9 %       59.6 %        56.2 %      41.1 %
     60-80    99     +3.0 %    +3.5 %       48.5 %        46.5 %      57.6 %
    80-100   156     +6.0 %   +15.7 %       37.8 %        37.8 %      59.0 %

  PANIQUE — n=414
      zone     n  net moyen    médian  % perdants  stop touché  +20 vendu
      0-20   221     -1.1 %   -17.9 %       57.5 %        55.2 %      43.9 %
     20-40    81     -2.3 %   -10.5 %       60.5 %        55.6 %      44.4 %
     40-60    50     -2.2 %   -14.9 %       62.0 %        60.0 %      48.0 %
     60-80    43     -4.5 %   -17.9 %       58.1 %        53.5 %      44.2 %
    80-100    19    +13.5 %   +22.9 %       21.1 %        21.1 %      84.2 %
```

Points saillants :

- **PANIQUE est négative dans 4 zones sur 5**, seule la zone 80-100 (19 cas) est positive
  (+13,5 %). Les zones 0-20 (221 cas) et 40-60 (50 cas) ont une médiane de **−17,9 %** :
  le « rachat de panique en bas de fourchette » est exactement là où le stop mord le plus
  (55-60 % de stop touché).
- **La zone 40-60 est la pire pour EVEIL** (−17,9 % de médiane, 59,6 % de perdants) : le
  « milieu de fourchette » n'a ni rebond ni cassure.
- **CASSURE reste positive partout**, avec la zone 0-20 en tête (+28,7 % de médiane).

## 8. Impact de la taille de position (minimum de frais)

```
        taille  net moyen    médian  % perdants  espérance  net total
         50000     -1.2 %    -2.4 %       51.6 %     -1.2 %     -1.2 %
        100000     +2.2 %    -0.1 %       50.0 %     +2.2 %     +2.2 %
        500000     +3.6 %    +0.7 %       49.5 %     +3.6 %     +3.6 %
```

Tous schémas confondus (1 615 cas) : la taille de position fait varier l'espérance nette
de **−1,2 % à +3,6 %**, soit **4,8 points**, uniquement à cause du minimum de 1 000 F qui
écrase les ordres de 50 000 F. À 50 000 F, le plan complet est **perdant en moyenne**.
Le plan de vente par tiers aggrave ceci : il transforme chaque position en 4 ordres (1
achat + 3 ventes), dont 3 sous la barre des 125 000 F.

## 9. Contrainte de volume — 10 % du volume de la séance

| position | CASSURE | EVEIL | PANIQUE |
|---|---|---|---|
| 50 000 F | 28 cas (10,5 %) | 186 cas (19,9 %) | 102 cas (24,6 %) |
| 100 000 F | 51 cas (19,1 %) | 276 cas (29,6 %) | 141 cas (34,1 %) |
| 500 000 F | 123 cas (46,1 %) | 557 cas (59,6 %) | 260 cas (62,8 %) |

Un cas est « inexécutable » dès qu'**une** de ses ventes requises (stop ou palier) exige
plus de titres que 10 % du volume de la séance. Lecture : même à 100 000 F, **un cas de
panique sur trois** ne peut pas exécuter son ordre tel quel (le titre a un volume trop
mince au moment où le plan ordonne de vendre). À 500 000 F, plus de la moitié des cas le
sont. Le volume médian des séances suivies est de 846 titres : une position de 500 000 F
sur un titre à 5 000 F = 100 titres, dont chaque tiers (33 titres) dépasse 10 % du volume
d'une part importante des séances. **La contrainte est réelle et croît avec la taille** :
le plan n'est pas exécutable « à volonté » sur les titres illiquides de la BRVM.

## 10. Cas récents non matures — exclus des métriques

```
   schéma     n  stop déjà touché  encore ouvert  3 tiers vendus
  CASSURE    82                17             31              34
    EVEIL   160                41             58              61
  PANIQUE    50                12             25              13
```

292 signaux récents (moins de 12 mois de recul) ont été détectés puis **écartés** des
métriques à 12 mois. Parmi eux, 70 ont déjà touché le stop, 114 sont encore ouverts, 108
ont déjà vendu leurs trois tiers. Ces cas sont hors statistique : on ne peut pas encore
connaître leur issue.

## 11. Synthèse — ce qui change

| Mesure publiée | Ce qu'elle dit | Ce que le plan encaisse réellement |
|---|---|---|
| « +20 % touché dans 59 % des cas » (PANIQUE) | plus haut atteint, stop ignoré | **46,4 %** des cas vendent réellement le 1er tiers |
| « +50 % touché dans 32 % des cas » (PANIQUE) | idem | **24,2 %** vendent les trois tiers |
| médiane nette PANIQUE +3,2 % | rendement 12 mois net de 2,8 % | **−10,2 %** une fois stop + tiers + frais minimum |
| médiane nette EVEIL +5,9 % | idem | **−1,5 %** |
| médiane nette CASSURE +16,3 % | idem | **+15,0 %** |

L'écart vient de trois mécanismes qui se cumulent : (1) le stop sort avant le palier dans
plus de la moitié des cas (le « touché après le stop » est un gain fantôme) ; (2) le plan
vend un tiers à +20 % seulement et garde le reliquat jusqu'au bout, il plafonne les
gagnants et garde les perdants ; (3) les frais réels (minimum 1 000 F, ordres découpés en
tiers) et la contrainte de volume rabotent l'encaissable sur les petites positions et les
titres illiquides.

## 12. Ce que ce rejeu ne prouve pas

- **Pas une stratégie rentable ou non.** Ce rejeu mesure l'encaissable du plan annoncé,
  pas la rentabilité future ; c'est un constat descriptif sur 1 615 épisodes passés.
- **Pas de comparaison à un benchmark.** Aucun indice BRVM ni alternative « acheter-tenir
  sans paliers » n'est rejoué ici : on ne sait pas si garder la position entière 12 mois
  aurait fait mieux ou moins bien que le plan par tiers.
- **Pas de dividendes encaissés.** Les cours du cache propre sont non ajustés des
  dividendes ; le loyer éventuel (≈ 4,6 % net/an sur le noyau) s'ajouterait en plus — il
  est hors du plan spéculatif, qui joue le prix.
- **Pas de couverture du biais de survie.** Les titres radiés sont absents du cache : les
  chiffres sont optimistes, exactement comme ceux qu'ils corrigent.
- **Pas de résolution intraday.** L'exécution au close et le « stop d'abord » sont des
  conventions ; un rejeu sur données intraday (absent du projet) pourrait donner un
  encaissable différent, très probablement plus bas pour le stop.
- **Pas de validité statistique fine des zones.** Les cellules de zone × schéma sous
  ~10 cas (ex. PANIQUE 80-100, n=19 ; CASSURE 60-80, n=30) sont des indications, pas des
  lois — même règle que `SEUIL_CAS_ZONE = 10` dans le projet.
- **La contrainte de volume est une hypothèse de participation (10 %), pas une règle du
  marché.** Une autre hypothèse (5 % ou 20 %) déplacerait le nombre de cas inexécutables.
- **Pas de frais de conservation ni d'IRVM** : seuls les frais de transaction
  (`commission()`) sont appliqués — c'est la grille de l'ordre, pas le coût de détention.
