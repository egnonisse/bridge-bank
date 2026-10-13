"""Seuils de vente sur plus-value — significativité, calibrage et journal des changements.

TROIS RESPONSABILITÉS, TOUTES LIÉES AU MÊME OBJET (le seuil de vente d'un titre)
-------------------------------------------------------------------------------
  1. SIGNIFICATIVITÉ — un seuil ne déclenche une vente que si son signal bat le hasard
     (intervalle de confiance de Wilson). Sinon il reste visible mais informatif.
  2. CALIBRAGE — mesurer, sur l'historique d'un titre, le seuil dont la probabilité de
     baisse à J+20 est la plus haute.
  3. JOURNAL — garder trace de CHAQUE modification de seuil, avec son motif.

Le calibrage vivait dans `portfolio.py` : la règle et sa mesure étaient dans deux modules,
ce qui obligeait à sauter de l'un à l'autre pour comprendre une seule décision.

POURQUOI CE TEST EXISTE
-----------------------
Le calibrage choisissait le seuil dont la PROBABILITE PONCTUELLE de baisse etait la plus
haute. Sur SNTS, ce choix tombait sur 86 % ... mesure sur 7 cas seulement. L'intervalle de
confiance a 95 % de ce 86 % va de 49 % a 97 % : la borne basse est sous 50 %, donc on ne
peut PAS affirmer que ce seuil fasse mieux que pile ou face.

Le defaut n'etait pas le choix du seuil mais l'ABSENCE DE TEST DE SIGNIFICATIVITE. Ce
module apporte ce test et en deduit un MODE :

    "declencheur"  le signal est statistiquement fonde  -> alerte de vente proposee
    "informatif"   le signal n'est pas fonde            -> information seule, pas de vente

MESURE SUR LES 4 TITRES DU PORTEFEUILLE (08/10/2026) : borne basse 49 % (SNTS), 46 %
(SGBC), 36 % (SLBC), 34 % (PALC). AUCUN ne depasse 50 %. Le mode informatif est donc la
regle, pas l'exception — ce qui est coherent avec l'attribution qui chiffre les paliers a
-43,1 points de rendement ajuste.

POURQUOI UN JOURNAL (demande LEO du 08/10/2026)
-----------------------------------------------
**Git ne suffit pas.** Il dit quand le CODE a change — pas quand un SEUIL a change pendant
l'execution, ni pourquoi. Un seuil recalibre automatiquement peut basculer sans qu'aucun
commit n'apparaisse, et l'information est alors perdue. Le journal est **append-only** (une
ligne JSON par evenement, jamais de reecriture) : une ecriture interrompue ne peut pas
corrompre les entrees precedentes.

L'INTERVALLE DE WILSON, PAS L'INTERVALLE NORMAL
----------------------------------------------
Sur petit echantillon, l'intervalle normal (p +/- 1,96*sqrt(p(1-p)/n)) donne des bornes
absurdes (negatives ou > 1) : sur 7 cas a 86 %, il produit une borne haute de 112 %. La
formule de Wilson reste dans [0, 1] et se comporte correctement a petit n — c'est la
bonne reference ici.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from ..infrastructure.paths import PROFIT_THRESHOLDS, SEUILS_JOURNAL  # chemins centralisés (lot 0 du plan docs/architecture.md)

Z = 1.96                  # couverture 95 %
# Règles de significativité : définies dans src/regles.py (catalogue unique).
from ..regles import BORNE_BASSE_MIN, EPISODES_MIN as MIN_EPISODES  # noqa: E402
from ..regles import PROFIT_ALERT_THRESHOLD  # noqa: E402  (B1-12 : défaut central, 12/10)

SEUILS_FILE = PROFIT_THRESHOLDS  # définis dans paths.py (P6-01)
JOURNAL_FILE = SEUILS_JOURNAL

# Vocabulaire du mode, schéma du fichier et protection des décisions : DÉFINIS dans
# `src/calibration/schema_seuils.py` (source unique, déplacé avec ce module au lot 3) et
# RÉEXPORTÉS ici — les appelants gardent leurs noms
# (`from src.calibration.seuils_vente import MODE_DECLENCHEUR` continue de fonctionner).
from .schema_seuils import (MODE_DECLENCHEUR, MODE_INFORMATIF,  # noqa: E402,F401
                            SeuilProtege, SeuilsInvalides, ecrire_atomique, est_protege,
                            lire_et_valider, refus_ecriture, valider)  # noqa: F401

MOTIF_CALIBRAGE = "calibrage automatique"
MOTIF_MIGRATION = "migration (ajout du mode)"
MOTIF_REFUS = "refus : ecriture automatique sur un reglage protege"
ORIGINE_AUTO = "automatique"
ORIGINE_MANUELLE = "manuelle"

METHODE_DEFAUT = "episodes de +seuil % en 20 seances, dedoublonnes par vague"

# Seuils candidats et table de départ (utilisée SEULEMENT si le fichier calibré est vide).
SEUILS_CANDIDATS = (0.05, 0.08, 0.10, 0.13, 0.15)
SEUILS_PAR_DEFAUT = {"SNTS": 0.13, "SGBC": 0.10, "SLBC": 0.05, "PALC": 0.05}


def intervalle_wilson(succes: int, total: int) -> tuple[float, float, float]:
    """Intervalle de confiance a 95 % (Wilson). Retourne (p, borne_basse, borne_haute)."""
    if total <= 0:
        return 0.0, 0.0, 1.0
    p = succes / total
    d = 1 + Z * Z / total
    centre = (p + Z * Z / (2 * total)) / d
    demi = Z * ((p * (1 - p) / total + Z * Z / (4 * total * total)) ** 0.5) / d
    return p, max(0.0, centre - demi), min(1.0, centre + demi)


def evaluer(succes: int, total: int) -> dict:
    """Evalue un seuil candidat : probabilite, intervalle, et mode qui en decoule.

    Renvoie un dict pret a etre stocke dans data/profit_thresholds.json.
    """
    p, bas, haut = intervalle_wilson(succes, total)
    significatif = (total >= MIN_EPISODES) and (bas >= BORNE_BASSE_MIN)
    return {
        "down_prob": round(p * 100),
        "borne_basse": round(bas * 100),
        "episodes": total,
        "significatif": significatif,
        "mode": MODE_DECLENCHEUR if significatif else MODE_INFORMATIF,
    }


def mode_pour(info: dict | None) -> str:
    """Mode d'un seuil deja calibre.

    Un seuil ANCIEN (avant l'introduction du test) n'a pas de champ `mode` : on le
    classe INFORMATIF — c'est le choix prudent, et c'est ce que disent les donnees
    (borne basse < 50 % pour les 4 titres du portefeuille). Un seuil explicite est
    respecte tel quel : c'est ce qui garantit que la decision ne peut pas etre
    reecrite par un recalcul.
    """
    if not info:
        return MODE_INFORMATIF
    mode = info.get("mode")
    if mode in (MODE_DECLENCHEUR, MODE_INFORMATIF):
        return mode
    return MODE_INFORMATIF


def est_declencheur(info: dict | None) -> bool:
    """Vrai si le seuil peut proposer une VENTE (et pas seulement informer)."""
    return mode_pour(info) == MODE_DECLENCHEUR


def explication(info: dict | None) -> str:
    """Pourquoi aucune vente n'est proposée, dit en langage courant.

    Traduction volontairement concrète : « rebaissé 26 fois sur 56 cas » plutôt que
    « borne basse 34 % ». Le repère du pile ou face est explicite, sinon un lecteur non
    averti lit « 46 % » comme un signal alors que c'est du hasard.
    """
    if not info or info.get("down_prob") is None or info.get("episodes") is None:
        return ("   Pourquoi je ne te propose pas de vendre :\n"
                "      ce titre n'a pas assez d'historique pour qu'on sache si vendre\n"
                "      à ce niveau a un intérêt. Par prudence, on ne propose rien.")
    prob = info["down_prob"]
    n = info["episodes"]
    k = round(prob / 100 * n)
    return (f"   Pourquoi je ne te propose pas de vendre :\n"
            f"      sur {n} cas passés où le prix avait monté comme ça, il est\n"
            f"      rebaissé {k} fois ({prob} %). C'est trop proche du pile ou face\n"
            f"      (50 %) pour en faire une règle.")


# ══════════════════════════════════════════════════════════════════════════════
#  2. CALIBRAGE  (déplacé depuis portfolio.py — la règle et sa mesure réunies)
# ══════════════════════════════════════════════════════════════════════════════


def indices_episodes(closes: list[float], seuil: float) -> list[int]:
    """Indices des épisodes retenus — LA définition de référence du projet.

    Un épisode = le prix a monté d'au moins `seuil` sur les 20 dernières séances. Les
    fenêtres sont rendues DISJOINTES (saut de 20 après chaque détection) : deux épisodes à
    10 séances d'écart partageraient la moitié de leur fenêtre et ne seraient pas
    indépendants. Espacer moins gonfle le nombre de cas sans apporter d'information —
    *davantage de cas n'est pas une meilleure preuve*.

    C'est cette fonction que DOIVENT utiliser toute mesure du même phénomène (seuil de
    vente et profil de retournement), sinon deux chiffres divergents réapparaissent.
    """
    idx, i = [], 20
    while i < len(closes) - 20:
        ref = closes[i - 20]
        if ref > 0 and closes[i] >= ref * (1 + seuil):
            idx.append(i)
            i += 20          # dédoublonnage par vague (indépendance)
        else:
            i += 1
    return idx


def episodes(closes: list[float], seuil: float) -> list[float]:
    """Rendement à J+20 de chaque épisode — dérivé de `indices_episodes` (une seule règle).

    Dédoublonné par vague (`i += 20` après une détection) pour que les épisodes soient
    indépendants — sinon un seul grand mouvement compterait vingt fois.
    """
    return [closes[i + 20] / closes[i] - 1 for i in indices_episodes(closes, seuil)]


def calibrer(code: str, closes: list[float]) -> dict | None:
    """Seuil dont la probabilité de baisse à J+20 est la plus haute, PUIS testé.

    Le filtre `MIN_EPISODES` (8) est celui de `src/regles.py` : un candidat mesuré sur
    moins de 8 cas n'est même pas proposé. C'est le MÊME seuil que celui qui juge la
    significativité — il n'y a plus deux réponses à la question « combien de cas ».
    """
    import statistics

    best: dict | None = None
    best_p = -1.0
    for seuil in SEUILS_CANDIDATS:
        ep = episodes(closes, seuil)
        if len(ep) < MIN_EPISODES:
            continue
        n = len(ep)
        k = sum(1 for r in ep if r < 0)
        p = k / n
        med = statistics.median(ep) * 100
        if p > best_p:            # comparaison sur le float, jamais sur un champ arrondi
            best_p = p
            best = {"code": code.upper(), "threshold": seuil,
                    "median_pct": round(med, 1), **evaluer(k, n)}
    return best


def charger(chemin: Path | None = None) -> dict:
    """Lit les seuils calibrés — et REFUSE un fichier inexploitable.

    Renvoyait `{}` sur toute erreur : le système retombait alors sur la table de départ, tout
    passait en `informatif`, plus aucune vente n'était proposée — et rien ne le disait. Un
    fichier ABSENT reste légitime (aucun seuil calibré) ; un fichier illisible ne l'est pas :
    il lève `SeuilsInvalides` en nommant la ligne ou l'entrée fautive.
    """
    return lire_et_valider(chemin or SEUILS_FILE)


def enregistrer(data: dict, *, origine: str = ORIGINE_AUTO,
                autorise_protege: bool = False, chemin: Path | None = None,
                journal: Path | None = None) -> None:
    """Écrit les seuils — après validation du contenu ET contrôle de ce qui est remplacé.

    Deux refus, et dans les deux cas le fichier n'est PAS touché :

      - `SeuilsInvalides` : le contenu ne respecte pas le schéma (`src/schema_seuils.py`) ;
      - `SeuilProtege`    : l'écriture changerait le seuil ou le mode d'une entrée protégée
        (un `declencheur`, ou toute entrée portant `protege: true`). `autorise_protege=True`
        déclare l'autorisation explicite : c'est le geste manuel, jamais le recalcul.

    `origine` vaut « automatique » par défaut — le mode le plus restrictif. Un appelant
    automatique n'a donc rien à déclarer pour être traité comme tel.

    Le refus est JOURNALISÉ avant d'être levé : un refus silencieux serait aussi grave que
    l'écrasement qu'il évite.
    """
    erreurs, _ = valider(data, complet=True)      # contrat d'ÉCRITURE : rien d'incomplet
    if erreurs:
        raise SeuilsInvalides("écriture refusée — " + " ; ".join(erreurs))
    cible = chemin or SEUILS_FILE
    avant = lire_et_valider(cible)     # on refuse de détruire ce qu'on ne sait pas relire
    refus = [] if autorise_protege else refus_ecriture(avant, data)
    if refus:
        par_code: dict[str, list[str]] = {}
        for raison in refus:
            par_code.setdefault(raison.split(" :")[0], []).append(raison)
        for code, raisons in par_code.items():
            seuil_actuel = (avant.get(code) or {}).get("threshold")
            journaliser(code, avant=seuil_actuel, apres=seuil_actuel,
                        motif=f"{MOTIF_REFUS} — " + " ; ".join(raisons),
                        origine=origine, methode="ecriture automatique refusee",
                        chemin=journal)
        raise SeuilProtege("écriture refusée — " + " ; ".join(refus))
    ecrire_atomique(cible, data)


def pour(code: str, defaut: float | None = None) -> float:
    """Seuil applicable à un code : fichier calibré → table de départ → défaut central.

    B1-12 (corrigé le 12/10) : le défaut était un littéral `0.13` recopié — il vient
    désormais de `regles.PROFIT_ALERT_THRESHOLD` (catalogue unique), pour qu'une
    évolution du défaut n'existe qu'en un seul endroit.
    """
    if defaut is None:
        defaut = PROFIT_ALERT_THRESHOLD
    info = charger().get(code.upper())
    if info:
        return float(info.get("threshold", defaut))
    return SEUILS_PAR_DEFAUT.get(code.upper(), defaut)


# ══════════════════════════════════════════════════════════════════════════════
#  3. JOURNAL APPEND-ONLY DES CHANGEMENTS DE SEUIL
# ══════════════════════════════════════════════════════════════════════════════


def journaliser(titre: str, avant: float | None, apres: float | None,
                motif: str, origine: str, methode: str = "",
                test: dict | None = None, chemin: Path | None = None) -> dict:
    """Écrit UNE ligne dans le journal des seuils. Append-only, jamais de réécriture.

    Les sept informations exigées (demande LEO 08/10/2026) : date et heure · titre ·
    ancienne et nouvelle valeur · motif · méthode de calibration · résultat du test
    statistique · origine (automatique ou manuelle).
    """
    entree = {
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        "titre": titre.upper(),
        "avant": avant,
        "apres": apres,
        "motif": motif,
        "origine": origine,
        "methode": methode or (METHODE_DEFAUT if test else ""),
        "test": test or {},
    }
    cible = chemin or JOURNAL_FILE
    cible.parent.mkdir(parents=True, exist_ok=True)
    with cible.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    return entree


def lire_journal(titre: str | None = None, chemin: Path | None = None) -> list[dict]:
    """Relit le journal (le plus ancien d'abord). `titre` filtre sur un code."""
    cible = chemin or JOURNAL_FILE
    try:
        lignes = cible.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ligne in lignes:
        if not ligne.strip():
            continue
        try:
            e = json.loads(ligne)
        except json.JSONDecodeError:
            continue          # ligne corrompue : ignorée, le reste du journal survit
        if titre is None or e.get("titre") == titre.upper():
            out.append(e)
    return out


def dernier_changement(titre: str, chemin: Path | None = None) -> dict | None:
    """Dernière modification connue d'un seuil — sert à justifier une alerte."""
    hist = lire_journal(titre, chemin)
    return hist[-1] if hist else None


def resume_justification(code: str) -> str:
    """Ligne courte pour une alerte : d'où vient le seuil appliqué (demande LEO).

    C'est la version MINIMALE de la traçabilité : on garde la justification et la version
    du seuil ayant produit une alerte, sans instrumenter chaque décision du système.

    Le taux brut est accompagné de sa conclusion (« non concluant ») quand le test
    statistique ne le soutient pas : un chiffre affiché seul se lit toujours comme une
    preuve, même quand ce n'en est pas une.
    """
    info = charger().get(code.upper())
    if not info:
        return ""
    change = dernier_changement(code)
    origine = f" · {change['origine']}, {change['horodatage'][:10]}" if change else ""
    prob, n = info.get("down_prob"), info.get("episodes")
    seuil = info.get("threshold", 0) * 100
    if prob is None or n is None:
        return f"   (seuil {seuil:.0f} %{origine})"
    verdict = "" if info.get("significatif") else ", non concluant"
    return (f"   (seuil {seuil:.0f} % — {prob} % de baisse sur {n} cas{verdict}{origine})")
