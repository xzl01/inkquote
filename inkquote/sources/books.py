"""从 TXT / EPUB 电子书提取带章节位置的候选句子。

自动提取只做「候选」，默认 verified=False；建议人工筛选后再标 verified=True。
"""
from __future__ import annotations

import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from ..models import Quote

_CHAPTER_RE = re.compile(
    r"^\s*(第[一二三四五六七八九十百千零〇0-9]+[章节回卷篇][^\n]{0,30}|Chapter\s+\d+[^\n]{0,40})\s*$",
    re.I,
)
_SENT_SPLIT = re.compile(r"(?<=[。！？!?…；;])\s*")
_BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "section", "article", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre",
}


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[tuple[str, str]] = []  # (chapter, text)
        self._buf: list[str] = []
        self._chapter = ""
        self._in_heading = 0

    def _flush(self) -> None:
        text = " ".join("".join(self._buf).split())
        self._buf.clear()
        if text:
            self.paragraphs.append((self._chapter or "正文", text))

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in ("h1", "h2", "h3"):
            self._flush()
            self._in_heading += 1
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("h1", "h2", "h3"):
            if self._in_heading:
                self._in_heading -= 1
            self._flush()
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        data = data.strip()
        if not data:
            return
        if self._in_heading:
            self._chapter = data
        else:
            self._buf.append(data)


def _sentences(text: str) -> list[str]:
    out = []
    for part in _SENT_SPLIT.split(text):
        s = part.strip(" 　\"'“”‘’「」")
        if s:
            out.append(s)
    return out


def _candidates(
    paragraphs: Iterable[tuple[str, str]],
    work: str,
    author: str,
    min_chars: int,
    max_chars: int,
    limit: int,
    license: str,
) -> list[Quote]:
    out: list[Quote] = []
    seen: set[str] = set()
    for chapter, text in paragraphs:
        for sentence in _sentences(text):
            if not (min_chars <= len(sentence) <= max_chars):
                continue
            if sentence in seen:
                continue
            seen.add(sentence)
            out.append(
                Quote(
                    text=sentence,
                    category="book",
                    work=work,
                    author=author,
                    location=chapter or "正文",
                    license=license,
                    tags=["电子书"],
                    verified=False,
                )
            )
            if len(out) >= limit:
                return out
    return out


def quotes_from_txt(
    raw: str,
    work: str,
    author: str = "",
    min_chars: int = 8,
    max_chars: int = 60,
    limit: int = 50,
    license: str = "user-provided",
) -> list[Quote]:
    paragraphs: list[tuple[str, str]] = []
    chapter = "正文"
    buf: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _CHAPTER_RE.match(stripped):
            if buf:
                paragraphs.append((chapter, " ".join(buf)))
                buf = []
            chapter = stripped
            continue
        buf.append(stripped)
    if buf:
        paragraphs.append((chapter, " ".join(buf)))
    return _candidates(paragraphs, work, author, min_chars, max_chars, limit, license)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_text(root, name: str, default: str = "") -> str:
    for el in root.iter():
        if _local(el.tag) == name:
            return (el.text or "").strip()
    return default


def quotes_from_epub(
    path: str | Path,
    work: str,
    author: str = "",
    min_chars: int = 8,
    max_chars: int = 60,
    limit: int = 50,
    license: str = "user-provided",
) -> list[Quote]:
    path = Path(path)
    paragraphs: list[tuple[str, str]] = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        container = "META-INF/container.xml"
        opf_path = ""
        if container in names:
            root = ET.fromstring(zf.read(container))
            for el in root.iter():
                if _local(el.tag) == "rootfile":
                    opf_path = el.attrib.get("full-path", "")
                    break
        if not opf_path:
            opf_candidates = [n for n in names if n.lower().endswith(".opf")]
            if not opf_candidates:
                raise ValueError("EPUB 中找不到 OPF 文件")
            opf_path = opf_candidates[0]
        opf_dir = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
        opf = ET.fromstring(zf.read(opf_path))
        manifest: dict[str, str] = {}
        spine: list[str] = []
        for el in opf.iter():
            if _local(el.tag) == "item":
                manifest[el.attrib.get("id", "")] = el.attrib.get("href", "")
            elif _local(el.tag) == "itemref":
                spine.append(el.attrib.get("idref", ""))
        for idref in spine:
            href = manifest.get(idref)
            if not href:
                continue
            full = f"{opf_dir}/{href}" if opf_dir else href
            full = re.sub(r"/\./", "/", full)
            if full not in names:
                continue
            raw = zf.read(full)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gb18030", errors="replace")
            parser = _HtmlText()
            parser.feed(text)
            paragraphs.extend(parser.paragraphs)
    return _candidates(paragraphs, work, author, min_chars, max_chars, limit, license)
