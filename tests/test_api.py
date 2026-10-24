import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from inkquote.api import InkQuoteHandler
from inkquote.models import Quote
from inkquote.store import QuoteStore


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = QuoteStore(Path(self.tmp.name) / "api.db").init()
        self.store.upsert(
            Quote(
                text="千里之行，始于足下。",
                category="book",
                work="道德经",
                location="第六十四章",
                verified=True,
            )
        )
        InkQuoteHandler.store = self.store
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), InkQuoteHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_health(self):
        status, data = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["stats"]["total"], 1)

    def test_random(self):
        _, data = self.get("/api/random?category=book")
        self.assertEqual(data["quote"]["work"], "道德经")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/random?category=anime")
        self.assertEqual(ctx.exception.code, 404)

    def test_search(self):
        _, data = self.get("/api/quotes?q=%E9%81%93%E5%BE%B7")
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["items"]), 1)

    def test_quote_by_id(self):
        quote = self.store.search()[0][0]
        _, data = self.get(f"/api/quotes/{quote['id']}")
        self.assertEqual(data["quote"]["id"], quote["id"])

    def test_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/quotes/not-exist")
        self.assertEqual(ctx.exception.code, 404)

    def test_bad_category(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/random?category=podcast")
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
