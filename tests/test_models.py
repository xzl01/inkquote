import unittest

from inkquote.models import Quote, detect_language


class QuoteModelTest(unittest.TestCase):
    def test_valid_quote_gets_id_and_language(self):
        q = Quote(text="千里之行，始于足下。", category="book", work="道德经", location="第六十四章")
        self.assertEqual(q.language, "zh")
        self.assertEqual(len(q.id), 16)
        self.assertEqual(q.id, q.compute_id())
        self.assertIn("T", q.retrieved_at)

    def test_english_quote_language(self):
        q = Quote(text="To be, or not to be.", category="book", work="Hamlet", location="Act 3, Scene 1")
        self.assertEqual(q.language, "en")
        self.assertEqual(detect_language("hello world"), "en")

    def test_missing_work_rejected(self):
        with self.assertRaises(ValueError):
            Quote(text="一句话", category="book", work="", location="第一章").validate()

    def test_missing_location_rejected(self):
        with self.assertRaises(ValueError):
            Quote(text="一句话", category="book", work="某书", location="未知").validate()

    def test_internet_requires_url(self):
        with self.assertRaises(ValueError):
            Quote(text="Talk is cheap.", category="internet", work="LKML", location="2000-08-25").validate()
        q = Quote(
            text="Talk is cheap.",
            category="internet",
            work="LKML",
            location="2000-08-25",
            source_url="https://lkml.org/lkml/2000/8/25/132",
        ).validate()
        self.assertTrue(q.source_url.startswith("https://"))

    def test_bad_category_rejected(self):
        with self.assertRaises(ValueError):
            Quote(text="一句话", category="podcast", work="某播客", location="第1期").validate()

    def test_from_dict_roundtrip(self):
        q = Quote(text="上善若水。", category="book", work="道德经", location="第八章", author="老子")
        data = q.to_dict()
        q2 = Quote.from_dict(data)
        self.assertEqual(q.id, q2.id)
        self.assertEqual(q.to_dict(), q2.to_dict())


if __name__ == "__main__":
    unittest.main()
