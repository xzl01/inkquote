"""命令行入口：python -m inkquote --help"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .models import CATEGORIES, Quote
from .sources.books import quotes_from_epub, quotes_from_txt
from .sources.srt import quotes_from_srt
from .sources.wikiquote import fetch_page, quotes_from_wikitext
from .store import QuoteStore


def _fmt(quote: dict) -> str:
    text = f"「{quote['text']}」"
    author = quote.get("author") or "佚名"
    line2 = f"— {author}《{quote['work']}》 · {quote['location']}"
    lines = [text, line2]
    if quote.get("speaker"):
        lines.append(f"  说话者：{quote['speaker']}")
    if quote.get("source_url"):
        lines.append(f"  来源：{quote['source_url']}")
    lines.append(f"  id={quote['id']} · {quote['category']} · license={quote['license']}"
                 f" · verified={'是' if quote.get('verified') else '否'}")
    return "\n".join(lines)


def _emit_quotes(quotes, dry: bool) -> None:
    for q in quotes:
        try:
            q.validate()
        except ValueError as exc:
            print(f"[skip] {q.work}/{q.location}: {exc}", file=sys.stderr)
            continue
        if dry:
            print(json.dumps(q.to_dict(), ensure_ascii=False, sort_keys=True))
        else:
            print(_fmt(q.to_dict()))
            print()


def _read_text(path: str) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inkquote",
        description="引据 InkQuote —— 可溯源的金句库 / API / CLI",
    )
    parser.add_argument("--version", action="version", version=f"InkQuote {__version__}")
    parser.add_argument("--db", default="data/inkquote.db", help="SQLite 路径（默认 data/inkquote.db）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="初始化数据库")
    sub.add_parser("stats", help="统计信息")

    p = sub.add_parser("add", help="添加一条金句（必须写清出处）")
    p.add_argument("--text", required=True)
    p.add_argument("--category", required=True, choices=CATEGORIES)
    p.add_argument("--work", required=True, help="作品名")
    p.add_argument("--location", required=True, help="章节/集数/时间戳/URL 片段")
    p.add_argument("--author", default="")
    p.add_argument("--speaker", default="")
    p.add_argument("--source-url", default="")
    p.add_argument("--license", default="unknown")
    p.add_argument("--tags", default="", help="逗号分隔")
    p.add_argument("--verified", action="store_true")

    p = sub.add_parser("import", help="导入 JSONL")
    p.add_argument("file")

    p = sub.add_parser("export", help="导出 JSONL")
    p.add_argument("file")

    p = sub.add_parser("validate", help="校验 JSONL 文件")
    p.add_argument("file")

    p = sub.add_parser("random", help="随机取一条")
    p.add_argument("--category", choices=CATEGORIES)
    p.add_argument("--tag")
    p.add_argument("--language")
    p.add_argument("--verified-only", action="store_true")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("search", help="搜索")
    p.add_argument("--q", default="")
    p.add_argument("--category", choices=CATEGORIES)
    p.add_argument("--tag")
    p.add_argument("--language")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--verified-only", action="store_true")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("serve", help="启动只读 HTTP API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)

    p = sub.add_parser("wikiquote", help="从 Wikiquote 抓取并导入（CC BY-SA 4.0）")
    p.add_argument("--lang", default="zh")
    p.add_argument("--page", action="append", required=True, help="页面名，可重复")
    p.add_argument("--min-chars", type=int, default=4)
    p.add_argument("--max-chars", type=int, default=120)
    p.add_argument("--limit", type=int, default=100, help="每个页面最多导入条数")
    p.add_argument("--verified", action="store_true")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("srt", help="从 SRT 字幕提取候选台词")
    p.add_argument("file")
    p.add_argument("--work", required=True, help="作品名，如 千与千寻")
    p.add_argument("--category", choices=("anime", "movie"), default="anime")
    p.add_argument("--episode", default="", help="如 S01E01 或 第1集")
    p.add_argument("--speaker", default="")
    p.add_argument("--source-url", default="")
    p.add_argument("--min-chars", type=int, default=6)
    p.add_argument("--max-chars", type=int, default=40)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("books", help="从 TXT / EPUB 提取候选句子")
    p.add_argument("file")
    p.add_argument("--work", required=True)
    p.add_argument("--author", default="")
    p.add_argument("--min-chars", type=int, default=8)
    p.add_argument("--max-chars", type=int, default=60)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "serve":
        from .api import serve

        serve(args.db, args.host, args.port)
        return 0

    store = QuoteStore(args.db).init()

    if args.cmd == "init":
        print(f"已初始化 {args.db}")
        print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "stats":
        print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        quote = Quote(
            text=args.text,
            category=args.category,
            work=args.work,
            location=args.location,
            author=args.author,
            speaker=args.speaker,
            source_url=args.source_url,
            license=args.license,
            tags=tags,
            verified=args.verified,
        )
        try:
            store.upsert(quote)
        except ValueError as exc:
            print(f"✗ 校验失败：{exc}", file=sys.stderr)
            return 2
        print("✓ 已写入")
        print(_fmt(quote.to_dict()))
        return 0

    if args.cmd == "import":
        print(json.dumps(store.import_jsonl(args.file), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "export":
        n = store.export_jsonl(args.file)
        print(f"已导出 {n} 条到 {args.file}")
        return 0

    if args.cmd == "validate":
        result = store.validate_file(args.file)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["bad"] == 0 else 1

    if args.cmd == "random":
        quote = store.random(
            category=args.category,
            tag=args.tag,
            language=args.language,
            verified_only=args.verified_only,
        )
        if not quote:
            print("没有符合条件的金句", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps({"quote": quote}, ensure_ascii=False, indent=2))
        else:
            print(_fmt(quote))
        return 0

    if args.cmd == "search":
        items, total = store.search(
            q=args.q or None,
            category=args.category,
            tag=args.tag,
            language=args.language,
            verified_only=args.verified_only,
            limit=args.limit,
            offset=args.offset,
        )
        if args.json:
            print(json.dumps({"total": total, "items": items}, ensure_ascii=False, indent=2))
        else:
            print(f"共 {total} 条，显示 {len(items)} 条：\n")
            for item in items:
                print(_fmt(item))
                print()
        return 0

    if args.cmd == "wikiquote":
        total = 0
        for page in args.page:
            try:
                wikitext = fetch_page(args.lang, page)
            except Exception as exc:  # noqa: BLE001
                print(f"✗ 抓取 {page} 失败：{exc}", file=sys.stderr)
                continue
            quotes = quotes_from_wikitext(
                wikitext,
                lang=args.lang,
                page=page,
                min_chars=args.min_chars,
                max_chars=args.max_chars,
                verified=args.verified,
            )[: args.limit]
            print(f"{page}: 解析出 {len(quotes)} 条", file=sys.stderr)
            if args.dry_run:
                _emit_quotes(quotes, dry=True)
            else:
                result = store.upsert_many(quotes)
                total += result["inserted"] + result["updated"]
                print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        print(f"共处理 {total} 条")
        return 0

    if args.cmd == "srt":
        raw = _read_text(args.file)
        quotes = quotes_from_srt(
            raw,
            work=args.work,
            category=args.category,
            episode=args.episode,
            speaker=args.speaker,
            source_url=args.source_url,
            min_chars=args.min_chars,
            max_chars=args.max_chars,
            limit=args.limit,
        )
        if args.dry_run:
            _emit_quotes(quotes, dry=True)
        else:
            print(json.dumps(store.upsert_many(quotes), ensure_ascii=False, indent=2))
        print(f"候选 {len(quotes)} 条", file=sys.stderr)
        return 0

    if args.cmd == "books":
        path = Path(args.file)
        if path.suffix.lower() == ".epub":
            quotes = quotes_from_epub(
                path,
                work=args.work,
                author=args.author,
                min_chars=args.min_chars,
                max_chars=args.max_chars,
                limit=args.limit,
            )
        else:
            quotes = quotes_from_txt(
                _read_text(args.file),
                work=args.work,
                author=args.author,
                min_chars=args.min_chars,
                max_chars=args.max_chars,
                limit=args.limit,
            )
        if args.dry_run:
            _emit_quotes(quotes, dry=True)
        else:
            print(json.dumps(store.upsert_many(quotes), ensure_ascii=False, indent=2))
        print(f"候选 {len(quotes)} 条", file=sys.stderr)
        return 0

    return 1
