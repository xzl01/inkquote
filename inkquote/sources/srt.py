"""字幕（SRT）→ 带集数/时间戳的候选金句。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Quote

_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")
_MUSIC_RE = re.compile(r"[♪♫]|^\s*[\[(].*[\])]\s*$")


@dataclass
class Cue:
    index: int
    start: float
    end: float
    text: str

    @property
    def time_label(self) -> str:
        total = int(self.start)
        return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def parse_srt(raw: str) -> list[Cue]:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    cues: list[Cue] = []
    for block in re.split(r"\n{2,}", raw):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        try:
            idx = int(lines[0])
        except ValueError:
            idx = len(cues) + 1
            continue
        if len(lines) < 3:
            continue
        m = _TIME_RE.search(lines[1])
        if not m:
            continue
        start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
        end = int(m.group(5)) * 3600 + int(m.group(6)) * 60 + int(m.group(7)) + int(m.group(8)) / 1000
        text = " ".join(lines[2:])
        cues.append(Cue(idx, start, end, text))
    return cues


def clean_text(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def quotes_from_srt(
    raw: str,
    work: str,
    category: str = "movie",
    episode: str = "",
    speaker: str = "",
    source_url: str = "",
    min_chars: int = 6,
    max_chars: int = 40,
    min_duration: float = 0.8,
    limit: int = 50,
    license: str = "fair-use-short-quote",
) -> list[Quote]:
    if category not in ("anime", "movie"):
        raise ValueError("category 必须是 anime 或 movie")
    out: list[Quote] = []
    seen: set[str] = set()
    for cue in parse_srt(raw):
        text = clean_text(cue.text)
        if not text or _MUSIC_RE.search(text):
            continue
        if not (min_chars <= len(text) <= max_chars):
            continue
        if cue.end - cue.start < min_duration:
            continue
        if text in seen:
            continue
        seen.add(text)
        location = f"{episode} {cue.time_label}".strip()
        q = Quote(
            text=text,
            category=category,
            work=work,
            speaker=speaker,
            location=location,
            source_url=source_url,
            license=license,
            tags=["字幕"],
            verified=False,
        )
        out.append(q)
        if len(out) >= limit:
            break
    return out
