"""OCR du relevé + vérif BOC 18/08 (18/08/2026)."""
import os
import sys
from pathlib import Path

import requests
import pymupdf

from rapidocr_onnxruntime import RapidOCR

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.infrastructure.paths import chemin_data  # noqa: E402  (B2-09)

os.makedirs(chemin_data("avis"), exist_ok=True)

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
eng = RapidOCR()

# --- OCR releves.pdf ---
try:
    doc = pymupdf.open(r"C:\Users\LEO\Downloads\releves.pdf")
    full = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3))
        img = str(chemin_data(f"avis/releves_p{i}.png"))
        pix.save(img)
        res, _ = eng(img)
        txt = "\n".join(r[1] for r in res) if res else ""
        full.append(f"--- PAGE {i + 1} ---\n{txt}")
    text = "\n".join(full)
    with open(chemin_data("avis/releves.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"### releves  ({len(text)} chars)\n{'-' * 90}\n{text[:3000]}")
except Exception as e:  # noqa: BLE001
    print(f"### releves -> ERREUR: {type(e).__name__}: {e}")

# --- BOC 18/08 (brvm officiel + NSIA) ---
for name, url in {
    "boc_2026-08-18_brvm": "https://www.brvm.org/sites/default/files/boc_20260818_2.pdf",
    "boc_18-aout_nsia": "https://nsiacapital.com/wp-content/uploads/2026/08/BOC-DU-18-AOUT.pdf",
}.items():
    try:
        r = requests.get(url, headers=UA, timeout=60)
        print(f"\n### {name}: HTTP {r.status_code} ({len(r.content)} bytes)")
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            with open(chemin_data(f"{name}.pdf"), "wb") as f:
                f.write(r.content)
            print(f"  -> sauvegardé {chemin_data(f'{name}.pdf')}")
    except Exception as e:  # noqa: BLE001
        print(f"\n### {name}: {type(e).__name__}: {e}")
