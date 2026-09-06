"""Familles de mots-clés proposées dans le formulaire du service web.

Chaque famille regroupe plusieurs mots-clés proches (synonymes, variantes) :
le formulaire les propose groupés pour qu'on choisisse un thème entier
(« Fidget toys », « Animaux articulés »…) plutôt que de cocher les mots-clés
un par un.
"""

from __future__ import annotations

KEYWORD_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Fidget toys", [
        "fidget toy",
        "fidget toys",
        "fidget",
        "infinity cube",
        "planetary gear",
        "print in place fidget",
        "fidget slider",
    ]),
    ("Animaux articulés", [
        "articulated animal",
        "articulated dragon",
        "articulated snake",
        "flexi animal",
        "print in place animal",
    ]),
    ("Accessoires de bureau", [
        "desk accessory",
        "desk organizer",
        "pen holder",
        "cable organizer",
        "phone stand",
    ]),
    ("Personnalisé", [
        "personalized",
        "personalized gift",
        "custom name",
        "name tag",
    ]),
]


def all_keywords() -> list[str]:
    """Tous les mots-clés des familles ci-dessus, sans doublon, dans l'ordre."""
    seen: set[str] = set()
    result: list[str] = []
    for _, keywords in KEYWORD_CATEGORIES:
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
    return result
