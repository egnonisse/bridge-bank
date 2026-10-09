# Audit des constantes métier — inventaire, doublons et familles

**202 définitions** pour **186 constantes distinctes**.

---

## 1. ⚠️ La même NOTION sous plusieurs noms — le piège le plus dangereux

Le détecteur par nom ne voit rien ici : les constantes s'appellent différemment
alors qu'elles parlent de la même chose. **Un module qui copie l'une en croyant
l'autre produit un chiffre faux sans qu'aucun test ne s'en aperçoive.**

### frais de courtage

| Constante | Valeur | Module |
|---|---|---|
| `FRAIS_ALLER_RETOUR` | `<expression: 2 * FRAIS_PAR_SENS>` | src.regles |
| `FRAIS_MINIMUM` | `<expression: BROKERAGE_MIN>` | src.regles |
| `FRAIS_PAR_SENS` | `<expression: BROKERAGE_FEE>` | src.regles |

### limites de concentration

| Constante | Valeur | Module |
|---|---|---|
| `CONCENTRATION_WARN` | `30.0` | src.report |
| `MAX_BUY_WEIGHT` | `0.4` | src.regles |
| `MAX_MARKET_WEIGHT` | `0.5` | src.regles |
| `MAX_POSITION_WEIGHT` | `0.35` | src.regles |

### part du benefice versee

| Constante | Valeur | Module |
|---|---|---|
| `PAYOUT_CRITICAL` | `1.0` | src.regles |
| `PAYOUT_MAX` | `0.8` | src.regles |
| `PAYOUT_TIGHT` | `<expression: PAYOUT_MAX>` | src.regles |

### prix maximum paye

| Constante | Valeur | Module |
|---|---|---|
| `PER_ABSURD` | `50.0` | src.regles |
| `PER_MAX` | `14.0` | src.regles |

### rendement minimum exige

| Constante | Valeur | Module |
|---|---|---|
| `DIV_YIELD_ENTRY` | `<expression: gross_yield_for_net(TARGET_NET_YIELD_ENTRY)>` | src.portfolio |
| `DIV_YIELD_EXIT` | `<expression: gross_yield_for_net(TARGET_NET_YIELD_EXIT)>` | src.portfolio |
| `RENDEMENT_NET_ENTREE` | `<expression: TARGET_NET_YIELD_ENTRY>` | src.regles |
| `RENDEMENT_NET_MIN` | `<expression: RENDEMENT_NET_ENTREE>` | src.regles |
| `RENDEMENT_NET_SORTIE` | `<expression: TARGET_NET_YIELD_EXIT>` | src.regles |
| `TARGET_NET_YIELD_ENTRY` | `0.04` | src.taxation |
| `TARGET_NET_YIELD_EXIT` | `0.02` | src.taxation |

### reserve de liquidites

| Constante | Valeur | Module |
|---|---|---|
| `CASH_ALERT_DAYS` | `3` | src.report |
| `CASH_ALERT_MARGIN` | `5.0` | src.report |
| `TARGET_CASH` | `30.0` | src.report |

### retenue a la source

| Constante | Valeur | Module |
|---|---|---|
| `IRVM` | `<expression: IRVM_DIVIDEND_TAX>` | src.regles |
| `IRVM_DIVIDEND_TAX` | `0.12` | src.taxation |

### seuil de vente sur gain

| Constante | Valeur | Module |
|---|---|---|
| `BORNE_BASSE_MIN` | `0.5` | src.regles |
| `EPISODES_MIN` | `8` | src.regles |
| `PROFIT_ALERT_THRESHOLD` | `0.13` | src.regles |
| `PROFIT_DOWN_PROB` | `{'SNTS': 86, 'SGBC': 63, 'SLBC': 54, 'PALC': 45}` | src.portfolio |
| `PROFIT_SEUILS_CANDIDATS` | `<expression: SEUILS_CANDIDATS>` | src.portfolio |
| `PROFIT_THRESHOLDS` | `<expression: DATA_DIR / 'profit_thresholds.json'>` | src.paths |
| `PROFIT_THRESHOLDS_FILE` | `<expression: SEUILS_FILE>` | src.portfolio |
| `SELL_FRACTION` | `<expression: 1 / 3>` | src.regles |

### sortie de secours

| Constante | Valeur | Module |
|---|---|---|
| `LOSS_ALERT_THRESHOLD` | `0.1` | src.regles |
| `STOPOUT_COOLDOWN_DAYS` | `30` | src.spec_veille |
| `STOPOUT_SUSPEND_COUNT` | `2` | src.spec_veille |
| `STOPOUT_SUSPEND_DAYS` | `60` | src.spec_veille |

---

## 2. Doublons incohérents — même nom, valeurs différentes

**Aucune règle métier en divergence.** ✅

### Constantes techniques — divergence NORMALE

Ces constantes portent le même nom générique dans plusieurs modules
avec des valeurs différentes **par conception** (`STATE_FILE` vaut un
chemin distinct dans chaque module). Rien à corriger.

| Constante | Valeurs | Modules |
|---|---|---|
| `STATE_FILE` | <expression: DATA / 'spec_seen_state.jso · <expression: DATA_DIR / 'alerts_state.js · <expression: DATA_DIR / 'boc_state.json' · <expression: DATA_DIR / 'news_state.json · <expression: DATA_DIR / 'portfolio_state | src.alerts · src.boc · src.news · src.report · src.spec_veille |
| `MAX_WORKERS` | 3 · 6 · 8 | src.backtest · src.screener · src.screening |
| `CACHE_FILE` | <expression: DATA_DIR / 'fundamentals_ca · <expression: DATA_DIR / 'history_cache.p | src.backtest · src.screener |
| `COMPANY_HINTS` | {'bank_of_africa_sn': 'BOAS', 'societe_g · {'sgb': 'SGBC', 'sgci': 'SGBC', 'societe | src.boc · src.news |
| `POSITIONS_FILE` | <expression: DATA_DIR / 'bonds_positions · <expression: DATA_DIR / 'spec_positions. | src.bonds · src.speculation |
| `PROFIT_THRESHOLDS` | <expression: DATA_DIR / 'profit_threshol · <expression: SEUILS_PAR_DEFAUT> | src.paths · src.portfolio |
| `ALERT_STATE_FILE` | <expression: DATA_DIR / 'portf_alert_sta · <expression: DATA_DIR / 'radar_alert_sta | src.portfolio · src.radar |

---

## 3. Doublons cohérents (même valeur, plusieurs endroits)

| Constante | Fois | Modules |
|---|---|---|
| `HEADERS` | 5 | src.boc · src.dividend_history · src.fundamentals · src.live · src.news |
| `REVERSAL_FILE` | 2 | src.cache_integrity · src.portfolio |

---

## 4. Inventaire complet par domaine

### allocation (3)

| Constante | Valeur | Module |
|---|---|---|
| `TARGET_BONDS` | `0.0` | src.report |
| `TARGET_CASH` | `30.0` | src.report |
| `TARGET_STOCKS` | `70.0` | src.report |

### autre (101)

| Constante | Valeur | Module |
|---|---|---|
| `BAISSIER` | `baissier` | src.regime_marche |
| `BASE` | `https://stockanalysis.com/quote/brvm/{}/{}` | src.fondamentaux_historiques |
| `BROKERAGE_FEE` | `<expression: BROKERAGE_RATE * (1 + TVA_RATE) + BRVM_FEES_RATE>` | src.taxation |
| `BROKERAGE_MIN` | `1000.0` | src.taxation |
| `BROKERAGE_RATE` | `0.008` | src.taxation |
| `BRVM_ANNOUNCE_PAGES` | `{'dividendes': 'https://www.brvm.org/fr/esv/paiement-de-dividendes', 'communiques': 'https://www.brvm.org/fr/emetteurs/type-annonces/communiques', 'ag': 'https://www.brvm.org/fr/emetteurs/type-annonces/convocations-assemblees-generales', 'dirigeants': 'https://www.brvm.org/fr/emetteurs/type-annonces/changements-de-dirigeants', 'notations': 'https://www.brvm.org/fr/emetteurs/type-annonces/notations-financieres'}` | src.news |
| `BRVM_FEES_RATE` | `0.00456` | src.taxation |
| `CASH_CREDIT_OFFSET_DAYS` | `1` | src.live |
| `CHAMPS_AUTORISES` | `<expression: ('code', 'protege') + CHAMPS_MESURE + CHAMPS_DECISION>` | src.schema_seuils |
| `CHAMPS_DECISION` | `['threshold', 'mode']` | src.schema_seuils |
| `CHAMPS_MESURE` | `['down_prob', 'borne_basse', 'episodes', 'median_pct', 'significatif']` | src.schema_seuils |
| `CHAMPS_REQUIS_ECRITURE` | `['code', 'threshold', 'down_prob', 'borne_basse', 'episodes', 'significatif', 'mode']` | src.schema_seuils |
| `CHAMPS_REQUIS_LECTURE` | `['threshold']` | src.schema_seuils |
| `CODE_ATTENDU` | `<expression: re.compile('^[A-Z0-9][A-Z0-9.\\-]{0,15}$')>` | src.schema_seuils |
| `COMPANY_HINTS` | `{'sgb': 'SGBC', 'sgci': 'SGBC', 'societe generale': 'SGBC', 'sonatel': 'SNTS', 'solibra': 'SLBC', 'palm': 'PALC', 'palmci': 'PALC', 'sogb': 'SOGC', 'boa senegal': 'BOAS', 'bank of africa senegal': 'BOAS'}` | src.boc |
| `COMPARATEURS` | `['<=', '>=', '<', '>', '==', '!=']` | src.challenge_schema |
| `CONFIG_PATH` | `<expression: ROOT / 'config.yaml'>` | src.main |
| `CUSTODY_ANNUAL` | `<expression: CUSTODY_PER_QUARTER * 4>` | src.taxation |
| `CUSTODY_MIN_PER_QUARTER` | `2500.0` | src.taxation |
| `CUSTODY_PER_QUARTER` | `0.002` | src.taxation |
| `DECALAGE_PUBLICATION_BPA` | `1` | src.fondamentaux_historiques |
| `DIVISIONS_OFFICIELLES` | `<expression: DATA_DIR / 'divisions_officielles.json'>` | src.paths |
| `DIV_CUT_RATIO` | `0.5` | src.portfolio |
| `FENETRE` | `200` | src.regime_marche |
| `FICHIER` | `<expression: RACINE / 'data' / 'divisions_officielles.json'>` | src.divisions_officielles |
| `FONDAMENTAUX_BIAISES` | `['per', 'net_yield', 'payout']` | src.challenge_schema |
| `FUNDAMENTALS_HISTORIQUES` | `<expression: DATA_DIR / 'fondamentaux_historiques.json'>` | src.paths |
| `GROWTH_MIN_PCT` | `-10.0` | src.dividend_history |
| `HAUSSIER` | `haussier` | src.regime_marche |
| `HISTORY_DAYS` | `90` | src.screening |
| `HISTORY_START` | `20170101` | src.backtest |
| `HOLDING_YEARS` | `3` | src.portfolio |
| `HORIZON` | `252` | src.spec_profiles |
| `INDICATEURS` | `{'r5': 'rendement sur 5 seances', 'r20': 'rendement sur 20 seances', 'r60': 'rendement sur 60 seances', 'r120': 'rendement sur 120 seances', 'r250': 'rendement sur 250 seances', 'vol60': 'volatilite annualisee sur 60 seances', 'dd250': 'distance au plus haut des 250 seances (negatif)', 'dd_atl': 'drawdown depuis le plus haut historique (negatif)', 'pos5a': 'position dans la fourchette 5 ans', 'prix_vs_mm50': 'cours / moyenne mobile 50 seances - 1', 'prix_vs_mm200': 'cours / moyenne mobile 200 seances - 1', 'vol_ratio': 'volume du jour / volume median 60 seances - 1', 'per': 'PER (cours / benefice par action)', 'net_yield': 'rendement net du dividende', 'payout': 'dividende / benefice'}` | src.challenge_schema |
| `LEVEL_DECISION` | `2` | src.portfolio |
| `LEVEL_EXIT` | `4` | src.portfolio |
| `LEVEL_FUNDAMENTAL` | `3` | src.portfolio |
| `LEVEL_INFO` | `1` | src.portfolio |
| `MAX_COMPARE_AGE_DAYS` | `3` | src.cache_integrity |
| `MAX_JUMP` | `3.0` | src.cache_integrity |
| `METHODE_DEFAUT` | `episodes de +seuil % en 20 seances, dedoublonnes par vague` | src.seuils_vente |
| `MIN_SIGNALS` | `3` | src.speculation |
| `MIN_TITRES` | `5` | src.regime_marche |
| `MIN_VOLUME_MILLIONS` | `5.0` | src.dividend_history |
| `MODES` | `<expression: (MODE_DECLENCHEUR, MODE_INFORMATIF)>` | src.schema_seuils |
| `MODE_DECLENCHEUR` | `declencheur` | src.schema_seuils |
| `MODE_INFORMATIF` | `informatif` | src.schema_seuils |
| `MOIS_FR` | `{'1': 'JANVIER', '2': 'FEVRIER', '3': 'MARS', '4': 'AVRIL', '5': 'MAI', '6': 'JUIN', '7': 'JUILLET', '8': 'AOUT', '9': 'SEPTEMBRE', '10': 'OCTOBRE', '11': 'NOVEMBRE', '12': 'DECEMBRE'}` | src.boc |
| `MOTIF_CALIBRAGE` | `calibrage automatique` | src.seuils_vente |
| `MOTIF_MIGRATION` | `migration (ajout du mode)` | src.seuils_vente |
| `MOTIF_REFUS` | `refus : ecriture automatique sur un reglage protege` | src.seuils_vente |
| `NB_TIRAGES_ALEATOIRES` | `100` | src.challenge_validateur |
| `NET_MAX` | `0.1` | src.noyau_check |
| `NOMINAL` | `10000.0` | src.bonds |
| `OFFICIAL_DPS` | `{'SNTS': 1977.0, 'BOAS': 511.0, 'PALC': 501.6, 'SOGC': 570.0, 'SLBC': 2127.0, 'SGBC': 2606.0}` | src.fundamentals |
| `OPERATEURS` | `['et', 'ou']` | src.challenge_schema |
| `ORDER_CUTOFF_BSTRADE` | `<expression: time(13, 30)>` | src.live |
| `ORDER_CUTOFF_EMAIL` | `<expression: time(11, 0)>` | src.live |
| `ORIGINE_AUTO` | `automatique` | src.seuils_vente |
| `ORIGINE_MANUELLE` | `manuelle` | src.seuils_vente |
| `PER_ABSURD` | `50.0` | src.regles |
| `PER_EXPLODE` | `40.0` | src.portfolio |
| `PORTFOLIO_STATE` | `<expression: DATA_DIR / 'portfolio_state.json'>` | src.paths |
| `PRICE_TOLERANCE` | `0.25` | src.cache_integrity |
| `RACINE` | `<expression: Path(__file__).resolve().parent.parent>` | src.paths |
| `RATIOS_BRVM` | `[2, 3, 4, 5, 10, 20, 50, 100]` | src.ajustement |
| `REENTER_GAP_DAYS` | `5` | src.radar |
| `REFERENCE_AMOUNT` | `100000.0` | src.noyau_check |
| `REGULARITY_MIN_YEARS` | `4` | src.dividend_history |
| `REINF_COOLDOWN_DAYS` | `7` | src.portfolio |
| `REINF_IMPROVE_DOWN_PCT` | `0.03` | src.portfolio |
| `SAUT_MIN` | `1.8` | src.ajustement |
| `SCHEMA_LABELS` | `{'CASSURE': '🔓 CASSURE DE 1 AN', 'EVEIL': '🌅 REBOND CONFIRMÉ', 'PANIQUE': '🩹 RACHAT DE PANIQUE'}` | src.spec_fiche |
| `SCHEMA_ORDER` | `['CASSURE', 'EVEIL', 'PANIQUE']` | src.spec_fiche |
| `SCHEMA_WORDS` | `{'CASSURE': 'cassure de 1 an', 'EVEIL': 'rebond confirmé de +10 % depuis le creux des 60 séances', 'PANIQUE': 'rachat de panique'}` | src.spec_fiche |
| `SEANCES_MIN_INDICATEURS` | `250` | src.challenge_validateur |
| `SESSION_CLOSE` | `<expression: time(15, 0)>` | src.live |
| `SESSION_START` | `<expression: time(9, 0)>` | src.live |
| `SETTLEMENT_DAYS` | `3` | src.live |
| `SEUIL` | `5.0` | src.nettoyage_aberrantes |
| `SEUILS_CANDIDATS` | `[0.05, 0.08, 0.1, 0.13, 0.15]` | src.seuils_vente |
| `SEUILS_JOURNAL` | `<expression: DATA_DIR / 'seuils_journal.jsonl'>` | src.paths |
| `SEUILS_PAR_DEFAUT` | `{'SNTS': 0.13, 'SGBC': 0.1, 'SLBC': 0.05, 'PALC': 0.05}` | src.seuils_vente |
| `SPAM_DAYS` | `7` | src.spec_veille |
| `TAKE_1` | `0.2` | src.speculation |
| `TAKE_2` | `0.35` | src.speculation |
| `TAKE_3` | `0.5` | src.speculation |
| `TELEGRAM_API` | `https://api.telegram.org/bot{token}/sendMessage` | src.notify |
| `TERME` | `<expression: re.compile('^\\s*([a-z_0-9]+)\\s*(<=|>=|<|>|==|!=)\\s*(-?[0->` | src.challenge_schema |
| `TOLERANCE_PER_PCT` | `40.0` | src.fondamentaux_historiques |
| `TOLERANCE_RATIO` | `0.05` | src.ajustement |
| `TRAILING` | `0.1` | src.speculation |
| `TVA_RATE` | `0.18` | src.taxation |
| `VOISINS` | `20` | src.nettoyage_aberrantes |
| `ZONE_BAS_ECRASE` | `[0.0, 0.2]` | src.spec_profiles |
| `ZONE_BAS_SOLIDE` | `[0.2, 0.4]` | src.spec_profiles |
| `ZONE_DEAD_INFO_DAYS` | `60` | src.speculation |
| `ZONE_DEAD_REVIEW_DAYS` | `120` | src.speculation |
| `ZONE_FORCE` | `[0.8, 1.01]` | src.spec_profiles |
| `ZONE_HAUT_FRAGILE` | `[0.6, 0.8]` | src.spec_profiles |
| `ZONE_LABELS` | `{'FORCE': ['✅ ZONE DE FORCE', 'le prix est près de son plus haut de 5 ans — historiquement la meilleure zone (83 % de réussite)'], 'BAS_SOLIDE': ['🟡 ZONE BASSE MAIS SAINE', '20-40 % de la fourchette : bon compromis (80 % de réussite)'], 'MILIEU': ['🟡 MILIEU DE FOURCHETTE', 'zone neutre'], 'HAUT_FRAGILE': ['🔴 ZONE DANGER', "60-80 % : les anciens champions qui s'essoufflent — 0 gagnant sur 4 dans l'histoire"], 'BAS_ECRASE': ['🔴 ZONE PIÈGE', 'les 20 % du bas : « pas cher » ne paie pas (50 % de réussite, +3,5 % médian)']}` | src.spec_fiche |

### concentration (4)

| Constante | Valeur | Module |
|---|---|---|
| `CONCENTRATION_WARN` | `30.0` | src.report |
| `MAX_BUY_WEIGHT` | `0.4` | src.regles |
| `MAX_MARKET_WEIGHT` | `0.5` | src.regles |
| `MAX_POSITION_WEIGHT` | `0.35` | src.regles |

### filtres_entree (14)

| Constante | Valeur | Module |
|---|---|---|
| `DIV_YIELD_ENTRY` | `<expression: gross_yield_for_net(TARGET_NET_YIELD_ENTRY)>` | src.portfolio |
| `DIV_YIELD_EXIT` | `<expression: gross_yield_for_net(TARGET_NET_YIELD_EXIT)>` | src.portfolio |
| `PAYOUT_CRITICAL` | `1.0` | src.regles |
| `PAYOUT_MAX` | `0.8` | src.regles |
| `PAYOUT_TIGHT` | `<expression: PAYOUT_MAX>` | src.regles |
| `PER_MAX` | `14.0` | src.regles |
| `RENDEMENT_NET_ENTREE` | `<expression: TARGET_NET_YIELD_ENTRY>` | src.regles |
| `RENDEMENT_NET_MIN` | `<expression: RENDEMENT_NET_ENTREE>` | src.regles |
| `RENDEMENT_NET_SORTIE` | `<expression: TARGET_NET_YIELD_EXIT>` | src.regles |
| `TARGET_NET_YIELD_ENTRY` | `0.04` | src.taxation |
| `TARGET_NET_YIELD_EXIT` | `0.02` | src.taxation |
| `YIELD_ABSURD` | `30.0` | src.screener |
| `YIELD_MIN` | `<expression: gross_yield_for_net(TARGET_NET_YIELD_ENTRY) * 100>` | src.screener |
| `YIELD_SUSPECT` | `10.0` | src.screener |

### fiscalite_frais (5)

| Constante | Valeur | Module |
|---|---|---|
| `FRAIS_ALLER_RETOUR` | `<expression: 2 * FRAIS_PAR_SENS>` | src.regles |
| `FRAIS_MINIMUM` | `<expression: BROKERAGE_MIN>` | src.regles |
| `FRAIS_PAR_SENS` | `<expression: BROKERAGE_FEE>` | src.regles |
| `IRVM` | `<expression: IRVM_DIVIDEND_TAX>` | src.regles |
| `IRVM_DIVIDEND_TAX` | `0.12` | src.taxation |

### sorties_alertes (15)

| Constante | Valeur | Module |
|---|---|---|
| `ALERT_COOLDOWN_DAYS` | `7` | src.portfolio |
| `ALERT_STATE_FILE` | `<expression: DATA_DIR / 'portf_alert_state.json'>` | src.portfolio |
| `BORNE_BASSE_MIN` | `0.5` | src.regles |
| `CASH_ALERT_DAYS` | `3` | src.report |
| `CASH_ALERT_MARGIN` | `5.0` | src.report |
| `EPISODES_MIN` | `8` | src.regles |
| `LOSS_ALERT_THRESHOLD` | `0.1` | src.regles |
| `PREP_REALERT_DOWN_PCT` | `0.03` | src.noyau_check |
| `PROFIT_ALERT_THRESHOLD` | `0.13` | src.regles |
| `PROFIT_DOWN_PROB` | `{'SNTS': 86, 'SGBC': 63, 'SLBC': 54, 'PALC': 45}` | src.portfolio |
| `PROFIT_SEUILS_CANDIDATS` | `<expression: SEUILS_CANDIDATS>` | src.portfolio |
| `PROFIT_THRESHOLDS` | `<expression: DATA_DIR / 'profit_thresholds.json'>` | src.paths |
| `PROFIT_THRESHOLDS_FILE` | `<expression: SEUILS_FILE>` | src.portfolio |
| `SELL_FRACTION` | `<expression: 1 / 3>` | src.regles |
| `STOP_LOSS` | `0.15` | src.speculation |

### speculation (6)

| Constante | Valeur | Module |
|---|---|---|
| `PER_SUSPECT` | `25.0` | src.screener |
| `STOPOUT_COOLDOWN_DAYS` | `30` | src.spec_veille |
| `STOPOUT_SUSPEND_COUNT` | `2` | src.spec_veille |
| `STOPOUT_SUSPEND_DAYS` | `60` | src.spec_veille |
| `STOP_INITIAL` | `-0.15` | src.paliers_sortie |
| `TARGET_SPEC` | `0.0` | src.report |

### technique (38)

| Constante | Valeur | Module |
|---|---|---|
| `BASE_URL` | `https://bstrade.bridge-securities.com/BSTradeServer/` | src.bsapi |
| `BRVM_BOC_URL` | `https://www.brvm.org/sites/default/files/boc_{yyyymmdd}_2.pdf` | src.boc |
| `CACHE` | `<expression: RACINE / 'data' / 'fondamentaux_historiques.json'>` | src.fondamentaux_historiques |
| `CACHE_FILE` | `<expression: DATA_DIR / 'history_cache.pkl'>` | src.backtest |
| `CACHE_MAX_AGE_DAYS` | `7` | src.backtest |
| `CACHE_MAX_AGE_HOURS` | `24` | src.screener |
| `CANDIDATES_STATE_FILE` | `<expression: DATA_DIR / 'spec_candidates_state.json'>` | src.speculation |
| `DATA_DIR` | `<expression: RACINE / 'data'>` | src.paths |
| `DECISIONS_DIR` | `<expression: DOCS_DIR / 'decisions'>` | src.paths |
| `DIVIDENDES_FILE` | `<expression: DATA_DIR / 'dividendes.json'>` | src.dividends |
| `DOCS_DIR` | `<expression: RACINE / 'docs'>` | src.paths |
| `HEADERS` | `{'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}` | src.boc |
| `HISTORY_CACHE` | `<expression: DATA_DIR / 'history_clean.pkl'>` | src.paths |
| `JOURNAL_FILE` | `<expression: DATA_DIR / 'seuils_journal.jsonl'>` | src.seuils_vente |
| `MARKET_DIR` | `<expression: DATA_DIR / 'market'>` | src.paths |
| `MARKET_FILE` | `<expression: DATA_DIR / 'bonds_market.json'>` | src.bonds |
| `MAX_CACHE_AGE_DAYS` | `8` | src.cache_integrity |
| `MAX_WORKERS` | `8` | src.backtest |
| `NSIA_BOC_URL` | `https://nsiacapital.com/wp-content/uploads/{yyyy}/{mm}/BOC-DU-{dd}-{MOIS}.pdf` | src.boc |
| `PER_CACHE_FILE` | `<expression: DATA_DIR / 'per_cache.json'>` | src.fundamentals |
| `PORTFOLIO_DIR` | `<expression: DATA_DIR / 'portfolio'>` | src.paths |
| `PORTFOLIO_FILE` | `<expression: DATA_DIR / 'portfolio.json'>` | src.portfolio |
| `POSITIONS_FILE` | `<expression: DATA_DIR / 'bonds_positions.json'>` | src.bonds |
| `PREP_WATCH_FILE` | `<expression: DATA_DIR / 'prep_watch_state.json'>` | src.noyau_check |
| `PROFILES_FILE` | `<expression: DATA / 'spec_profiles.json'>` | src.spec_profiles |
| `REINF_STATE_FILE` | `<expression: DATA_DIR / 'reinf_alert_state.json'>` | src.portfolio |
| `REVERSAL_FILE` | `<expression: DATA_DIR / 'reversal_profiles.json'>` | src.cache_integrity |
| `REVERSAL_PROFILES` | `<expression: DATA_DIR / 'reversal_profiles.json'>` | src.paths |
| `SCRIPTS_DIR` | `<expression: RACINE / 'scripts'>` | src.paths |
| `SEEN_STATE_FILE` | `<expression: DATA_DIR / 'radar_seen_state.json'>` | src.radar |
| `SESSION_TIMEOUT` | `20` | src.bsapi |
| `SEUILS_FILE` | `<expression: DATA_DIR / 'profit_thresholds.json'>` | src.seuils_vente |
| `SIKA_DIV_URL` | `https://www.sikafinance.com/marches/dividendes` | src.boc |
| `SRC_DIR` | `<expression: RACINE / 'src'>` | src.paths |
| `STATE_FILE` | `<expression: DATA_DIR / 'alerts_state.json'>` | src.alerts |
| `TESTS_DIR` | `<expression: RACINE / 'tests'>` | src.paths |
| `URL` | `https://www.brvm.org/fr/cours-actions/0` | src.live |
| `VALUE_STATE_FILE` | `<expression: DATA_DIR / 'value_state.json'>` | src.screener |
