"""Structures de données communes à toutes les plateformes."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .licenses import LicenseInfo, normalize

SOURCE_LABELS = {
    "thingiverse": "Thingiverse",
    "printables": "Printables",
    "makerworld": "MakerWorld",
    "crealitycloud": "Creality Cloud",
}


@dataclass
class ModelFile:
    """Un fichier téléchargeable (STL, 3MF, STEP, ZIP...)."""

    name: str
    url: str
    size: int | None = None
    kind: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "url": self.url, "size": self.size, "kind": self.kind or _ext(self.name)}


def _ext(name: str) -> str:
    m = re.search(r"\.([a-z0-9]{2,5})$", (name or "").lower())
    return m.group(1).upper() if m else ""


@dataclass
class Model:
    """Un modèle 3D normalisé, quelle que soit la plateforme d'origine."""

    source: str
    source_id: str
    url: str
    title: str
    description: str = ""
    image: str = ""                       # vignette principale (URL distante)
    local_image: str = ""                 # chemin relatif dans le rapport
    images: list[str] = field(default_factory=list)
    creator: str = ""
    creator_url: str = ""
    license_raw: str = ""
    license: LicenseInfo | None = None
    files: list[ModelFile] = field(default_factory=list)
    download_url: str = ""                # page/lien de téléchargement principal
    tags: list[str] = field(default_factory=list)
    likes: int = 0
    downloads: int = 0
    published_at: str = ""
    keyword: str = ""                     # mot-clé qui a permis de le trouver
    group: str = ""                       # famille détectée automatiquement
    group_slug: str = ""
    also_on: list[str] = field(default_factory=list)  # mêmes titres sur d'autres plateformes

    def __post_init__(self) -> None:
        if self.license is None:
            self.license = normalize(self.license_raw, self.source)

    # -- identité ---------------------------------------------------------
    @property
    def uid(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS.get(self.source, self.source.title())

    @property
    def fingerprint(self) -> str:
        """Empreinte du titre, pour repérer un même modèle publié ailleurs."""
        return normalize_title(self.title)

    @property
    def image_key(self) -> str:
        return hashlib.sha1(f"{self.uid}|{self.image}".encode()).hexdigest()[:16]

    @property
    def excerpt(self) -> str:
        txt = re.sub(r"<[^>]+>", " ", self.description or "")
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt[:320] + ("…" if len(txt) > 320 else "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_label": self.source_label,
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "excerpt": self.excerpt,
            "image": self.image,
            "local_image": self.local_image,
            "images": self.images,
            "creator": self.creator,
            "creator_url": self.creator_url,
            "license": self.license.to_dict() if self.license else None,
            "files": [f.to_dict() for f in self.files],
            "download_url": self.download_url,
            "tags": self.tags,
            "likes": self.likes,
            "downloads": self.downloads,
            "published_at": self.published_at,
            "keyword": self.keyword,
            "group": self.group,
            "group_slug": self.group_slug,
            "also_on": self.also_on,
        }


def normalize_title(title: str) -> str:
    """Titre réduit à ses mots significatifs, sans accent ni ponctuation."""
    txt = unicodedata.normalize("NFKD", title or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c)).lower()
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def slugify(value: str) -> str:
    slug = normalize_title(value).replace(" ", "-")
    return slug or "divers"
