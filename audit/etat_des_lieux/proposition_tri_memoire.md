# Proposition de tri de la mémoire — 73 entrées → 3 classes

**Date** : 13/10/2026 · **Statut : ✅ EXÉCUTÉ le 13/10/2026 — voir `migration_memoire_2026-10-13.md` (73→19 entrées, 43 131→7 860 chars, backups + checkpoints OK)**
**Source** : `%HERMES_HOME%\memories\MEMORY.md` — 73 entrées, 43 347 chars (98 % du plafond de 44 000)

---

## 1. Objectif et critères

**Pourquoi** : la mémoire est à 98 % → la prochaine sauvegarde importante échouera ou devra remplacer au jugé. Et chaque tour charge 44,9 KB dont **~4 % seulement concernent Bridge Bank** (V7). Trop de faits projet y vivent, alors que leur place est dans les skills (chargés au bon moment).

**Critères de tri :**
- **A — GARDER** : s'applique à chaque session quel que soit le projet (identité, préférences, règles strictes, quirks machine, faits transverses). Certaines seront **raccourcies** (le détail va au skill, la règle reste).
- **B — MIGRER** : fait spécifique à UN projet → à copier dans le skill du projet (où il sera lu quand c'est pertinent), puis retiré de la mémoire.
- **C — RETIRER** : contenu **déjà couvert par un skill** (à vérifier point par point avant retrait) ou état daté sans valeur durable.

**Règle d'or de l'exécution** : *copier d'abord dans le skill, vérifier, PUIS retirer de la mémoire.* Aucune perte. Backup de MEMORY.md avant toute modification.

## 2. Le tri — 73 entrées

| # | Taille | Entrée (début) | Classe | Destination / note |
|---|-------:|----------------|--------|--------------------|
| 01 | 196 | L'utilisateur parle français. Préfère réponses concises, DRY, co | **A** | Garder — préférences de style |
| 02 | 291 | LEO = Egnonisse Léonard (Egno) — c'est son nom PUBLIC/profession | **A** | Garder — identité LEO |
| 03 | 841 | Zariamall : e-commerce Côte d'Ivoire, WooCommerce sur zariamall. | **B** | → zariamall-bot |
| 04 | 1107 | BASE_RULES éditables via dashboard ⚙️ Règles (data/base_rules.js | **B** | → zariamall-bot (base_rules, modules) |
| 05 | 604 | Hermes sur cette machine : HERMES_HOME = C:\Users\LEO\AppData\Lo | **A** | Garder (raccourcir) — faits Hermes machine |
| 06 | 511 | VPS BotWhatsApp : vmi3483493 = 169.58.117.185 (Contabo), Ubuntu  | **A** | Garder (raccourcir) — VPS |
| 07 | 460 | Vision Hermes : auxiliary.vision = gemini/gemini-2.5-flash, clé  | **B** | → hermes-agent (config vision) |
| 08 | 249 | PROD : https://sellercenter-eight.vercel.app (projet Vercel zari | **B** | → sellercenter |
| 09 | 853 | Sur ce PC Windows (git-bash MSYS) : LE RESEAU NE ROUTE PAS L'IPv | **A** | Garder (raccourcir) — quirks Windows/MSYS |
| 10 | 361 | Leçons SellerCenter : Next 15.5.23 (16.3.0 cassé au build). Pris | **B** | → sellercenter |
| 11 | 257 | SellerCenter : avant toute fonctionnalité, consulter C:\Users\LE | **B** | → sellercenter |
| 12 | 313 | Firebase boostsocial-a7720 (projet réutilisé, reste CF submitRec | **B** | → pharmascan |
| 13 | 1202 | SellerCenter RBAC + modules (09/08) : 4 rôles (SUPER_ADMIN=Admin, KAM... | **B** | → sellercenter (RBAC/modules) |
| 14 | 284 | Quirk Windows/MSYS + Flutter/Dart : une variable d'env `tmp` (mi | **A** | Garder — quirk Flutter TMP |
| 15 | 350 | Champs pharmacie : lat/lng + phone1/phone2 (formulaire admin). I | **B** | → pharmascan |
| 16 | 746 | Téléphones Android de LEO : Samsung Galaxy A17 (SM A175F, Androi | **A** | Garder (raccourcir) — téléphones test |
| 17 | 912 | Gradle 8.14.2+AGP 8.11.1+Kotlin 2.2.20. Piège AD_ID : firebase_a | **B** | → pharmascan / google-play-publishing |
| 18 | 478 | Firecrawl : quota free ÉPUISÉ → web_search = ddgs... Clarity | **A+B** | Règle ddgs reste (court) ; Clarity → clarity-analytics |
| 19 | 439 | Hermes desktop Projects : chaque projet est ancré à un primary_p | **A** | Garder (raccourcir) — projets Hermes |
| 20 | 248 | Projet Zariamall (C:\Users\LEO\projects\Zariamall) = projet GLOB | **A** | Garder — distinction Zariamall vs BotWhatsApp |
| 21 | 220 | Attributs WC zariamall : doublons EN/FR + termes incohérents (12 | **B** | → zariamall-catalog-import |
| 22 | 235 | Préférence LEO : contenu SEO qualitatif rédigé par IA (DeepSeek) | **A** | Garder — préférence SEO IA |
| 23 | 117 | IRVM CI dividendes = 12 % en 2026 (BOC 15/06/2026 ; 10 % en 2019... | **A** | Garder — IRVM (BRVM) |
| 24 | 298 | LEO est abonné MTN Côte d'Ivoire et a parfois des zones sans cou | **A** | Garder — profil réseau LEO |
| 25 | 719 | RÈGLE STRICTE LEO (14/08) : les clés/credentials d'un projet res | **A** | Garder — RÈGLE clés par projet |
| 26 | 793 | SellerCenter (14/08) : gel du taux de commission À LA VENTE — Or | **B** | → sellercenter (commissions) |
| 27 | 269 | Leçon Windows (14/08) : hermes verify --json boucle (>10 min) su | **B** | → hermes-maintenance (builds Next) |
| 28 | 572 | RÈGLE OUTILLAGE (14/08, décidée par LEO) : pour les recherches w | **A** | Garder — RÈGLE outillage ddgs |
| 29 | 1282 | GitHub — DEUX IDENTITES A NE JAMAIS CONFONDRE (regle LEO 09/10/2026)... | **A** | Garder (raccourcir) — RÈGLE GitHub 2 identités |
| 30 | 753 | Newsletter Brevo aiwatch.ci (17/08) : compte info@aiwatch.ci, fr | **C** | Vérifier couverture email-marketing-brevo puis retirer |
| 31 | 919 | Panier abandonné AIWATCH = PLUGIN WP aiwatch-cart-recovery v1.5. | **C** | Vérifier couverture woocommerce-cart-debugging puis retirer |
| 32 | 421 | Newsletter AIWATCH — sélection produits par TRANCHES DE PRIX 2/t | **B** | → email-marketing-brevo |
| 33 | 951 | aiwatch.ci : WC 10.7.0, thème Konte (boutons fiche = konte_ajax_ | **B** | → woocommerce-cart-debugging |
| 34 | 466 | RADAR+veille 09h45 (job e8974cd7337d, monitor radar_new_codes.py | **B** | → brvm-value-investing (orchestration radar) |
| 35 | 608 | Dashboard admin_web : page Gardes (CRUD dates + import JSON). Gé | **B** | → gardes-pharmacies-unppci |
| 36 | 682 | Projet Book (auto-édition Murmure Nocturne, C:\Users\LEO\project | **B** | → self-publishing |
| 37 | 811 | browser_exec (Browser Use) : Chrome d'automatisation DÉDIÉ isolé | **A** | Garder (raccourcir) — browser_exec |
| 38 | 545 | aiwatch.ci (SEO 17-21/08) : WP Application Password (tribulant@a | **B** | → woocommerce-seo-audit |
| 39 | 255 | Slogan officiel AIWATCH (site aiwatch.ci) : « AÏWATCH, la boutiq | **B** | → woocommerce-seo-audit (slogan) |
| 40 | 459 | Fiscalité CI 2026 : NCC particulier = présentiel (PAS de portail | **B** | → ci-business-compliance |
| 41 | 1201 | aiwatch.ci GSC + pages footer (17/08/2026) : Compte de service G | **B** | → woocommerce-seo-audit (GSC/footer) |
| 42 | 751 | Leçons SEO WordPress aiwatch.ci (17/08) : metas RankMath des PAG | **B** | → woocommerce-seo-audit (RankMath) |
| 43 | 615 | Gardes CI : source UNPPCI (unppci.org, PDFs downloads.php 663-96 | **B** | → gardes-pharmacies-unppci |
| 44 | 249 | AIWATCH pages légales : forme juridique/IFU/hébergeur NON affich | **B** | → woocommerce-seo-audit (pages légales) |
| 45 | 352 | Google Business Profile AIWATCH existe DÉJÀ (confirmé par LEO 17 | **B** | → woocommerce-seo-audit (GBP) |
| 46 | 258 | Produits private aiwatch.ci = RUPTURE DE STOCK / réappro improba | **B** | → woocommerce-seo-audit (private) |
| 47 | 424 | Skill gardes-pharmacies-unppci (créé 22/08) est NON-adopté (crea | **A** | Garder (court) — tant que curator adopt pas fait |
| 48 | 799 | Référentiel medications = 13 601 ANSM avec titulaire (recherche  | **B** | → pharmascan |
| 49 | 575 | Leçons déploiement Firebase functions (22/08) : onDocumentCreate | **B** | → pharmascan (Firebase) |
| 50 | 621 | Déploiement Play PharmaScan (com.softhubapp.scanapp) : auto-bump | **B** | → google-play-publishing |
| 51 | 712 | firebase-admin v14 (Node) : `admin.messaging` et `admin.credenti | **B** | → pharmascan (firebase-admin) |
| 52 | 525 | Piège PharmaScan/Firestore : TOUTE requête `where(champA) + orde | **B** | → pharmascan (index Firestore) |
| 53 | 472 | Assets officiels PharmaScan (play/screenshots/) : App_Icon_Appli | **B** | → pharmascan (assets) |
| 54 | 654 | BotWhatsApp (24/08) : filtres anti-hallucination passés au STRUC | **C** | Vérifier couverture zariamall-bot puis retirer |
| 55 | 302 | Roadmap docs/ROADMAP.md (1.2 parrainage FAIT 28/08 : code 6 char | **B** | → pharmascan (roadmap) |
| 56 | 892 | Plugin AIWATCH woo-perplexity-enhancer (Aiwatch/plugins/, zip, i | **C** | Vérifier couverture woocommerce-plugin-development puis retirer |
| 57 | 1483 | Projet TapyCash (C:\Users\LEO\projects\Whatnot, créé 26/08/2026) | **B** | → live-commerce-afrique (TapyCash) |
| 58 | 393 | WooCommerce API : PUT /products/{id} attributes REMPLACE tout (j | **B** | → woocommerce-plugin-development (API attributes) |
| 59 | 395 | Catalogue aiwatch.ci : 99 nouveaux produits (28/08) enrichis ≥90 | **C** | État daté (catalogue 28/08) — archiver |
| 60 | 492 | Woodmart : LEO détient une LICENCE MULTI-SITE (réutilisable sur  | **B** | → woocommerce-plugin-development (licence Woodmart) |
| 61 | 809 | Plugin zariamall-whatsapp (projet C:\Users\LEO\projects\Zariamal | **C** | Vérifier couverture woocommerce-plugin-development puis retirer |
| 62 | 1212 | Aiwatch (aiwatch.ci, thème Konte) : mu-plugin woodmart-bridge (A | **B** | → woocommerce-plugin-development (woodmart-bridge) |
| 63 | 945 | Bridge Bank (C:\Users\LEO\projects\Bridge Bank ; repo privé egno | **A** | Garder (raccourcir) — BRVM Bridge Bank |
| 64 | 190 | test.zariamall.com = site TEST WooCommerce 11.0.1 (Hostinger mut | **B** | → woocommerce-plugin-development (import CSV) |
| 65 | 835 | AIWATCH Buffer (02/09, v1.4.2 le 22/09) : token BUFFER_API_TOKEN | **C** | Vérifier couverture woocommerce-plugin-development puis retirer |
| 66 | 379 | Compte utilisateur PharmaScan (décision LEO finale) : connexion  | **B** | → pharmascan (comptes) |
| 67 | 907 | PharmaScan (09/2026) : repo GitHub RENOMMÉ egnonisse/PharmaScan  | **B** | → pharmascan (Sentry/CI) |
| 68 | 592 | aiwatch.ci monitoring+perf (11-12/09) : Sentry org aiwatch-ci (W | **B** | → woocommerce-cart-debugging (Sentry/LiteSpeed) |
| 69 | 1102 | YouTube (C:\Users\LEO\projects\YouTube) : chaîne « Why You Do Th | **B** | → youtube-shorts-pipeline |
| 70 | 650 | Projet BetclicAgent (C:\Users\LEO\projects\BetclicAgent, repo gi | **B** | → betclic-agent |
| 71 | 499 | Vercel AI Gateway — accès GLOBAL tous projets : endpoint https:/ | **A** | Garder (raccourcir) — AI Gateway global |
| 72 | 370 | ShopMa (marque validee 28/09/2026) : Odoo 18 en marque blanche — | **B** | → odoo-deployment (ShopMa) |
| 73 | 399 | PROJET LINKEDIN SUPPRIME (29/09/2026, décision LEO, sans archive | **C** | Archiver (projet supprimé) ; piège MCP générique → hermes-maintenance |

## 3. Synthèse chiffrée

| Classe | Entrées | Chars | Cible |
|---|---:|---:|---|
| **A — garder** | 20 | 10 552 | ~**7 900** après raccourcissements (détails → skills) |
| **B — migrer** | 46 | 27 401 | 0 en mémoire après migration vérifiée |
| **C — retirer** (couverture à vérifier) | 8 | 5 656 | 0 en mémoire après vérification (sinon migrer d'abord) |
| **TOTAL** | 73 | 43 347 | **≈ 8 000 chars (18 % du plafond)** — marge retrouvée pour des mois |

*Note : l'entrée 18 (478 chars) est mixte — découpée entre A (~200) et B (~278).*

## 4. Ce qui RESTE en mémoire (les 20 A, après raccourcissement)

Règles transverses (clés par projet, ddgs, GitHub 2 identités, poches/projets) · identité & préférences LEO · quirks machine Windows/MSYS (IPv6, TMP, chemins) · config Hermes (HERMES_HOME, projets, browser_exec, AI Gateway) · VPS · téléphones de test · profil réseau · 3 entrées BRVM (IRVM, radar, Bridge Bank) · consigne curator gardes.

## 5. Plan d'exécution proposé (après ta validation)

1. **Backup** : copie horodatée de `MEMORY.md` (+ `USER.md` par prudence) dans un dossier d'archive — rollback possible à tout moment.
2. **Migrations B par lots de projet** (ordre : AIWATCH → pharmascan → sellercenter → zariamall/bot → sites WC → autres) : j'écris d'abord dans le skill cible (patch ou `references/`), je vérifie, puis je retire l'entrée de la mémoire.
3. **Les 8 C** : contrôle point par point que le skill couvre le contenu → sinon migration d'abord. Rien n'est retiré sans couverture prouvée.
4. **Raccourcissements A** : je te soumets les 13 versions courtes (avant/après) dans un seul diff lisible — validation en un coup d'œil.
5. **Réécriture MEMORY.md** (batch unique) + contrôles finaux : compte d'entrées, chars, grep des points clés migrés (checklist de non-perte).
6. **Mise à jour** de `ecarts.csv` (E7 mémoire → statut résolu).

**Effort estimé** : ~2 sessions (le gros = les 46 migrations, mécaniques mais soigneuses). **Risque** : faible — ordre copier→vérifier→retirer + backup + checklist.

## 6. Points à trancher par LEO

1. **Valides-tu le tri** (les 73 lignes) — ou veux-tu ajuster certains classements (ex. garder en A une entrée projet que tu consultes souvent) ?
2. **Les 6 C-« déjà couvert »** (30, 31, 54, 56, 61, 65) : OK pour retirer **après vérification** du skill, ou tu préfères un traitement B (migration) par défaut ?
3. **Ordre d'exécution** : je propose AIWATCH d'abord (le plus gros lot, 28 %) — OK ?
