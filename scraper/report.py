"""Génération du compte rendu : 2 pages HTML + exports JSON/CSV."""

from __future__ import annotations

import csv
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .grouping import Group
from .http import Http
from .licenses import LABELS_FR, Sellable
from .models import Model

log = logging.getLogger("money-finder.report")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

SELLABLE_ORDER = [Sellable.YES, Sellable.CONDITIONS, Sellable.UNKNOWN, Sellable.NO]


@dataclass
class ReportData:
    models: list[Model]
    groups: list[Group]
    keywords: list[str]
    sources: list[str]
    warnings: list[str] = field(default_factory=list)
    demo: bool = False
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or datetime.now().strftime("%d/%m/%Y à %H:%M")

    # -- statistiques ------------------------------------------------------
    @property
    def by_source(self) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for m in self.models:
            counts[m.source_label] = counts.get(m.source_label, 0) + 1
        return sorted(counts.items(), key=lambda kv: -kv[1])

    @property
    def by_license(self) -> list[tuple[str, str, int]]:
        """(valeur, libellé FR, nombre) dans l'ordre d'intérêt commercial."""
        out = []
        for status in SELLABLE_ORDER:
            count = sum(1 for m in self.models if m.license and m.license.sellable == status.value)
            out.append((status.value, LABELS_FR[status], count))
        return out

    @property
    def sellable_total(self) -> int:
        return sum(1 for m in self.models
                   if m.license and m.license.sellable in (Sellable.YES.value, Sellable.CONDITIONS.value))


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["number"] = lambda v: f"{int(v or 0):,}".replace(",", " ")
    env.filters["filesize"] = _filesize
    return env


def _filesize(value: int | None) -> str:
    if not value:
        return ""
    size = float(value)
    for unit in ("o", "ko", "Mo", "Go"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.0f} To"


def download_images(models: list[Model], http: Http, output_dir: Path) -> None:
    """Enregistre les vignettes en local pour un rapport consultable hors-ligne."""
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for model in models:
        if not model.image:
            continue
        ext = ".jpg"
        for candidate in (".png", ".webp", ".gif", ".jpeg", ".jpg"):
            if candidate in model.image.lower():
                ext = candidate
                break
        dest = images_dir / f"{model.source}-{model.image_key}{ext}"
        if dest.exists() or http.download(model.image, dest):
            model.local_image = f"images/{dest.name}"
            ok += 1
    log.info("vignettes enregistrées : %s/%s", ok, len(models))


def write_report(data: ReportData, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _env()

    assets_src = TEMPLATES_DIR / "assets"
    assets_dst = output_dir / "assets"
    if assets_dst.exists():
        shutil.rmtree(assets_dst)
    shutil.copytree(assets_src, assets_dst)

    pages = {
        "index.html": env.get_template("index.html"),
        "groupes.html": env.get_template("groupes.html"),
    }
    written: dict[str, Path] = {}
    for filename, template in pages.items():
        path = output_dir / filename
        path.write_text(template.render(data=data, page=filename), encoding="utf-8")
        written[filename] = path

    # exports bruts
    json_path = output_dir / "models.json"
    json_path.write_text(json.dumps(
        {
            "generated_at": data.generated_at,
            "keywords": data.keywords,
            "sources": data.sources,
            "warnings": data.warnings,
            "groups": [{"label": g.label, "slug": g.slug, "count": g.size} for g in data.groups],
            "models": [m.to_dict() for m in data.models],
        },
        ensure_ascii=False, indent=2), encoding="utf-8")
    written["models.json"] = json_path

    csv_path = output_dir / "models.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Famille", "Nom", "Plateforme", "Licence", "Vendable", "Auteur",
                         "Téléchargements", "Likes", "Image", "Fichiers 3D", "URL", "Description"])
        for m in data.models:
            lic = m.license
            writer.writerow([
                m.group, m.title, m.source_label,
                lic.code if lic else "", lic.label if lic else "",
                m.creator, m.downloads, m.likes, m.image,
                " | ".join(f"{f.name} <{f.url}>" for f in m.files) or m.download_url,
                m.url, m.excerpt,
            ])
    written["models.csv"] = csv_path
    return written
