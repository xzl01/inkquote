"""SQLite 存储 + JSONL 导入导出。"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from .models import CATEGORIES, Quote

SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    work TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    speaker TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    license TEXT NOT NULL DEFAULT 'unknown',
    language TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    retrieved_at TEXT NOT NULL DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_quotes_category ON quotes(category);
CREATE INDEX IF NOT EXISTS idx_quotes_work ON quotes(work);
CREATE INDEX IF NOT EXISTS idx_quotes_verified ON quotes(verified);
"""


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["verified"] = bool(d.get("verified"))
    return d


class QuoteStore:
    def __init__(self, path: str | os.PathLike = "data/inkquote.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> "QuoteStore":
        with self._connect() as conn:
            conn.executescript(SCHEMA)
        return self

    def upsert(self, quote: Quote) -> bool:
        """写入一条；校验失败抛 ValueError。返回是否新插入。"""
        quote.validate()
        d = quote.to_dict()
        with self._connect() as conn:
            existed = conn.execute("SELECT 1 FROM quotes WHERE id=?", (d["id"],)).fetchone()
            conn.execute(
                """INSERT INTO quotes
                (id, text, category, work, author, speaker, location, source_url,
                 license, language, tags, retrieved_at, verified)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                 text=excluded.text, category=excluded.category, work=excluded.work,
                 author=excluded.author, speaker=excluded.speaker, location=excluded.location,
                 source_url=excluded.source_url, license=excluded.license,
                 language=excluded.language, tags=excluded.tags,
                 retrieved_at=excluded.retrieved_at, verified=excluded.verified""",
                (
                    d["id"], d["text"], d["category"], d["work"], d["author"],
                    d["speaker"], d["location"], d["source_url"], d["license"],
                    d["language"], json.dumps(d["tags"], ensure_ascii=False),
                    d["retrieved_at"], 1 if d["verified"] else 0,
                ),
            )
            return existed is None

    def upsert_many(self, quotes: Iterable[Quote]) -> dict[str, int]:
        inserted = updated = invalid = 0
        errors: list[str] = []
        for q in quotes:
            try:
                if self.upsert(q):
                    inserted += 1
                else:
                    updated += 1
            except ValueError as exc:
                invalid += 1
                errors.append(f"{q.work}/{q.location}: {exc}")
                if len(errors) >= 10:
                    break
        return {"inserted": inserted, "updated": updated, "invalid": invalid, "errors": errors}

    def get(self, quote_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
        return _row_to_dict(row) if row else None

    def random(
        self,
        category: str | None = None,
        tag: str | None = None,
        language: str | None = None,
        verified_only: bool = False,
    ) -> dict | None:
        sql = "SELECT * FROM quotes WHERE 1=1"
        args: list = []
        if category:
            sql += " AND category=?"
            args.append(category)
        if language:
            sql += " AND language=?"
            args.append(language)
        if verified_only:
            sql += " AND verified=1"
        if tag:
            sql += " AND tags LIKE ?"
            args.append(f'%"{tag}"%')
        sql += " ORDER BY RANDOM() LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(sql, args).fetchone()
        return _row_to_dict(row) if row else None

    def search(
        self,
        q: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        language: str | None = None,
        verified_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        where = " WHERE 1=1"
        args: list = []
        if q:
            where += " AND (text LIKE ? OR work LIKE ? OR author LIKE ? OR speaker LIKE ?)"
            like = f"%{q}%"
            args.extend([like, like, like, like])
        if category:
            where += " AND category=?"
            args.append(category)
        if language:
            where += " AND language=?"
            args.append(language)
        if verified_only:
            where += " AND verified=1"
        if tag:
            where += " AND tags LIKE ?"
            args.append(f'%"{tag}"%')
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM quotes" + where, args).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM quotes" + where + " ORDER BY category, work, id LIMIT ? OFFSET ?",
                args + [limit, offset],
            ).fetchall()
        return [_row_to_dict(r) for r in rows], total

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0]
            verified = conn.execute("SELECT COUNT(*) FROM quotes WHERE verified=1").fetchone()[0]
            by_cat = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT category, COUNT(*) FROM quotes GROUP BY category"
                ).fetchall()
            }
            works = conn.execute("SELECT COUNT(DISTINCT work) FROM quotes").fetchone()[0]
        return {
            "total": total,
            "verified": verified,
            "works": works,
            "by_category": {c: by_cat.get(c, 0) for c in CATEGORIES},
            "db": str(self.path),
        }

    def iter_all(self) -> Iterator[dict]:
        yield from self.iter_filtered()

    def iter_filtered(
        self,
        category: str | None = None,
        verified_only: bool = False,
        language: str | None = None,
    ) -> Iterator[dict]:
        sql = "SELECT * FROM quotes WHERE 1=1"
        args: list = []
        if category:
            sql += " AND category=?"
            args.append(category)
        if language:
            sql += " AND language=?"
            args.append(language)
        if verified_only:
            sql += " AND verified=1"
        sql += " ORDER BY category, work, id"
        with self._connect() as conn:
            for row in conn.execute(sql, args):
                yield _row_to_dict(row)

    def export_jsonl(self, path: str | os.PathLike) -> int:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with p.open("w", encoding="utf-8") as fh:
            for d in self.iter_all():
                fh.write(json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n")
                n += 1
        return n

    def export_json(
        self,
        path: str | os.PathLike,
        category: str | None = None,
        verified_only: bool = False,
        language: str | None = None,
        minified: bool = True,
    ) -> int:
        """导出为单个 JSON 数组（ESP/嵌入式友好）。"""
        items = list(self.iter_filtered(category, verified_only, language))
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            if minified:
                json.dump(items, fh, ensure_ascii=False, separators=(",", ":"))
            else:
                json.dump(items, fh, ensure_ascii=False, indent=2)
        return len(items)

    def daily(
        self,
        date_str: str,
        category: str | None = None,
        verified_only: bool = False,
    ) -> dict | None:
        """按日期稳定选一条：day_number % n，ESP 离线也能复现同一结果。"""
        from datetime import date as _date

        try:
            day = _date.fromisoformat(date_str)
        except ValueError as exc:
            raise ValueError("date 必须是 YYYY-MM-DD") from exc
        items = list(self.iter_filtered(category, verified_only))
        if not items:
            return None
        day_number = (day - _date(1970, 1, 1)).days
        return items[day_number % len(items)]

    def import_jsonl(self, path: str | os.PathLike) -> dict[str, int]:
        quotes: list[Quote] = []
        with Path(path).open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    quotes.append(Quote.from_dict(json.loads(line)))
                except Exception as exc:  # noqa: BLE001
                    quotes.append(Quote(text="", category="", work="", location=""))
                    print(f"[skip] {path}:{lineno}: {exc}")
        return self.upsert_many(quotes)

    def validate_file(self, path: str | os.PathLike) -> dict:
        ok = bad = 0
        errors: list[str] = []
        with Path(path).open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    Quote.from_dict(json.loads(line)).validate()
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    bad += 1
                    errors.append(f"line {lineno}: {exc}")
        return {"ok": ok, "bad": bad, "errors": errors}

    def random_id(self) -> str | None:
        rows = list(self.iter_all())
        return random.choice(rows)["id"] if rows else None
