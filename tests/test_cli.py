import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "quotes.jsonl"
SEED_COUNT = sum(1 for line in SEED.read_text(encoding="utf-8").splitlines() if line.strip())


class CliPackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "cli.db"
        subprocess.run(
            [sys.executable, "-m", "inkquote", "--db", str(self.db), "import", str(SEED)],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_pack_outputs_esp_files(self):
        out = Path(self.tmp.name) / "static"
        result = subprocess.run(
            [sys.executable, "-m", "inkquote", "--db", str(self.db), "pack", str(out)],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        self.assertIn(f"{SEED_COUNT} 条", result.stdout)
        for name in ("quotes.json", "quotes.jsonl", "manifest.json",
                     "book.json", "internet.json", "anime.json", "movie.json"):
            self.assertTrue((out / name).exists(), name)
        quotes = json.loads((out / "quotes.json").read_text(encoding="utf-8"))
        self.assertEqual(len(quotes), SEED_COUNT)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["total"], SEED_COUNT)
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIn("text", manifest["fields"])

    def test_export_json_cli(self):
        out = Path(self.tmp.name) / "export.json"
        subprocess.run(
            [sys.executable, "-m", "inkquote", "--db", str(self.db),
             "export", str(out), "--category", "book", "--verified-only"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(data)
        self.assertTrue(all(q["category"] == "book" and q["verified"] for q in data))


if __name__ == "__main__":
    unittest.main()
