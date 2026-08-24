"""Découverte automatique des familles de modèles (infinity cube, planetary gear…).

Aucune liste de familles n'est codée en dur : on extrait les expressions
(1 à 3 mots) qui reviennent le plus souvent dans les titres, on garde celles
qui atteignent un seuil, et chaque modèle rejoint l'expression la plus
précise qui le décrit.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .models import Model, normalize_title, slugify

# Mots trop génériques pour nommer une famille.
STOPWORDS = {
    # anglais courant
    "a", "an", "the", "of", "for", "and", "or", "with", "without", "in", "on", "at",
    "to", "by", "from", "my", "your", "this", "that", "it", "its", "you", "no", "not",
    # vocabulaire impression 3d
    "3d", "print", "printed", "printable", "printer", "printing", "printinplace",
    "place", "stl", "3mf", "step", "gcode", "file", "files", "model", "models",
    "support", "supports", "supported", "free", "easy", "quick", "fast", "simple",
    "multicolor", "multicolour", "color", "colour", "colors", "multi", "single",
    "filament", "ams", "spool", "bambu", "prusa", "creality", "ender", "elegoo",
    "remix", "version", "edition", "update", "updated", "upgrade", "improved",
    "better", "best", "new", "ultimate", "super", "mega", "giant", "mini", "micro",
    "tiny", "small", "big", "large", "xl", "xxl", "custom", "customizable", "diy",
    "cool", "awesome", "amazing", "nice", "fun", "funny", "satisfying", "perfect",
    "gift", "kids", "kid", "adult", "adults", "office", "desk", "pocket", "toy",
    "toys", "fidget", "fidgets", "sensory", "anti", "stress", "antistress", "asmr",
    "part", "parts", "set", "kit", "pack", "pieces", "piece", "assembly", "assembled",
    # français
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "avec", "sans", "pour",
    "jouet", "jouets", "imprimable", "imprime", "impression", "facile", "gratuit",
    "anneau", "petit", "grand",
}

# Tokens sans intérêt (versions, dimensions, nombres seuls…)
JUNK = re.compile(r"^(v\d+|\d+(mm|cm|x\d+)?|\d+)$")


@dataclass
class Group:
    """Une famille détectée (ex. « Infinity Cube »)."""

    key: str
    label: str
    slug: str
    models: list[Model] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.models)

    @property
    def sellable_count(self) -> int:
        return sum(1 for m in self.models if m.license and m.license.sellable == "yes")

    @property
    def sources(self) -> list[str]:
        return sorted({m.source_label for m in self.models})

    @property
    def cover(self) -> str:
        for m in self.models:
            if m.local_image or m.image:
                return m.local_image or m.image
        return ""


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _tokens(title: str) -> list[str]:
    words = normalize_title(title).split()
    return [w for w in words if w not in STOPWORDS and not JUNK.match(w) and len(w) > 2]


def _candidates(tokens: list[str], max_n: int = 3) -> list[tuple[str, str]]:
    """Expressions candidates (clé normalisée, libellé), de la plus longue à la plus courte."""
    out: list[tuple[str, str]] = []
    for n in range(min(max_n, len(tokens)), 0, -1):
        for i in range(len(tokens) - n + 1):
            chunk = tokens[i:i + n]
            key = " ".join(_singular(w) for w in chunk)
            out.append((key, " ".join(chunk)))
    return out


def discover_groups(models: list[Model], min_size: int = 3) -> list[Group]:
    """Regroupe les modèles par famille détectée automatiquement."""
    if not models:
        return []

    cand_by_model: dict[str, list[tuple[str, str]]] = {}
    doc_freq: Counter[str] = Counter()
    labels: dict[str, Counter[str]] = defaultdict(Counter)

    for model in models:
        cands = _candidates(_tokens(model.title))
        cand_by_model[model.uid] = cands
        for key, label in dict(cands).items():
            doc_freq[key] += 1
            labels[key][label] += 1

    eligible = {k for k, c in doc_freq.items() if c >= min_size}

    # Attribution itérative : les familles trop petites après attribution
    # sont retirées et leurs modèles redistribués.
    assignment: dict[str, str] = {}
    while True:
        assignment = {}
        for model in models:
            for key, _label in cand_by_model[model.uid]:
                if key in eligible:
                    assignment[model.uid] = key
                    break
        counts = Counter(assignment.values())
        too_small = {k for k, c in counts.items() if c < min_size}
        if not too_small:
            break
        eligible -= too_small
        if not eligible:
            break

    groups: dict[str, Group] = {}
    others = Group(key="_divers", label="Divers / modèles isolés", slug="divers")
    for model in models:
        key = assignment.get(model.uid)
        if key:
            label = labels[key].most_common(1)[0][0].title()
            group = groups.setdefault(key, Group(key=key, label=label, slug=slugify(label)))
        else:
            group = others
        group.models.append(model)
        model.group = group.label
        model.group_slug = group.slug

    ordered = sorted(groups.values(), key=lambda g: (-g.size, g.label))
    for group in ordered:
        group.models.sort(key=lambda m: (-m.downloads, -m.likes, m.title.lower()))
    if others.models:
        others.models.sort(key=lambda m: (-m.downloads, -m.likes, m.title.lower()))
        ordered.append(others)
    return ordered


def tag_duplicates(models: list[Model]) -> None:
    """Marque les modèles au titre identique publiés sur plusieurs plateformes."""
    by_fingerprint: dict[str, list[Model]] = defaultdict(list)
    for model in models:
        if model.fingerprint:
            by_fingerprint[model.fingerprint].append(model)
    for group in by_fingerprint.values():
        if len(group) < 2:
            continue
        for model in group:
            model.also_on = sorted({m.source_label for m in group if m.source != model.source})
