"""Serveur du rapport avec collecte automatique (service `web`).

Au démarrage, si aucun rapport n'existe, la collecte est lancée toute seule
dans un thread. Tant qu'elle tourne, la racine affiche une page d'avancement
qui se rafraîchit et bascule sur le rapport dès qu'il est prêt.

Endpoints :
  GET  /            rapport, ou page d'avancement si une collecte est en cours
  GET  /index.html  toujours le rapport tel quel (même pendant une collecte)
  GET  /_status     état JSON {running, done, has_report, log, ...}
  POST /_run        relance une collecte (ignorée si une est déjà en cours)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from collections import deque
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Settings

log = logging.getLogger("money-finder.serve")

LOG_LINES = 300


class LogBuffer(logging.Handler):
    """Garde les dernières lignes de journal pour la page d'avancement."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: deque[str] = deque(maxlen=LOG_LINES)
        self.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


class Collector:
    """Pilote la collecte en arrière-plan (une seule à la fois)."""

    def __init__(self, settings: Settings, refresh_hours: float = 0.0) -> None:
        self.settings = settings
        self.refresh_hours = refresh_hours
        self.buffer = LogBuffer()
        logging.getLogger("money-finder").addHandler(self.buffer)
        self._lock = threading.Lock()
        self.running = False
        self.started_at = 0.0
        self.finished_at = 0.0
        self.error = ""
        self.runs = 0

    # ------------------------------------------------------------------
    @property
    def has_report(self) -> bool:
        return (self.settings.output_dir / "index.html").exists()

    def status(self) -> dict:
        return {
            "running": self.running,
            "has_report": self.has_report,
            "runs": self.runs,
            "error": self.error,
            "elapsed": int((self.finished_at or time.time()) - self.started_at)
            if self.started_at else 0,
            "log": list(self.buffer.lines)[-40:],
        }

    # ------------------------------------------------------------------
    def start(self, reason: str = "") -> bool:
        """Démarre une collecte si aucune n'est en cours."""
        with self._lock:
            if self.running:
                return False
            self.running = True
            self.started_at = time.time()
            self.finished_at = 0.0
            self.error = ""
        threading.Thread(target=self._run, args=(reason,), daemon=True).start()
        return True

    def _run(self, reason: str) -> None:
        from .pipeline import run                       # import tardif : évite un cycle
        log.info("collecte lancée%s", f" ({reason})" if reason else "")
        try:
            run(self.settings)
            log.info("collecte terminée, rapport disponible")
        except Exception as exc:                        # noqa: BLE001 - le serveur doit survivre
            self.error = f"{exc.__class__.__name__}: {exc}"
            log.exception("collecte interrompue : %s", exc)
        finally:
            self.running = False
            self.finished_at = time.time()
            self.runs += 1

    def schedule_refresh(self) -> None:
        """Relance la collecte toutes les N heures si REFRESH_HOURS > 0."""
        if self.refresh_hours <= 0:
            return

        def loop() -> None:
            while True:
                time.sleep(self.refresh_hours * 3600)
                self.start(reason="rafraîchissement planifié")

        threading.Thread(target=loop, daemon=True).start()
        log.info("rafraîchissement automatique toutes les %s h", self.refresh_hours)


STATUS_PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Collecte en cours — money-finder</title>
<style>
 :root{color-scheme:dark}
 body{margin:0;background:#0e1116;color:#e6edf3;
   font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
   display:grid;place-items:center;min-height:100vh;padding:24px}
 .box{width:min(860px,100%);background:#161b22;border:1px solid #2a3340;
   border-radius:14px;padding:26px 30px}
 h1{margin:0 0 4px;font-size:21px;display:flex;align-items:center;gap:10px}
 .dot{width:11px;height:11px;border-radius:50%;background:#4ea1ff;
   animation:pulse 1.2s ease-in-out infinite}
 .dot.idle{background:#8b949e;animation:none}
 .dot.err{background:#f85149;animation:none}
 @keyframes pulse{0%,100%{opacity:.25}50%{opacity:1}}
 p{color:#9aa7b4;margin:6px 0}
 pre{background:#0d1117;border:1px solid #2a3340;border-radius:10px;
   padding:12px 14px;max-height:340px;overflow:auto;font-size:12.5px;
   color:#9aa7b4;white-space:pre-wrap}
 .row{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
 a.btn,button{background:#1c232d;color:#e6edf3;border:1px solid #2a3340;
   border-radius:9px;padding:9px 14px;font-size:14px;cursor:pointer;
   text-decoration:none;font-family:inherit}
 a.btn:hover,button:hover{background:#222b37}
 .err{color:#f85149}
</style></head><body><div class="box">
<h1><span class="dot" id="dot"></span><span id="title">Collecte en cours…</span></h1>
<p id="sub">Les plateformes sont interrogées une par une. Cette page bascule
sur le rapport dès qu'il est prêt.</p>
<pre id="log">démarrage…</pre>
<div class="row">
  <a class="btn" id="prev" href="index.html" style="display:none">Voir le rapport précédent</a>
  <button id="run">Relancer la collecte</button>
</div>
</div>
<script>
let wasRunning = false;
async function tick() {
  try {
    const s = await (await fetch('_status', {cache: 'no-store'})).json();
    document.getElementById('log').textContent = s.log.join('\\n') || 'démarrage…';
    document.getElementById('prev').style.display = s.has_report ? '' : 'none';
    const dot = document.getElementById('dot'), title = document.getElementById('title');
    if (s.running) {
      wasRunning = true;
      dot.className = 'dot';
      title.textContent = 'Collecte en cours… (' + s.elapsed + ' s)';
    } else {
      dot.className = s.error ? 'dot err' : 'dot idle';
      title.textContent = s.error ? 'Collecte interrompue' : 'Aucune collecte en cours';
      if (s.error) {
        document.getElementById('sub').innerHTML =
          '<span class="err">' + s.error + '</span>';
      }
      if (wasRunning && s.has_report) { location.href = 'index.html'; return; }
    }
  } catch (e) { /* serveur qui redémarre : on réessaie */ }
  setTimeout(tick, 2000);
}
document.getElementById('run').addEventListener('click', async () => {
  await fetch('_run', {method: 'POST'});
  wasRunning = true;
});
tick();
</script></body></html>
"""


class ReportHandler(SimpleHTTPRequestHandler):
    """Sert le rapport et expose l'état de la collecte."""

    collector: Collector

    def do_GET(self) -> None:  # noqa: N802 - nom imposé par http.server
        path = self.path.split("?")[0]
        if path == "/_status":
            self._send_json(self.collector.status())
            return
        if path == "/_run":                      # dépannage : /_run en GET aussi
            self._trigger_run()
            return
        if path == "/" and (self.collector.running or not self.collector.has_report):
            self._send_html(STATUS_PAGE)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/_run":
            self._trigger_run()
            return
        self.send_error(405, "Method Not Allowed")

    # ------------------------------------------------------------------
    def _trigger_run(self) -> None:
        started = self.collector.start(reason="demande depuis l'interface")
        self._send_json({"started": started, **self.collector.status()})

    def _send_json(self, payload: dict) -> None:
        self._send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                         "application/json; charset=utf-8")

    def _send_html(self, html: str) -> None:
        self._send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        log.debug("[web] %s", fmt % args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="money-finder-web",
        description="Sert le rapport et lance la collecte automatiquement.")
    parser.add_argument("-p", "--port", type=int, default=int(os.getenv("WEB_PORT", "8081")))
    parser.add_argument("-d", "--directory", default="")
    parser.add_argument("--no-auto", action="store_true",
                        help="ne pas lancer la collecte au démarrage")
    parser.add_argument("--refresh-hours", type=float,
                        default=float(os.getenv("REFRESH_HOURS", "0") or 0),
                        help="relancer la collecte toutes les N heures (0 = jamais)")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if args.directory:
        settings.output_dir = Path(args.directory)
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    collector = Collector(settings, refresh_hours=args.refresh_hours)
    handler = partial(ReportHandler, directory=str(settings.output_dir))
    ReportHandler.collector = collector

    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"Rapport servi sur http://localhost:{args.port} "
          f"(dossier {settings.output_dir.resolve()})", flush=True)

    if collector.has_report:
        print("Rapport déjà présent : « Relancer la collecte » pour le mettre à jour.",
              flush=True)
    elif not args.no_auto:
        collector.start(reason="aucun rapport présent au démarrage")
    collector.schedule_refresh()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
