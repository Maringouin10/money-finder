"""Printables — API GraphQL publique (api.printables.com/graphql/).

Le schéma évolue souvent : plusieurs variantes de requête sont essayées
dans l'ordre, la première qui répond sans erreur est mémorisée.
Une requête maison peut être imposée via PRINTABLES_SEARCH_QUERY (fichier
ou chaîne) dans le .env.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from ..licenses import normalize
from ..models import Model, ModelFile
from .base import Source, as_int, as_text, first_records, pick

SEARCH_QUERIES = [
    # variante actuelle (searchPrints2 + cursor)
    """
    query SearchModels($query: String!, $limit: Int!, $cursor: String) {
      result: searchPrints2(query: $query, limit: $limit, cursor: $cursor,
                            printType: "print", ordering: "best_match") {
        cursor
        items {
          id name slug summary likesCount downloadCount datePublished
          image { filePath }
          user { publicUsername }
          license { id name disallowRemixing }
        }
      }
    }
    """,
    # variante précédente (searchPrints + offset)
    """
    query SearchModels($query: String!, $limit: Int!) {
      result: searchPrints(query: $query, limit: $limit, offset: 0, ordering: "best_match") {
        items {
          id name slug summary likesCount downloadCount datePublished
          image { filePath }
          user { publicUsername }
          license { id name }
        }
      }
    }
    """,
    # variante minimale (si les champs optionnels sautent)
    """
    query SearchModels($query: String!, $limit: Int!) {
      result: searchPrints2(query: $query, limit: $limit) {
        items { id name slug summary image { filePath } license { id name } }
      }
    }
    """,
]

DETAIL_QUERY = """
query PrintDetail($id: ID!) {
  print(id: $id) {
    id name slug description summary likesCount downloadCount datePublished
    license { id name disallowRemixing }
    user { publicUsername }
    images { filePath }
    tags { name }
    stls { id name filePath fileSize }
    slas { id name filePath fileSize }
    otherFiles { id name filePath fileSize }
  }
}
"""

MEDIA_BASE = "https://media.printables.com/"


class PrintablesSource(Source):
    name = "printables"
    label = "Printables"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._query_index = 0
        override = os.getenv("PRINTABLES_SEARCH_QUERY", "").strip()
        if override:
            path = Path(override)
            SEARCH_QUERIES.insert(0, path.read_text() if path.is_file() else override)

    @property
    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.printables.com",
            "Referer": "https://www.printables.com/",
        }

    # ------------------------------------------------------------------
    def _graphql(self, query: str, variables: dict) -> dict:
        payload = {"query": query, "variables": variables}
        data = self.http.post_json(self.settings.printables_api, json=payload, headers=self._headers)
        if isinstance(data, dict) and data.get("errors"):
            msg = "; ".join(as_text(e.get("message")) for e in data["errors"][:2])
            raise RuntimeError(f"GraphQL Printables : {msg}")
        return data if isinstance(data, dict) else {}

    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        errors: list[str] = []
        for idx in range(self._query_index, len(SEARCH_QUERIES)):
            query = SEARCH_QUERIES[idx]
            try:
                data = self._graphql(query, {"query": keyword, "limit": min(limit, 60), "cursor": None})
            except Exception as exc:  # noqa: BLE001 - on tente la variante suivante
                errors.append(str(exc)[:160])
                continue
            records = first_records(data, ("id",), ("name", "title"))
            if not records:
                errors.append("réponse sans résultat exploitable")
                continue
            self._query_index = idx  # variante qui marche : on la garde
            return [self._to_model(rec, keyword) for rec in records[:limit]]

        self.warn("aucune variante de requête GraphQL n'a fonctionné : " + " | ".join(errors))
        return []

    # ------------------------------------------------------------------
    def _to_model(self, rec: dict, keyword: str) -> Model:
        pid = as_text(pick(rec, "id"))
        slug = as_text(pick(rec, "slug"), pid)
        return Model(
            source=self.name,
            source_id=pid,
            url=f"https://www.printables.com/model/{slug}" if slug else f"https://www.printables.com/model/{pid}",
            title=as_text(pick(rec, "name", "title")),
            description=as_text(pick(rec, "summary", "description")),
            image=_media(as_text(pick(rec, "image.filePath", "image"))),
            creator=as_text(pick(rec, "user.publicUsername", "user.handle")),
            creator_url=_user_url(as_text(pick(rec, "user.publicUsername"))),
            license_raw=as_text(pick(rec, "license.name", "license.id", "license")),
            likes=as_int(pick(rec, "likesCount", "likes")),
            downloads=as_int(pick(rec, "downloadCount", "downloads")),
            published_at=as_text(pick(rec, "datePublished", "created"))[:10],
            keyword=keyword,
        )

    def enrich(self, model: Model) -> None:
        try:
            data = self._graphql(DETAIL_QUERY, {"id": model.source_id})
        except Exception as exc:  # noqa: BLE001
            self.warn(f"détail indisponible pour {model.source_id} ({exc})")
            return
        detail = pick(data, "data.print") or {}
        if not isinstance(detail, dict):
            return
        model.description = as_text(pick(detail, "description", "summary"), model.description)
        model.license_raw = as_text(pick(detail, "license.name", "license.id"), model.license_raw)
        model.license = normalize(model.license_raw, self.name)
        model.images = [_media(as_text(pick(i, "filePath"))) for i in (detail.get("images") or [])][:6]
        model.images = [i for i in model.images if i]
        model.image = model.image or (model.images[0] if model.images else "")
        model.tags = [as_text(t) for t in (detail.get("tags") or []) if as_text(t)]
        model.download_url = f"{model.url}/files" if model.url else ""
        for key, kind in (("stls", "STL"), ("slas", "SLA"), ("otherFiles", "AUTRE")):
            for entry in detail.get(key) or []:
                name = as_text(pick(entry, "name"))
                path = as_text(pick(entry, "filePath"))
                if name:
                    model.files.append(ModelFile(
                        name=name, url=_media(path) or model.download_url,
                        size=as_int(pick(entry, "fileSize")), kind=kind))


def _media(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return MEDIA_BASE + path.lstrip("/")


def _user_url(username: str) -> str:
    return f"https://www.printables.com/@{username}" if username else ""
