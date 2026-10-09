"""Tests du suivi des annonces BRVM (parse, mapping, détection de nouveautés)."""
from src.analyse.news import (
    detect_new,
    fetch_announcements,
    filter_codes,
    match_code,
    parse_date,
    parse_society,
)


# --------------------------------------------------------------- parse
def test_parse_date():
    assert parse_date("20260806_-_avis_-_societe_generale_ci.pdf") == "2026-08-06"
    assert parse_date("fiche_de_notation_-_oragroup_sa_-_2025.pdf") is None


def test_parse_society():
    assert parse_society("20260806_-_avis_ndeg231_-_societe_generale_ci.pdf") == "societe_generale_ci"
    assert parse_society("20260724_-_communique_-_sonatel_sn_0.pdf") == "sonatel_sn"
    assert parse_society("20260722_-_avis_-_sogb_ci.pdf") == "sogb_ci"


# -------------------------------------------------------------- mapping
def test_match_code_noyau():
    assert match_code("societe_generale_ci") == "SGBC"
    assert match_code("sonatel_sn") == "SNTS"
    assert match_code("sogb_ci") == "SOGC"
    assert match_code("solibra_ci") == "SLBC"
    assert match_code("palmci") == "PALC"
    assert match_code("boa_sn") == "BOAS"


def test_match_code_inconnu():
    assert match_code("nestle_ci") is None
    assert match_code("filtisac_ci") is None


# ------------------------------------------------------------- filtrage
def test_filter_codes():
    anns = [
        {"code": "SGBC", "date": "2026-08-06"},
        {"code": "SNTS", "date": "2026-07-24"},
        {"code": None, "date": "2026-07-07"},
        {"code": "NTLC", "date": "2026-07-30"},
    ]
    out = filter_codes(anns, ["SGBC", "SNTS", "SOGC", "SLBC", "PALC", "BOAS"])
    assert {a["code"] for a in out} == {"SGBC", "SNTS"}


# ------------------------------------------------------ détection nouveautés
def test_detect_new_first_run_all_new(monkeypatch, tmp_path):
    monkeypatch.setattr("src.analyse.news.STATE_FILE", tmp_path / "news.json")
    anns = [
        {"code": "SGBC", "url": "https://x/sg.pdf", "date": "2026-08-06"},
        {"code": "SNTS", "url": "https://x/sn.pdf", "date": "2026-07-24"},
        {"code": "NTLC", "url": "https://x/nt.pdf", "date": "2026-07-30"},
    ]
    new = detect_new(anns, ["SGBC", "SNTS"])
    assert len(new) == 2  # seulement les 2 du noyau


def test_detect_new_second_run_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr("src.analyse.news.STATE_FILE", tmp_path / "news.json")
    anns = [
        {"code": "SGBC", "url": "https://x/sg.pdf", "date": "2026-08-06"},
        {"code": "SNTS", "url": "https://x/sn.pdf", "date": "2026-07-24"},
    ]
    codes = ["SGBC", "SNTS"]
    assert len(detect_new(anns, codes)) == 2  # premier run
    assert len(detect_new(anns, codes)) == 0  # rien de nouveau


def test_fetch_announcements_parses_real_shape(monkeypatch):
    """fetch_announcements parse correctement la forme réelle des PDF brvm.org."""
    class FakeResp:
        text = (
            '<a href="/sites/default/files/20260806_-_avis_ndeg231_brvmdg_-_'
            'paiement_de_dividendes_exercice_2025_-_societe_generale_ci.pdf">x</a>'
            '<a href="/sites/default/files/20260724_-_communique_de_presse_-_sonatel_sn.pdf">x</a>'
            '<a href="/sites/default/files/20260722_-_avis_-_sogb_ci.pdf">x</a>'
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr("src.analyse.news.requests.get", lambda *a, **k: FakeResp())
    monkeypatch.setattr(
        "src.analyse.news.BRVM_ANNOUNCE_PAGES", {"dividendes": "https://fake/div"}
    )
    anns = fetch_announcements()
    codes = {a["code"] for a in anns}
    assert codes == {"SGBC", "SNTS", "SOGC"}
