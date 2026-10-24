"""可溯源金句的数据模型。

每条金句必须带有可核对的具体出处：作品、章节/集数/时间戳或 URL。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

CATEGORIES = ("book", "internet", "anime", "movie")
CATEGORY_LABELS = {
    "book": "书本",
    "internet": "互联网",
    "anime": "动漫",
    "movie": "电影",
}
MAX_TEXT_LEN = 300
MIN_TEXT_LEN = 2
_BAD_LOCATIONS = {"", "未知", "unknown", "-", "无", "n/a", "na", "待定"}
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def detect_language(text: str) -> str:
    """极简语言判断：含较多 CJK 字符视为中文，否则英文。"""
    if not text:
        return "zh"
    cjk = len(_CJK.findall(text))
    return "zh" if cjk / max(len(text), 1) >= 0.2 else "en"


@dataclass
class Quote:
    text: str
    category: str
    work: str
    location: str
    author: str = ""
    speaker: str = ""
    source_url: str = ""
    license: str = "unknown"
    language: str = ""
    tags: list[str] = field(default_factory=list)
    retrieved_at: str = ""
    verified: bool = False
    id: str = ""

    def __post_init__(self) -> None:
        self.text = (self.text or "").strip()
        self.category = (self.category or "").strip().lower()
        self.work = (self.work or "").strip()
        self.location = (self.location or "").strip()
        self.author = (self.author or "").strip()
        self.speaker = (self.speaker or "").strip()
        self.source_url = (self.source_url or "").strip()
        self.license = (self.license or "unknown").strip()
        if isinstance(self.tags, str):
            self.tags = [t.strip() for t in self.tags.split(",") if t.strip()]
        self.tags = list(dict.fromkeys(self.tags))
        if not self.language:
            self.language = detect_language(self.text)
        if not self.retrieved_at:
            self.retrieved_at = _now_iso()
        if not self.id:
            self.id = self.compute_id()

    def compute_id(self) -> str:
        raw = f"{self.category}|{self.work}|{self.location}|{self.text}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def validate(self) -> "Quote":
        errors: list[str] = []
        if not self.text:
            errors.append("text 为空")
        elif not (MIN_TEXT_LEN <= len(self.text) <= MAX_TEXT_LEN):
            errors.append(f"text 长度需在 {MIN_TEXT_LEN}..{MAX_TEXT_LEN} 之间，实际 {len(self.text)}")
        if self.category not in CATEGORIES:
            errors.append(f"category 必须是 {CATEGORIES} 之一，实际 {self.category!r}")
        if not self.work:
            errors.append("work（作品名）不能为空")
        if self.location.lower() in _BAD_LOCATIONS or len(self.location) < 2:
            errors.append("location（章节/集数/时间戳/URL 片段）必须具体")
        if self.category == "internet" and not self.source_url.startswith(("http://", "https://")):
            errors.append("internet 类金句必须带 http(s) source_url")
        if self.source_url and not self.source_url.startswith(("http://", "https://")):
            errors.append("source_url 必须是 http(s) 链接")
        if not self.license:
            errors.append("license 不能为空")
        if errors:
            raise ValueError("；".join(errors))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category,
            "work": self.work,
            "author": self.author,
            "speaker": self.speaker,
            "location": self.location,
            "source_url": self.source_url,
            "license": self.license,
            "language": self.language,
            "tags": self.tags,
            "retrieved_at": self.retrieved_at,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Quote":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
