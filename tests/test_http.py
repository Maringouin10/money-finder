"""Comportement du client HTTP face aux limitations de débit (429)."""

from __future__ import annotations

import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scraper.http import Http, HttpError


class FlakyHandler(BaseHTTPRequestHandler):
    """Répond 429 avec `Retry-After: 0` (comme Thingiverse) puis 200."""

    fails_left = 0
    hits = 0

    def do_GET(self):  # noqa: N802
        FlakyHandler.hits += 1
        if FlakyHandler.fails_left > 0:
            FlakyHandler.fails_left -= 1
            self.send_response(429)
            self.send_header("Retry-After", "0")      # valeur inexploitable
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TestRateLimitHandling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FlakyHandler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _http(self, **kwargs):
        params = dict(user_agent="test", delay=0.0, max_retries=3, retry_base=0.05,
                      max_delay=0.4)
        params.update(kwargs)
        return Http(**params)

    def test_retry_after_zero_never_means_no_wait(self):
        FlakyHandler.fails_left, FlakyHandler.hits = 2, 0
        http = self._http()
        start = time.monotonic()
        data = http.get_json(f"http://127.0.0.1:{self.port}/x")
        elapsed = time.monotonic() - start
        http.close()

        self.assertEqual(data, {"ok": True})
        self.assertEqual(FlakyHandler.hits, 3)
        # backoff réel : 0.05 puis 0.10 (au lieu de 0 s auparavant)
        self.assertGreaterEqual(elapsed, 0.15)

    def test_429_slows_the_client_down(self):
        FlakyHandler.fails_left, FlakyHandler.hits = 2, 0
        http = self._http(delay=0.1)
        http.get_json(f"http://127.0.0.1:{self.port}/x")
        self.assertGreater(http.delay, 0.1)          # ralentissement appliqué
        self.assertEqual(http.throttled, 2)
        http.close()

    def test_set_pace_resets_the_rhythm_per_platform(self):
        http = self._http(delay=0.1)
        http.delay = 0.4
        http.set_pace(1.1)
        self.assertEqual(http.delay, 1.1)
        self.assertEqual(http.base_delay, 1.1)
        http.close()

    def test_gives_up_after_max_retries(self):
        FlakyHandler.fails_left, FlakyHandler.hits = 10, 0
        http = self._http(max_retries=2)
        with self.assertRaises(HttpError):
            http.get_json(f"http://127.0.0.1:{self.port}/x")
        self.assertEqual(FlakyHandler.hits, 2)
        http.close()


if __name__ == "__main__":
    unittest.main()
