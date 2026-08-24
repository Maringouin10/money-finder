"""Connecteurs par plateforme."""

from .base import Source
from .crealitycloud import CrealityCloudSource
from .makerworld import MakerWorldSource
from .printables import PrintablesSource
from .thingiverse import ThingiverseSource

REGISTRY: dict[str, type[Source]] = {
    "thingiverse": ThingiverseSource,
    "printables": PrintablesSource,
    "makerworld": MakerWorldSource,
    "crealitycloud": CrealityCloudSource,
}

__all__ = ["Source", "REGISTRY", "ThingiverseSource", "PrintablesSource",
           "MakerWorldSource", "CrealityCloudSource"]
