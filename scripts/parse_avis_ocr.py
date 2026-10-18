"""OCR des avis BRVM scannés + retry sikafinance + richbourse (18/08/2026)."""
import os
import re
import sys
from pathlib import Path

import requests
import pymupdf

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.infrastructure.paths import chemin_data  # noqa: E402  (B2-09)

os.makedirs(chemin_data("avis"), exist_ok=True)

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

# --- OCR engine ---
try:
    from rapidocr_onnxruntime import RapidOCR
    _eng = RapidOCR()
    def ocr(img):
        res, _ = _eng(img)
        return "\n".join(r[1] for r in res) if res else ""
except ImportError:
    from rapidocr import RapidOCR
    _eng = RapidOCR()
    def ocr(img):
        res = _eng(img)
        return "\n".join(res.txts) if res else ""

SCANS = ["mali_620_2022-2032", "tpci_590_2024-2029", "tpci_o77_taux",
         "tpbf_630_2022-2034", "totalenergies_div_2025"]

for name in SCANS:
    try:
        pdf = str(chemin_data(f"avis/{name}.pdf"))
        doc = pymupdf.open(pdf)
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(3, 3))
        img = str(chemin_data(f"avis/{name}.png"))
        pix.save(img)
        text = ocr(img)
        with open(chemin_data(f"avis/{name}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\n{'=' * 90}\n### {name}  ({len(text)} chars)\n{'-' * 90}\n{text}")
    except Exception as e:  # noqa: BLE001
        print(f"\n### {name} -> ERREUR: {type(e).__name__}: {e}")

# --- sikafinance (retry verify=False) ---
try:
    url = ("https://www.sikafinance.com/docs/servair-abidjan-ci-servair-abidjan-"
           "cote-d%C2%B7ivoire--paiement-de-dividendes--exercice-2025.pdf")
    r = requests.get(url, headers=UA, timeout=90, verify=False)
    r.raise_for_status()
    with open(chemin_data("avis/servair_div_2025.pdf"), "wb") as f:
        f.write(r.content)
    doc = pymupdf.open(str(chemin_data("avis/servair_div_2025.pdf")))
    text = "\n".join(p.get_text() for p in doc).strip()
    if not text:  # scan -> OCR
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(3, 3))
        pix.save(str(chemin_data("avis/servair_div_2025.png")))
        text = ocr(str(chemin_data("avis/servair_div_2025.png")))
    with open(chemin_data("avis/servair_div_2025.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n{'=' * 90}\n### servair_div_2025  ({len(text)} chars)\n{'-' * 90}\n{text[:1800]}")
except Exception as e:  # noqa: BLE001
    print(f"\n### servair_div_2025 -> ERREUR: {type(e).__name__}: {e}")

# --- richbourse (SAFCA admission) ---
try:
    url = ("https://www.richbourse.com/common/actualite/afficher-fichier/"
           "11-08-2026-safca-ci-admission-a-la-cote-des-actions-nouvelles")
    r = requests.get(url, headers=UA, timeout=90, verify=False)
    r.raise_for_status()
    ct = r.headers.get("Content-Type", "")
    print(f"\n### richbourse content-type: {ct}, {len(r.content)} bytes")
    if "pdf" in ct.lower() or r.content[:4] == b"%PDF":
        with open(chemin_data("avis/safca_admission.pdf"), "wb") as f:
            f.write(r.content)
        doc = pymupdf.open(str(chemin_data("avis/safca_admission.pdf")))
        text = "\n".join(p.get_text() for p in doc).strip()
    else:
        html = r.text
        # strip scripts/styles puis tags
        html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
        html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
    with open(chemin_data("avis/safca_admission.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n### safca_admission  ({len(text)} chars)\n{'-' * 90}\n{text[:2500]}")
except Exception as e:  # noqa: BLE001
    print(f"\n### safca_admission -> ERREUR: {type(e).__name__}: {e}")
