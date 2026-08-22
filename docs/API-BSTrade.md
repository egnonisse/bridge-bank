# BS Trade — Exploration API (12/08/2026)

Plateforme : https://bstrade.bridge-securities.com/ (Bridge Securities, SGI ivoirienne)
API interne : `https://bstrade.bridge-securities.com/BSTradeServer/`

## Accès PUBLIC (sans compte) — testé

| Endpoint | Données |
|---|---|
| `MarketDetails.aspx?mode=1` | Horaires de séance (`<PACQ>09:44:00|14:59:00|09:00:00|F</PACQ>`) |
| `MarketDetails.aspx?mode=2` | Flux continu indices BRVM (historique intraday) |
| `MarketDetails.aspx?mode=3` | Snapshot marché complet : 11 indices + ~118 titres. Format XML `<PAC_DET>` lignes `~Re/!CODE|...` séparées `\|`. Titres : code, ISIN, cours, ouverture, +haut, +bas, variation, volumes, carnet 5 niveaux. Obligations = codes `.O*` |
| `MarketDetails.aspx?mode=4` | Updates incrémentales temps réel (param `seq`, `m_seq`, `list_exec`) |
| `Service.svc/GetDataStockByCodeAndInterval2` | Historique OHLCV (JSON) : `?codeStock=SIVC&StartDate=20260701&EndDate=20260812` (GET) → `{BRVM10, CloseP, HighP, LowP, OpenP, Volume, CurrentDate(ms)}` |
| `Service.svc/GetRSIValuesWithCorrespendDates` | RSI : `?codeStock&StartDate&EndDate&Periods` |
| `Service.svc/GetBollingerBandsValuesWithCorrespendDates` | Bollinger |
| `Service.svc/GetATRValuesWithCorrespendDates` | ATR |
| `Service.svc/GetEMAValuesWithCorrespendDates` / `GetSMA…` / `GetMFI…` / `GetMomentum…` / `GetROC…` / `GetStochastic…` / `GetWR…` | Indicateurs techniques serveur |
| `Service.svc/GetListOfIndicators` | Liste des indicateurs dispo (JSON) |
| `Service.svc/get_infos`, `get_ETAT_MARCHE`, `echanges_exceptionnels`, `grapheBRVMC/10/PRES` | Infos, état marché, échanges exceptionnels, graphes indices |

## Accès PRIVÉ (login requis — compte client)

- Auth : `Service.svc/Auth` (GET JSONP, params `log`, `psw`=SHA1(mdp), `resolution` ; réponse `|`-séparée)
- Portefeuille : `returnGrillePF`, `PrRelTrimNLie` (portfolioBRVM.js)
- Ordres : `f_AJORDRE`, `Nouvelle_COTATION`, `cancelOrdreFIX`, `get_HIST_ORDRES`, `rechercherOrdre`… (Order.js)
- Relevés : `returnReleveEspeces`, `returnReleve_tit`, `Default.aspx?R=*&typ=PDF` (RELEVES.js)

## Notes techniques

- Stack : jQuery 1.11, CryptoJS (SHA1 login), Highcharts, JSONP (crossDomain)
- `URL_SERVICE` = `https://bstrade.bridge-securities.com/BSTradeServer/`
- Les appels POST simples fonctionnent en CORS/fetch depuis navigateur
- Ticker temps réel via `mode=4` avec seq

## Exemple parse mode=3 (titre)

`~Re/!SIVC|CI0000000550|4|2430|2355|2455.00000000|2400|-1.23456790123457|1713|2250|2610|...|AIR LIQUIDE CI|17|2400| |12/08/2026 14:29:18`
→ code|isin|?|dernier|ouverture|+haut|+bas|variation%|volume|min52?|max52?|...

Indices : `~Re/!BRVM-C|...|493.9|490.98|494.95|492.16|0|12/08/2026 14:34:36|...`
→ code|isin|?|valeur|ouverture|+haut|+bas|...|horodatage
