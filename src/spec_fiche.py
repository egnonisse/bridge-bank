"""Fiche spé complète — génération du message néophyte pour un titre détecté.

4 blocs : schéma + probabilité · zone de prix · prix d'entrée · filet.
Le verdict combine schéma ET zone : une zone DANGER/PIÈGE dit NON même si
le schéma est allumé (ex. SCRC : panique à 75 % de la fourchette).

Style néophyte (règle LEO 03/09) : un chiffre = sa signification,
fait / hypothèse / décision séparés, jamais d'ordre automatique.
"""
from dataclasses import dataclass, field

from .spec_profiles import load_profiles, zone_of, zone_label, detect_schemas

# Emojis / libellés par schéma
SCHEMA_LABELS = {
    "CASSURE": "🔓 CASSURE DE 1 AN",
    "EVEIL": "🌅 DÉBUT DE HAUSSE",
    "PANIQUE": "🩹 RACHAT DE PANIQUE",
}
SCHEMA_WORDS = {
    "CASSURE": "cassure de 1 an",
    "EVEIL": "début de hausse",
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


def build_fiche(code: str, name: str, closes: list) -> FicheSpec | None:
    """Construit la fiche pour la dernière séance d'une série.

    Retourne None si aucun schéma actif ou série trop courte.
    """
    schemas = detect_schemas(closes)
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
        "palier20": entry_lo * 1.20,
        "palier35": entry_lo * 1.35,
        "palier50": entry_lo * 1.50,
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

    head = (f"{SCHEMA_LABELS[main]} — {f.code} ({f.name})\n\n"
            f"Cours de référence : {f.price:,.0f} F "
            f"({'LIVE du moment' if b.get('cours_source') == 'live' else 'dernière clôture connue'})\n"
            f"Ce qui se passe : ce cours a déclenché le schéma "
            f"« {mot} » — un signal rare, jamais automatique.\n\n"
            f"📊 CE QUE DISENT NOS 10 ANS DE DONNÉES :\n"
            f"   • {b['win_12m']*100:.0f} % des {b['n']} cas finissent plus hauts 12 mois après "
            f"(+{b['median_net']*100:.0f} % net médian)\n")
    if touched:
        head += (f"   • Ton palier +20 % : touché dans {touched.get('0.20', 0)*100:.0f} % des cas\n"
                 f"   • Ton palier +50 % : touché dans {touched.get('0.50', 0)*100:.0f} % des cas\n")
    head += (f"   • {zlabel} : {ztxt}{zwin}\n"
             f"   ⚠️ {b['n']} cas seulement : probabilité honnête, pas une certitude — "
             f"les perdants existent.\n")

    if f.verdict == "NON":
        return head + ("\n📋 VERDICT : ❌ LA FICHE DIT NON.\n"
                       "   Le schéma est allumé mais la zone de prix le contredit.\n"
                       "   On laisse tomber, sans regret : la veille sait dire non.\n"
                       "\n🚫 Règle d'or : un pari perdant ne devient JAMAIS un loyer.")

    body = (f"\n📋 SI TU DÉCIDES DE JOUER (ta décision, jamais automatique) :\n"
            f"   • Achat : entre {b['entry_lo']:,.0f} et {b['entry_hi']:,.0f} F — jamais plus cher\n"
            f"   • Stop −15 % : {b['stop']:,.0f} F → tu vends tout, sans discuter\n"
            f"   • +20 % ({b['palier20']:,.0f} F) → vends ⅓\n"
            f"   • +35 % ({b['palier35']:,.0f} F) → vends ⅓\n"
            f"   • +50 % ({b['palier50']:,.0f} F) → vends le reste\n"
            f"   • Le signal vit tant que le prix reste au-dessus de {b['entry_lo']:,.0f} F\n"
            f"\n🚫 Règle d'or : un pari perdant ne devient JAMAIS un loyer.")
    return head + body
