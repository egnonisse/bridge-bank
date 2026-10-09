"""Formatage des nombres pour un lecteur francophone.

LE PROBLÈME
-----------
Python formate par défaut avec la virgule comme séparateur de MILLIERS
(`f"{3784:,.0f}"` → `"3,784"`). En français, la virgule est le séparateur
DÉCIMAL : un lecteur lit « 3,784 F » comme trois francs et sept cent
quatre-vingt-quatre centimes, pas comme trois mille sept cent quatre-vingt-quatre.

Sur une alerte destinée à quelqu'un qui n'a aucune notion de bourse, c'est un
piège de lecture qui peut faire prendre une décision sur un chiffre mal compris
— exactement le contraire du but.

LA RÈGLE
--------
Montants en francs : **espace** comme séparateur de milliers, jamais de virgule.

    >>> fcfa(3784)
    '3 784 F'
    >>> fcfa(699718)
    '699 718 F'
    >>> fcfa(-16000)
    '-16 000 F'
    >>> fcfa(16000, signe=True)
    '+16 000 F'

Les pourcentages et les ratios gardent leur point décimal (usage courant en
finance), mais les FRANCS sont toujours formatés par cette fonction.
"""
from __future__ import annotations


def fcfa(montant: float, signe: bool = False, suffixe: str = " F") -> str:
    """Formate un montant en francs à la française : « 3 784 F ».

    `signe=True` force le « + » sur les valeurs positives (pour les gains).
    """
    arrondi = round(montant)
    texte = f"{abs(arrondi):,.0f}".replace(",", "\u202f")   # espace fine insécable
    if arrondi < 0:
        return f"-{texte}{suffixe}"
    if signe and arrondi > 0:
        return f"+{texte}{suffixe}"
    return f"{texte}{suffixe}"


def nombre(valeur: float) -> str:
    """Formate un nombre sans unité, à la française (« 1 234 »)."""
    return f"{round(valeur):,.0f}".replace(",", "\u202f")


def pct(valeur: float, decimales: int = 1, signe: bool = False) -> str:
    """Formate un pourcentage à la française : « 3,8 % » (virgule, pas point).

    Python écrit `3.8` — le séparateur décimal anglais. Un lecteur francophone y voit
    une date ou un code, pas un nombre. Même piège que pour les milliers, inversé.
    """
    texte = f"{abs(valeur):.{decimales}f}".replace(".", ",")
    if valeur < 0:
        return f"-{texte} %"
    if signe and valeur > 0:
        return f"+{texte} %"
    return f"{texte} %"
