# Décision — Corrections LOT 3 (audit technique du 12/10/2026)

**Portée** : les deux look-aheads des évaluations point-in-time (A3-01, A3-02), la
vérification TLS (B2-02/B0-03), le nettoyeur symétrique (B2-11), la centralisation des
taux fiscaux (C4/A3-06), les duplications de seuils (C10/B1-12) et la divergence
assumée avec l'IPS (A3-07). Exécution : 12/10/2026, commit dédié.

## Corrections appliquées

| # | Item | Avant | Après | Preuve |
|---|------|-------|-------|--------|
| 1 | **A3-01** parseur BPA — colonne TTM | TTM jamais écarté (branche morte) : 12 titres avec deux exercices au montant **exactement égal** (ABJC 2024=2025=121,98) et, en général, chaque exercice recevait la valeur du précédent | TTM écarté **par position**, cellules vides préservées (None), refus si structure incohérente | **12 doublons → 0** ; 22/47 titres recalculés ; ABJC 2024 : 121,98 → **138,84** ; SNTS inchangé |
| 2 | **A3-02** date de publication du BPA | connu dès le 01/01 N+1 (look-ahead de 3 à 6 mois) | publié au **30/06 N+1** (`bpa_public_avant`) — conservateur | tests frontière 29/06 vs 30/06 ; PER indisponible en janvier |
| 3 | **B2-02/B0-03** TLS `verify=False` | désactivé sur 5 sources (BOC, live, dividendes, annonces, fondamentaux) | vérification **active** partout sauf BSTrade | 6 domaines testés en `verify=True` → HTTP 200 ; BSTrade → SSLError (seul cas, documenté) |
| 4 | **B2-11** nettoyeur d'aberrantes | pics seulement (> ×5) — les effondrements isolés (÷10) fabriquaient de fausses cassures | test **symétrique** [÷5, ×5] | tests : artefact bas détecté ; une vraie baisse (÷2,5) NON nettoyée |
| 5 | **C4/A3-06** taux fiscaux en dur | `0.88` / `0.008` recopiés dans 6 modules (challenge, noyau, fiche, stratégie) | `net_yield()` / `IRVM_DIVIDEND_TAX` importés de `taxation.py` | test gardien **récursif** + littéraux fiscaux interdits (hors taxation.py) |
| 6 | **C10/B1-12** duplications de seuils | `PROFIT_DOWN_PROB` figé (PALC 45 vs **46** dans le fichier calibré) ; défaut `0.13` en littéral ; import mort | copie supprimée (le % ne s'affiche que s'il vient de la mesure) ; défaut → `regles.PROFIT_ALERT_THRESHOLD` | test : signature sans littéral + valeur du catalogue |
| 7 | **A3-07** divergence IPS | non documentée (les rendements simulés pouvaient passer pour ceux de l'IPS) | docstring : cash 15 % vs 30 %, paliers +15/+20 vs +20/+35/+50, aucun stop modélisé | — (documentation) |

## Ce que ça change (et ne change pas)

- **Change** : les évaluations point-in-time qui s'appuyaient sur les BPA par exercice
  (PER, payout par date) étaient **biaisées d'un an** sur 22 titres sur 47 — silencieusement
  pour 10 d'entre eux (sans doublon visible). Toute évaluation passée qui cite un PER
  point-in-time d'un des titres recalculés doit être considérée comme suspecte.
- **Ne change pas** : les décisions Noyau du portefeuille réel (elles utilisent le PER
  du jour, pas le cache historique) ; les sorties texte des alertes (gardien
  `test_sorties_invariables` : 0 changement).
- Le **contrôle croisé** (validation par PER de référence) continue de rejeter les BPA
  douteux : 25/47 fiables avant comme après.

## Tests

- `tests/test_fondamentaux_historiques.py` (nouveau, 9 tests) : TTM numérique / tiret /
  absent, cellule vide au milieu, structure incohérente refusée, frontière de publication.
- `tests/test_regressions_audit.py` : B2-11 **gelé** (2 tests) — plus aucun xfail.
- `tests/test_regles_centralisees.py` : scan récursif + `AnnAssign` + littéraux fiscaux
  interdits + défaut central de `pour()`.
- Suite complète : **374 passed, 0 xfailed** (avant : 361 passed + 1 xfailed).

## Reste de l'audit (lots suivants)

- Phases 6-7 (contrats d'interface, sécurité) et 8 (exécution contrôlée) : à mener.
- C7 restant : « deux caches divergents tamponnés frais », dividende récent sans limite d'âge.
- C9 restant : B2-05 (divisions avalées), B2-06 (repli 2 ans), B2-10 (3 caches d'autorité).
