"""MakerWorld — API publique utilisée par le site (non documentée).

Recherche : GET /api/v1/search-service/select/design?keyword=...
Détail    : GET /api/v1/design-service/design/{id}
Les noms de champs varient selon les versions : lecture tolérante via pick().
"""

from __future__ import annotations

from typing import Iterable

from ..licenses import normalize
from ..models import Model, ModelFile
from .base import Source, as_int, as_text, first_records, pick

SEARCH_PATHS = [
    "/search-service/select/design",
    "/search-service/select/instant",
]


class MakerWorldSource(Source):
    name = "makerworld"
    label = "MakerWorld"

    @property
    def _headers(self) -> dict:
        return {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://makerworld.com/",
            "Origin": "https://makerworld.com",
        }

    # ------------------------------------------------------------------
    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        base = self.settings.makerworld_api.rstrip("/")
        errors: list[str] = []
        for path in SEARCH_PATHS:
            models: list[Model] = []
            page = 1
            try:
                while len(models) < limit:
                    data = self.http.get_json(
                        base + path,
                        params={"keyword": keyword, "page": page,
                                "limit": min(20, limit), "sort": "hot"},
                        headers=self._headers,
                    )
                    records = first_records(data, ("id", "designId"), ("title", "name"))
                    if not records:
                        break
                    for rec in records:
                        models.append(self._to_model(rec, keyword))
                        if len(models) >= limit:
                            break
                    if len(records) < min(20, limit):
                        break
                    page += 1
            except Exception as exc:  # noqa: BLE001 - on tente l'endpoint suivant
                errors.append(f"{path}: {str(exc)[:140]}")
                continue
            if models:
                return models
        self.warn("recherche impossible : " + " | ".join(errors or ["aucun résultat"]))
        return []

    def _to_model(self, rec: dict, keyword: str) -> Model:
        design_id = as_text(pick(rec, "designId", "id", "modelId"))
        return Model(
            source=self.name,
            source_id=design_id,
            url=f"https://makerworld.com/en/models/{design_id}",
            title=as_text(pick(rec, "title", "name")),
            description=as_text(pick(rec, "summary", "description", "intro")),
            image=as_text(pick(rec, "cover", "coverUrl", "cover.url", "coverPic", "image")),
            creator=as_text(pick(rec, "designCreator.name", "creator.name", "userName", "nickname")),
            creator_url=_creator_url(rec),
            license_raw=as_text(pick(rec, "license", "licenseType", "licenseName")),
            likes=as_int(pick(rec, "likeCount", "likes")),
            downloads=as_int(pick(rec, "downloadCount", "downloads")),
            published_at=as_text(pick(rec, "createTime", "publishTime", "createdAt"))[:10],
            keyword=keyword,
        )

    # ------------------------------------------------------------------
    def enrich(self, model: Model) -> None:
        base = self.settings.makerworld_api.rstrip("/")
        try:
            data = self.http.get_json(f"{base}/design-service/design/{model.source_id}",
                                      headers=self._headers)
        except Exception as exc:  # noqa: BLE001
            self.warn(f"détail indisponible pour {model.source_id} ({exc})")
            return
        detail = data.get("design") if isinstance(data, dict) and "design" in data else data
        if not isinstance(detail, dict):
            return
        model.description = as_text(pick(detail, "description", "summary", "intro"), model.description)
        model.license_raw = as_text(pick(detail, "license", "licenseType", "licenseName"),
                                    model.license_raw)
        model.license = normalize(model.license_raw, self.name)
        model.image = model.image or as_text(pick(detail, "cover", "coverUrl", "cover.url"))
        model.tags = [as_text(t) for t in (pick(detail, "tags", "labels", default=[]) or []) if as_text(t)]
        model.download_url = model.url

        # fichiers : instances (.3mf) et fichiers modèles bruts
        for entry in _file_entries(detail):
            name = as_text(pick(entry, "name", "title", "fileName"))
            url = as_text(pick(entry, "url", "downloadUrl", "modelUrl", "fileUrl"), model.url)
            if name:
                model.files.append(ModelFile(name=name, url=url, size=as_int(pick(entry, "size"))))


def _file_entries(detail: dict) -> list[dict]:
    entries: list[dict] = []
    for key in ("instances", "modelFiles", "designFiles", "files", "modelList"):
        value = detail.get(key)
        if isinstance(value, list):
            entries.extend(v for v in value if isinstance(v, dict))
    return entries


def _creator_url(rec: dict) -> str:
    handle = as_text(pick(rec, "designCreator.handle", "creator.handle", "userHandle"))
    uid = as_text(pick(rec, "designCreator.uid", "creator.uid", "userId"))
    if handle:
        return f"https://makerworld.com/en/@{handle}"
    return f"https://makerworld.com/en/u/{uid}" if uid else ""
