"""Jeu de données local pour tester le rapport sans réseau ni clé d'API.

Ces fiches sont fictives : elles servent uniquement à vérifier le rendu,
le regroupement automatique et l'analyse de licence (`--demo`).
"""

from __future__ import annotations

from urllib.parse import quote

from .models import Model, ModelFile

_PALETTE = {"thingiverse": "#38bdf8", "printables": "#fb923c",
            "makerworld": "#a78bfa", "crealitycloud": "#34d399"}


def _placeholder(title: str, source: str) -> str:
    color = _PALETTE.get(source, "#4ea1ff")
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300'>"
        f"<rect width='400' height='300' fill='#1c232d'/>"
        f"<circle cx='200' cy='130' r='60' fill='none' stroke='{color}' stroke-width='6'/>"
        f"<text x='200' y='145' font-family='sans-serif' font-size='42' fill='{color}'"
        " text-anchor='middle'>DEMO</text>"
        f"<text x='200' y='250' font-family='sans-serif' font-size='18' fill='#9aa7b4'"
        f" text-anchor='middle'>{title[:28]}</text></svg>"
    )
    return "data:image/svg+xml;utf8," + quote(svg)


_ROWS = [
    # (source, id, titre, licence, auteur, downloads, likes)
    ("thingiverse", "1001", "Infinity Cube fidget toy", "Creative Commons - Attribution", "demo_maker", 48210, 3120),
    ("printables", "2001", "Infinity Cube print in place", "CC-BY-SA", "demo_printer", 31200, 2410),
    ("makerworld", "3001", "Infinity Cube V2 multicolor", "CC BY-NC", "demo_bambu", 21870, 1980),
    ("crealitycloud", "4001", "Infinity Cube smooth edition", "", "demo_creality", 5400, 320),
    ("thingiverse", "1002", "Planetary Gear fidget", "Creative Commons - Attribution - Non-Commercial", "gear_guy", 27600, 1750),
    ("printables", "2002", "Planetary Gear bearing toy", "CC0", "gear_lab", 19850, 1520),
    ("makerworld", "3002", "Planetary Gear keychain", "Standard Digital File License", "mw_designer", 15400, 990),
    ("printables", "2003", "Planetary Gear desk spinner", "CC-BY", "gear_lab", 8700, 640),
    ("thingiverse", "1003", "Fidget Spinner classic three arms", "Creative Commons - Attribution - Share Alike", "spinner_shop", 65400, 4200),
    ("printables", "2004", "Fidget Spinner no bearing", "CC-BY-ND", "spinner_shop", 24300, 1810),
    ("makerworld", "3003", "Fidget Spinner tri blade", "CC BY", "mw_designer", 17600, 1230),
    ("crealitycloud", "4002", "Fidget Spinner glow", "CC BY-NC-SA", "cc_user", 4300, 260),
    ("thingiverse", "1004", "Fidget Slider magnetic", "GPL-3.0", "slider_dev", 12300, 870),
    ("printables", "2005", "Fidget Slider pocket", "CC-BY", "slider_dev", 9800, 720),
    ("makerworld", "3004", "Fidget Slider snap", "CC BY-SA", "mw_designer", 7600, 540),
    ("thingiverse", "1005", "Gear Cube puzzle", "Creative Commons - Public Domain Dedication", "puzzle_pro", 15600, 1120),
    ("printables", "2006", "Gear Cube mini", "CC-BY-NC-ND", "puzzle_pro", 6400, 410),
    ("makerworld", "3005", "Gear Cube articulated", "CC BY", "mw_designer", 5200, 380),
    ("thingiverse", "1006", "Articulated Dragon flexi", "Creative Commons - Attribution", "flexi_maker", 98400, 7600),
    ("printables", "2007", "Hexagonal fidget ring", "CC-BY-SA", "ring_maker", 3400, 220),
    ("crealitycloud", "4003", "Bike chain fidget bracelet", "", "cc_user", 2100, 140),
    ("makerworld", "3006", "Tiny fidget dice tower", "BSDL", "mw_designer", 1800, 95),
]


def demo_models() -> list[Model]:
    models: list[Model] = []
    for source, sid, title, license_raw, creator, downloads, likes in _ROWS:
        model = Model(
            source=source,
            source_id=sid,
            url=f"https://example.invalid/{source}/{sid}",
            title=title,
            description=(f"Fiche de démonstration pour « {title} ». Le texte réel provient "
                         "de la description publiée par l'auteur sur la plateforme."),
            creator=creator,
            creator_url=f"https://example.invalid/{source}/u/{creator}",
            license_raw=license_raw,
            downloads=downloads,
            likes=likes,
            published_at="2025-11-02",
            keyword="fidget toy",
            files=[ModelFile(name=f"{title.split()[0].lower()}.stl",
                             url=f"https://example.invalid/{source}/{sid}/file.stl",
                             size=2_400_000, kind="STL")],
            download_url=f"https://example.invalid/{source}/{sid}/download",
        )
        model.local_image = _placeholder(title, source)
        models.append(model)
    return models
