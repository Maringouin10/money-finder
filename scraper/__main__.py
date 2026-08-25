"""Point d'entrée CLI : python -m scraper [options]."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import ALL_SOURCES, Settings
from .pipeline import run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="money-finder",
        description="Scrape MakerWorld, Creality Cloud, Printables et Thingiverse, "
                    "analyse les licences et produit un compte rendu HTML.",
    )
    p.add_argument("-k", "--keywords", help="mots-clés séparés par des virgules "
                                            "(défaut : KEYWORDS du .env)")
    p.add_argument("-s", "--sources", help=f"plateformes à interroger parmi {', '.join(ALL_SOURCES)}")
    p.add_argument("-l", "--limit", type=int, help="nombre de modèles par mot-clé et par plateforme")
    p.add_argument("-o", "--output", help="dossier de sortie du rapport")
    p.add_argument("--commercial-only", action="store_true",
                   help="ne garder que les modèles exploitables commercialement")
    p.add_argument("--strict", action="store_true",
                   help="avec --commercial-only : exclure aussi les licences non identifiées")
    p.add_argument("--min-group-size", type=int, help="taille minimale d'une famille (défaut 3)")
    p.add_argument("--no-images", action="store_true", help="ne pas télécharger les vignettes")
    p.add_argument("--no-enrich", action="store_true",
                   help="ne pas ouvrir les pages détail (plus rapide, licences incomplètes)")
    p.add_argument("--demo", action="store_true",
                   help="génère un rapport d'exemple hors-ligne (sans API ni réseau)")
    p.add_argument("-v", "--verbose", action="store_true", help="journal détaillé")
    return p


def settings_from_args(argv: list[str] | None = None) -> Settings:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()

    if args.keywords:
        settings.keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if args.sources:
        settings.sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    if args.limit:
        settings.limit_per_keyword = args.limit
    if args.output:
        settings.output_dir = Path(args.output)
    if args.min_group_size:
        settings.min_group_size = args.min_group_size
    if args.commercial_only:
        settings.commercial_only = True
    if args.strict:
        settings.include_unknown = False
    if args.no_images:
        settings.download_images = False
    if args.no_enrich:
        settings.enrich = False
    if args.demo:
        settings.demo = True
    if args.verbose:
        settings.debug = True

    unknown = [s for s in settings.sources if s not in ALL_SOURCES]
    if unknown:
        print(f"Sources inconnues : {', '.join(unknown)} (valides : {', '.join(ALL_SOURCES)})",
              file=sys.stderr)
        settings.sources = [s for s in settings.sources if s in ALL_SOURCES]
    return settings


def main(argv: list[str] | None = None) -> int:
    settings = settings_from_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if not settings.sources:
        print("Aucune source valide sélectionnée.", file=sys.stderr)
        return 2

    written = run(settings)
    index = written.get("index.html")
    print("\nRapport prêt :")
    print(f"  • page « tous les modèles »  : {index}")
    print(f"  • page « par famille »       : {written.get('groupes.html')}")
    print(f"  • exports                    : {written.get('models.csv')} / {written.get('models.json')}")
    print("\nAffichage : docker compose up web  →  http://localhost:8081")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
