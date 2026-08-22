"""OCR léger du relevé — rendu 2x, page par page (18/08/2026)."""
import pymupdf
from rapidocr_onnxruntime import RapidOCR

eng = RapidOCR()
doc = pymupdf.open(r"C:\Users\LEO\Downloads\releves.pdf")
print(f"pages: {len(doc)}")
parts = []
for i, page in enumerate(doc):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
    img = f"data/avis/releves_p{i}.png"
    pix.save(img)
    res, _ = eng(img)
    txt = "\n".join(r[1] for r in res) if res else "(vide)"
    parts.append(f"--- PAGE {i+1} ---\n{txt}")
    print(f"page {i+1}/{len(doc)} OCR ok ({len(txt)} chars)")
text = "\n".join(parts)
with open("data/avis/releves.txt", "w", encoding="utf-8") as f:
    f.write(text)
print(f"\n{'='*90}\n{text[:3200]}")
