"""MakerWorld — API publique utilisée par le site (non documentée).

Endpoints validés par sondage réseau (2026-08) :
- recherche : GET /api/v1/search-service/select/design2?keyword=…&limit=…&offset=…
  (pagination par `offset`, aucun header d'authentification requis)
- détail    : GET /api/v1/design-service/design/{id}  → JSON à la racine

Le hit de recherche ne contient pas de description : `enrich()` est
nécessaire pour récupérer `summary` et la liste des fichiers.
"""

from __future__ import annotations

from typing import Iterable

from ..licenses import normalize
from ..models import Model, ModelFile
from .base import Source, as_int, as_text, first_records, pick, records_at

SEARCH_PATH = "/search-service/select/design2"
PAGE_SIZE = 20


class MakerWorldSource(Source):
    name = "makerworld"
    label = "MakerWorld"
    needs_enrich = True

    @property
    def _headers(self) -> dict:
        return {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://makerworld.com/",
        }

    # ------------------------------------------------------------------
    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        base = self.settings.makerworld_api.rstrip("/")
        models: list[Model] = []
        offset = 0
        while len(models) < limit:
            page_size = min(PAGE_SIZE, limit - len(models))
            try:
                data = self.http.get_json(
                    base + SEARCH_PATH,
                    params={"keyword": keyword, "limit": page_size,
                            "offset": offset, "orderBy": "score", "designType": 0},
                    headers=self._headers,
                )
            except Exception as exc:  # noqa: BLE001 - remonté en avertissement
                self.warn(f"recherche « {keyword} » impossible : {str(exc)[:160]}")
                break
            records = (records_at(data, "hits", "data.hits", "result.hits")
                       or first_records(data, ("id", "designId"), ("title", "name")))
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

    def _to_model(self, rec: dict, keyword: str) -> Model:
        design_id = as_text(pick(rec, "id", "designId", "modelId"))
        return Model(
            source=self.name,
            source_id=design_id,
            url=f"https://makerworld.com/en/models/{design_id}",
            title=as_text(pick(rec, "title", "name")),
            # absent du hit de recherche : rempli par enrich()
            description=as_text(pick(rec, "summary", "description", "intro")),
            image=as_text(pick(rec, "cover", "coverUrl", "coverPortrait", "coverLandscape")),
            creator=as_text(pick(rec, "designCreator.name", "creator.name", "userName")),
            creator_url=_creator_url(rec),
            license_raw=as_text(pick(rec, "license", "licenseType", "licenseName")),
            likes=as_int(pick(rec, "likeCount", "likes")),
            downloads=as_int(pick(rec, "downloadCount", "downloads")),
            published_at=as_text(pick(rec, "createTime", "publishTime", "createdAt"))[:10],
            tags=[as_text(t) for t in (rec.get("tags") or []) if as_text(t)],
            keyword=keyword,
        )

    # ------------------------------------------------------------------
    def enrich(self, model: Model) -> None:
        base = self.settings.makerworld_api.rstrip("/")
        try:
            detail = self.http.get_json(f"{base}/design-service/design/{model.source_id}",
                                        headers=self._headers)
        except Exception as exc:  # noqa: BLE001
            self.warn(f"détail indisponible pour {model.source_id} ({exc})")
            return
        if not isinstance(detail, dict):
            return

        model.description = as_text(pick(detail, "summary", "description", "intro"),
                                    model.description)
        model.license_raw = as_text(pick(detail, "license", "licenseType", "licenseName"),
                                    model.license_raw)
        model.license = normalize(model.license_raw, self.name)
        model.image = model.image or as_text(pick(detail, "coverUrl", "cover", "coverPortrait"))
        model.tags = model.tags or [as_text(t) for t in (detail.get("tags") or []) if as_text(t)]
        model.download_url = model.url

        # Les fichiers source sont dans designExtension.model_files (arborescence
        # avec dossiers) ; modelUrl est vide sans session, on renvoie alors la
        # page du modèle.
        for entry in _model_files(pick(detail, "designExtension.model_files", default=[]) or []):
            name = as_text(pick(entry, "modelName", "name", "fileName"))
            if not name:
                continue
            model.files.append(ModelFile(
                name=name,
                url=as_text(pick(entry, "modelUrl", "url", "downloadUrl"), model.url),
                size=as_int(pick(entry, "modelSize", "size")),
                kind=as_text(pick(entry, "modelType")).upper(),
            ))


def _model_files(entries: list, depth: int = 0) -> list[dict]:
    """Aplatit l'arborescence designExtension.model_files (dossiers + children)."""
    out: list[dict] = []
    if depth > 5:
        return out
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("isDir"):
            out.extend(_model_files(entry.get("children") or [], depth + 1))
            continue
        out.append(entry)
        if entry.get("children"):
            out.extend(_model_files(entry["children"], depth + 1))
    return out


def _creator_url(rec: dict) -> str:
    handle = as_text(pick(rec, "designCreator.handle", "creator.handle", "userHandle"))
    uid = as_text(pick(rec, "designCreator.uid", "creator.uid", "userId"))
    if handle:
        return f"https://makerworld.com/en/@{handle}"
    return f"https://makerworld.com/en/u/{uid}" if uid else ""
