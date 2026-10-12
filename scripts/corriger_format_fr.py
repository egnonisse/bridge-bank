"""Correction C1/B1-02 — format français des montants (invariant E1), passe élargie.

Transforme les f-strings `{expr:,.0f}` / `{expr:+,.0f}` / `{expr:>N,.0f}` / `{expr:,}`
en appels `fcfa()` / `nombre()` du helper `src/portefeuille/format_fr.py`.

Usage :
    python scripts/corriger_format_fr.py            # dry-run : liste, ne modifie RIEN
    python scripts/corriger_format_fr.py --appliquer
"""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# (fichier, import relatif à ajouter si absent)
FICHIERS = {
    "src/main.py": "from .portefeuille.format_fr import fcfa, nombre",
    "src/report.py": "from .portefeuille.format_fr import fcfa, nombre",
    "src/strategie/speculation.py": "from ..portefeuille.format_fr import fcfa, nombre",
    "src/strategie/noyau_check.py": "from ..portefeuille.format_fr import fcfa, nombre",
    "src/collecte/cache_integrity.py": "from ..portefeuille.format_fr import fcfa, nombre",
}

# {expr:>8,.0f} — alignement à droite + milliers + décimales 0
RE_ALIGN = re.compile(r"\{([^{}:]+?):>(>?\d+),\.0f\}")
# {expr:+,.0f} — signe explicite
RE_SIGNE = re.compile(r"\{([^{}:]+?):(\+?),\.0f\}")
# {expr:,} — entier avec séparateurs (volumes, quantités)
RE_ENTIER = re.compile(r"\{([^{}:]+?):(>?\d*),\}")


def transformer(contenu: str) -> tuple[str, list[str]]:
    journal: list[str] = []

    def _align(m):
        expr, largeur = m.group(1), int(m.group(2))
        journal.append(f"  align  : {{{expr}:>{largeur},.0f}} -> fcfa()")
        return "{" + f"fcfa({expr}):>{largeur + 2}" + "}"

    def _signe(m):
        expr, signe = m.group(1), m.group(2)
        journal.append(f"  signe  : {{{expr}:{signe},.0f}} -> fcfa(signe={bool(signe)})")
        return "{" + f"fcfa({expr}, signe={bool(signe)})" + "}"

    def _entier(m):
        expr, largeur = m.group(1), m.group(2)
        journal.append(f"  entier : {{{expr}:{largeur},}} -> nombre()")
        cible = "{" + f"nombre({expr})"
        if largeur:
            cible += f":>{largeur}"
        return cible + "}"

    contenu = RE_ALIGN.sub(_align, contenu)
    contenu = RE_SIGNE.sub(_signe, contenu)
    contenu = RE_ENTIER.sub(_entier, contenu)

    # fcfa() produit déjà « X F » : on retire l'unité qui suivait l'ancien placeholder
    def _dedoublonner(m):
        milieu, suffixe = m.group(1), m.group(2)
        reste = {" FCFA/": "/", " F/an": "/an", " FCFA": "", " F": ""}[suffixe]
        journal.append(f"  unite  : '{suffixe.strip()}' redondant supprimé")
        return "{" + milieu + "}" + reste

    contenu = re.sub(r"\{(fcfa\([^{}]+\)(?::>[0-9]+)?)\}( FCFA/| F/an| FCFA| F)", _dedoublonner, contenu)
    return contenu, journal


def main() -> None:
    appliquer = "--appliquer" in sys.argv
    total = 0
    for rel, imp in FICHIERS.items():
        chemin = RACINE / rel
        if not chemin.exists():
            print(f"⚠ absent : {rel}")
            continue
        avant = chemin.read_text(encoding="utf-8")
        apres, journal = transformer(avant)
        if not journal:
            print(f"— {rel} : rien à transformer")
            continue
        # ajout de l'import si un helper est utilisé et absent
        besoin = []
        if "fcfa(" in apres:
            besoin.append("fcfa")
        if re.search(r"nombre\(", apres):
            besoin.append("nombre")
        deja = any(l.startswith("from ..portefeuille.format_fr import")
                   or l.startswith("from .portefeuille.format_fr import")
                   for l in avant.splitlines())
        if besoin and not deja:
            # insertion dans le contenu TRANSFORMÉ (jamais dans `avant` : on perdrait les remplacements)
            lignes = apres.splitlines()
            # insertion après le dernier import du bloc d'en-tête
            dernier = max(i for i, l in enumerate(lignes[:80])
                          if l.startswith("import ") or l.startswith("from "))
            lignes.insert(dernier + 1, imp + "  # format FR (invariant E1, correction C1)")
            apres = "\n".join(lignes) + ("\n" if apres.endswith("\n") else "")
            journal.append(f"  import : + {imp}")
        print(f"— {rel} : {len(journal)} remplacement(s)")
        for j in journal[:6]:
            print(j)
        if len(journal) > 6:
            print(f"  … +{len(journal) - 6} autres")
        total += len([j for j in journal if "import" not in j])
        if appliquer:
            chemin.write_text(apres, encoding="utf-8")
    print(f"\n{'APPLIQUÉ' if appliquer else 'DRY-RUN — rien écrit'} : {total} remplacement(s)")


if __name__ == "__main__":
    main()
