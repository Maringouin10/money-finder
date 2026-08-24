"""Creality Cloud — API de recherche publique + page détail rendue côté serveur.

Endpoints validés par sondage (2026-08) :
- recherche : POST https://www.crealitycloud.com/api/cxy/smart_search/v1/model
  corps {"keyword", "page", "pageSize"} → `result.list[]`
  (seul `Content-Type: application/json` est nécessaire)
- détail    : l'API `modelGroupDetail` refuse les appels anonymes ; on lit la
  page /model-detail/{id} et son payload Nuxt `__NUXT_DATA__`.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable

from ..licenses import normalize
from ..models import Model, ModelFile
from .base import Source, as_int, as_text, first_records, pick, records_at
from .nuxt import extract_nuxt_data, find_dict

DEFAULT_SEARCH_PATHS = ["/api/cxy/smart_search/v1/model"]
PAGE_SIZE = 20


class CrealityCloudSource(Source):
    name = "crealitycloud"
    label = "Creality Cloud"
    needs_enrich = True

    @property
    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.crealitycloud.com/",
        }

    def _search_paths(self) -> list[str]:
        raw = os.getenv("CREALITYCLOUD_SEARCH_PATHS", "").strip()
        if raw:
            return [p.strip() for p in raw.split(",") if p.strip()]
        return DEFAULT_SEARCH_PATHS

    # ------------------------------------------------------------------
    def search(self, keyword: str, limit: int) -> Iterable[Model]:
        base = self.settings.crealitycloud_api.rstrip("/")
        errors: list[str] = []
        for path in self._search_paths():
            models: list[Model] = []
            page = 1
            try:
                while len(models) < limit:
                    page_size = min(PAGE_SIZE, limit - len(models))
                    data = self.http.post_json(
                        base + path,
                        json={"keyword": keyword, "page": page, "pageSize": page_size},
                        headers=self._headers,
                    )
                    if isinstance(data, dict) and as_int(data.get("code"), 0) != 0:
                        raise RuntimeError(as_text(data.get("msg"), "réponse en erreur"))
                    records = (records_at(data, "result.list", "data.list", "list")
                               or first_records(data, ("id", "_id", "modelId"),
                                                ("groupName", "name", "title", "modelName")))
                    if not records:
                        break
                    for rec in records:
                        models.append(self._to_model(rec, keyword))
                        if len(models) >= limit:
                            break
                    if len(records) < page_size:
                        break
                    page += 1
            except Exception as exc:  # noqa: BLE001 - on tente le chemin suivant
                errors.append(f"{path}: {str(exc)[:140]}")
                continue
            if models:
                return models

        models = self._search_html(keyword, limit, errors)
        if not models:
            self.warn("recherche impossible : " + " | ".join(errors))
        return models

    # ------------------------------------------------------------------
    def _search_html(self, keyword: str, limit: int, errors: list[str]) -> list[Model]:
        """Repli : page de recherche rendue côté serveur (payload Nuxt)."""
        web = self.settings.crealitycloud_web.rstrip("/")
        url = f"{web}/search/models/{keyword.replace(' ', '%20')}"
        try:
            html = self.http.get_text(url, headers={"Accept": "text/html"})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"page HTML: {str(exc)[:120]}")
            return []
        payload = extract_nuxt_data(html)
        if payload is None:
            errors.append("page HTML: payload __NUXT_DATA__ introuvable")
            return []
        records = first_records(payload, ("id", "_id", "modelId"),
                                ("groupName", "name", "title", "modelName"))
        if not records:
            errors.append("page HTML: aucun modèle dans le payload")
        return [self._to_model(r, keyword) for r in records[:limit]]

    # ------------------------------------------------------------------
    def _to_model(self, rec: dict, keyword: str) -> Model:
        mid = as_text(pick(rec, "id", "_id", "modelId", "groupId"))
        return Model(
            source=self.name,
            source_id=mid,
            url=_detail_url(mid),
            title=as_text(pick(rec, "groupName", "name", "title", "modelName")),
            # absente des résultats de recherche : remplie par enrich()
            description=as_text(pick(rec, "groupDesc", "description", "intro")),
            image=_cover(rec),
            creator=as_text(pick(rec, "userInfo.nickName", "nickName", "userName")),
            creator_url=_user_url(rec),
            license_raw=as_text(pick(rec, "license", "licenseType", "copyright", "protocol")),
            likes=as_int(pick(rec, "likeCount", "praiseCount", "likes")),
            downloads=as_int(pick(rec, "downloadCount", "downloads")),
            published_at=_epoch_date(pick(rec, "createTime", "lastSharedTime", "publishTime")),
            keyword=keyword,
        )

    # ------------------------------------------------------------------
    def enrich(self, model: Model) -> None:
        """Le détail n'est accessible qu'en lisant la page rendue côté serveur."""
        try:
            html = self.http.get_text(model.url, headers={"Accept": "text/html"})
        except Exception as exc:  # noqa: BLE001
            self.warn(f"détail indisponible pour {model.source_id} ({exc})")
            return
        payload = extract_nuxt_data(html)
        detail = find_dict(payload, ("groupName", "groupDesc")) or \
            find_dict(payload, ("groupName", "model3mfList"))
        if not detail:
            return

        model.description = as_text(pick(detail, "groupDesc", "description"), model.description)
        model.license_raw = as_text(pick(detail, "license", "licenseType", "copyright"),
                                    model.license_raw)
        model.license = normalize(model.license_raw, self.name)
        model.image = model.image or _cover(detail)
        model.tags = [as_text(pick(t, "name", "alias")) for t in (detail.get("tags") or [])
                      if as_text(pick(t, "name", "alias"))]
        model.download_url = as_text(pick(detail, "downloadZip"), model.url)

        for entry in (detail.get("model3mfList") or []):
            if not isinstance(entry, dict):
                continue
            name = as_text(pick(entry, "name", "secondName"))
            if name:
                model.files.append(ModelFile(
                    name=name,
                    url=as_text(pick(entry, "url", "downloadUrl"), model.url),
                    size=as_int(pick(entry, "size")),
                    kind="3MF"))


def _detail_url(mid: str) -> str:
    return f"https://www.crealitycloud.com/model-detail/{mid}" if mid else ""


def _cover(rec: dict) -> str:
    """covers/pcCovers sont des listes d'objets {url, type, ...}."""
    for key in ("covers", "pcCovers", "editCovers", "appCovers"):
        entries = rec.get(key)
        if isinstance(entries, list):
            for entry in entries:
                url = as_text(pick(entry, "url", "originUrl")) if isinstance(entry, dict) else as_text(entry)
                if url:
                    return url
    return as_text(pick(rec, "cover", "coverUrl", "thumbnail", "image"))


def _epoch_date(value: object) -> str:
    """createTime est un timestamp epoch (secondes)."""
    seconds = as_int(value)
    if not seconds:
        return as_text(value)[:10]
    if seconds > 10_000_000_000:      # millisecondes
        seconds //= 1000
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def _user_url(rec: dict) -> str:
    uid = as_text(pick(rec, "userId", "userInfo.userId", "uid"))
    return f"https://www.crealitycloud.com/user/{uid}" if uid else ""
