"""Creality Cloud — API non documentée + repli sur le HTML du site.

Stratégie :
1. endpoints JSON connus (surchargables via CREALITYCLOUD_SEARCH_PATHS) ;
2. si tout échoue, on récupère la page de recherche et on lit le JSON
   embarqué (__NEXT_DATA__ / __NUXT__ / window.__INITIAL_STATE__).
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable

from ..licenses import normalize
from ..models import Model, ModelFile
from .base import Source, as_int, as_text, first_records, pick

DEFAULT_SEARCH_PATHS = [
    "/api/cxy/v3/model/search",
    "/api/cxy/v2/model/search",
    "/api/cxy/v3/model/list",
]

EMBEDDED_JSON = [
    re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S),
    re.compile(r"window\.__NUXT__\s*=\s*(\{.*?\});?\s*</script>", re.S),
    re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>", re.S),
]


class CrealityCloudSource(Source):
    name = "crealitycloud"
    label = "Creality Cloud"

    @property
    def _headers(self) -> dict:
        return {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.crealitycloud.com/",
            "__CXY_APP_ID_": "creality_model",
            "__CXY_PLATFORM_": "12",
        }

    def _search_paths(self) -> list[str]:
        raw = os.getenv("CREALITYCLOUD_SEARCH_PATHS", "").strip()
        if raw:
            return [p.strip() for p in raw.split(",") if p.strip()]
        return DEFAULT_SEARCH_PATHS

    # ------------------------------------------------------------------
    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        errors: list[str] = []
        api = self.settings.crealitycloud_api.rstrip("/")
        for path in self._search_paths():
            try:
                data = self.http.get_json(
                    api + path,
                    params={"keyword": keyword, "key": keyword, "page": 1,
                            "pageSize": min(limit, 40), "size": min(limit, 40)},
                    headers=self._headers,
                )
            except Exception as exc:  # noqa: BLE001 - endpoint suivant
                errors.append(f"{path}: {str(exc)[:120]}")
                continue
            records = first_records(data, ("id", "_id", "modelId"), ("name", "title", "modelName"))
            if records:
                return [self._to_model(r, keyword) for r in records[:limit]]
            errors.append(f"{path}: réponse sans modèle")

        models = self._search_html(keyword, limit, errors)
        if not models:
            self.warn("recherche impossible : " + " | ".join(errors))
        return models

    # ------------------------------------------------------------------
    def _search_html(self, keyword: str, limit: int, errors: list[str]) -> list[Model]:
        """Repli : JSON embarqué dans la page de recherche."""
        web = self.settings.crealitycloud_web.rstrip("/")
        url = f"{web}/search"
        try:
            html = self.http.get_text(url, params={"keyword": keyword, "type": "model"},
                                      headers={"Accept": "text/html"})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"page HTML: {str(exc)[:120]}")
            return []
        for pattern in EMBEDDED_JSON:
            match = pattern.search(html)
            if not match:
                continue
            try:
                data = json.loads(match.group(1))
            except ValueError:
                continue
            records = first_records(data, ("id", "_id", "modelId"), ("name", "title", "modelName"))
            if records:
                return [self._to_model(r, keyword) for r in records[:limit]]
        errors.append("page HTML: aucun JSON de modèles trouvé")
        return []

    # ------------------------------------------------------------------
    def _to_model(self, rec: dict, keyword: str) -> Model:
        mid = as_text(pick(rec, "id", "_id", "modelId", "groupId"))
        return Model(
            source=self.name,
            source_id=mid,
            url=as_text(pick(rec, "url", "detailUrl"),
                        f"https://www.crealitycloud.com/model-detail/{mid}"),
            title=as_text(pick(rec, "name", "title", "modelName")),
            description=as_text(pick(rec, "description", "intro", "content", "summary")),
            image=as_text(pick(rec, "cover", "coverUrl", "thumbnail", "image", "covers")),
            creator=as_text(pick(rec, "userName", "nickName", "user.nickName", "author.name")),
            creator_url=_user_url(rec),
            license_raw=as_text(pick(rec, "license", "licenseType", "copyright", "protocol")),
            likes=as_int(pick(rec, "likeCount", "praiseCount", "likes")),
            downloads=as_int(pick(rec, "downloadCount", "downloads")),
            published_at=as_text(pick(rec, "createTime", "publishTime", "createdAt"))[:10],
            keyword=keyword,
        )

    def enrich(self, model: Model) -> None:
        api = self.settings.crealitycloud_api.rstrip("/")
        for path in ("/api/cxy/v3/model/detail", "/api/cxy/v2/model/detail"):
            try:
                data = self.http.get_json(api + path, params={"id": model.source_id},
                                          headers=self._headers)
            except Exception:  # noqa: BLE001 - endpoint suivant
                continue
            detail = pick(data, "result", "data", default=data)
            if not isinstance(detail, dict):
                continue
            model.description = as_text(pick(detail, "description", "intro", "content"),
                                        model.description)
            model.license_raw = as_text(pick(detail, "license", "licenseType", "copyright", "protocol"),
                                        model.license_raw)
            model.license = normalize(model.license_raw, self.name)
            model.image = model.image or as_text(pick(detail, "cover", "coverUrl", "thumbnail"))
            model.download_url = model.url
            for entry in (pick(detail, "files", "modelFiles", "fileList", default=[]) or []):
                if isinstance(entry, dict):
                    name = as_text(pick(entry, "name", "fileName", "title"))
                    if name:
                        model.files.append(ModelFile(
                            name=name,
                            url=as_text(pick(entry, "url", "downloadUrl", "fileUrl"), model.url),
                            size=as_int(pick(entry, "size", "fileSize"))))
            return
        model.download_url = model.download_url or model.url


def _user_url(rec: dict) -> str:
    uid = as_text(pick(rec, "userId", "uid", "user.id", "author.id"))
    return f"https://www.crealitycloud.com/user/{uid}" if uid else ""
