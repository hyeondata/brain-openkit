"""A read-only, loopback-only browser for the local BM25 workflow."""

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import parse_qs, urlsplit

from .vault import validate_vault
from .workflows import search


_SCRIPT = r"""
const form = document.querySelector('form');
const input = document.querySelector('input');
const results = document.querySelector('#results');
const status = document.querySelector('#status');
function element(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!input.value.trim()) { input.focus(); return; }
  form.querySelector('button').disabled = true;
  results.replaceChildren();
  status.textContent = 'Searching local notes…';
  try {
    const url = '/api/search?q=' + encodeURIComponent(input.value);
    if (url.length > 60000) throw new Error('Search query is too long for the browser URL. Please shorten it.');
    const response = await fetch(url);
    const report = await response.json();
    if (!response.ok) throw new Error(report.error || 'Search failed.');
    status.textContent = report.results.length + ' results · BM25 · source notes unchanged';
    if (report.index.errors.length) status.textContent += ' · Some files could not be indexed.';
    for (const hit of report.results) {
      const article = document.createElement('article');
      article.append(element('h2', hit.title));
      article.append(element('p', hit.path + ':' + hit.start_line + '–' + hit.end_line));
      article.append(element('pre', hit.text));
      results.append(article);
    }
    if (!report.results.length) results.append(element('p', 'No matching passages. Try a term from your notes.'));
  } catch (error) {
    status.textContent = error.message;
  } finally {
    form.querySelector('button').disabled = false;
  }
});
"""
_HTML = ("""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Brain OpenKit — Local notes</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif;line-height:1.6}
body{max-width:900px;margin:48px auto;padding:0 24px;background:light-dark(#f8f7f4,#171a19);color:light-dark(#242c29,#e7eee9)}
h1{font-size:2.4rem;letter-spacing:-.04em;margin-bottom:0}header p{margin-top:.3rem;color:light-dark(#53665c,#abc0b1)}
form{display:flex;gap:12px;margin:32px 0 12px}input,button{font:inherit;padding:12px 16px;border-radius:8px;border:1px solid #789887}
input{flex:1;min-width:0}button{background:#235c43;color:white;cursor:pointer}button:disabled{opacity:.6}
label{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
article{border-top:1px solid #789887;padding:16px 0}h2{font-size:1.2rem;margin:0}article p{font-family:ui-monospace,monospace;font-size:.85rem;overflow-wrap:anywhere}
pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0}#status{font-size:.9rem;min-height:2em}
footer{margin-top:40px;font-size:.85rem;color:light-dark(#53665c,#abc0b1)}
</style></head><body>
<header><h1>Brain OpenKit</h1><p>Find the passage. Keep the source.</p></header>
<main><form><label for="query">Search your local notes</label>
<input id="query" name="q" maxlength="8000" placeholder="Search your local notes / 노트 검색" required autofocus>
<button type="submit">Search</button></form>
<p id="status" role="status" aria-live="polite">Local search · no model or API key needed</p>
<section id="results" aria-label="Search results"></section></main>
<footer>This viewer reads your vault. Use the CLI or agent skills to preview and apply changes.</footer>
<script>""" + _SCRIPT + "</script></body></html>").encode("utf-8")
_SCRIPT_HASH = base64.b64encode(hashlib.sha256(_SCRIPT.encode()).digest()).decode()
_CSP = ("default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
        "connect-src 'self'; style-src 'unsafe-inline'; script-src 'sha256-" + _SCRIPT_HASH + "'")


def make_server(vault: Path, cache_dir: Path, *, port: int = 8765) -> ThreadingHTTPServer:
    """Create a server; the caller owns its serve/shutdown lifecycle."""
    vault = validate_vault(vault)
    cache_dir = Path(cache_dir).absolute()
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Requests may contain private search terms; do not echo access logs.
            pass

        def _send(self, status, payload, content_type="application/json; charset=utf-8"):
            data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", _CSP)
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def _allowed(self):
            hosts = self.headers.get_all("Host", [])
            host = f"127.0.0.1:{self.server.server_port}"
            return (hosts == [host]
                    and self.headers.get("Origin", f"http://{host}") == f"http://{host}"
                    and self.headers.get("Sec-Fetch-Site") != "cross-site")

        def send_error(self, code, message=None, explain=None):
            if code == 414:
                self._send(414, {"error": "Search query is too long for the browser URL. Please shorten it."})
            else:
                super().send_error(code, message, explain)

        def do_GET(self):
            if not self._allowed():
                self._send(403, {"error": "Only requests from this local page are accepted."})
                return
            try:
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc or parsed.fragment:
                    raise ValueError("Invalid request path")
                if parsed.path == "/" and not parsed.query:
                    self._send(200, _HTML, "text/html; charset=utf-8")
                elif parsed.path == "/api/search":
                    if len(parsed.query) > 96016:
                        raise ValueError("Search query is too long")
                    values = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True,
                                      encoding="utf-8", errors="strict", max_num_fields=2)
                    if set(values) != {"q"} or len(values["q"]) != 1:
                        raise ValueError("Supply one search query")
                    query = values["q"][0]
                    if not query.strip() or len(query) > 8000:
                        raise ValueError("Search query must contain 1 to 8000 characters")
                    self._send(200, search(vault, query, cache_dir=cache_dir))
                else:
                    self._send(404, {"error": "Not found"})
            except (ValueError, UnicodeError):
                self._send(400, {"error": "Supply one valid UTF-8 search query of 1 to 8000 characters."})
            except (OSError, sqlite3.DatabaseError):
                self._send(500, {"error": "The vault or search index could not be read."})

        def do_POST(self):
            self._send(405, {"error": "This viewer supports read-only GET requests."})

        do_PUT = do_POST
        do_DELETE = do_POST
        do_PATCH = do_POST
        do_OPTIONS = do_POST

    class LocalServer(ThreadingHTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(10)
            return connection, address

    return LocalServer(("127.0.0.1", port), Handler)


def serve(vault: Path, cache_dir: Path, *, port: int = 8765) -> None:
    server = make_server(vault, cache_dir, port=port)
    print(f"Brain OpenKit: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
