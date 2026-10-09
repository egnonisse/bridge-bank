"""Schéma et protection de `data/profit_thresholds.json`.

POURQUOI CE MODULE EXISTE
-------------------------
Ce fichier porte des DÉCISIONS : le seuil qui propose une vente, et son mode. Deux dangers
ont été mesurés dans le code réel (09/10/2026) :

1. **Un fichier mal formé devenait un système sans seuils, en silence.** `charger()` avalait
   l'erreur JSON et renvoyait `{}` : `pour()` retombait sur la table de départ, `mode_pour`
   classait tout en `informatif` — donc plus aucune vente proposée — et rien ne le signalait.
   Un fichier tronqué changeait ainsi une décision d'investissement sans un mot.
2. **Rien n'empêchait un calibrage automatique d'écraser une décision.** `enregistrer()`
   écrivait le dictionnaire reçu, sans contrôler ni le contenu, ni ce qui était remplacé.

DEUX CONTRATS, PARCE QUE LIRE ET ÉCRIRE N'ONT PAS LE MÊME RISQUE
----------------------------------------------------------------
- **LIRE doit rester tolérant** aux fichiers HISTORIQUES. Un seuil calibré avant l'introduction
  du mode n'a ni `mode` ni `borne_basse` ; `mode_pour` sait le classer prudemment en
  `informatif`. Refuser de le lire supprimerait une décision existante au lieu de la protéger.
- **ÉCRIRE doit être strict** : ce que le système produit est complet et cohérent, sinon la
  qualité de demain dépend de ce qui traînait hier.

Dans les deux cas, **un champ PRÉSENT mais invalide est refusé** : c'est exactement le cas où
le silence change une décision — un `mode` inconnu retomberait en `informatif`, et une vente
disparaîtrait sans un mot.

CE QUI EST PROTÉGÉ
------------------
Une **décision en vigueur** ne se réécrit pas sans autorisation explicite, même par un
recalcul automatique : `mode: declencheur` (implicite — ce seuil propose de VENDRE) ou
`protege: true` (explicite — geler un seuil qu'on ne veut pas voir bouger).

`mode` est défini ICI et réexporté par `seuils_vente` : le vocabulaire de l'enregistrement en
est la source. Les appelants continuent d'écrire
`from src.calibration.seuils_vente import MODE_DECLENCHEUR`.

COHÉRENCE `significatif` / `mode`
---------------------------------
    declencheur + non significatif   ->  ERREUR         (un déclencheur sans preuve)
    informatif  + significatif       ->  AVERTISSEMENT  (rétrogradation VOLONTAIRE : c'est
                                        l'invariant B3 — une décision humaine ne s'efface
                                        pas parce qu'un recalcul la trouverait favorable)

Ni l'un ni l'autre n'est interdit : ce sont deux choses différentes qu'on refuse de
confondre par accident. Un avertissement n'empêche pas l'écriture, il la rend visible.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# ── Vocabulaire du mode — SOURCE UNIQUE (réexporté par seuils_vente) ─────────────
MODE_DECLENCHEUR = "declencheur"
MODE_INFORMATIF = "informatif"
MODES = (MODE_DECLENCHEUR, MODE_INFORMATIF)

# ── Champs ──────────────────────────────────────────────────────────────────────
# Un champ inconnu est refusé, pas ignoré : une faute de frappe (« thresold ») doit se voir
# tout de suite, sinon la valeur reste à son ancienne place et le nouveau réglage est inerte.
CHAMPS_MESURE = ("down_prob", "borne_basse", "episodes", "median_pct", "significatif")
CHAMPS_DECISION = ("threshold", "mode")
CHAMPS_AUTORISES = ("code", "protege") + CHAMPS_MESURE + CHAMPS_DECISION

# À LIRE : seul le seuil est indispensable (sans lui, aucune décision n'est lisible).
CHAMPS_REQUIS_LECTURE = ("threshold",)
# À ÉCRIRE : tout ce que le système produit doit être présent et cohérent.
CHAMPS_REQUIS_ECRITURE = ("code", "threshold", "down_prob", "borne_basse", "episodes",
                          "significatif", "mode")

# Codes BRVM : majuscules et chiffres, « . » et « - » pour les lignes d'obligations.
CODE_ATTENDU = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,15}$")

# Bornes du seuil : au-delà de 1, ce n'est plus un seuil mais une faute d'unité (13 pour 0.13).
THRESHOLD_MIN, THRESHOLD_MAX = 0.0, 1.0


class SeuilsInvalides(ValueError):
    """Le contenu ne respecte pas le schéma. RIEN n'a été écrit ni supprimé."""


class SeuilProtege(PermissionError):
    """Une écriture visait une décision protégée sans autorisation explicite."""


def est_protege(info: dict | None) -> bool:
    """Vrai si l'entrée porte une décision qui ne se réécrit pas sans autorisation.

    Deux protections, dans cet ordre :
      - **explicite** : `protege: true` — geler un seuil qu'on ne veut pas voir bouger ;
      - **implicite** : `mode == declencheur` — ce seuil propose de VENDRE : ce n'est plus
        une mesure à rafraîchir, c'est une décision en vigueur.
    """
    if not isinstance(info, dict):
        return False
    if info.get("protege") is True:
        return True
    return info.get("mode") == MODE_DECLENCHEUR


def _est_nombre(valeur) -> bool:
    """Nombre réel — `True` est un `int` en Python, et ce n'est pas un seuil."""
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def _est_entier(valeur) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _valider_identite(code, info: dict, erreurs: list[str], complet: bool) -> None:
    if not isinstance(code, str) or not CODE_ATTENDU.match(code):
        erreurs.append(f"{code!r} : code invalide (majuscules, chiffres, « . » et « - »)")
    if not isinstance(info, dict):
        return
    inconnus = sorted(set(info) - set(CHAMPS_AUTORISES))
    if inconnus:
        erreurs.append(f"{code} : champ(s) inconnu(s) {inconnus} — faute de frappe, ou format "
                       f"d'une autre version")
    interieur = info.get("code")
    if interieur is None:
        if complet:
            erreurs.append(f"{code} : champ « code » manquant")
    elif str(interieur).upper() != str(code).upper():
        erreurs.append(f"{code} : le champ « code » vaut {interieur!r} — il doit valoir "
                       f"{code!r} (copier-coller)")


def _valider_presence(code: str, info: dict, erreurs: list[str], complet: bool) -> None:
    """Les champs absents. `complet=True` applique le contrat d'ÉCRITURE."""
    requis = CHAMPS_REQUIS_ECRITURE if complet else CHAMPS_REQUIS_LECTURE
    for champ in requis:
        if info.get(champ) is None:
            erreurs.append(f"{code} : « {champ} » manquant" + (" (écriture)" if complet else ""))


def _valider_decision(code: str, info: dict, erreurs: list[str]) -> None:
    seuil = info.get("threshold")
    if seuil is not None:
        if not _est_nombre(seuil):
            erreurs.append(f"{code} : « threshold » doit être un nombre, trouvé {seuil!r}")
        elif not (THRESHOLD_MIN < float(seuil) < THRESHOLD_MAX):
            erreurs.append(f"{code} : « threshold » = {seuil!r} hors de ]0 ; 1[ — "
                           f"écrire 0.13, pas 13")

    mode = info.get("mode")
    # Un mode ABSENT est toléré à la lecture (seuil historique) ; un mode INCONNU ne l'est
    # jamais : il retomberait silencieusement en informatif, et une vente disparaîtrait.
    if mode is not None and mode not in MODES:
        erreurs.append(f"{code} : « mode » = {mode!r} inconnu (attendu : {', '.join(MODES)})")

    protege = info.get("protege")
    if protege is not None and not isinstance(protege, bool):
        erreurs.append(f"{code} : « protege » doit être un booléen, trouvé {protege!r}")


def _valider_mesures(code: str, info: dict, erreurs: list[str]) -> None:
    for champ in ("down_prob", "borne_basse"):
        valeur = info.get(champ)
        if valeur is None:
            continue                 # absent = toléré à la lecture ; vu par _valider_presence
        if not _est_entier(valeur):
            erreurs.append(f"{code} : « {champ} » doit être un entier, trouvé {valeur!r}")
        elif not 0 <= valeur <= 100:
            erreurs.append(f"{code} : « {champ} » = {valeur} hors de [0 ; 100]")

    episodes = info.get("episodes")
    if episodes is not None:
        if not _est_entier(episodes):
            erreurs.append(f"{code} : « episodes » doit être un entier, trouvé {episodes!r}")
        elif episodes < 0:
            erreurs.append(f"{code} : « episodes » = {episodes} négatif")

    med = info.get("median_pct")
    if med is not None and not _est_nombre(med):
        erreurs.append(f"{code} : « median_pct » doit être un nombre, trouvé {med!r}")

    # La borne basse d'un intervalle de Wilson est TOUJOURS ≤ la probabilité estimée.
    bas, prob = info.get("borne_basse"), info.get("down_prob")
    if _est_entier(bas) and _est_entier(prob) and bas > prob:
        erreurs.append(f"{code} : « borne_basse » ({bas}) dépasse « down_prob » ({prob}) — "
                       f"impossible pour un intervalle de Wilson : la donnée a été fabriquée "
                       f"ou corrompue")

    sig = info.get("significatif")
    if sig is not None and not isinstance(sig, bool):
        erreurs.append(f"{code} : « significatif » doit être un booléen, trouvé {sig!r}")


def _valider_coherence(code: str, info: dict, erreurs: list[str],
                       avertissements: list[str]) -> None:
    """Le mode doit correspondre aux statistiques — quand les deux sont renseignés."""
    mode, sig = info.get("mode"), info.get("significatif")
    bas, n = info.get("borne_basse"), info.get("episodes")
    if mode is None or sig is None:
        return                     # seuil historique incomplet : rien à confronter
    if mode == MODE_DECLENCHEUR:
        if sig is not True:
            erreurs.append(f"{code} : mode « {MODE_DECLENCHEUR} » avec « significatif » "
                           f"{sig!r} — un déclencheur de vente exige un test concluant")
        elif _est_entier(bas) and _est_entier(n):
            from ..regles import BORNE_BASSE_MIN, EPISODES_MIN
            # ⚠ UNITÉ : `BORNE_BASSE_MIN` est une FRACTION (0.50) — `borne_basse` dans le
            # fichier est un POURCENTAGE (49, 86…). Comparer les deux directement ne
            # déclencherait jamais : le contrôle serait décoratif. D'où la conversion.
            borne_min_pct = round(BORNE_BASSE_MIN * 100)
            if bas < borne_min_pct or n < EPISODES_MIN:
                erreurs.append(f"{code} : mode « {MODE_DECLENCHEUR} » alors que les mesures "
                               f"ne passent pas le test (borne basse {bas} < {borne_min_pct} "
                               f"ou épisodes {n} < {EPISODES_MIN})")
    elif mode == MODE_INFORMATIF and sig is True:
        avertissements.append(
            f"{code} : « significatif » est vrai mais le mode reste « {MODE_INFORMATIF} » — "
            f"rétrogradation volontaire conservée (invariant B3)")


def valider_entree(code, info, *, complet: bool = False) -> tuple[list[str], list[str]]:
    """Contrôle une entrée. Retourne (erreurs, avertissements).

    `complet=True` applique le contrat d'ÉCRITURE (tous les champs obligatoires) ;
    `complet=False` (défaut) applique celui de LECTURE : les champs de mesure sont facultatifs.
    """
    if not isinstance(info, dict):
        return ([f"{code!r} : l'entrée doit être un objet JSON, trouvé "
                 f"{type(info).__name__}"], [])
    erreurs: list[str] = []
    avertissements: list[str] = []
    _valider_identite(code, info, erreurs, complet)
    _valider_presence(str(code), info, erreurs, complet)
    _valider_decision(str(code), info, erreurs)
    _valider_mesures(str(code), info, erreurs)
    _valider_coherence(str(code), info, erreurs, avertissements)
    return erreurs, avertissements


def valider(donnees, *, complet: bool = False) -> tuple[list[str], list[str]]:
    """Contrôle le fichier entier. Retourne (erreurs, avertissements)."""
    if not isinstance(donnees, dict):
        return ([f"la racine doit être un objet JSON {{code: entrée}}, trouvé "
                 f"{type(donnees).__name__}"], [])
    erreurs: list[str] = []
    avertissements: list[str] = []
    for code, info in donnees.items():
        e, a = valider_entree(code, info, complet=complet)
        erreurs += e
        avertissements += a
    return erreurs, avertissements


def lire_et_valider(chemin: Path) -> dict:
    """Lit le fichier et le valide — lève `SeuilsInvalides` si son contenu est inexploitable.

    Contrat de LECTURE (tolérant aux seuils historiques). Un fichier **absent** n'est pas une
    erreur : aucun seuil calibré, la table de départ s'applique. Un fichier **présent mais
    illisible** en est une : c'est précisément le cas qui transformait le système en « aucun
    seuil » sans le dire.
    """
    if not chemin.exists():
        return {}
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError as exc:
        raise SeuilsInvalides(f"{chemin} : illisible ({exc})") from exc
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise SeuilsInvalides(
            f"{chemin} : JSON invalide ligne {exc.lineno} ({exc.msg}) — le fichier est "
            f"tronqué ou corrompu. Aucun seuil n'a été appliqué.") from exc
    erreurs, _ = valider(donnees)
    if erreurs:
        detail = "\n  - ".join(erreurs)
        raise SeuilsInvalides(f"{chemin} : {len(erreurs)} entrée(s) non conforme(s) :\n  - {detail}")
    return donnees


def refus_ecriture(avant: dict, apres: dict) -> list[str]:
    """Ce qu'une écriture ferait perdre — liste vide si elle est permise.

    Permis à une écriture automatique : **ajouter** un titre non calibré, **rafraîchir** des
    mesures. Interdit : changer `threshold` ou `mode` d'une entrée protégée, **supprimer** une
    entrée protégée, ou **créer** un `declencheur` (une vente ne s'active pas toute seule).
    """
    refus: list[str] = []
    for code, ancien in avant.items():
        if not est_protege(ancien):
            continue
        if code not in apres:
            refus.append(f"{code} : suppression d'un réglage protégé")
            continue
        nouveau = apres[code] or {}
        for champ in CHAMPS_DECISION:
            if ancien.get(champ) != nouveau.get(champ):
                refus.append(f"{code} : « {champ} » {ancien.get(champ)!r} -> "
                             f"{nouveau.get(champ)!r} sur un réglage protégé")
    for code, nouveau in apres.items():
        if code in avant or not isinstance(nouveau, dict):
            continue
        if nouveau.get("mode") == MODE_DECLENCHEUR:
            refus.append(f"{code} : création automatique d'un « {MODE_DECLENCHEUR} » — "
                         f"activer une vente demande une autorisation explicite")
    return refus


def ecrire_atomique(chemin: Path, donnees: dict) -> None:
    """Écrit via un fichier temporaire puis remplace : jamais de fichier à moitié écrit.

    `os.replace` est atomique sur un même volume : une coupure laisse soit l'ancien fichier
    intact, soit le nouveau complet — l'état intermédiaire qui faisait perdre les seuils
    n'existe plus.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaire, chemin)
