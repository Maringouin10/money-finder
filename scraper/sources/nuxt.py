"""Lecture des payloads Nuxt 3 (`__NUXT_DATA__`, format *devalue*).

Le payload est un tableau plat : l'entrée 0 est la racine, et les nombres
présents dans les objets/tableaux sont des **index** vers d'autres entrées.
Un `json.loads` seul ne suffit donc pas, il faut résoudre les références.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator

NUXT_DATA = re.compile(
    r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)

# Constantes négatives de devalue
_SPECIALS = {-1: None, -2: None, -3: float("nan"),
             -4: float("inf"), -5: float("-inf"), -6: -0.0}

_TAGGED = {"Date", "Set", "Map", "RegExp", "BigInt", "URL", "Object", "null"}


def extract_nuxt_data(html: str) -> Any:
    """Renvoie le payload Nuxt hydraté trouvé dans une page, sinon None."""
    match = NUXT_DATA.search(html or "")
    if not match:
        return None
    try:
        raw = json.loads(match.group(1))
    except ValueError:
        return None
    return devalue_parse(raw)


def devalue_parse(raw: Any) -> Any:
    """Résout un tableau plat devalue en structure Python classique."""
    if not isinstance(raw, list) or not raw:
        return raw
    resolved: dict[int, Any] = {}

    def hydrate(ref: Any, depth: int = 0) -> Any:
        if depth > 60:
            return None
        if isinstance(ref, bool) or not isinstance(ref, int):
            return ref
        if ref < 0:
            return _SPECIALS.get(ref)
        if ref >= len(raw):
            return None
        if ref in resolved:
            return resolved[ref]

        value = raw[ref]
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            resolved[ref] = out                      # avant récursion : coupe les cycles
            for key, child in value.items():
                out[key] = hydrate(child, depth + 1)
            return out
        if isinstance(value, list):
            if value and isinstance(value[0], str) and value[0] in _TAGGED:
                tag, *rest = value
                payload = [hydrate(r, depth + 1) for r in rest]
                if tag == "Date":
                    return payload[0] if payload else None
                if tag in ("Set", "Map", "Object"):
                    return payload[0] if len(payload) == 1 else payload
                return payload[0] if payload else None
            items: list[Any] = []
            resolved[ref] = items
            for child in value:
                items.append(hydrate(child, depth + 1))
            return items
        resolved[ref] = value
        return value

    return hydrate(0)


def walk_dicts(data: Any, depth: int = 0) -> Iterator[dict]:
    """Tous les dictionnaires d'une structure, en profondeur d'abord."""
    if depth > 40:
        return
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from walk_dicts(value, depth + 1)
    elif isinstance(data, list):
        for value in data:
            yield from walk_dicts(value, depth + 1)


def find_dict(data: Any, required: tuple[str, ...]) -> dict | None:
    """Premier dictionnaire contenant toutes les clés demandées."""
    for candidate in walk_dicts(data):
        if all(key in candidate for key in required):
            return candidate
    return None
