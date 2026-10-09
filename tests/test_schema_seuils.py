"""Tests du schéma et de la protection de `data/profit_thresholds.json`.

CE QUI EST VÉRIFIÉ ICI — ET POURQUOI CE SONT DES TESTS NÉGATIFS
--------------------------------------------------------------
Les tests existants vérifient que le système fait ce qu'il doit. Ceux-ci vérifient qu'il
**REFUSE ce qu'il ne doit pas faire** — parce que le danger n'est pas qu'il tombe en panne,
c'est qu'il continue avec une décision fausse et silencieuse.

Trois familles :
  1. fichier illisible      — ne doit plus devenir « aucun seuil », utilisé sans le dire ;
  2. contenu non conforme   — clé manquante, type ou valeur invalide, champ inconnu ;
  3. écrasement protégé     — un recalcul ne doit pas toucher une décision en vigueur.

Dans TOUS les cas de refus, le fichier sur disque doit rester **octet pour octet identique** :
c'est la seule preuve qui compte (un refus qui écrit quand même n'est pas un refus).
"""
import json

import pytest

from src import seuils_vente as sv
from src import schema_seuils as schema
from src.schema_seuils import (MODE_DECLENCHEUR, MODE_INFORMATIF, SeuilProtege,
                               SeuilsInvalides, est_protege, refus_ecriture, valider)

CODES_HISTORIQUES = ("SNTS", "SGBC", "SLBC", "PALC")


def _entree(code: str = "SNTS", **remplacements) -> dict:
    """Entrée conforme, à déformer champ par champ dans chaque test."""
    base = {"code": code, "threshold": 0.13, "down_prob": 86, "borne_basse": 49,
            "episodes": 7, "median_pct": -1.8, "significatif": False,
            "mode": MODE_INFORMATIF}
    base.update(remplacements)
    return base


def _fichier(chemin, donnees):
    chemin.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    return chemin


def _octets(chemin) -> bytes:
    return chemin.read_bytes() if chemin.exists() else b""


def _refus_ecriture(chemin, donnees, journal, **kwargs) -> None:
    """Écrit en s'attendant à un refus, et vérifie que le fichier n'a PAS bougé."""
    avant = _octets(chemin)
    with pytest.raises(SeuilProtege):
        sv.enregistrer(donnees, chemin=chemin, journal=journal, **kwargs)
    assert _octets(chemin) == avant, "le fichier a été modifié malgré le refus"


# ══════════════════════════════════════════════════════════════════════════════
#  1. Fichier illisible : le silence était le vrai défaut
# ══════════════════════════════════════════════════════════════════════════════

def test_fichier_absent_nest_pas_une_erreur(tmp_path):
    """Aucun seuil calibré est un état NORMAL : la table de départ s'applique."""
    assert sv.charger(tmp_path / "absent.json") == {}


def test_json_corrompu_leve_une_erreur(tmp_path):
    """Avant, un JSON tronqué donnait `{}` : plus de seuil, tout en informatif, en silence."""
    fichier = tmp_path / "seuils.json"
    fichier.write_text('{"SNTS": {"threshold": 0.13,', encoding="utf-8")
    with pytest.raises(SeuilsInvalides) as exc:
        sv.charger(fichier)
    assert "JSON invalide" in str(exc.value)


def test_fichier_illisible_nest_jamais_un_dictionnaire_vide(tmp_path):
    """Le contrôle de fond : `{}` n'est plus une façon d'échouer silencieusement."""
    fichier = tmp_path / "seuils.json"
    fichier.write_text("pas du json du tout", encoding="utf-8")
    with pytest.raises(SeuilsInvalides):
        sv.charger(fichier)


def test_racine_non_objet_refusee(tmp_path):
    fichier = _fichier(tmp_path / "seuils.json", [{"code": "SNTS"}])
    with pytest.raises(SeuilsInvalides):
        sv.charger(fichier)


# ══════════════════════════════════════════════════════════════════════════════
#  2. Contenu non conforme : champs, types, valeurs, cohérence
# ══════════════════════════════════════════════════════════════════════════════

def test_champ_manquant_refuse():
    """`threshold` absent : le seuil EST la décision, il ne peut pas manquer."""
    erreurs, _ = valider({"SNTS": _entree(threshold=None)})
    assert any("threshold" in e and "manquant" in e for e in erreurs)


def test_unite_du_seuil_refusee():
    """`13` au lieu de `0.13` : la faute d'unité la plus probable, et la plus coûteuse."""
    erreurs, _ = valider({"SNTS": _entree(threshold=13)})
    assert any("0.13" in e for e in erreurs)


def test_seuil_negatif_ou_nul_refuse():
    assert valider({"SNTS": _entree(threshold=-0.05)})[0]
    assert valider({"SNTS": _entree(threshold=0)})[0]


def test_valeur_hors_bornes_refusee():
    """Une probabilité de 150 % n'existe pas — c'est une donnée corrompue, pas un cas limite."""
    erreurs, _ = valider({"SNTS": _entree(down_prob=150)})
    assert any("down_prob" in e and "150" in e for e in erreurs)


def test_episodes_negatifs_refuses():
    erreurs, _ = valider({"SNTS": _entree(episodes=-1)})
    assert any("episodes" in e for e in erreurs)


def test_types_invalides_refuses():
    """`"beaucoup"` d'épisodes, `"oui"` pour un booléen : le type fait partie du contrat."""
    erreurs, _ = valider({"SNTS": _entree(episodes="beaucoup", significatif="oui")})
    assert any("episodes" in e for e in erreurs)
    assert any("significatif" in e for e in erreurs)


def test_booleen_nest_pas_un_nombre():
    """`True` est un `int` en Python : sans garde-fou, il passerait pour un seuil valide."""
    erreurs, _ = valider({"SNTS": _entree(threshold=True)})
    assert erreurs


def test_champ_inconnu_refuse():
    """Une faute de frappe doit se voir : sinon le nouveau réglage reste inerte."""
    entree = _entree()
    entree["thresold"] = 0.20
    erreurs, _ = valider({"SNTS": entree})
    assert any("inconnu" in e and "thresold" in e for e in erreurs)


def test_code_incoherent_avec_la_cle_refuse():
    """Copier-coller d'une entrée sur une autre : le champ interne ne suit pas la clé."""
    erreurs, _ = valider({"SNTS": _entree(code="SGBC")})
    assert any("code" in e for e in erreurs)


def test_code_invalide_refuse():
    erreurs, _ = valider({"snts": _entree(code="snts")})
    assert any("code invalide" in e for e in erreurs)


def test_mode_inconnu_refuse():
    erreurs, _ = valider({"SNTS": _entree(mode="peut-etre")})
    assert any("mode" in e for e in erreurs)


def test_a_ecriture_un_seuil_incomplet_est_refuse():
    """Contrat d'ÉCRITURE : le système n'écrit que des entrées complètes.

    `mode` absent est toléré à la LECTURE (seuil historique) mais jamais produit à l'écriture —
    sinon la complétude de demain dépendrait de ce qui traînait hier.
    """
    erreurs, _ = valider({"SNTS": _entree(mode=None)}, complet=True)
    assert any("mode" in e and "manquant" in e for e in erreurs)

    erreurs, _ = valider({"SNTS": {"threshold": 0.13}}, complet=True)
    manquants = {c for c in ("code", "down_prob", "borne_basse", "episodes", "significatif",
                             "mode") if any(c in e for e in erreurs)}
    assert manquants == {"code", "down_prob", "borne_basse", "episodes", "significatif", "mode"}


def test_a_lecture_un_seuil_historique_partiel_reste_lisible(tmp_path):
    """Un seuil calibré AVANT le mode n'a ni `mode` ni `borne_basse` : il doit rester lisible.

    C'est la tolérance qui protège l'existant : refuser de lire un seuil historique le
    supprimerait au lieu de le protéger. `mode_pour` sait le classer en `informatif`.
    """
    fichier = _fichier(tmp_path / "seuils.json",
                       {"SNTS": {"threshold": 0.13, "down_prob": 86, "episodes": 7}})
    donnees = sv.charger(fichier)                     # ne lève pas
    assert donnees["SNTS"]["threshold"] == 0.13
    assert sv.est_declencheur(donnees["SNTS"]) is False     # classé informatif, sans le dire


def test_a_lecture_un_mode_inconnu_reste_refuse(tmp_path):
    """Tolérer un champ ABSENT n'est pas tolérer une valeur INCONNUE : elle dégraderait en
    silence (un déclencheur deviendrait informatif, la vente disparaîtrait sans un mot)."""
    fichier = _fichier(tmp_path / "seuils.json",
                       {"SNTS": {"threshold": 0.13, "mode": "peut-etre",
                                 "down_prob": 86, "episodes": 7}})
    with pytest.raises(SeuilsInvalides):
        sv.charger(fichier)


def test_borne_basse_superieure_a_la_probabilite_signalee():
    """La borne basse de Wilson est TOUJOURS ≤ p : l'inverse trahit une donnée inventée."""
    erreurs, _ = valider({"SNTS": _entree(down_prob=40, borne_basse=70)})
    assert any("borne_basse" in e or "down_prob" in e for e in erreurs)


# ══════════════════════════════════════════════════════════════════════════════
#  3. Cohérence `significatif` / `mode`
# ══════════════════════════════════════════════════════════════════════════════

def test_declencheur_sans_preuve_statistique_refuse():
    """Un déclencheur de vente sans test concluant : c'est le défaut fondateur du 08/10."""
    erreurs, _ = valider({"SNTS": _entree(mode=MODE_DECLENCHEUR, significatif=False)})
    assert any(MODE_DECLENCHEUR in e and "significatif" in e for e in erreurs)


def test_declencheur_avec_mesures_trop_faibles_refuse():
    """Déclarer `significatif` ne suffit pas : les mesures doivent le confirmer."""
    entree = _entree("SGBC", mode=MODE_DECLENCHEUR, significatif=True, borne_basse=46,
                     episodes=30)
    erreurs, _ = valider({"SGBC": entree})
    assert any("ne passent pas le test" in e for e in erreurs)


def test_la_borne_minimale_est_comparee_dans_la_bonne_unite():
    """Piège d'unité : `BORNE_BASSE_MIN` vaut 0.50 (fraction), `borne_basse` 49 (pourcentage).

    Comparer les deux directement rendrait le contrôle DÉCORATIF — il ne refuserait jamais
    rien. Ce test échoue si quelqu'un « simplifie » la conversion.
    """
    from src.regles import BORNE_BASSE_MIN
    juste_sous = round(BORNE_BASSE_MIN * 100) - 1
    entree = _entree("SNTS", mode=MODE_DECLENCHEUR, significatif=True, borne_basse=juste_sous,
                     episodes=30)
    erreurs, _ = valider({"SNTS": entree})
    assert any("ne passent pas le test" in e for e in erreurs)

    juste_au_dessus = _entree("SNTS", mode=MODE_DECLENCHEUR, significatif=True,
                              borne_basse=round(BORNE_BASSE_MIN * 100), episodes=30)
    assert valider({"SNTS": juste_au_dessus})[0] == []


def test_declencheur_conforme_accepte():
    entree = _entree(mode=MODE_DECLENCHEUR, significatif=True, borne_basse=62, episodes=45)
    assert valider({"SNTS": entree}) == ([], [])


def test_informatif_avec_preuve_est_un_avertissement_pas_une_erreur():
    """Une rétrogradation VOLONTAIRE doit rester possible — mais jamais silencieuse."""
    erreurs, avertissements = valider({"SNTS": _entree(mode=MODE_INFORMATIF,
                                                        significatif=True,
                                                        borne_basse=62, episodes=45)})
    assert erreurs == []
    assert any("B3" in a for a in avertissements)


# ══════════════════════════════════════════════════════════════════════════════
#  4. Protection : ce qu'un recalcul automatique ne peut pas faire
# ══════════════════════════════════════════════════════════════════════════════

def test_un_declencheur_est_protege_sans_le_declarer():
    assert est_protege(_entree(mode=MODE_DECLENCHEUR, significatif=True,
                               borne_basse=62, episodes=45))
    assert not est_protege(_entree())


def test_protege_explicite_sur_un_informatif():
    assert est_protege(_entree(protege=True))


def test_ecrasement_automatique_dun_declencheur_refuse(tmp_path):
    """Le cœur de la demande : un recalcul ne change pas un seuil qui propose une vente."""
    fichier = tmp_path / "seuils.json"
    actuel = {"SNTS": _entree(mode=MODE_DECLENCHEUR, significatif=True,
                              borne_basse=62, episodes=45)}
    _fichier(fichier, actuel)
    modifie = {"SNTS": {**actuel["SNTS"], "threshold": 0.20}}
    _refus_ecriture(fichier, modifie, tmp_path / "journal.jsonl")


def test_ecrasement_automatique_dun_protege_explicite_refuse(tmp_path):
    fichier = tmp_path / "seuils.json"
    actuel = {"PALC": _entree("PALC", protege=True)}
    _fichier(fichier, actuel)
    modifie = {"PALC": {**actuel["PALC"], "threshold": 0.20}}
    _refus_ecriture(fichier, modifie, tmp_path / "journal.jsonl")


def test_suppression_dun_protege_refusee(tmp_path):
    """Retirer une décision du fichier, c'est l'effacer sans trace dans le code."""
    fichier = tmp_path / "seuils.json"
    _fichier(fichier, {"SNTS": _entree(protege=True)})
    _refus_ecriture(fichier, {}, tmp_path / "journal.jsonl")


def test_creation_automatique_dun_declencheur_refusee(tmp_path):
    """Une vente ne s'active pas toute seule : le mode déclencheur est une décision."""
    fichier = tmp_path / "seuils.json"
    _fichier(fichier, {"SNTS": _entree()})
    nouveau = {"SNTS": _entree(), "SNTS2": _entree("SNTS2", mode=MODE_DECLENCHEUR,
                                                  significatif=True, borne_basse=62,
                                                  episodes=45)}
    _refus_ecriture(fichier, nouveau, tmp_path / "journal.jsonl")


def test_rafraichir_les_mesures_dun_protege_est_permis(tmp_path):
    """Une MESURE se remesure : c'est le travail de `rafraichir_stats_seuils.py`."""
    fichier = tmp_path / "seuils.json"
    actuel = {"SNTS": _entree(protege=True)}
    _fichier(fichier, actuel)
    remesure = {"SNTS": {**actuel["SNTS"], "down_prob": 54, "borne_basse": 39, "episodes": 41}}
    sv.enregistrer(remesure, chemin=fichier, journal=tmp_path / "journal.jsonl")
    apres = sv.charger(fichier)
    assert apres["SNTS"]["down_prob"] == 54
    assert apres["SNTS"]["threshold"] == actuel["SNTS"]["threshold"]   # décision intacte


def test_ajouter_un_titre_non_calibre_est_permis(tmp_path):
    """Calibrer un titre qui n'en avait pas : c'est le travail de la calibration automatique."""
    fichier = tmp_path / "seuils.json"
    _fichier(fichier, {"SNTS": _entree()})
    donnees = {"SNTS": _entree(), "ONCP": _entree("ONCP")}
    sv.enregistrer(donnees, chemin=fichier, journal=tmp_path / "journal.jsonl")
    assert "ONCP" in sv.charger(fichier)


def test_autorisation_explicite_autorise_lecrasement(tmp_path):
    """Le geste manuel, et lui seul, peut réécrire une décision protégée."""
    fichier = tmp_path / "seuils.json"
    actuel = {"SNTS": _entree(protege=True)}
    _fichier(fichier, actuel)
    nouveau = {"SNTS": {**actuel["SNTS"], "threshold": 0.20}}
    sv.enregistrer(nouveau, chemin=fichier, journal=tmp_path / "journal.jsonl",
                   autorise_protege=True, origine=sv.ORIGINE_MANUELLE)
    assert sv.charger(fichier)["SNTS"]["threshold"] == 0.20


def test_ecriture_refusee_si_le_fichier_actuel_est_corrompu(tmp_path):
    """On ne détruit pas un fichier qu'on n'arrive pas à relire — on s'arrête."""
    fichier = tmp_path / "seuils.json"
    fichier.write_text('{"SNTS": {"threshold"', encoding="utf-8")
    before = _octets(fichier)
    with pytest.raises(SeuilsInvalides):
        sv.enregistrer({"SNTS": _entree()}, chemin=fichier)
    assert _octets(fichier) == before


def test_une_seule_entree_invalide_bloque_toute_leciture(tmp_path):
    """L'écriture est refusée EN BLOC : jamais un fichier à moitié mis à jour."""
    fichier = tmp_path / "seuils.json"
    _fichier(fichier, {"SNTS": _entree()})
    before = _octets(fichier)
    donnees = {"SNTS": _entree(), "SLBC": _entree("SLBC", threshold=13)}
    with pytest.raises(SeuilsInvalides):
        sv.enregistrer(donnees, chemin=fichier)
    assert _octets(fichier) == before


def test_le_refus_est_journalise(tmp_path):
    """Un refus silencieux serait aussi grave que l'écrasement qu'il évite."""
    fichier = tmp_path / "seuils.json"
    journal = tmp_path / "journal.jsonl"
    _fichier(fichier, {"SNTS": _entree(protege=True)})
    _refus_ecriture(fichier, {"SNTS": _entree(protege=True, threshold=0.20)}, journal)

    entrees = sv.lire_journal(chemin=journal)
    assert len(entrees) == 1
    entree = entrees[0]
    assert entree["titre"] == "SNTS"
    assert entree["origine"] == sv.ORIGINE_AUTO
    assert sv.MOTIF_REFUS in entree["motif"]
    assert "threshold" in entree["motif"]
    assert entree["avant"] == entree["apres"] == 0.13      # rien n'a bougé, c'est le point


def test_le_refus_ecrit_le_journal_sans_toucher_aux_seuils(tmp_path):
    """Le journal est append-only : un refus s'ajoute, il ne réécrit rien."""
    fichier = tmp_path / "seuils.json"
    journal = tmp_path / "journal.jsonl"
    _fichier(fichier, {"SNTS": _entree(protege=True)})
    seuils_avant = _octets(fichier)
    journal_avant = _octets(journal)
    _refus_ecriture(fichier, {"SNTS": _entree(protege=True, threshold=0.20)}, journal)
    assert _octets(fichier) == seuils_avant
    assert _octets(journal).startswith(journal_avant)      # ajout, jamais réécriture


def test_refus_ecriture_ne_signale_rien_quand_tout_est_permis():
    avant = {"SNTS": _entree()}
    assert refus_ecriture(avant, {"SNTS": _entree(), "ONCP": _entree("ONCP")}) == []


# ══════════════════════════════════════════════════════════════════════════════
#  5. Non-régression sur le fichier réel et sur l'API publique
# ══════════════════════════════════════════════════════════════════════════════

def test_le_fichier_reel_est_conforme():
    """Le fichier de production doit passer le schéma — sinon la validation est inapplicable."""
    donnees = sv.charger()
    erreurs, _ = valider(donnees)
    assert erreurs == []
    assert donnees, "le fichier de seuils ne doit pas être vide"
    assert set(CODES_HISTORIQUES) <= set(donnees)


def test_le_vocabulaire_du_mode_nest_defini_quune_fois():
    """`schema_seuils` est la source ; `seuils_vente` la réexporte sans la redéfinir."""
    assert sv.MODE_DECLENCHEUR == schema.MODE_DECLENCHEUR == MODE_DECLENCHEUR
    assert sv.MODE_INFORMATIF == schema.MODE_INFORMATIF == MODE_INFORMATIF
    assert sv.MODE_DECLENCHEUR != sv.MODE_INFORMATIF


def test_les_appelants_historiques_continuent_de_fonctionner():
    """`portfolio.py` alias les fonctions de `seuils_vente` : la signature doit tenir."""
    from src.portfolio import load_profit_thresholds, save_profit_thresholds
    assert load_profit_thresholds is sv.charger
    assert save_profit_thresholds is sv.enregistrer
    assert set(sv.charger()) == set(load_profit_thresholds())


def test_les_exceptions_sont_accessibles_des_deux_cotes():
    assert sv.SeuilsInvalides is SeuilsInvalides
    assert sv.SeuilProtege is SeuilProtege
