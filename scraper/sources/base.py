"""Contrat commun aux connecteurs + helpers de parsing tolérant.

Les APIs publiques de MakerWorld / Printables / Creality Cloud ne sont pas
documentées et changent régulièrement de forme. Tous les connecteurs lisent
donc les réponses via `pick()` / `deep_find_lists()` qui acceptent plusieurs
noms de champs possibles au lieu d'un schéma figé.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Iterable, Iterator

from ..config import Settings
from ..http import Http
from ..models import Model

log = logging.getLogger("money-finder.source")


class Source(ABC):
    """Un connecteur de plateforme."""

    name: str = ""
    label: str = ""
    requires_key: bool = False
    # True quand la recherche seule ne suffit pas (licence/description/fichiers
    # ne sont disponibles que sur la page détail).
    needs_enrich: bool = False
    # Rythme minimal imposé par la plateforme, en secondes entre deux requêtes.
    min_delay: float = 0.0

    def __init__(self, settings: Settings, http: Http) -> None:
        self.settings = settings
        self.http = http
        self.warnings: list[str] = []

    # ------------------------------------------------------------------
    def available(self) -> tuple[bool, str]:
        """(utilisable ?, raison si non)"""
        return True, ""

    @abstractmethod
    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        """Renvoie les modèles correspondant au mot-clé."""

    def enrich(self, model: Model) -> None:
        """Complète un modèle avec les infos de la page détail (licence, fichiers)."""

    # ------------------------------------------------------------------
    def warn(self, message: str) -> None:
        log.warning("[%s] %s", self.name, message)
        self.warnings.append(message)


# ----------------------------------------------------------------------
# Helpers de lecture tolérante
# ----------------------------------------------------------------------
def pick(data: Any, *paths: str, default: Any = None) -> Any:
    """Premier chemin existant parmi `paths`, ex : pick(d, "cover.url", "coverUrl").

    Renvoie `default` si rien n'est trouvé (ou si la valeur est None/"" ).
    """
    if not isinstance(data, dict):
        return default
    for path in paths:
        cur: Any = data
        for part in path.split("."):
            if isinstance(cur, list):
                cur = cur[0] if cur else None
            if not isinstance(cur, dict) or part not in cur:
                cur = None
                break
            cur = cur[part]
        if cur not in (None, "", [], {}):
            return cur
    return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    if isinstance(value, dict):
        for key in ("name", "title", "label", "value", "text"):
            if key in value:
                return as_text(value[key])
    if isinstance(value, list):
        return ", ".join(filter(None, (as_text(v) for v in value)))
    return default


def records_at(data: Any, *paths: str) -> list[dict]:
    """Liste d'objets située à l'un des chemins donnés (chemin validé en premier).

    À préférer à `first_records()` : une réponse contient souvent d'autres
    listes (tags, catégories, suggestions) qui peuvent être plus longues que
    la liste de résultats.
    """
    for path in paths:
        value = pick(data, path)
        if isinstance(value, list):
            records = [v for v in value if isinstance(v, dict)]
            if records:
                return records
    return []


def first_records(data: Any, id_keys: tuple[str, ...], name_keys: tuple[str, ...]) -> list[dict]:
    """Meilleure liste d'objets « modèle » trouvée dans une réponse inconnue.

    Sert à extraire les résultats d'une réponse dont on ne connaît pas
    l'arborescence exacte (payload Next.js, enveloppe API qui change...).
    On retient la plus grande liste d'objets possédant à la fois un
    identifiant et un nom.
    """
    best: list[dict] = []
    for records in walk_lists(data):
        usable = [r for r in records if _has_any(r, id_keys) and _has_any(r, name_keys)]
        if len(usable) > len(best):
            best = usable
    return best


def walk_lists(data: Any) -> Iterator[list[dict]]:
    """Toutes les listes d'objets présentes dans un JSON, récursivement."""
    if isinstance(data, list):
        dicts = [d for d in data if isinstance(d, dict)]
        if dicts:
            yield dicts
        for entry in data:
            yield from walk_lists(entry)
    elif isinstance(data, dict):
        for value in data.values():
            yield from walk_lists(value)


def _has_any(item: dict, keys: tuple[str, ...]) -> bool:
    return any(k in item for k in keys)
