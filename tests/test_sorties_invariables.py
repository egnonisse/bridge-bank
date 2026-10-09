"""Vérifie que les SORTIES du noyau dividende n'ont pas changé.

LE FILET DU DÉCOUPAGE (lot 5). Les constantes disent que les RÉGLAGES n'ont pas bougé ; les 333
tests disent que les chemins de code connus fonctionnent. Ce test-ci dit la troisième chose, celle
qu'aucun des deux ne voit : **ce qui SORT est identique, au caractère près** — messages d'alerte,
niveaux, lignes d'historique, textes de renforcement.

Quand il échoue, la sortie de `scripts/capturer_sorties.py` montre exactement quelle phrase a
changé. C'est ce qu'on veut d'un découpage : un diff, pas une impression.

Régénérer la référence (uniquement si le changement est VOULU et relu) :
    python scripts/capturer_sorties.py
"""
from __future__ import annotations

import json

import pytest

from scripts.capturer_sorties import SORTIE, capturer, normaliser


@pytest.fixture(scope="module")
def reference() -> dict:
    if not SORTIE.exists():
        pytest.skip(f"référence absente : {SORTIE} (lancer scripts/capturer_sorties.py)")
    return json.loads(SORTIE.read_text(encoding="utf-8"))


def test_la_reference_existe_et_est_utilisee(reference):
    assert len(reference) > 100, "référence suspicieusement petite — capture incomplète ?"


def test_les_sorties_sont_identiques(reference):
    """Comparaison champ par champ, avec le détail des écarts (jamais un simple « différent »)."""
    courant = normaliser(capturer())

    disparues = sorted(set(reference) - set(courant))
    apparues = sorted(set(courant) - set(reference))
    changees = {
        cle: {"avant": reference[cle], "apres": courant[cle]}
        for cle in sorted(set(reference) & set(courant))
        if reference[cle] != courant[cle]
    }

    detail = []
    for cle in disparues[:5]:
        detail.append(f"  DISPARUE  {cle}")
    for cle in apparues[:5]:
        detail.append(f"  APPARUE   {cle}")
    for cle, v in list(changees.items())[:5]:
        detail.append(f"  CHANGÉE   {cle}\n    avant : {str(v['avant'])[:200]}\n    après : {str(v['apres'])[:200]}")

    assert not (disparues or apparues or changees), (
        f"{len(disparues)} sortie(s) disparue(s), {len(apparues)} apparue(s), "
        f"{len(changees)} modifiée(s) :\n" + "\n".join(detail)
    )


def test_le_nombre_de_sorties_est_stable(reference):
    """Une capture qui perd la moitié de ses clés passerait le test d'égalité par vacuité."""
    assert set(reference) == set(normaliser(capturer()))
