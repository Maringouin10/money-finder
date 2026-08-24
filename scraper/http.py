"""Client HTTP partagé : retries, backoff, throttling, téléchargement d'images."""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("money-finder.http")


class HttpError(RuntimeError):
    pass


class Http:
    def __init__(self, user_agent: str, timeout: float = 30.0, delay: float = 0.8,
                 max_retries: int = 3, debug: bool = False) -> None:
        self.delay = delay
        self.max_retries = max_retries
        self.debug = debug
        self._last_call = 0.0
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            },
        )

    # ------------------------------------------------------------------
    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Http":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    def _throttle(self) -> None:
        wait = self.delay - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self.client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                last_exc = exc
                log.warning("%s %s : erreur réseau (%s) tentative %s/%s",
                            method, url, exc.__class__.__name__, attempt, self.max_retries)
            else:
                if resp.status_code in (429, 500, 502, 503, 504):
                    retry_after = resp.headers.get("Retry-After")
                    pause = float(retry_after) if (retry_after or "").isdigit() else 2 ** attempt
                    log.warning("%s %s : HTTP %s, nouvelle tentative dans %.0fs",
                                method, url, resp.status_code, pause)
                    last_exc = HttpError(f"HTTP {resp.status_code} sur {url}")
                    time.sleep(pause)
                    continue
                if resp.status_code >= 400:
                    body = resp.text[:300] if self.debug else ""
                    raise HttpError(f"HTTP {resp.status_code} sur {url} {body}")
                return resp
            time.sleep(2 ** attempt + random.random())
        raise HttpError(f"Échec après {self.max_retries} tentatives : {url} ({last_exc})")

    # ------------------------------------------------------------------
    def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = self.request("GET", url, **kwargs)
        try:
            return resp.json()
        except ValueError as exc:
            raise HttpError(f"Réponse non-JSON depuis {url}") from exc

    def post_json(self, url: str, json: Any, **kwargs: Any) -> Any:
        resp = self.request("POST", url, json=json, **kwargs)
        try:
            return resp.json()
        except ValueError as exc:
            raise HttpError(f"Réponse non-JSON depuis {url}") from exc

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self.request("GET", url, **kwargs).text

    # ------------------------------------------------------------------
    def download(self, url: str, dest: Path) -> bool:
        """Télécharge un fichier (image) ; renvoie False en cas d'échec."""
        if not url:
            return False
        try:
            resp = self.request("GET", url)
        except Exception as exc:  # noqa: BLE001 - une image manquante ne doit rien casser
            log.debug("image non téléchargée %s (%s)", url, exc)
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return True
