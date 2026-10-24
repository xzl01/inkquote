"""从 Wikiquote（维基语录）解析带出处的金句。

用法：
    from inkquote.sources.wikiquote import fetch_page, quotes_from_wikitext
    quotes = quotes_from_wikitext(fetch_page("zh", "论语"), lang="zh", page="论语")

解析规则：取 `*` 开头的列表行，去掉 wiki 标记，把 `——作者《作品》`
拆成作者/作品；章节标题作为 location；来源链接指向对应 Wikiquote 页面。
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request

from ..models import Quote

API = "https://{lang}.wikiquote.org/w/api.php"
PAGE_URL = "https://{lang}.wikiquote.org/wiki/{page}"
UA = "InkQuote/0.1 (+https://github.com/xzl01/inkquote)"

_REF_RE = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", re.S | re.I)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
_LINK_RE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_EXT_LINK_RE = re.compile(r"\[https?://[^\s\]]+\s*([^\]]*)\]")
_TAG_RE = re.compile(r"<[^>]+>")
_MARK_RE = re.compile(r"'{2,}")
_HEADING_RE = re.compile(r"^(=+)\s*(.+?)\s*\1\s*$")
_WORK_RE = re.compile(r"《([^》]+)》")
_ATTR_RE = re.compile(r"\s*(?:——|—{1,2}|--)\s*(.+)$")


def fetch_page(lang: str, page: str, timeout: int = 20) -> str:
    params = {
        "action": "parse",
        "page": page,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
    }
    url = API.format(lang=lang) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "error" in data:
        raise RuntimeError(data["error"].get("info", str(data["error"])))
    return data.get("parse", {}).get("wikitext", "")


def strip_markup(text: str) -> str:
    text = _COMMENT_RE.sub("", text)
    text = _REF_RE.sub("", text)
    for _ in range(5):  # 嵌套模板
        new = _TEMPLATE_RE.sub("", text)
        if new == text:
            break
        text = new
    text = _LINK_RE.sub(r"\2", text)
    text = _WIKILINK_RE.sub(r"\1", text)
    text = _EXT_LINK_RE.sub(lambda m: m.group(1) or "", text)
    text = _TAG_RE.sub("", text)
    text = _MARK_RE.sub("", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _split_attribution(line: str) -> tuple[str, str]:
    """返回 (句子, 出处/作者原文)。"""
    m = _ATTR_RE.search(line)
    if not m:
        return line, ""
    body = line[: m.start()].strip()
    attribution = m.group(1).strip()
    if not body:
        return "", ""
    return body, attribution


def _parse_attribution(attribution: str, page: str) -> tuple[str, str, str]:
    """从 ``作者《作品》`` 解析 (author, work, speaker)。"""
    if not attribution:
        return "", page, ""
    work_m = _WORK_RE.search(attribution)
    work = work_m.group(1).strip() if work_m else page
    before_work = attribution[: work_m.start()] if work_m else attribution
    author = re.sub(r"[，,、；;：:\s]+$", "", before_work).strip(" ，,、；;：:")
    # 常见形式：角色名 —— 作者《作品》 / 作者《作品》第X章
    speaker = ""
    if "：" in attribution and not author:
        speaker, _, rest = attribution.partition("：")
        author = rest.strip()
    return author, work, speaker


def quotes_from_wikitext(
    wikitext: str,
    lang: str,
    page: str,
    min_chars: int = 4,
    max_chars: int = 120,
    verified: bool = False,
) -> list[Quote]:
    section = ""
    out: list[Quote] = []
    seen: set[str] = set()
    page_url = PAGE_URL.format(lang=lang, page=urllib.parse.quote(page.replace(" ", "_")))
    for raw in wikitext.splitlines():
        line = raw.strip()
        hm = _HEADING_RE.match(line)
        if hm:
            section = strip_markup(hm.group(2))
            continue
        if not line.startswith("*") or line.startswith("**"):
            continue
        item = strip_markup(line.lstrip("*").strip())
        if not item:
            continue
        body, attribution = _split_attribution(item)
        body = body.strip(" 　\"'“”‘’「」")
        if not (min_chars <= len(body) <= max_chars):
            continue
        author, work, speaker = _parse_attribution(attribution, page)
        location = section or page
        key = f"{work}|{location}|{body}"
        if key in seen:
            continue
        seen.add(key)
        q = Quote(
            text=body,
            category="internet",
            work=work,
            author=author,
            speaker=speaker,
            location=location,
            source_url=page_url,
            license="CC-BY-SA-4.0",
            language=lang,
            tags=["wikiquote"],
            verified=verified,
        )
        if q.text and q.work and q.location:
            out.append(q)
    return out
