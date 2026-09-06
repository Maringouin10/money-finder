"""Orchestration : collecte → enrichissement → filtrage → regroupement → rapport."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from .config import Settings
from .grouping import discover_groups, tag_duplicates
from .http import Http
from .licenses import Sellable
from .models import Model
from .report import ReportData, download_images, write_report
from .sources import REGISTRY

log = logging.getLogger("money-finder")

OnModel = Callable[[Model], None]


def collect(
    settings: Settings, http: Http, on_model: OnModel | None = None,
) -> tuple[list[Model], list[str]]:
    models: dict[str, Model] = {}
    warnings: list[str] = []

    needy = [REGISTRY[n].label for n in settings.sources
             if n in REGISTRY and REGISTRY[n].needs_enrich]
    if needy and not settings.enrich:
        warnings.append(
            "ENRICH_DETAILS désactivé : licences, descriptions et fichiers sont "
            f"incomplets pour {', '.join(needy)} (leur recherche ne les renvoie pas)."
        )

    for name in settings.sources:
        cls = REGISTRY.get(name)
        if cls is None:
            warnings.append(f"source inconnue ignorée : {name}")
            continue
        source = cls(settings, http)
        http.set_pace(max(settings.delay, source.min_delay))
        ok, reason = source.available()
        if not ok:
            log.warning("[%s] désactivée : %s", name, reason)
            warnings.append(f"{source.label} désactivée : {reason}")
            continue

        found_before = len(models)
        for keyword in settings.keywords:
            log.info("[%s] recherche « %s »…", name, keyword)
            try:
                results = list(source.search(keyword, settings.limit_per_keyword))
            except Exception as exc:  # noqa: BLE001 - une source cassée ne bloque pas le reste
                log.error("[%s] recherche « %s » échouée : %s", name, keyword, exc)
                warnings.append(f"{source.label} · « {keyword} » : {exc}")
                continue
            for model in results:
                if model.source_id and model.title and model.uid not in models:
                    models[model.uid] = model
                    if on_model:
                        on_model(model)
            log.info("[%s] « %s » : %s résultats", name, keyword, len(results))

        new_models = [m for m in models.values() if m.source == name]
        if settings.enrich:
            for index, model in enumerate(new_models, 1):
                try:
                    source.enrich(model)
                except Exception as exc:  # noqa: BLE001
                    log.debug("[%s] enrichissement %s échoué : %s", name, model.source_id, exc)
                else:
                    if on_model:
                        on_model(model)
                if index % 25 == 0:
                    log.info("[%s] détails récupérés : %s/%s", name, index, len(new_models))
        log.info("[%s] terminé : %s modèles", name, len(models) - found_before)
        if http.throttled:
            warnings.append(
                f"{source.label} : {http.throttled} refus pour excès de requêtes (429/503). "
                f"Le rythme a été ralenti automatiquement à {http.delay:.1f} s. "
                "Réduire LIMIT_PER_KEYWORD ou augmenter REQUEST_DELAY pour les éviter."
            )
            http.throttled = 0
        warnings.extend(f"{source.label} : {w}" for w in source.warnings[:10])

    return list(models.values()), warnings


def filter_models(models: list[Model], settings: Settings) -> list[Model]:
    if not settings.commercial_only:
        return models
    allowed = {Sellable.YES.value, Sellable.CONDITIONS.value}
    if settings.include_unknown:
        allowed.add(Sellable.UNKNOWN.value)
    kept = [m for m in models if m.license and m.license.sellable in allowed]
    log.info("filtre commercial : %s/%s modèles conservés", len(kept), len(models))
    return kept


def run(settings: Settings, on_model: OnModel | None = None) -> dict[str, Path]:
    if settings.demo:
        from .demo_data import demo_models
        models, warnings = demo_models(), []
        log.info("mode démonstration : %s modèles d'exemple", len(models))
        if on_model:
            for model in models:
                on_model(model)
        http = None
    else:
        http = Http(user_agent=settings.user_agent, timeout=settings.timeout,
                    delay=settings.delay, max_retries=settings.max_retries,
                    debug=settings.debug, retry_base=settings.retry_base,
                    max_delay=settings.max_delay)
        models, warnings = collect(settings, http, on_model=on_model)

    models = filter_models(models, settings)
    models.sort(key=lambda m: (-m.downloads, -m.likes, m.title.lower()))
    tag_duplicates(models)
    groups = discover_groups(models, settings.min_group_size)
    log.info("%s familles détectées", len(groups))

    if settings.download_images and http is not None:
        download_images(models, http, settings.output_dir)
    if http is not None:
        http.close()

    data = ReportData(models=models, groups=groups, keywords=settings.keywords,
                      sources=[REGISTRY[s].label for s in settings.sources if s in REGISTRY],
                      warnings=warnings, demo=settings.demo)
    written = write_report(data, settings.output_dir)
    for name, path in written.items():
        log.info("écrit : %s", path)
    return written
