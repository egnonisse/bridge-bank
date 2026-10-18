"""Télécharge et parse les avis BRVM / SikaFinance partagés par LEO (18/08/2026)."""
import os
import sys
from pathlib import Path

import requests
import pymupdf

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.infrastructure.paths import chemin_data  # noqa: E402  (B2-09)

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

PDFS = {
    "mali_620_2022-2032": "https://www.brvm.org/sites/default/files/20260810_-_avis_ndeg234_brvmdg_-_pmt_int._annuels_et_remb_cap_-_etat_du_mali_620_2022-2032.pdf",
    "tpci_590_2024-2029": "https://www.brvm.org/sites/default/files/20250810_-_avis_ndeg233_-_pmt_int._annuels_-_tpci_590_2024-2029.pdf",
    "nourmony_725_notation": "https://www.brvm.org/sites/default/files/20260813_-_notation_financiere_-_nourmony_holding_sa_725_2024-2029.pdf",
    "tpci_o77_taux": "https://www.brvm.org/sites/default/files/20260813_-_avis_ndeg242_brvmdg_-_fixation_du_taux_dinteret_trimestriel_tpci.o77.pdf",
    "tpbf_630_2022-2034": "https://www.brvm.org/sites/default/files/20260813_-_avis_ndeg239_brvmdg_-_pmt_int._semestriels_-_tpbf_630_2022-2034_tpbf.o14.pdf",
    "totalenergies_div_2025": "https://www.brvm.org/sites/default/files/20260814_-_avis_ndeg245_brvmdg_-_paiement_de_dividendes_exo_2025_-_totalenergies_marketing_ci.pdf",
    "servair_div_2025": "https://www.sikafinance.com/docs/servair-abidjan-ci-servair-abidjan-cote-d%C2%B7ivoire--paiement-de-dividendes--exercice-2025.pdf",
}

os.makedirs(chemin_data("avis"), exist_ok=True)

for name, url in PDFS.items():
    try:
        r = requests.get(url, headers=UA, timeout=90)
        r.raise_for_status()
        path = str(chemin_data(f"avis/{name}.pdf"))
        with open(path, "wb") as f:
            f.write(r.content)
        doc = pymupdf.open(path)
        text = "\n".join(page.get_text() for page in doc).strip()
        with open(chemin_data(f"avis/{name}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\n{'=' * 90}\n### {name}  ({len(text)} chars)\n{'-' * 90}")
        print(text[:1800])
    except Exception as e:  # noqa: BLE001
        print(f"\n### {name} -> ERREUR: {type(e).__name__}: {e}")
