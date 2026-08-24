"""Normalisation des licences et évaluation du droit de vente.

Chaque plateforme renvoie la licence sous une forme différente
("Creative Commons - Attribution", "CC-BY-NC-SA", "BSDL", ...).
Ce module ramène tout ça à un code canonique + un verdict commercial.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from enum import Enum


class Sellable(str, Enum):
    """Peut-on vendre les impressions issues du modèle ?"""

    YES = "yes"              # vente libre (attribution éventuelle)
    CONDITIONS = "conditions"  # vente possible mais avec contraintes fortes
    NO = "no"                # vente interdite
    UNKNOWN = "unknown"      # licence absente ou non reconnue -> à vérifier


LABELS_FR = {
    Sellable.YES: "Vendable",
    Sellable.CONDITIONS: "Vendable sous conditions",
    Sellable.NO: "Vente interdite",
    Sellable.UNKNOWN: "À vérifier",
}

CC_URLS = {
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-ND": "https://creativecommons.org/licenses/by-nd/4.0/",
    "CC-BY-NC": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC-BY-NC-SA": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC-BY-NC-ND": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
}


@dataclass
class LicenseInfo:
    raw: str                 # texte brut renvoyé par la plateforme
    code: str                # code canonique (CC-BY-SA, GPL-3.0, SDFL, ...)
    name: str                # libellé lisible
    url: str                 # lien vers le texte de la licence
    sellable: str            # valeur de Sellable
    attribution: bool        # crédit auteur obligatoire
    share_alike: bool        # partage à l'identique obligatoire
    no_derivatives: bool     # modification interdite
    note: str                # explication en français

    @property
    def label(self) -> str:
        return LABELS_FR[Sellable(self.sellable)]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["label"] = self.label
        return d


def _flatten(raw: str) -> str:
    """minuscule, sans accent, séparateurs unifiés en espace."""
    txt = unicodedata.normalize("NFKD", raw or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", txt).strip()


def _has(flat: str, *words: str) -> bool:
    return any(re.search(rf"(^| ){re.escape(w)}( |$)", flat) for w in words)


def normalize(raw: str | None, source: str = "") -> LicenseInfo:
    """Transforme un intitulé de licence brut en LicenseInfo."""
    raw = (raw or "").strip()
    flat = _flatten(raw)

    if not flat:
        return LicenseInfo(
            raw="", code="UNKNOWN", name="Licence non renseignée", url="",
            sellable=Sellable.UNKNOWN.value, attribution=False, share_alike=False,
            no_derivatives=False,
            note="La plateforme n'a pas renvoyé de licence : vérifier sur la page du modèle avant toute vente.",
        )

    # --- Domaine public / CC0 ---------------------------------------------
    if _has(flat, "cc0", "cc 0") or "public domain" in flat or "publicdomain" in flat or _has(flat, "zero"):
        return LicenseInfo(
            raw=raw, code="CC0", name="CC0 / Domaine public", url=CC_URLS["CC0"],
            sellable=Sellable.YES.value, attribution=False, share_alike=False,
            no_derivatives=False,
            note="Domaine public : vente des impressions et des dérivés libre, aucune obligation.",
        )

    # --- Licences propriétaires / fichiers standard ------------------------
    proprietary = (
        "standard digital file" in flat
        or _has(flat, "sdfl", "sdl")
        or "all rights reserved" in flat
        or _has(flat, "proprietary", "propriete", "commercial use prohibited")
    )
    if proprietary:
        return LicenseInfo(
            raw=raw, code="SDFL", name="Licence fichier standard / tous droits réservés", url="",
            sellable=Sellable.NO.value, attribution=True, share_alike=False, no_derivatives=True,
            note="Usage personnel uniquement. Vendre les impressions demande l'accord écrit de l'auteur.",
        )

    # --- Creative Commons --------------------------------------------------
    is_cc = "creative commons" in flat or re.search(r"(^| )cc( |-|$)", flat) is not None
    nc = _has(flat, "nc") or "non commercial" in flat or "noncommercial" in flat
    nd = _has(flat, "nd") or "no derivative" in flat or "no derivatives" in flat or "noderiv" in flat
    sa = _has(flat, "sa") or "share alike" in flat or "sharealike" in flat
    by = _has(flat, "by") or "attribution" in flat

    if is_cc or nc or nd or sa:
        parts = ["CC"]
        if by or not (nc or nd or sa):
            parts.append("BY")
        if nc:
            parts.append("NC")
        if sa:
            parts.append("SA")
        if nd:
            parts.append("ND")
        code = "-".join(parts)
        url = CC_URLS.get(code, "https://creativecommons.org/licenses/")

        if nc:
            return LicenseInfo(
                raw=raw, code=code, name=f"Creative Commons {code}", url=url,
                sellable=Sellable.NO.value, attribution=by, share_alike=sa, no_derivatives=nd,
                note="Clause NonCommercial : interdit de vendre les impressions ou les dérivés.",
            )
        if nd:
            return LicenseInfo(
                raw=raw, code=code, name=f"Creative Commons {code}", url=url,
                sellable=Sellable.CONDITIONS.value, attribution=True, share_alike=False, no_derivatives=True,
                note="Vente des impressions du modèle tel quel autorisée avec crédit auteur, "
                     "mais toute modification/remix est interdite.",
            )
        if sa:
            return LicenseInfo(
                raw=raw, code=code, name=f"Creative Commons {code}", url=url,
                sellable=Sellable.CONDITIONS.value, attribution=True, share_alike=True, no_derivatives=False,
                note="Vente autorisée avec crédit auteur ; toute version modifiée doit être "
                     "repartagée sous la même licence.",
            )
        return LicenseInfo(
            raw=raw, code=code, name=f"Creative Commons {code}", url=url,
            sellable=Sellable.YES.value, attribution=True, share_alike=False, no_derivatives=False,
            note="Vente autorisée, crédit de l'auteur obligatoire (nom + lien vers le modèle).",
        )

    # --- Licences logicielles / libres ------------------------------------
    if _has(flat, "gpl", "gplv2", "gplv3", "agpl", "lgpl") or "general public license" in flat:
        code = "GPL"
        if "3" in flat:
            code = "GPL-3.0"
        elif "2" in flat:
            code = "GPL-2.0"
        if _has(flat, "lgpl"):
            code = "LGPL"
        return LicenseInfo(
            raw=raw, code=code, name=f"{code} (GNU)", url="https://www.gnu.org/licenses/",
            sellable=Sellable.CONDITIONS.value, attribution=True, share_alike=True, no_derivatives=False,
            note="Vente autorisée ; les sources/fichiers modifiés doivent rester sous la même licence.",
        )

    if _has(flat, "mit", "bsd", "apache", "unlicense", "wtfpl", "zlib"):
        code = next(w.upper() for w in ("mit", "bsd", "apache", "unlicense", "wtfpl", "zlib") if _has(flat, w))
        return LicenseInfo(
            raw=raw, code=code, name=f"Licence {code}", url="",
            sellable=Sellable.YES.value, attribution=True, share_alike=False, no_derivatives=False,
            note="Licence permissive : vente autorisée, conserver la mention de licence d'origine.",
        )

    # --- BSDL (Bambu Studio Design License, MakerWorld) --------------------
    if _has(flat, "bsdl") or "bambu" in flat:
        return LicenseInfo(
            raw=raw, code="BSDL", name="Bambu Studio Design License", url="",
            sellable=Sellable.NO.value, attribution=True, share_alike=False, no_derivatives=True,
            note="Licence maison MakerWorld : usage personnel, exploitation commerciale non accordée par défaut.",
        )

    return LicenseInfo(
        raw=raw, code="UNKNOWN", name=raw, url="",
        sellable=Sellable.UNKNOWN.value, attribution=True, share_alike=False, no_derivatives=False,
        note="Licence non reconnue automatiquement : lire la page du modèle avant de vendre.",
    )
