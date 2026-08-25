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
    """Client HTTP avec throttling adaptatif.

    Les APIs publiques limitent le débit (Thingiverse renvoie `429` avec un
    `Retry-After: 0` inexploitable). Le client ralentit donc tout seul quand
    les 429 arrivent, et réaccélère progressivement quand ça repasse.
    """

    def __init__(self, user_agent: str, timeout: float = 30.0, delay: float = 0.8,
                 max_retries: int = 3, debug: bool = False,
                 retry_base: float = 2.0, max_delay: float = 8.0) -> None:
        self.base_delay = delay
        self.delay = delay
        self.max_delay = max(max_delay, delay)
        self.retry_base = retry_base
        self.max_retries = max_retries
        self.debug = debug
        self.throttled = 0            # nombre de réponses 429/503 rencontrées
        self._ok_streak = 0
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
    def set_pace(self, delay: float) -> None:
        """Fixe le rythme de base (appelé par plateforme)."""
        self.base_delay = delay
        self.delay = max(delay, 0.0)
        self._ok_streak = 0

    def _slow_down(self, reason: str) -> None:
        """Ralentit durablement après un refus pour excès de requêtes."""
        self.throttled += 1
        new_delay = min(self.delay * 1.6 + 0.2, self.max_delay)
        if new_delay > self.delay + 0.05:
            log.warning("ralentissement automatique : %.1f s → %.1f s entre requêtes (%s)",
                        self.delay, new_delay, reason)
            self.delay = new_delay
        self._ok_streak = 0

    def _speed_up(self) -> None:
        """Revient doucement au rythme normal après une série de succès."""
        self._ok_streak += 1
        if self._ok_streak >= 30 and self.delay > self.base_delay:
            self.delay = max(self.base_delay, self.delay * 0.8)
            self._ok_streak = 0

    def _retry_pause(self, resp: httpx.Response, attempt: int) -> float:
        """Attente avant nouvelle tentative : jamais nulle, jamais absurde.

        `Retry-After` est pris en compte quand il est exploitable ; Thingiverse
        renvoie `0`, qui doit être ignoré au profit du backoff exponentiel.
        """
        hint = (resp.headers.get("Retry-After") or "").strip()
        suggested = float(hint) if hint.isdigit() else 0.0
        backoff = self.retry_base * (2 ** (attempt - 1))
        return min(max(suggested, backoff, self.delay), 60.0)

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
                    if resp.status_code in (429, 503):
                        self._slow_down(f"HTTP {resp.status_code}")
                    pause = self._retry_pause(resp, attempt)
                    log.warning("%s %s : HTTP %s, nouvelle tentative dans %.0f s (%s/%s)",
                                method, url, resp.status_code, pause, attempt, self.max_retries)
                    last_exc = HttpError(f"HTTP {resp.status_code} sur {url}")
                    time.sleep(pause)
                    continue
                if resp.status_code >= 400:
                    body = resp.text[:300] if self.debug else ""
                    raise HttpError(f"HTTP {resp.status_code} sur {url} {body}")
                self._speed_up()
                return resp
            time.sleep(min(self.retry_base * (2 ** (attempt - 1)) + random.random(), 60.0))
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
