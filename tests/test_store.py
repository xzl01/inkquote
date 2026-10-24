import json
import tempfile
import unittest
from pathlib import Path

from inkquote.models import Quote
from inkquote.store import QuoteStore


def sample_quotes():
    return [
        Quote(text="千里之行，始于足下。", category="book", work="道德经", location="第六十四章", verified=True),
        Quote(text="Talk is cheap. Show me the code.", category="internet", work="LKML",
              location="2000-08-25", source_url="https://lkml.org/lkml/2000/8/25/132", verified=True),
        Quote(text="我是路飞！", category="anime", work="海贼王", location="第1集"),
    ]


class QuoteStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.store = QuoteStore(self.db).init()
        for q in sample_quotes():
            self.store.upsert(q)

    def tearDown(self):
        self.tmp.cleanup()

    def test_stats(self):
        stats = self.store.stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["verified"], 2)
        self.assertEqual(stats["by_category"]["book"], 1)

    def test_random_filter(self):
        for _ in range(6):
            q = self.store.random(category="anime")
            self.assertIsNotNone(q)
            self.assertEqual(q["category"], "anime")
        self.assertIsNotNone(self.store.random(verified_only=True))

    def test_search(self):
        items, total = self.store.search(q="道德")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["work"], "道德经")
        items, total = self.store.search(tag="不存在")
        self.assertEqual(total, 0)

    def test_upsert_updates_existing(self):
        q = sample_quotes()[0]
        q.verified = False
        self.store.upsert(q)
        self.assertEqual(self.store.stats()["total"], 3)
        self.assertFalse(self.store.get(q.id)["verified"])

    def test_invalid_quote_raises(self):
        with self.assertRaises(ValueError):
            self.store.upsert(Quote(text="x", category="book", work="", location=""))

    def test_export_json_and_daily(self):
        out = Path(self.tmp.name) / "quotes.json"
        n = self.store.export_json(out, category="book")
        self.assertEqual(n, 1)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("\n  ", text)  # 默认 minified
        data = json.loads(text)
        self.assertEqual(data[0]["work"], "道德经")
        pretty = Path(self.tmp.name) / "quotes-pretty.json"
        self.store.export_json(pretty, minified=False)
        self.assertIn("\n  ", pretty.read_text(encoding="utf-8"))

        q1 = self.store.daily("2026-10-24")
        q2 = self.store.daily("2026-10-24")
        self.assertEqual(q1["id"], q2["id"])
        with self.assertRaises(ValueError):
            self.store.daily("2026/10/24")

    def test_export_import_roundtrip(self):
        out = Path(self.tmp.name) / "out.jsonl"
        self.assertEqual(self.store.export_jsonl(out), 3)
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)
        json.loads(lines[0])
        db2 = Path(self.tmp.name) / "copy.db"
        store2 = QuoteStore(db2).init()
        result = store2.import_jsonl(out)
        self.assertEqual(result["inserted"], 3)
        self.assertEqual(store2.stats()["total"], 3)


if __name__ == "__main__":
    unittest.main()
