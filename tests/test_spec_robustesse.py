"""Tests de robustesse de la détection — données dégradées.

Ces tests viennent d'une alerte d'audit : `detect_schemas` levait un ZeroDivisionError
quand une clôture valait 0 dans la fenêtre des 60 séances (donnée manquante, titre
suspendu). Comme cette fonction est appelée par la calibration ET par la production,
le plantage aurait fait tomber les alertes du matin — pas seulement un script d'audit.
"""
import pytest

from src.strategie.spec_profiles import detect_schemas, index_fin_horizon, fenetre_complete


class TestClotureNulle:
    """Une clôture à 0 ne doit jamais faire tomber la détection."""

    def test_zero_dans_la_fenetre_des_60_ne_plante_pas(self):
        # Reproduit le bug : creux60 = 0 -> division par zéro sur closes[i] / creux60.
        serie = [100.0] * 250 + [100.0] * 58 + [0.0, 100.0, 105.0]
        resultat = detect_schemas(serie)          # ne doit pas lever
        assert isinstance(resultat, list)

    def test_zero_dans_la_fenetre_ne_cree_pas_de_faux_eveil(self):
        """Un creux nul ne peut pas servir de référence : on ne mesure pas un rebond
        depuis zéro. EVEIL doit rester éteint."""
        serie = [100.0] * 250 + [100.0] * 58 + [0.0, 100.0, 105.0]
        assert "EVEIL" not in detect_schemas(serie)

    def test_titre_suspendu_ne_declenche_rien(self):
        """Un titre dont les 70 dernières clôtures sont à 0 n'a aucun signal."""
        serie = [100.0] * 250 + [0.0] * 70
        assert detect_schemas(serie) == []

    def test_zero_ancien_hors_fenetre_est_inoffensif(self):
        """Un 0 plus vieux que la fenêtre des 60 séances ne doit pas gêner."""
        serie = [100.0] * 250 + [0.0] + [100.0] * 60
        assert isinstance(detect_schemas(serie), list)

    def test_serie_normale_non_regressee(self):
        """Garde-fou inverse : le correctif ne doit pas éteindre une détection réelle."""
        serie = [100.0] * 260 + [115.0]
        schemas = detect_schemas(serie)
        assert "CASSURE" in schemas and "EVEIL" in schemas


class TestHorizonCalendaire:
    """index_fin_horizon / fenetre_complete : la machinerie de l'horizon de 365 jours."""

    @staticmethod
    def _dates(n, pas=1):
        import datetime
        return [datetime.date(2020, 1, 1) + datetime.timedelta(days=pas * k) for k in range(n)]

    def test_fenetre_vide_renvoie_i_et_est_declaree_incomplete(self):
        """Sans séance dans l'année qui suit, l'index vaut i et la fenêtre est vide :
        c'est cette garde qui manquait et faisait lever max() sur une séquence vide.
        Il faut des séances espacées de PLUS d'un an pour obtenir une fenêtre vide —
        des séances tous les 3 jours en contiennent une centaine dans l'année."""
        dates = self._dates(10, pas=400)         # une séance par an environ
        i = 0
        j = index_fin_horizon(dates, i)
        assert j == i
        assert fenetre_complete(dates, i, j) is False

    def test_fenetre_normale_est_complete(self):
        dates = self._dates(600, pas=1)          # une séance par jour
        j = index_fin_horizon(dates, 0)
        assert j > 0
        assert fenetre_complete(dates, 0, j) is True

    def test_horizon_couvre_bien_365_jours(self):
        dates = self._dates(800, pas=1)
        i = 100
        j = index_fin_horizon(dates, i)
        ecart = (dates[j] - dates[i]).days
        assert 364 <= ecart <= 365               # jamais au-delà de la limite
