"""Configuration : variables d'environnement (.env) + arguments CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ALL_SOURCES = ["thingiverse", "printables", "makerworld", "crealitycloud"]

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = _env(name).lower()
    if not val:
        return default
    return val in {"1", "true", "yes", "oui", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = _env(name)
    if not raw:
        return list(default)
    return [v.strip() for v in raw.split(",") if v.strip()]


@dataclass
class Settings:
    # --- recherche -------------------------------------------------------
    keywords: list[str] = field(default_factory=lambda: ["fidget toy"])
    sources: list[str] = field(default_factory=lambda: list(ALL_SOURCES))
    limit_per_keyword: int = 60
    commercial_only: bool = False
    include_unknown: bool = True
    min_group_size: int = 3

    # --- sortie ----------------------------------------------------------
    output_dir: Path = Path("output")
    download_images: bool = True
    enrich: bool = True
    demo: bool = False

    # --- réseau ----------------------------------------------------------
    timeout: float = 30.0
    delay: float = 0.8
    max_retries: int = 3
    user_agent: str = DEFAULT_UA
    debug: bool = False

    # --- clés / endpoints ------------------------------------------------
    thingiverse_token: str = ""
    thingiverse_api: str = "https://api.thingiverse.com"
    printables_api: str = "https://api.printables.com/graphql/"
    makerworld_api: str = "https://makerworld.com/api/v1"
    crealitycloud_api: str = "https://www.crealitycloud.com"
    crealitycloud_web: str = "https://www.crealitycloud.com"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            keywords=_env_list("KEYWORDS", ["fidget toy"]),
            sources=[s.lower() for s in _env_list("SOURCES", ALL_SOURCES)],
            limit_per_keyword=_env_int("LIMIT_PER_KEYWORD", 60),
            commercial_only=_env_bool("COMMERCIAL_ONLY", False),
            include_unknown=_env_bool("INCLUDE_UNKNOWN_LICENSE", True),
            min_group_size=_env_int("MIN_GROUP_SIZE", 3),
            output_dir=Path(_env("OUTPUT_DIR", "output")),
            download_images=_env_bool("DOWNLOAD_IMAGES", True),
            enrich=_env_bool("ENRICH_DETAILS", True),
            timeout=_env_float("REQUEST_TIMEOUT", 30.0),
            delay=_env_float("REQUEST_DELAY", 0.8),
            max_retries=_env_int("MAX_RETRIES", 3),
            user_agent=_env("USER_AGENT", DEFAULT_UA),
            debug=_env_bool("DEBUG", False),
            thingiverse_token=_env("THINGIVERSE_TOKEN") or _env("THINGIVERSE_API_KEY"),
            thingiverse_api=_env("THINGIVERSE_API", "https://api.thingiverse.com"),
            printables_api=_env("PRINTABLES_API", "https://api.printables.com/graphql/"),
            makerworld_api=_env("MAKERWORLD_API", "https://makerworld.com/api/v1"),
            crealitycloud_api=_env("CREALITYCLOUD_API", "https://www.crealitycloud.com"),
            crealitycloud_web=_env("CREALITYCLOUD_WEB", "https://www.crealitycloud.com"),
        )
