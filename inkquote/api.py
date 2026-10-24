"""零依赖只读 HTTP API。"""
from __future__ import annotations

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .models import CATEGORIES
from .store import QuoteStore


ALLOWED_FIELDS = {
    "id", "text", "category", "work", "author", "speaker", "location",
    "source_url", "license", "language", "tags", "retrieved_at", "verified",
}


def _param(query: dict[str, list[str]], name: str, default=None):
    vals = query.get(name)
    return vals[0] if vals else default


def _fields(query: dict[str, list[str]]) -> list[str] | None:
    raw = _param(query, "fields")
    if not raw:
        return None
    fields = [f.strip() for f in raw.split(",") if f.strip()]
    bad = [f for f in fields if f not in ALLOWED_FIELDS]
    if bad:
        raise ValueError(f"不支持的字段：{bad}；可用字段：{sorted(ALLOWED_FIELDS)}")
    return fields


def _project(quote: dict, fields: list[str] | None) -> dict:
    if not fields:
        return quote
    return {k: quote.get(k) for k in fields}


class InkQuoteHandler(BaseHTTPRequestHandler):
    server_version = f"InkQuote/{__version__}"
    store: QuoteStore

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        if os.environ.get("INKQUOTE_VERBOSE"):
            super().log_message(fmt, *args)

    def _json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message, "status": status}, status)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/":
                self._json(
                    {
                        "name": "InkQuote / 引据",
                        "version": __version__,
                        "description": "可溯源的短语/金句只读 API",
                        "endpoints": [
                            "GET /api/health",
                            "GET /api/random?category=book|internet|anime|movie&tag=&language=&verified=1&fields=text,work,author,location",
                            "GET /api/daily?date=YYYY-MM-DD&category=&verified=1",
                            "GET /api/export.json?category=&verified=1&minified=1&fields=text,work",
                            "GET /api/quotes?q=&category=&tag=&language=&limit=20&offset=0&verified=1",
                            "GET /api/quotes/{id}",
                            "GET /api/stats",
                            "GET /api/categories",
                            "GET /api/export.jsonl",
                        ],
                    }
                )
                return
            if path == "/api/health":
                self._json({"ok": True, "version": __version__, "stats": self.store.stats()})
                return
            if path == "/api/categories":
                self._json({"categories": list(CATEGORIES)})
                return
            if path == "/api/stats":
                self._json(self.store.stats())
                return
            if path == "/api/random":
                category = _param(query, "category")
                if category and category not in CATEGORIES:
                    self._error(400, f"category 必须是 {CATEGORIES} 之一")
                    return
                try:
                    fields = _fields(query)
                except ValueError as exc:
                    self._error(400, str(exc))
                    return
                quote = self.store.random(
                    category=category,
                    tag=_param(query, "tag"),
                    language=_param(query, "language"),
                    verified_only=_param(query, "verified") in ("1", "true", "yes"),
                )
                if not quote:
                    self._error(404, "没有符合条件的金句")
                    return
                self._json({"quote": _project(quote, fields)})
                return
            if path == "/api/daily":
                date_str = _param(query, "date") or __import__("datetime").date.today().isoformat()
                category = _param(query, "category")
                if category and category not in CATEGORIES:
                    self._error(400, f"category 必须是 {CATEGORIES} 之一")
                    return
                try:
                    fields = _fields(query)
                    quote = self.store.daily(
                        date_str,
                        category=category,
                        verified_only=_param(query, "verified") in ("1", "true", "yes"),
                    )
                except ValueError as exc:
                    self._error(400, str(exc))
                    return
                if not quote:
                    self._error(404, "没有符合条件的金句")
                    return
                self._json({"date": date_str, "quote": _project(quote, fields)})
                return
            if path == "/api/quotes":
                category = _param(query, "category")
                if category and category not in CATEGORIES:
                    self._error(400, f"category 必须是 {CATEGORIES} 之一")
                    return
                try:
                    limit = int(_param(query, "limit", 20))
                    offset = int(_param(query, "offset", 0))
                    fields = _fields(query)
                except ValueError as exc:
                    self._error(400, f"limit/offset 必须是整数；{exc}")
                    return
                items, total = self.store.search(
                    q=_param(query, "q"),
                    category=category,
                    tag=_param(query, "tag"),
                    language=_param(query, "language"),
                    verified_only=_param(query, "verified") in ("1", "true", "yes"),
                    limit=limit,
                    offset=offset,
                )
                self._json(
                    {"total": total, "limit": limit, "offset": offset,
                     "items": [_project(q, fields) for q in items]}
                )
                return
            if path.startswith("/api/quotes/"):
                quote_id = path.rsplit("/", 1)[-1]
                quote = self.store.get(quote_id)
                if not quote:
                    self._error(404, "找不到该 id")
                    return
                self._json({"quote": quote})
                return
            if path == "/api/export.json":
                category = _param(query, "category")
                if category and category not in CATEGORIES:
                    self._error(400, f"category 必须是 {CATEGORIES} 之一")
                    return
                try:
                    fields = _fields(query)
                except ValueError as exc:
                    self._error(400, str(exc))
                    return
                items = list(
                    self.store.iter_filtered(
                        category=category,
                        verified_only=_param(query, "verified") in ("1", "true", "yes"),
                        language=_param(query, "language"),
                    )
                )
                items = [_project(q, fields) for q in items]
                minified = _param(query, "minified", "1") not in ("0", "false", "no")
                body = json.dumps(
                    items,
                    ensure_ascii=False,
                    separators=(",", ":") if minified else None,
                    indent=None if minified else 2,
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=60")
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/export.jsonl":
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                for quote in self.store.iter_all():
                    self.wfile.write(
                        json.dumps(quote, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
                    )
                return
            self._error(404, "not found")
        except BrokenPipeError:
            pass
        except Exception as exc:  # noqa: BLE001
            self._error(500, f"{type(exc).__name__}: {exc}")


def serve(db_path: str = "data/inkquote.db", host: str = "127.0.0.1", port: int = 8765) -> None:
    store = QuoteStore(db_path).init()
    InkQuoteHandler.store = store
    httpd = ThreadingHTTPServer((host, port), InkQuoteHandler)
    print(f"InkQuote {__version__} serving on http://{host}:{port}  (db: {db_path})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
