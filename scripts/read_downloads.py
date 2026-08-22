"""Lit les documents BSTrade pertinents trouvés dans Downloads (18/08/2026)."""
import pymupdf

FILES = [
    ("Tarification", r"C:\Users\LEO\Downloads\Tarification.pdf"),
    ("Manuel_BSTrade", r"C:\Users\LEO\Downloads\Manuel d'utilisation BSTrade V1.0.pdf"),
    ("Services_WCA", r"C:\Users\LEO\Downloads\Presentation_Services_WCA.pdf"),
    ("releves", r"C:\Users\LEO\Downloads\releves.pdf"),
]

for name, path in FILES:
    try:
        doc = pymupdf.open(path)
        text = "\n".join(p.get_text() for p in doc).strip()
        n_pages = len(doc)
        print(f"\n{'=' * 90}\n### {name}  ({n_pages} pages, {len(text)} chars)\n{'-' * 90}")
        print(text[:2200])
    except Exception as e:  # noqa: BLE001
        print(f"\n### {name} -> ERREUR: {type(e).__name__}: {e}")
