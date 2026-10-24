import tempfile
import unittest
import zipfile
from pathlib import Path

from inkquote.sources.books import quotes_from_epub, quotes_from_txt
from inkquote.sources.srt import parse_srt, quotes_from_srt
from inkquote.sources.wikiquote import quotes_from_wikitext, strip_markup

SRT = """1
00:00:01,000 --> 00:00:03,500
生命不息，战斗不止。

2
00:00:04,000 --> 00:00:05,200
嗯。

3
00:00:06,000 --> 00:00:09,000
我要成为火影！
"""

WIKITEXT = """
== 学而 ==
* 学而时习之，不亦说乎？——[[孔子]]《[[论语]]》
* 温故而知新，可以为师矣。
* 这是一条没有出处的话

== 为政 ==
* 三人行，必有我师焉。 —— 孔子《论语》
"""


class SrtTest(unittest.TestCase):
    def test_parse_basic(self):
        cues = parse_srt(SRT)
        self.assertEqual(len(cues), 3)
        self.assertAlmostEqual(cues[0].start, 1.0)
        self.assertEqual(cues[0].time_label, "00:00:01")

    def test_quotes_filters_short_lines(self):
        quotes = quotes_from_srt(SRT, work="测试动画", episode="第1集", category="anime")
        texts = [q.text for q in quotes]
        self.assertIn("生命不息，战斗不止。", texts)
        self.assertIn("我要成为火影！", texts)
        self.assertNotIn("嗯。", texts)  # 太短，被过滤
        self.assertEqual(quotes[0].location, "第1集 00:00:01")


class WikiquoteTest(unittest.TestCase):
    def test_strip_markup(self):
        self.assertEqual(strip_markup("[[孔子|孔丘]]《[[论语]]》"), "孔丘《论语》")

    def test_parse_quotes(self):
        quotes = quotes_from_wikitext(WIKITEXT, lang="zh", page="论语")
        self.assertGreaterEqual(len(quotes), 2)
        first = quotes[0]
        self.assertIn("学而时习之", first.text)
        self.assertEqual(first.author, "孔子")
        self.assertEqual(first.work, "论语")
        self.assertEqual(first.location, "学而")
        self.assertEqual(first.category, "internet")
        self.assertEqual(first.license, "CC-BY-SA-4.0")
        self.assertIn("wikiquote.org", first.source_url)
        self.assertIn("论语", __import__("urllib.parse").parse.unquote(first.source_url))


class BooksTest(unittest.TestCase):
    def test_txt_chapters(self):
        raw = """第一章

这是第一句测试句子，长度需要足够长一点。

这是第二句测试句子，也应该被提取出来。

第二章

这是第三章之前的句子，同样需要足够长一些。
"""
        quotes = quotes_from_txt(raw, work="测试书", author="作者", min_chars=8, max_chars=40)
        self.assertTrue(quotes)
        self.assertEqual(quotes[0].location, "第一章")
        self.assertTrue(all(q.work == "测试书" for q in quotes))

    def test_epub_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
            opf = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/></manifest>
  <spine><itemref idref="ch1"/></spine>
</package>"""
            xhtml = """<html><body><h1>第一章 起点</h1>
<p>这是第一章里的一句测试文字，需要足够长才能被提取。</p></body></html>"""
            with zipfile.ZipFile(epub, "w") as z:
                z.writestr("mimetype", "application/epub+zip")
                z.writestr("META-INF/container.xml", container)
                z.writestr("OEBPS/content.opf", opf)
                z.writestr("OEBPS/ch1.xhtml", xhtml)
            quotes = quotes_from_epub(epub, work="测试 EPUB", author="作者", min_chars=8, max_chars=60)
            self.assertTrue(quotes)
            self.assertEqual(quotes[0].location, "第一章 起点")


if __name__ == "__main__":
    unittest.main()
