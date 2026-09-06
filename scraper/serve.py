"""Serveur du rapport avec collecte à la demande (service `web`).

Au démarrage, aucune collecte n'est lancée : la racine affiche une page de
configuration (mots-clés, plateformes, limite) avec un bouton « Démarrer la
collecte ». Une fois lancée, la même page affiche l'avancement en direct et
bascule sur le rapport dès qu'il est prêt.

Endpoints :
  GET  /            formulaire, ou avancement si une collecte tourne
  GET  /_setup      idem, quel que soit l'état du rapport
  GET  /index.html  toujours le rapport tel quel (même pendant une collecte)
  GET  /_status     état JSON {running, done, has_report, log, models, ...}
  POST /_run        démarre une collecte (ignorée si une est déjà en cours).
                     Le corps JSON {keywords, sources, limit} est obligatoire :
                     sans mots-clés ni plateformes, rien ne démarre.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import replace
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import ALL_SOURCES, Settings

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
        self._found_lock = threading.Lock()
        self.found: dict[str, dict] = {}
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
        with self._found_lock:
            found = list(self.found.values())
        return {
            "running": self.running,
            "has_report": self.has_report,
            "runs": self.runs,
            "error": self.error,
            "elapsed": int((self.finished_at or time.time()) - self.started_at)
            if self.started_at else 0,
            "log": list(self.buffer.lines)[-40:],
            "keywords": self.settings.keywords,
            "sources": self.settings.sources,
            "all_sources": ALL_SOURCES,
            "limit_per_keyword": self.settings.limit_per_keyword,
            "found": len(found),
            "models": found,
        }

    def _on_model(self, model) -> None:
        """Callback appelé par le pipeline dès qu'un modèle est trouvé/enrichi."""
        from .models import Model  # import tardif : évite un cycle
        assert isinstance(model, Model)
        with self._found_lock:
            self.found[model.uid] = {
                "uid": model.uid,
                "title": model.title,
                "source": model.source,
                "source_label": model.source_label,
                "url": model.url,
                "image": model.image,
                "creator": model.creator,
                "sellable": model.license.sellable if model.license else None,
            }

    # ------------------------------------------------------------------
    def start(self, reason: str = "", overrides: dict | None = None) -> bool:
        """Démarre une collecte si aucune n'est en cours.

        `overrides` (keywords/sources/limit_per_keyword) remplace les
        réglages courants pour cette collecte et les suivantes, afin que la
        page de configuration se souvienne du dernier choix.
        """
        with self._lock:
            if self.running:
                return False
            if overrides:
                self.settings = replace(self.settings, **overrides)
            self.running = True
            self.started_at = time.time()
            self.finished_at = 0.0
            self.error = ""
        with self._found_lock:
            self.found = {}
        threading.Thread(target=self._run, args=(reason,), daemon=True).start()
        return True

    def _run(self, reason: str) -> None:
        from .pipeline import run                       # import tardif : évite un cycle
        log.info("collecte lancée%s", f" ({reason})" if reason else "")
        try:
            run(self.settings, on_model=self._on_model)
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
<title>Nouvelle collecte — money-finder</title>
<style>
 :root{color-scheme:dark}
 body{margin:0;background:#0e1116;color:#e6edf3;
   font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
   display:grid;place-items:center;min-height:100vh;padding:24px}
 .box{width:min(860px,100%);background:#161b22;border:1px solid #2a3340;
   border-radius:14px;padding:26px 30px}
 .box + .box{margin-top:18px}
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
 .row{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;align-items:center}
 a.btn,button{background:#1c232d;color:#e6edf3;border:1px solid #2a3340;
   border-radius:9px;padding:9px 14px;font-size:14px;cursor:pointer;
   text-decoration:none;font-family:inherit}
 a.btn:hover,button:hover{background:#222b37}
 button.primary{background:#1f6feb;border-color:#1f6feb;font-weight:600}
 button.primary:hover{background:#3382ff}
 .err{color:#f85149}
 .field{margin-top:16px}
 .field label{display:block;font-size:13px;color:#9aa7b4;margin-bottom:6px}
 .chips{display:flex;flex-wrap:wrap;gap:8px}
 .chip{display:flex;align-items:center;gap:6px;background:#1c232d;
   border:1px solid #2a3340;border-radius:20px;padding:6px 12px;font-size:13.5px;
   cursor:pointer;user-select:none}
 .chip input{margin:0}
 input[type=text],input[type=number]{background:#0d1117;border:1px solid #2a3340;
   color:#e6edf3;border-radius:8px;padding:8px 10px;font-size:14px;font-family:inherit}
 .count{color:#9aa7b4;font-size:13px;margin:10px 0 0}
 .live-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
   gap:10px;margin-top:10px;max-height:460px;overflow-y:auto;padding-right:2px}
 .live-card{background:#0d1117;border:1px solid #2a3340;border-radius:10px;
   overflow:hidden;display:flex;flex-direction:column;text-decoration:none;
   color:inherit}
 .live-card img{width:100%;height:90px;object-fit:cover;background:#1c232d;display:block}
 .live-card .body{padding:8px}
 .live-card .t{display:block;font-size:12.5px;font-weight:600;color:#e6edf3;
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .live-card .badges{display:flex;gap:4px;margin-top:5px;flex-wrap:wrap}
 .badge{border-radius:6px;padding:2px 6px;font-size:10.5px}
 .badge.src{background:#1c232d;border:1px solid #2a3340;color:#9aa7b4}
 .sell-yes{background:#0d3321;color:#4fd88a}
 .sell-conditions{background:#3a2f0d;color:#e6c14e}
 .sell-no{background:#3a1414;color:#f0807d}
 .sell-unknown,.sell-null{background:#1c232d;color:#9aa7b4}
 details.logbox{margin-top:14px}
 details.logbox summary{cursor:pointer;color:#9aa7b4;font-size:13px}
</style></head><body>

<div class="box" id="setupBox">
  <h1>Nouvelle collecte</h1>
  <p>Choisis les mots-clés et les plateformes à interroger, puis démarre la collecte.</p>
  <div class="field">
    <label>Mots-clés</label>
    <div class="chips" id="kwChips"></div>
    <div class="row">
      <input type="text" id="kwNew" placeholder="ajouter un mot-clé…">
      <button type="button" id="kwAdd">Ajouter</button>
    </div>
  </div>
  <div class="field">
    <label>Plateformes</label>
    <div class="chips" id="srcChips"></div>
  </div>
  <div class="field">
    <label>Limite par mot-clé et par plateforme</label>
    <input type="number" id="limit" min="1" style="width:110px">
  </div>
  <div class="row">
    <button class="primary" id="start">Démarrer la collecte</button>
    <a class="btn" id="prevFromSetup" href="index.html" style="display:none">Voir le rapport existant</a>
  </div>
</div>

<div class="box" id="progressBox" style="display:none">
  <h1><span class="dot" id="dot"></span><span id="title">Collecte en cours…</span></h1>
  <p id="sub">Les modèles apparaissent ci-dessous au fur et à mesure qu'ils sont trouvés.</p>
  <p class="count" id="count">0 modèle(s) trouvé(s)</p>
  <div class="live-grid" id="liveGrid"></div>
  <details class="logbox">
    <summary>Journal détaillé</summary>
    <pre id="log">démarrage…</pre>
  </details>
  <div class="row">
    <a class="btn" id="prev" href="index.html" style="display:none">Voir le rapport précédent</a>
  </div>
</div>

<script>
let wasRunning = false;
let initialized = false;
let kwList = [];
let srcList = [];

function renderChips() {
  const kwChips = document.getElementById('kwChips');
  kwChips.innerHTML = '';
  kwList.forEach((kw, i) => {
    const label = document.createElement('label');
    label.className = 'chip';
    label.innerHTML = '<input type="checkbox" data-i="' + i + '"' +
      (kw.checked ? ' checked' : '') + '> ' + kw.name;
    label.querySelector('input').addEventListener('change', (e) => {
      kwList[i].checked = e.target.checked;
    });
    kwChips.appendChild(label);
  });

  const srcChips = document.getElementById('srcChips');
  srcChips.innerHTML = '';
  srcList.forEach((src, i) => {
    const label = document.createElement('label');
    label.className = 'chip';
    label.innerHTML = '<input type="checkbox" data-i="' + i + '"' +
      (src.checked ? ' checked' : '') + '> ' + src.name;
    label.querySelector('input').addEventListener('change', (e) => {
      srcList[i].checked = e.target.checked;
    });
    srcChips.appendChild(label);
  });
}

const liveCards = new Map();   // uid -> {el, img, t, src, sell}
let sawRunning = false;

const SELL_LABELS = {yes: 'Vendable', conditions: 'Sous conditions',
  no: 'Non vendable', unknown: 'Inconnu'};

function upsertCard(m) {
  let refs = liveCards.get(m.uid);
  if (!refs) {
    const el = document.createElement('a');
    el.className = 'live-card';
    el.target = '_blank';
    el.rel = 'noopener';
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.addEventListener('error', () => { img.style.visibility = 'hidden'; });
    const body = document.createElement('div');
    body.className = 'body';
    const t = document.createElement('span');
    t.className = 't';
    const badges = document.createElement('div');
    badges.className = 'badges';
    const src = document.createElement('span');
    src.className = 'badge src';
    const sell = document.createElement('span');
    sell.className = 'badge';
    badges.appendChild(src);
    badges.appendChild(sell);
    body.appendChild(t);
    body.appendChild(badges);
    el.appendChild(img);
    el.appendChild(body);
    refs = {el, img, t, src, sell};
    liveCards.set(m.uid, refs);
    document.getElementById('liveGrid').prepend(el);
  }
  refs.el.href = m.url || '#';
  const image = m.image || '';
  if (refs.img.src !== image) refs.img.src = image;
  refs.t.textContent = m.title || '';
  refs.src.textContent = m.source_label || '';
  refs.sell.className = 'badge sell-' + (m.sellable || 'unknown');
  refs.sell.textContent = SELL_LABELS[m.sellable] || 'Inconnu';
}

function resetLiveGrid() {
  liveCards.clear();
  document.getElementById('liveGrid').innerHTML = '';
}

async function tick() {
  try {
    const s = await (await fetch('_status', {cache: 'no-store'})).json();
    if (!initialized) {
      kwList = s.keywords.map(k => ({name: k, checked: true}));
      srcList = s.all_sources.map(src => ({name: src, checked: s.sources.includes(src)}));
      document.getElementById('limit').value = s.limit_per_keyword;
      renderChips();
      initialized = true;
    }
    if (s.running && !sawRunning) { resetLiveGrid(); }
    sawRunning = s.running;
    (s.models || []).forEach(upsertCard);
    document.getElementById('count').textContent = (s.found || 0) + ' modèle(s) trouvé(s)';
    document.getElementById('log').textContent = s.log.join('\\n') || 'démarrage…';
    document.getElementById('prev').style.display = s.has_report ? '' : 'none';
    document.getElementById('prevFromSetup').style.display = s.has_report ? '' : 'none';
    const dot = document.getElementById('dot'), title = document.getElementById('title');
    const setupBox = document.getElementById('setupBox');
    const progressBox = document.getElementById('progressBox');
    if (s.running) {
      wasRunning = true;
      setupBox.style.display = 'none';
      progressBox.style.display = '';
      dot.className = 'dot';
      title.textContent = 'Collecte en cours… (' + s.elapsed + ' s)';
      document.getElementById('sub').className = '';
      document.getElementById('sub').textContent =
        "Les modèles apparaissent ci-dessous au fur et à mesure qu'ils sont trouvés.";
    } else {
      setupBox.style.display = '';
      progressBox.style.display = (s.runs > 0 || s.error) ? '' : 'none';
      dot.className = s.error ? 'dot err' : 'dot idle';
      title.textContent = s.error ? 'Collecte interrompue' : 'Aucune collecte en cours';
      if (s.error) {
        document.getElementById('sub').textContent = s.error;
        document.getElementById('sub').className = 'err';
      }
      if (wasRunning && s.has_report) { location.href = 'index.html'; return; }
    }
  } catch (e) { /* serveur qui redémarre : on réessaie */ }
  setTimeout(tick, 2000);
}

document.getElementById('kwAdd').addEventListener('click', () => {
  const input = document.getElementById('kwNew');
  const val = input.value.trim();
  if (val) { kwList.push({name: val, checked: true}); input.value = ''; renderChips(); }
});
document.getElementById('kwNew').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); document.getElementById('kwAdd').click(); }
});

document.getElementById('start').addEventListener('click', async () => {
  const keywords = kwList.filter(k => k.checked).map(k => k.name);
  const sources = srcList.filter(s => s.checked).map(s => s.name);
  const limit = parseInt(document.getElementById('limit').value, 10);
  if (!keywords.length) { alert('Choisis au moins un mot-clé.'); return; }
  if (!sources.length) { alert('Choisis au moins une plateforme.'); return; }
  const body = {keywords, sources};
  if (limit > 0) body.limit = limit;
  await fetch('_run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
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
            self._trigger_run({})
            return
        if path in ("/", "/_setup"):
            # La racine montre toujours le formulaire (ou l'avancement si une
            # collecte tourne) : le rapport reste sur /index.html.
            self._send_html(STATUS_PAGE)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/_run":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {}
            self._trigger_run(body if isinstance(body, dict) else {})
            return
        self.send_error(405, "Method Not Allowed")

    # ------------------------------------------------------------------
    def _trigger_run(self, body: dict) -> None:
        overrides: dict = {}

        keywords = body.get("keywords")
        if isinstance(keywords, list):
            cleaned = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
            if cleaned:
                overrides["keywords"] = cleaned

        sources = body.get("sources")
        if isinstance(sources, list):
            cleaned_sources = [
                s.strip().lower() for s in sources
                if isinstance(s, str) and s.strip().lower() in ALL_SOURCES
            ]
            if cleaned_sources:
                overrides["sources"] = cleaned_sources

        limit = body.get("limit")
        if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0:
            overrides["limit_per_keyword"] = limit

        # Rien ne démarre sans choix explicite : une page de rapport gardée en
        # cache appelle /_run sans corps, et relancerait sinon toute seule.
        if "keywords" not in overrides and "sources" not in overrides:
            self._send_json({
                "started": False,
                "needs_setup": True,
                "message": "Choisis des mots-clés et des plateformes sur /_setup.",
                **self.collector.status(),
            })
            return

        started = self.collector.start(reason="demande depuis l'interface",
                                       overrides=overrides)
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
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        # Vaut aussi pour assets/app.js : un script en cache garderait
        # l'ancien comportement du bouton « Relancer ».
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        log.debug("[web] %s", fmt % args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="money-finder-web",
        description="Sert le rapport et permet de démarrer une collecte depuis la page web.")
    parser.add_argument("-p", "--port", type=int, default=int(os.getenv("WEB_PORT", "8081")))
    parser.add_argument("-d", "--directory", default="")
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

    print("Choisis tes mots-clés sur la page d'accueil puis clique sur "
          "« Démarrer la collecte ».", flush=True)
    if collector.has_report:
        print(f"Rapport précédent disponible : http://localhost:{args.port}/index.html",
              flush=True)
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
