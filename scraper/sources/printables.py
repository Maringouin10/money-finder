"""Printables — API GraphQL publique (api.printables.com/graphql/).

Schéma validé par sondage (2026-08) : l'introspection est désactivée, mais le
validateur GraphQL a permis de cartographier les champs réels.

- recherche : query `searchPrints2(query, limit, offset, printType, ordering)`
  → `data.result.items[]` ; pagination par `offset`, pas de curseur.
- détail    : query `print(id: ID!)` → `data.print`.
- Les enums (`printType`, `ordering`) doivent être des littéraux NON quotés.
- Aucune URL de téléchargement de fichier n'est exposée : on renvoie la page
  « files » du modèle, les entrées `stls`/`gcodes` servent à lister les pièces.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from ..licenses import normalize
from ..models import Model, ModelFile
from .base import Source, as_int, as_text, first_records, pick, records_at

SEARCH_QUERY = """
query SearchModels($query: String!, $limit: Int!, $offset: Int!) {
  result: searchPrints2(query: $query, limit: $limit, offset: $offset,
                        printType: print, ordering: best_match) {
    totalCount
    items {
      id name slug summary likesCount downloadCount displayCount
      ratingAvg ratingCount datePublished filesCount nsfw
      image { id filePath }
      user { id publicUsername handle verified }
      license { id name abbreviation disallowRemixing }
      category { id name }
      tags { id name }
    }
  }
}
"""

DETAIL_QUERY = """
query PrintDetail($id: ID!) {
  print(id: $id) {
    id name slug description summary likesCount downloadCount displayCount
    datePublished filesCount printDuration numPieces weight nsfw
    license { id name abbreviation disallowRemixing }
    user { id publicUsername handle }
    image { id filePath }
    images { id filePath name }
    tags { id name }
    category { id name }
    stls { id name fileSize folder note order }
    slas { id name fileSize }
    otherFiles { id name fileSize note order }
    gcodes { id name fileSize }
  }
}
"""

MEDIA_BASE = "https://media.printables.com/"
PAGE_SIZE = 60


class PrintablesSource(Source):
    name = "printables"
    label = "Printables"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        override = os.getenv("PRINTABLES_SEARCH_QUERY", "").strip()
        self.search_query = SEARCH_QUERY
        if override:
            path = Path(override)
            self.search_query = path.read_text() if path.is_file() else override

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
        data = self.http.post_json(self.settings.printables_api,
                                   json={"query": query, "variables": variables},
                                   headers=self._headers)
        if isinstance(data, dict) and data.get("errors"):
            msg = "; ".join(as_text(e.get("message")) for e in data["errors"][:3])
            raise RuntimeError(f"GraphQL Printables : {msg}")
        return data if isinstance(data, dict) else {}

    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        models: list[Model] = []
        offset = 0
        while len(models) < limit:
            page_size = min(PAGE_SIZE, limit - len(models))
            try:
                data = self._graphql(self.search_query,
                                     {"query": keyword, "limit": page_size, "offset": offset})
            except Exception as exc:  # noqa: BLE001 - remonté en avertissement
                self.warn(f"recherche « {keyword} » impossible : {str(exc)[:200]}")
                break
            records = (records_at(data, "data.result.items", "data.searchPrints2.items")
                       or first_records(data, ("id",), ("name", "title")))
            if not records:
                break
            for rec in records:
                models.append(self._to_model(rec, keyword))
                if len(models) >= limit:
                    break
            if len(records) < page_size:
                break
            offset += len(records)
        return models

    # ------------------------------------------------------------------
    def _to_model(self, rec: dict, keyword: str) -> Model:
        pid = as_text(pick(rec, "id"))
        slug = as_text(pick(rec, "slug"))
        handle = as_text(pick(rec, "user.handle"))
        return Model(
            source=self.name,
            source_id=pid,
            url=_model_url(pid, slug),
            title=as_text(pick(rec, "name", "title")),
            description=as_text(pick(rec, "summary", "description")),
            image=_media(as_text(pick(rec, "image.filePath"))),
            creator=as_text(pick(rec, "user.publicUsername", "user.handle")),
            creator_url=f"https://www.printables.com/@{handle}" if handle else "",
            # `abbreviation` est plus propre que `name` (tirets cadratins, doubles espaces)
            license_raw=as_text(pick(rec, "license.abbreviation", "license.name", "license.id")),
            likes=as_int(pick(rec, "likesCount", "likes")),
            downloads=as_int(pick(rec, "downloadCount", "downloads")),
            published_at=as_text(pick(rec, "datePublished", "firstPublish"))[:10],
            tags=[as_text(pick(t, "name")) for t in (rec.get("tags") or []) if as_text(pick(t, "name"))],
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
        model.license_raw = as_text(pick(detail, "license.abbreviation", "license.name"),
                                    model.license_raw)
        model.license = normalize(model.license_raw, self.name)
        model.images = [_media(as_text(pick(i, "filePath"))) for i in (detail.get("images") or [])][:6]
        model.images = [i for i in model.images if i]
        model.image = model.image or (model.images[0] if model.images else "")
        model.tags = model.tags or [as_text(pick(t, "name")) for t in (detail.get("tags") or [])]
        model.url = model.url or _model_url(as_text(pick(detail, "id")), as_text(pick(detail, "slug")))
        model.download_url = f"{model.url}/files" if model.url else ""

        # L'API n'expose aucun chemin de fichier téléchargeable : les entrées
        # servent d'inventaire, le lien pointe vers l'onglet « Files ».
        for key, kind in (("stls", "STL"), ("slas", "SLA"),
                          ("gcodes", "GCODE"), ("otherFiles", "AUTRE")):
            for entry in detail.get(key) or []:
                name = as_text(pick(entry, "name"))
                if name:
                    model.files.append(ModelFile(name=name, url=model.download_url,
                                                 size=as_int(pick(entry, "fileSize")), kind=kind))


def _model_url(pid: str, slug: str) -> str:
    if pid and slug:
        return f"https://www.printables.com/model/{pid}-{slug}"
    return f"https://www.printables.com/model/{pid}" if pid else ""


def _media(path: str) -> str:
    if not path:
        return ""
    return path if path.startswith("http") else MEDIA_BASE + path.lstrip("/")
