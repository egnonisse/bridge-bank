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

ZONE_LABELS = {
    "FORCE": ("✅ ZONE DE FORCE", "le prix est près de son plus haut de 5 ans — "
              "historiquement la meilleure zone (83 % de réussite)"),
    "BAS_SOLIDE": ("🟡 ZONE BASSE MAIS SAINE", "20-40 % de la fourchette : bon compromis "
                   "(80 % de réussite)"),
    "MILIEU": ("🟡 MILIEU DE FOURCHETTE", "zone neutre"),
    "HAUT_FRAGILE": ("🔴 ZONE DANGER", "60-80 % : les anciens champions qui "
                     "s'essoufflent — 0 gagnant sur 4 dans l'histoire"),
    "BAS_ECRASE": ("🔴 ZONE PIÈGE", "les 20 % du bas : « pas cher » ne paie pas "
                   "(50 % de réussite, +3,5 % médian)"),
}


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
    prof = load_profiles()
    st = prof.get(main, {})
    zst = prof.get("ZONES", {}).get(zl, {})

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
        "zone_win": zst.get("win"),
        "zone_median": zst.get("median"),
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


def build_message(f: FicheSpec) -> str:
    b = f.blocks
    main = b["main"]
    zlabel, ztxt = ZONE_LABELS[b["zone_label"]]
    zwin = f" ({b['zone_win']*100:.0f} % de réussite)" if b.get("zone_win") is not None else ""
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

    head = (f"{SCHEMA_LABELS[main]} — {f.code} ({f.name})\n\n"
            f"Cours de référence : {fcfa(f.price)} "
            f"({'LIVE du moment' if b.get('cours_source') == 'live' else 'dernière clôture connue'})\n"
            f"Ce qui se passe : ce cours a déclenché le schéma "
            f"« {mot} » — {rare}, jamais automatique.\n\n"
            f"📊 FRÉQUENCES HISTORIQUES (10 ans, hors frais déjà déduits) :\n"
            f"   • La fréquence qui DÉCIDE est celle du schéma BRUT (avant\n"
            f"     les filtres zone + volume ci-dessous) : "
            f"{b['win_12m']*100:.0f} % de {b['n']} cas OBSERVÉS finissent plus hauts "
            f"12 mois après (+{b['median_net']*100:.0f} % net médian)\n"
            + ("   ⚠️ STATISTIQUES DE SECOURS : le calibrage courant est indisponible —\n"
               "      ces chiffres datent des épreuves de septembre 2026 et ne sont\n"
               "      PAS re-mesurés. Ne les traite pas comme la mesure du jour.\n"
               if b.get("stats_fallback") else ""))
    if touched:
        head += (f"   • Ton palier +20 % : touché dans {touched.get('0.20', 0)*100:.0f} % des cas observés\n"
                 f"   • Ton palier +50 % : touché dans {touched.get('0.50', 0)*100:.0f} % des cas observés\n")
    head += (f"   • {zlabel} : {ztxt}{zwin} — la zone MODULE le schéma\n"
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
