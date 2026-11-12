"""Fiche spé complète — génération du message néophyte pour un titre détecté.

4 blocs : schéma + probabilité · zone de prix · prix d'entrée · filet.
Le verdict combine schéma ET zone : une zone DANGER/PIÈGE dit NON même si
le schéma est allumé (ex. SCRC : panique à 75 % de la fourchette).

Style néophyte (règle LEO 03/09) : un chiffre = sa signification,
fait / hypothèse / décision séparés, jamais d'ordre automatique.
"""
from dataclasses import dataclass, field

from ..portefeuille.format_fr import fcfa  # montants à la française (invariant E1, correction B1-02 du 12/10)
from ..taxation import net_yield  # C4 : plus de 0,88/0,8 en dur (correction 12/10)
from .spec_profiles import load_profiles, zone_of, zone_label, detect_schemas

# Emojis / libellés par schéma
SCHEMA_LABELS = {
    "CASSURE": "🔓 CASSURE DE 1 AN",
    "EVEIL": "🌅 REBOND CONFIRMÉ",
    "PANIQUE": "🩹 RACHAT DE PANIQUE",
}
SCHEMA_WORDS = {
    "CASSURE": "cassure de 1 an",
    "EVEIL": "rebond confirmé de +10 % depuis le creux des 60 séances",
    "PANIQUE": "rachat de panique",
}
SCHEMA_ORDER = ["CASSURE", "EVEIL", "PANIQUE"]

# ── Taux de réussite PAR ZONE — MESURÉS, plus codés en dur ────────────────────────
# Chantier « prix des alertes spé » (09/11/2026). Remplace les taux figés
# (FORCE 83 %, BAS_SOLIDE 80 %, HAUT_FRAGILE « 0 sur 4 », BAS_ECRASE 50 %) par la
# mesure réelle : audit/spec_zones_mesure_2026-11-02.md (mesure du 02/11/2026 —
# 44 séries, 51 cas observés, 2017-2026, schémas confondus, net de frais 2,8 %).
# Fréquences observées, PAS des probabilités ; titres radiés ABSENTS (biais de
# survie) : les taux affichés sont donc optimistes.
#
# SEUIL_CAS_ZONE : sous 10 cas, aucune conclusion chiffrée n'est tirée d'une zone.
# Seuil à PROPOSER pour src/regles.py (non écrit ici — un fichier = une
# responsabilité) : `SEUIL_CAS_ZONE = 10  # provenance : mesure du 02/11/2026`.
SEUIL_CAS_ZONE = 10

# Par zone : n cas observés · % finissant plus haut à 12 mois · gain net médian (%).
ZONES_MESUREES = {
    "BAS_ECRASE":   {"n": 19, "win": 53,  "median": 56.8,  "plage": "0-20",
                     "pourquoi": "« pas cher » ne paie pas vraiment"},
    "BAS_SOLIDE":   {"n": 10, "win": 100, "median": 87.9,  "plage": "20-40",
                     "pourquoi": "la meilleure zone mesurée"},
    "MILIEU":       {"n": 13, "win": 62,  "median": 11.2,  "plage": "40-60",
                     "pourquoi": "ni bonne ni mauvaise"},
    "HAUT_FRAGILE": {"n": 7,  "win": 14,  "median": -32.9, "plage": "60-80",
                     "pourquoi": "historiquement la pire zone, les anciens "
                                 "champions qui s'essoufflent"},
    "FORCE":        {"n": 2,  "win": 50,  "median": 13.4,  "plage": "80-100",
                     "pourquoi": ""},
}

ZONE_CONTEXTES = {
    "FORCE":        "le prix est près de son plus haut de 5 ans",
    "BAS_SOLIDE":   "20-40 % de la fourchette",
    "MILIEU":       "40-60 % de la fourchette",
    "HAUT_FRAGILE": "60-80 % de la fourchette",
    "BAS_ECRASE":   "les 20 % du bas",
}

# Émoji de zone aligné sur le verdict mesuré. Historique : « ✅ ZONE DE FORCE » vantait
# une « meilleure zone » fondée sur un 83 % infondé (2 cas) ; le ✅ était passé au 20-40.
# (12/11/2026) Après réparation de l'espacement du calibrage, la zone 80-100 est MESURÉE
# meilleure (91 cas EVEIL à 67 %, médiane +18 %) : elle récupère son ✅, et le 20-40 le
# garde (61 % sur 39 cas pour la panique). Deux zones peuvent être favorables.
ZONE_EMOJIS = {
    "FORCE":        "✅ ZONE DE FORCE",
    "BAS_SOLIDE":   "✅ ZONE BASSE MAIS SAINE",
    "MILIEU":       "🟡 MILIEU DE FOURCHETTE",
    "HAUT_FRAGILE": "🔴 ZONE DANGER",
    "BAS_ECRASE":   "🔴 ZONE PIÈGE",
}

# Verdict prix (ligne informative « à côté » de 💵 Position du prix) : un niveau
# visuel par zone. INFORMATIF — jamais une règle, aucun achat n'est bloqué par là.
# (12/11/2026) Passerelle entre le libellé de zone et la tranche du fichier calibré :
# data/spec_profiles.json ventile désormais les stats par schéma ET par tranche.
ZONE_TRANCHE = {
    "BAS_ECRASE": "0-20",
    "BAS_SOLIDE": "20-40",
    "MILIEU": "40-60",
    "HAUT_FRAGILE": "60-80",
    "FORCE": "80-100",
}

VERDICT_PRIX = {
    "BAS_SOLIDE":   ("✅", "favorable"),
    "MILIEU":       ("🟡", "neutre"),
    "BAS_ECRASE":   ("🔴", "défavorable"),
    "HAUT_FRAGILE": ("🔴", "défavorable"),
    # (12/11/2026) La zone 80-100 n'est plus « non concluant » : après réparation de
    # l'espacement du calibrage, elle compte 91 cas pour EVEIL (67 % de réussite, médiane
    # +18 %) et 11 pour PANIQUE (72,7 %, +36 %) — c'est la MEILLEURE zone mesurée pour
    # l'éveil. Le ⚪ venait d'un échantillon de 2 cas, lui-même produit du bug.
    "FORCE":        ("✅", "favorable"),
}


def _texte_zone(zone_code: str, zone_stats: dict | None = None) -> str:
    """Descriptif néophyte d'une zone : contexte + taux MESURÉ POUR CE SCHÉMA + effectif.

    (12/11/2026) Cette ligne lisait ZONES_MESUREES, mesuré TOUS SCHÉMAS CONFONDUS : elle
    affichait « 100 % de réussite sur 10 cas » sur une alerte de rachat de panique dont le
    taux réel est 61 % sur 39 cas. Elle reçoit désormais les stats du schéma courant
    (`prof[schéma]["zones"][tranche]`), et sous SEUIL_CAS_ZONE cas elle s'abstient au lieu
    d'emprunter le chiffre d'une autre population.
    """
    contexte = ZONE_CONTEXTES[zone_code]
    stats = zone_stats or {}
    n = int(stats.get("n") or 0)
    if n < SEUIL_CAS_ZONE:
        return (f"{contexte} : {n} cas seulement POUR CE SCHÉMA — aucune conclusion "
                f"chiffrée tirée de cet échantillon")
    win = (stats.get("win_12m") or 0.0) * 100
    med = (stats.get("median_net_12m") or 0.0) * 100
    signe = "−" if med < 0 else "+"
    return (f"{contexte} : {win:.0f} % de réussite sur {n} cas observés, "
            f"gain médian {signe}{abs(med):.0f} %")


# Chantier « prix des alertes spé » (09/11/2026) : un percentile « sur 5 ans » exige
# 5 ans de séances (5 × 252). En deçà, la fiche affiche « indisponible » — abstention,
# jamais une valeur calculée sur un historique tronqué (règle : ne pas inventer).
SEANCES_5_ANS = 5 * 252


@dataclass
class FicheSpec:
    code: str
    name: str
    price: float
    schemas: list = field(default_factory=list)
    zone: float = 0.0
    verdict: str = "NON"   # "OUI" / "PRUDENCE" / "NON"
    blocks: dict = field(default_factory=dict)

    def message(self) -> str:
        return build_message(self)


def build_fiche(code: str, name: str, closes: list,
                volumes: list | None = None) -> FicheSpec | None:
    """Construit la fiche pour la dernière séance d'une série.

    Retourne None si aucun schéma actif ou série trop courte.
    volumes : aligné sur closes — la cassure exige un volume confirmé.
    """
    schemas = detect_schemas(closes, volumes)
    if not schemas:
        return None
    # priorité au schéma le plus informatif (cassure > éveil > panique)
    for s in SCHEMA_ORDER:
        if s in schemas:
            main = s
            break
    else:
        main = schemas[0]

    price = closes[-1]
    zone = zone_of(closes)
    zl = zone_label(zone)

    # Deux faits mesurés sur le PRIX (chantier « prix des alertes spé », 09/11/2026) :
    # informatifs, jamais des seuils — la fiche INFORME, elle ne bloque aucun achat.
    # - percentile_5ans : part des séances des 5 ans strictement sous le cours
    #   (= zone × 100, arrondi) ; None si l'historique couvre moins de 5 ans.
    # - depuis_creux_pct : chemin parcouru depuis le creux des 60 séances
    #   précédentes : (cours − creux) / creux × 100 ; None si le creux est invalide.
    percentile_5ans = round(zone * 100) if len(closes) >= SEANCES_5_ANS else None
    creux60 = min(closes[-61:-1]) if len(closes) >= 61 else None
    depuis_creux_pct = ((price - creux60) / creux60 * 100
                        if creux60 is not None and creux60 > 0 else None)

    prof = load_profiles()
    st = prof.get(main, {})

    # verdict : schéma + zone
    if zl in ("HAUT_FRAGILE", "BAS_ECRASE"):
        verdict = "NON"
    elif zl == "BAS_SOLIDE":
        verdict = "PRUDENCE"
    else:
        verdict = "OUI"

    # fondamental connu (la fiche ne juge PAS le loyer, mais SIGNALE les
    # risques connus : payout > 100 %, PER extrême — règle LEO 25/09)
    try:
        from ..collecte.fundamentals import get_fundamentals

        fund = get_fundamentals(code)
        dps = fund.get("dps") or 0
        per = fund.get("per") or 0
        payout = dps * per / price * 100 if dps and per else None
    except Exception:
        dps, per, payout = 0, 0, None

    # prix d'entrée et filet
    if main == "CASSURE":
        plafond = max(closes[-251:-1])
        entry_lo, entry_hi = plafond, plafond * 1.05
    else:
        entry_lo = price * 0.985
        entry_hi = price * 1.05
    stop = entry_lo * 0.85

    touched = st.get("touched", {})
    blocks = {
        "main": main,
        "all_schemas": schemas,
        "win_12m": st.get("win_12m", 0.0),
        "median_net": st.get("median_net_12m", 0.0),
        "n": st.get("n", 0),
        "touched": touched,
        "zone_pct": zone,
        "zone_label": zl,
        # (12/11/2026) Stats de la zone POUR CE SCHÉMA : la fiche affichait le taux tous
        # schémas confondus (10 épisodes) sur une alerte d'un schéma précis — d'où un
        # « ✅ 100 % de réussite » annoncé sur un rachat de panique qui vaut 61 %.
        "zone_stats": ((prof.get(main) or {}).get("zones") or {}).get(
            ZONE_TRANCHE.get(zl, ""), {}),
        # Position du prix (chantier « prix des alertes spé », 09/11/2026) — deux FAITS
        # mesurés, informatifs (jamais des seuils d'achat). None = « indisponible ».
        "percentile_5ans": percentile_5ans,
        "depuis_creux_pct": depuis_creux_pct,
        "entry_lo": entry_lo,
        "entry_hi": entry_hi,
        "stop": stop,
        # B1-11 (13/10/2026) : le stop est −15 % du PRIX PAYÉ — l'acheteur ne paie pas
        # forcément le bas de la fourchette ; les DEUX bornes sont donc publiées
        # (avant, « Stop −15 % : X » supposait l'achat au bas et annonçait jusqu'à
        # −19 % du prix réellement payé).
        "stop_hi": entry_hi * 0.85,
        # B1-10 (13/10/2026) : les stats affichées sont-elles calibrées ou figées ?
        "stats_fallback": bool(prof.get("_fallback")),
        "palier20": entry_lo * 1.20,
        "palier35": entry_lo * 1.35,
        "palier50": entry_lo * 1.50,
        "dps": dps,
        "per": per,
        "payout": payout,
    }
    return FicheSpec(code=code, name=name, price=price, schemas=schemas,
                     zone=zone, verdict=verdict, blocks=blocks)


def _ordinal_fr(n: int) -> str:
    """Ordinal français : 1 → « 1er », sinon « Ne » (2e, 3e, 34e…)."""
    return "1er" if n == 1 else f"{n}e"


def format_position_prix(b: dict) -> str:
    """Ligne « Position du prix » : deux faits mesurés, un chiffre = sa signification.

    Chantier « prix des alertes spé » (09/11/2026). Donnée absente (historique
    < 5 ans pour le percentile, creux introuvable pour le rebond) → « indisponible »,
    jamais une valeur inventée ni un zéro trompeur. Un cours SOUS le creux des
    60 séances (nouveau plus bas) est dit tel quel, pas maquillé en « + ».
    """
    p = b.get("percentile_5ans")
    gauche = (f"{_ordinal_fr(p)} percentile sur 5 ans"
              if p is not None else "percentile sur 5 ans : indisponible")
    c = b.get("depuis_creux_pct")
    if c is None:
        droite = "depuis le creux des 60 séances : indisponible"
    elif c < 0:
        droite = f"−{abs(c):.0f} % sous le creux des 60 séances (nouveau plus bas)"
    else:
        droite = f"+{c:.0f} % depuis le creux des 60 séances"
    return f"💵 Position du prix : {gauche} | {droite}"


def format_verdict_prix(b: dict) -> str:
    """Ligne « Verdict prix » : niveau visuel + taux MESURÉ POUR CE SCHÉMA dans cette zone.

    (12/11/2026) CORRECTION DE FOND. Cette ligne utilisait les taux de ZONES_MESUREES,
    mesurés TOUS SCHÉMAS CONFONDUS sur 10 épisodes. Une alerte « rachat de panique »
    affichait donc « ✅ favorable — 100 % de réussite sur 10 cas, gain médian +88 % »,
    alors que la mesure pour ce schéma dans cette zone est 61 % sur 39 cas, médiane +13 %.
    Un verdict ne doit jamais décrire une autre population que celle de l'alerte.
    Sous SEUIL_CAS_ZONE cas POUR CE SCHÉMA, le niveau est ⚪ et l'effectif est annoncé.
    """
    zl = b.get("zone_label")
    if zl not in VERDICT_PRIX:
        return ""
    emoji, mot = VERDICT_PRIX[zl]
    zs = b.get("zone_stats") or {}
    n = int(zs.get("n") or 0)
    plage = (ZONES_MESUREES.get(zl) or {}).get("plage", "")
    if n < SEUIL_CAS_ZONE:
        return (f"   ⚪ Verdict prix : non concluant POUR CE SCHÉMA — zone {plage} : "
                f"{n} cas seulement (moins de {SEUIL_CAS_ZONE}), aucune conclusion chiffrée")
    win = (zs.get("win_12m") or 0.0) * 100
    med = (zs.get("median_net_12m") or 0.0) * 100
    signe = "−" if med < 0 else "+"
    return (f"   {emoji} Verdict prix : {mot} — zone {plage} POUR CE SCHÉMA : "
            f"{win:.0f} % de réussite sur {n} cas, gain médian {signe}{abs(med):.0f} %")


def build_message(f: FicheSpec) -> str:
    b = f.blocks
    main = b["main"]
    zlabel = ZONE_EMOJIS[b["zone_label"]]
    ztxt = _texte_zone(b["zone_label"], b.get("zone_stats"))
    touched = b["touched"]
    mot = SCHEMA_WORDS.get(main, main.lower())
    # « rare » n'est vrai que pour la cassure — l'éveil est une marée
    if main == "CASSURE":
        rare = "un signal RARE (moins de 10 fois en 10 ans)"
    else:
        n_maree = b.get("nb_meme_schema")
        rare = (f"un signal de veille — attention : {n_maree} titre(s) cochent ce "
                f"même signal aujourd'hui (la marée du marché), ce n'est pas un "
                f"événement propre à ce titre") if n_maree else \
            "un signal de veille (courant en marché haussier : la marée du marché)"

    # (02/11/2026) Le même mensonge de précision que le « 83 % » des zones vivait ici :
    # « 80 % de 5 cas » était affirmé sans avertissement. Sous SEUIL_CAS_ZONE cas, la
    # fréquence ET les paliers sont annoncés comme fragiles — une fréquence observée sur
    # cinq cas n'est pas une statistique, et LEO décide avec ce chiffre.
    alerte_n = (f"     ⚠️ {b['n']} cas SEULEMENT : une indication, pas une statistique —\n"
                f"        ne t'appuie pas dessus pour décider.\n"
                if b["n"] < SEUIL_CAS_ZONE else "")
    head = (f"{SCHEMA_LABELS[main]} — {f.code} ({f.name})\n\n"
            f"Cours de référence : {fcfa(f.price)} "
            f"({'LIVE du moment' if b.get('cours_source') == 'live' else 'dernière clôture connue'})\n"
            f"{format_position_prix(b)}\n"
            f"{format_verdict_prix(b)}\n"
            f"Ce qui se passe : ce cours a déclenché le schéma "
            f"« {mot} » — {rare}, jamais automatique.\n\n"
            f"📊 FRÉQUENCES HISTORIQUES (10 ans, hors frais déjà déduits) :\n"
            f"   • La fréquence qui DÉCIDE est celle du schéma BRUT (avant\n"
            f"     les filtres zone + volume ci-dessous) : "
            f"{b['win_12m']*100:.0f} % de {b['n']} cas OBSERVÉS finissent plus hauts "
            f"12 mois après (+{b['median_net']*100:.0f} % net médian)\n"
            + alerte_n
            + ("   ⚠️ STATISTIQUES DE SECOURS : le calibrage courant est indisponible —\n"
               "      ces chiffres datent des épreuves de septembre 2026 et ne sont\n"
               "      PAS re-mesurés. Ne les traite pas comme la mesure du jour.\n"
               if b.get("stats_fallback") else ""))
    if touched:
        head += (f"   • Ton palier +20 % : touché dans {touched.get('0.20', 0)*100:.0f} % des cas observés\n"
                 f"   • Ton palier +50 % : touché dans {touched.get('0.50', 0)*100:.0f} % des cas observés\n")
    head += (f"   • {zlabel} : {ztxt} — la zone MODULE le schéma\n"
             f"   ⚠️ {b['n']} cas observés, titres radiés ABSENTS (biais de survie) : "
             f"fréquence historique, PAS une probabilité — les perdants existent.\n")

    # fondamental connu — signalé, jamais jugé (la poche spé joue le prix)
    if b.get("dps"):
        net = net_yield(b["dps"] / f.price) * 100 if f.price else 0
        fund = (f"   • 🏦 Fondamental connu : dividende {fcfa(b['dps'])}/an "
                f"(≈ {net:.1f} % net)")
        # B2-01 appliqué à l'AFFICHAGE (13/10) : un PER indisponible (« 0.00 » de brvm.org
        # = non calculable) ne doit jamais s'écrire « PER 0.0 » — ça se lit comme un vrai
        # PER nul. Même doctrine que le cache PER du noyau (lot 2).
        if b.get("per") and b["per"] > 0:
            fund += f", PER {b['per']:.1f}"
        else:
            fund += ", PER non calculable"
        if b.get("payout") and b["payout"] > 100:
            fund += (f", ⚠️ PAYOUT {b['payout']:.0f} % : elle paie PLUS qu'elle ne "
                     f"gagne — risque de coupe du dividende (un pari sur ce titre "
                     f"porte ce risque en plus)")
        elif b.get("per") and b["per"] > 25:
            fund += f", ⚠️ PER {b['per']:.0f} : le prix est loin de ses bénéfices"
        head += fund + "\n"

    if f.verdict == "NON":
        return head + ("\n📋 VERDICT : ❌ LA FICHE DIT NON.\n"
                       "   La zone de prix contredit le schéma — interdite PAR DÉFAUT\n"
                       "   (échantillon mince : la zone n'est pas une loi absolue ;\n"
                       "   une cassure confirmée par le volume pourrait la rouvrir).\n"
                       "   On laisse tomber, sans regret : la veille sait dire non.\n"
                       "\n🚫 Règle d'or : un pari perdant ne devient JAMAIS un loyer.")

    body = (f"\n📋 SI TU DÉCIDES DE JOUER (ta décision, jamais automatique) :\n"
            f"   • Achat : entre {fcfa(b['entry_lo'])} et {fcfa(b['entry_hi'])} — jamais plus cher\n"
            f"   • Stop −15 % de TON prix payé : entre {fcfa(b['stop'])} (achat au bas de la fourchette) et {fcfa(b['stop_hi'])} (achat plus haut) → tu vends tout, sans discuter\n"
            f"   • +20 % ({fcfa(b['palier20'])}) → vends ⅓\n"
            f"   • +35 % ({fcfa(b['palier35'])}) → vends ⅓\n"
            f"   • +50 % ({fcfa(b['palier50'])}) → vends le reste\n"
            f"   • Le signal vit tant que le prix reste au-dessus de {fcfa(b['entry_lo'])}\n"
            f"\n🚫 Règle d'or : un pari perdant ne devient JAMAIS un loyer.")
    return head + body
