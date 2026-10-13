"""P7-03 : le cache historique porte son empreinte — lecture vérifiée, écriture atomique.

`history_clean.pkl` alimente le régime de marché et le challenge : un cache modifié
hors du pipeline (corruption, remplacement, édition manuelle) produirait des décisions
sur des données fausses. Le sidecar `.sha256` rend la détection automatique ; le
sidecar ABSENT reste toléré (ancien cache — le pipeline le créera au prochain passage).
"""
import pickle

import pytest

from src.collecte.history_io import (
    CacheHistoriqueAltere,
    charger_cache,
    ecrire_cache,
    lire_sha,
    sha_fichier,
)


def test_ecrire_puis_charger(tmp_path):
    c = tmp_path / "cache.pkl"
    donnees = {"SNTS": [1, 2, 3], "PALC": [4]}
    sha = ecrire_cache(c, donnees)

    assert c.exists() and sha == sha_fichier(c)
    assert lire_sha(c) == sha
    assert charger_cache(c) == donnees


def test_ecriture_sans_residu_tmp(tmp_path):
    c = tmp_path / "cache.pkl"
    ecrire_cache(c, {"A": [1]})
    assert not (tmp_path / "cache.pkl.tmp").exists()
    assert not (tmp_path / "cache.pkl.sha256.tmp").exists()


def test_cache_modifie_est_bruyant(tmp_path):
    """Un octet change → le chargement échoue, il ne renvoie pas des données douteuses."""
    c = tmp_path / "cache.pkl"
    ecrire_cache(c, {"A": [1]})
    c.write_bytes(b"corrompu hors pipeline")

    with pytest.raises(CacheHistoriqueAltere, match="empreinte"):
        charger_cache(c)


def test_sans_sidecar_le_chargement_reste_possible(tmp_path):
    """Compatibilité : un cache écrit AVANT l'introduction du sidecar reste lisible."""
    c = tmp_path / "cache.pkl"
    with open(c, "wb") as fh:
        pickle.dump({"A": [1]}, fh)
    assert lire_sha(c) is None
    assert charger_cache(c) == {"A": [1]}
