"""Construit le jeu de donnees presente aux modeles du challenge.

SOURCE : `data/history_clean.pkl` — historique AJUSTE des divisions de nominal
et NETTOYE des valeurs aberrantes (genere par `scripts/preparer_historique_propre.py`).
Utiliser l'historique brut produirait des statistiques fausses (drawdowns a -96 %)
et ferait raisonner les modeles sur des donnees corrompues.

PRINCIPE DE SECURITE : les modeles ne recoivent que des STATISTIQUES
DESCRIPTIVES du passe. Ils ne recoivent JAMAIS :
  - les cours bruts (trop volumineux, et ils les surinterpretent)
  - les RESULTATS de backtest (sinon ils "devineraient" au lieu de raisonner)

Le fichier produit sert de contexte commun et identique pour tous les modeles,
ce qui garantit une comparaison equitable.
"""
import json
import pickle
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

DATA = RACINE / "data"
SORTIE = DATA / "challenge_dataset.json"

# Historique propre prioritaire ; le brut n'est qu'un repli explicite
CANDIDATS = ("history_clean.pkl", "history_cache.pkl")


def charge_historique():
    """Charge l'historique de cours (pickle contenant des HistoryBar)."""
    for nom in CANDIDATS:
        p = DATA / nom
        if p.exists():
            if nom == "history_cache.pkl":
                print("  ATTENTION : history_clean.pkl absent — repli sur le BRUT.")
                print("  Les statistiques seront fausses (divisions non ajustees).")
                print("  Lancer d'abord : python scripts/preparer_historique_propre.py")
            else:
                print(f"  Source : {nom} (divisions ajustees, aberrantes nettoyees)")
            with open(p, "rb") as fh:
                return pickle.load(fh)
    raise SystemExit(
        "Aucun historique trouve.\n"
        "Lancer : python scripts/preparer_historique_propre.py"
    )


def stats_titre(barres):
    """Statistiques descriptives d'un titre, sans exposer les cours bruts."""
    if len(barres) < 30:
        return None
    closes = [b.close for b in barres if getattr(b, "close", None)]
    if len(closes) < 30:
        return None

    # Rendements quotidiens
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1]:
            rets.append((closes[i] - closes[i - 1]) / closes[i - 1])

    def pct(v):
        return round(v * 100, 2)

    # Rendement cumule
    perf_totale = (closes[-1] / closes[0] - 1) if closes[0] else 0

    # Volatilite annualisee (252 seances)
    vol_ann = None
    if len(rets) > 2:
        try:
            vol_ann = pct(statistics.pstdev(rets) * (252 ** 0.5))
        except Exception:
            pass

    return {
        "seances": len(closes),
        "premier_jour": str(getattr(barres[0], "date", ""))[:10],
        "dernier_jour": str(getattr(barres[-1], "date", ""))[:10],
        "cours_initial": closes[0],
        "cours_final": closes[-1],
        "perf_totale_pct": pct(perf_totale),
        "perf_annuelle_pct": pct((1 + perf_totale) ** (252 / max(len(closes), 1)) - 1),
        "volatilite_annuelle_pct": vol_ann,
        "drawdown_max_pct": pct(drawdown_max(closes)),
        "volume_median": int(statistics.median(
            [b.volume for b in barres if getattr(b, "volume", 0) > 0] or [0])),
    }


def drawdown_max(closes):
    """Plus forte baisse depuis un sommet."""
    pic, dd = closes[0] or 1, 0.0
    for c in closes:
        pic = max(pic, c)
        if pic:
            dd = min(dd, (c - pic) / pic)
    return dd


def main():
    print("=" * 78)
    print("  CONSTRUCTION DU JEU DE DONNEES — CHALLENGE BRIDGE BANK")
    print("=" * 78)

    hist = charge_historique()
    print(f"\n  {len(hist)} titres charges")

    # --- Statistiques par titre -----------------------------------------
    par_titre = {}
    for code, barres in hist.items():
        s = stats_titre(barres)
        if s:
            par_titre[code] = s
    print(f"  {len(par_titre)} titres avec assez d'historique")

    # --- Fondamentaux ----------------------------------------------------
    fond = {}
    fp = DATA / "fundamentals_cache.json"
    if fp.exists():
        fond = json.loads(fp.read_text(encoding="utf-8"))
    print(f"  {len(fond)} titres avec fondamentaux")

    # --- Fusion : une fiche par titre ------------------------------------
    titres = []
    for code in sorted(par_titre):
        s = par_titre[code]
        f = fond.get(code, {})
        fiche = {
            "code": code,
            "cours_final": s["cours_final"],
            "perf_annuelle_pct": s["perf_annuelle_pct"],
            "volatilite_annuelle_pct": s["volatilite_annuelle_pct"],
            "drawdown_max_pct": s["drawdown_max_pct"],
            "volume_median": s["volume_median"],
            "seances": s["seances"],
            "per": f.get("per"),
            "dps": f.get("dps"),
            # PAYOUT REELLEMENT CALCULE : dps / benefice par action.
            # BPA = cours / per, donc payout = dps x per / cours.
            # Le bug corrige ici : la version precedente ecrivait dps / cours,
            # c'est-a-dire le RENDEMENT brut, pas le payout. Consequence mesuree :
            # ABJC affichait 5,54 % de payout alors que le vrai est 150 % — toute
            # regle utilisant ce champ raisonnait sur une donnee fausse.
            "payout_pct": (
                round(f["dps"] * f["per"] / s["cours_final"], 4) * 100
                if f.get("dps") and f.get("per") and s["cours_final"] else None
            ),
        }
        # Rendement net apres IRVM 12 %
        if fiche["dps"] and s["cours_final"]:
            brut = fiche["dps"] / s["cours_final"]
            fiche["rendement_brut_pct"] = round(brut * 100, 2)
            fiche["rendement_net_pct"] = round(brut * 0.88 * 100, 2)
        titres.append(fiche)

    print(f"  {len(titres)} fiches titres construites")

    # --- Statistiques de marche agregees ---------------------------------
    perfs = [t["perf_annuelle_pct"] for t in titres if t["perf_annuelle_pct"] is not None]
    vols = [t["volatilite_annuelle_pct"] for t in titres if t["volatilite_annuelle_pct"]]
    dds = [t["drawdown_max_pct"] for t in titres if t["drawdown_max_pct"] is not None]

    marche = {
        "nb_titres": len(titres),
        "perf_annuelle_mediane_pct": round(statistics.median(perfs), 2) if perfs else None,
        "perf_annuelle_moyenne_pct": round(statistics.fmean(perfs), 2) if perfs else None,
        "perf_annuelle_min_pct": round(min(perfs), 2) if perfs else None,
        "perf_annuelle_max_pct": round(max(perfs), 2) if perfs else None,
        "volatilite_mediane_pct": round(statistics.median(vols), 2) if vols else None,
        "drawdown_median_pct": round(statistics.median(dds), 2) if dds else None,
        "drawdown_pire_pct": round(min(dds), 2) if dds else None,
    }

    # --- Parametres actuels du projet (point de depart du challenge) ------
    parametres_actuels = {
        "critere_1_dividende": {"regle": "dividende officiel > 0", "note": "aucun seuil numerique"},
        "critere_2_rendement_net": {"seuil_pct": 4.0, "regle": "rendement net >= 4 % apres IRVM 12 %"},
        "critere_3_per": {"seuil": 14.0, "regle": "PER <= 14"},
        "critere_4_payout": {"seuil_pct": 80.0, "regle": "payout <= 80 %"},
        "critere_5_regularite": {"seuil": "4/5 ans", "regle": "dividende verse >= 4 des 5 derniers ans"},
        "critere_6_croissance": {"seuil_pct": -10.0, "regle": "croissance du dividende >= -10 %/an"},
        "critere_7_liquidite": {"seuil_fcfa_jour": 5_000_000, "regle": "volume >= 5 M F/jour"},
        "gestion_risque": {
            "stop_pct": -15.0,
            "palier_1": "+20 % -> vendre 1/3 (break-even)",
            "palier_2": "+35 % -> vendre 1/3 (stop suiveur)",
            "palier_3": "+50 % -> cloture",
        },
        "frais": {"courtage_pct": 1.4, "note": "aller-retour, minimum 1000 F"},
        "fiscalite": {"irvm_pct": 12.0, "note": "retenue sur dividendes"},
    }

    # --- Filtres anti-erreurs (contraintes a respecter) ------------------
    contraintes = {
        "titre_le_plus_faible_perf": min(titres, key=lambda t: t["perf_annuelle_pct"] or 0)["code"],
        "titre_le_plus_fort_perf": max(titres, key=lambda t: t["perf_annuelle_pct"] or -999)["code"],
        "attention_survivorship": (
            "Seuls les titres encore cotes en 2026 sont presents. Les titres "
            "radiés/faillis entre 2017 et 2026 sont ABSENTS : cela surestime "
            "la performance de toute strategie."
        ),
        "attention_frais": "Tout resultat doit etre net de 1,4 % de frais aller-retour.",
        "attention_irvm": "Les dividendes subissent 12 % de retenue.",
        "attention_echantillon": (
            f"{len(titres)} titres seulement : les p-values doivent etre traitees "
            "avec prudence, un resultat sur 20 observations n'est pas significatif."
        ),
    }

    # --- Epreuves DEJA menees (pour ne pas les refaire) ------------------
    epreuves_deja_faites = [
        {"nom": "breakout + volume >= 2x", "resultat": "PLACEBO", "p_value": 0.44,
         "detail": "6 612 mouvements testes : aucune valeur predictive"},
        {"nom": "acheter apres -15 %", "resultat": "NEGATIF", "detail": "pas de rebond systematique"},
        {"nom": "paliers de prise de profit", "resultat": "NET ~ 0", "detail": "effet neutre apres frais"},
        {"nom": "momentum extreme", "resultat": "NEGATIF out-of-sample", "detail": "ne survit pas"},
        {"nom": "pairs trading", "resultat": "INFERIEUR au hasard", "detail": "short impossible sur la BRVM"},
        {"nom": "profils de duree (CASSURE/EVEIL)", "resultat": "FAIBLE", "detail": "win_12m 0,61-0,70 mais echantillon minuscule (10-28 episodes)"},
    ]

    # --- Assemblage ------------------------------------------------------
    jeu = {
        "_meta": {
            "genere_le": datetime.now().isoformat(timespec="seconds"),
            "source": "Bridge Bank — donnees BSTrade + fondamentaux BRVM",
            "usage": "Contexte commun du challenge multi-modeles. Identique pour tous les modeles.",
            "avertissement": (
                "Les modeles ne doivent PAS proposer d'hypothese deja testee "
                "(voir epreuves_deja_menees). Ils doivent proposer des idees "
                "TESTABLES sur 9 ans d'historique."
            ),
        },
        "marche": marche,
        "parametres_actuels": parametres_actuels,
        "contraintes": contraintes,
        "epreuves_deja_menees": epreuves_deja_faites,
        "titres": titres,
    }

    SORTIE.write_text(json.dumps(jeu, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  ecrit : {SORTIE.name}  ({SORTIE.stat().st_size / 1024:.0f} Ko)")
    print(f"\n  Marche : {marche['nb_titres']} titres")
    print(f"    perf annuelle mediane  : {marche['perf_annuelle_mediane_pct']} %")
    print(f"    volatilite mediane     : {marche['volatilite_mediane_pct']} %")
    print(f"    drawdown median        : {marche['drawdown_median_pct']} %")
    print(f"    drawdown pire          : {marche['drawdown_pire_pct']} %")

    avec_fond = sum(1 for t in titres if t["per"])
    avec_rend = sum(1 for t in titres if t.get("rendement_net_pct") is not None)
    print(f"\n  Titres avec PER : {avec_fond} / {len(titres)}")
    print(f"  Titres avec rendement calculable : {avec_rend} / {len(titres)}")
    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()
