import tempfile
import unittest
from pathlib import Path

from inkquote.models import CATEGORIES, Quote
from inkquote.store import QuoteStore

SEED = Path(__file__).resolve().parents[1] / "data" / "quotes.jsonl"


class SeedDataTest(unittest.TestCase):
    def test_seed_exists_and_valid(self):
        self.assertTrue(SEED.exists(), f"缺少种子数据 {SEED}")
        with tempfile.TemporaryDirectory() as tmp:
            store = QuoteStore(Path(tmp) / "seed.db").init()
            result = store.import_jsonl(SEED)
            stats = store.stats()
        self.assertEqual(result["invalid"], 0)
        self.assertGreaterEqual(stats["total"], 15)
        for category in CATEGORIES:
            self.assertGreater(stats["by_category"][category], 0, f"{category} 分类没有种子数据")

    def test_every_seed_has_provenance(self):
        for line in SEED.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            q = Quote.from_dict(__import__("json").loads(line))
            q.validate()
            self.assertTrue(q.work)
            self.assertTrue(q.location)
            self.assertTrue(q.license)
            if q.category == "internet":
                self.assertTrue(q.source_url.startswith("http"))


if __name__ == "__main__":
    unittest.main()
