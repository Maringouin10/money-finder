"""Thingiverse — API officielle (nécessite un token dans le .env).

Doc : https://www.thingiverse.com/developers/rest-api-reference
"""

from __future__ import annotations

from typing import Iterable

from ..models import Model, ModelFile
from .base import Source, as_int, as_text, pick


class ThingiverseSource(Source):
    name = "thingiverse"
    label = "Thingiverse"
    requires_key = True

    def available(self) -> tuple[bool, str]:
        if not self.settings.thingiverse_token:
            return False, "THINGIVERSE_TOKEN absent du .env (clé sur thingiverse.com/apps/create)"
        return True, ""

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.settings.thingiverse_token}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        base = self.settings.thingiverse_api.rstrip("/")
        per_page = min(30, limit)
        collected: list[Model] = []
        page = 1
        while len(collected) < limit:
            data = self.http.get_json(
                f"{base}/search/{keyword}/",
                params={"type": "things", "per_page": per_page, "page": page,
                        "sort": "popular"},
                headers=self._headers,
            )
            hits = data.get("hits") if isinstance(data, dict) else data
            if not hits:
                break
            for hit in hits:
                collected.append(self._to_model(hit, keyword))
                if len(collected) >= limit:
                    break
            if len(hits) < per_page:
                break
            page += 1
        return collected

    def _to_model(self, hit: dict, keyword: str) -> Model:
        thing_id = as_text(pick(hit, "id", "thing_id"))
        return Model(
            source=self.name,
            source_id=thing_id,
            url=as_text(pick(hit, "public_url", "url"), f"https://www.thingiverse.com/thing:{thing_id}"),
            title=as_text(pick(hit, "name", "title")),
            description=as_text(pick(hit, "description", "details")),
            image=as_text(pick(hit, "preview_image", "thumbnail", "default_image.url")),
            creator=as_text(pick(hit, "creator.name", "creator.first_name")),
            creator_url=as_text(pick(hit, "creator.public_url")),
            license_raw=as_text(pick(hit, "license")),
            likes=as_int(pick(hit, "like_count", "likes")),
            downloads=as_int(pick(hit, "download_count", "collect_count")),
            published_at=as_text(pick(hit, "added", "published"))[:10],
            tags=[as_text(t) for t in (hit.get("tags") or []) if as_text(t)],
            keyword=keyword,
        )

    # ------------------------------------------------------------------
    def enrich(self, model: Model) -> None:
        base = self.settings.thingiverse_api.rstrip("/")
        detail = self.http.get_json(f"{base}/things/{model.source_id}", headers=self._headers)
        if isinstance(detail, dict):
            model.description = as_text(pick(detail, "description", "details"), model.description)
            model.license_raw = as_text(pick(detail, "license"), model.license_raw)
            model.image = model.image or as_text(pick(detail, "preview_image", "default_image.url"))
            model.images = [as_text(pick(img, "url", "sizes.url"))
                            for img in (detail.get("images") or [])][:6]
            model.images = [i for i in model.images if i]
            model.tags = model.tags or [as_text(t) for t in (detail.get("tags") or [])]
            model.download_url = as_text(pick(detail, "zip_url"),
                                         f"https://www.thingiverse.com/thing:{model.source_id}/zip")
        from ..licenses import normalize
        model.license = normalize(model.license_raw, self.name)

        try:
            files = self.http.get_json(f"{base}/things/{model.source_id}/files", headers=self._headers)
        except Exception as exc:  # noqa: BLE001 - les fichiers sont un bonus
            self.warn(f"fichiers indisponibles pour {model.source_id} ({exc})")
            return
        for entry in files or []:
            name = as_text(pick(entry, "name", "title"))
            url = as_text(pick(entry, "public_url", "download_url", "direct_url"))
            if name and url:
                model.files.append(ModelFile(name=name, url=url, size=as_int(pick(entry, "size"))))
