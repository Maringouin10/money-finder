"""Serveur du rapport (service `web` de docker compose).

`python -m http.server` affichait un listing de dossier nu quand le rapport
n'existait pas encore. Ici, la racine renvoie une page d'explication tant que
`index.html` n'a pas été généré.
"""

from __future__ import annotations

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLACEHOLDER = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rapport non généré — money-finder</title>
<style>
 body{{margin:0;background:#0e1116;color:#e6edf3;
   font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
   display:grid;place-items:center;min-height:100vh;padding:24px}}
 .box{{max-width:760px;background:#161b22;border:1px solid #2a3340;
   border-radius:14px;padding:28px 32px}}
 h1{{margin:0 0 6px;font-size:22px}} p{{color:#9aa7b4}}
 code{{background:#0d1117;border:1px solid #2a3340;border-radius:6px;
   padding:2px 6px;font-family:ui-monospace,monospace;color:#4ea1ff}}
 pre{{background:#0d1117;border:1px solid #2a3340;border-radius:10px;
   padding:14px 16px;overflow-x:auto}}
 li{{margin:6px 0}}
</style></head><body><div class="box">
<h1>Aucun rapport dans <code>{directory}</code></h1>
<p>Le serveur fonctionne, mais la collecte n'a pas encore écrit
<code>index.html</code>. Lance-la :</p>
<pre>docker compose run --rm scraper --commercial-only</pre>
<p>Pour vérifier l'affichage sans clé d'API ni réseau :</p>
<pre>docker compose run --rm scraper --demo</pre>
<p>Si la commande se termine sans rien écrire :</p>
<ul>
<li>relance-la avec <code>-v</code> pour voir les erreurs de chaque plateforme ;</li>
<li>vérifie que <code>.env</code> existe (<code>cp .env.example .env</code>) ;</li>
<li>vérifie le contenu du dossier : <code>ls -la output/</code>.</li>
</ul>
<p>Cette page se remplace toute seule dès que le rapport est généré
(il suffit de rafraîchir).</p>
{files}
</div></body></html>
"""


class ReportHandler(SimpleHTTPRequestHandler):
    """Sert le rapport ; explique quoi faire quand il n'existe pas encore."""

    def do_GET(self) -> None:  # noqa: N802 - nom imposé par http.server
        root = Path(self.directory)
        if self.path.split("?")[0] in ("/", "/index.html") and not (root / "index.html").exists():
            self._send_placeholder(root)
            return
        super().do_GET()

    def _send_placeholder(self, root: Path) -> None:
        try:
            entries = sorted(p.name for p in root.iterdir())
        except OSError:
            entries = []
        files = ("<p>Fichiers présents : <code>"
                 + "</code> <code>".join(entries[:20]) + "</code></p>") if entries else ""
        body = PLACEHOLDER.format(directory=root, files=files).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        # le rapport est régénéré à chaque run : pas de cache navigateur
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[web] {fmt % args}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="money-finder-web",
                                     description="Sert le rapport HTML généré.")
    parser.add_argument("-p", "--port", type=int, default=int(os.getenv("WEB_PORT", "8081")))
    parser.add_argument("-d", "--directory", default=os.getenv("OUTPUT_DIR", "output"))
    args = parser.parse_args(argv)

    root = Path(args.directory)
    root.mkdir(parents=True, exist_ok=True)
    handler = partial(ReportHandler, directory=str(root))
    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"Rapport servi sur http://localhost:{args.port} (dossier {root.resolve()})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
