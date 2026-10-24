# 引据 · InkQuote

**可溯源的短语 / 金句库 + 只读 HTTP API + CLI**，给其他项目直接消费。

和「随机鸡汤 API」的区别：每条都强制带**具体出处**（作品、章节/集数/时间戳或 URL），并提供 `verified`、`license` 字段，方便核对与合规使用。

- 存储：SQLite；交换格式：JSONL
- 接口：零依赖 Python 标准库 HTTP API
- 采集：Wikiquote、SRT 字幕、TXT / EPUB 电子书
- 用途：待机壁纸每日一句、阅读 App 摘录、桌面小组件、写作素材库、聊天机器人等

## 快速开始

要求：Python ≥ 3.10，**无第三方依赖**。

```bash
git clone https://github.com/xzl01/inkquote.git
cd inkquote

# 初始化 + 导入内置种子数据（21 条，四个分类都有）
python3 -m inkquote init
python3 -m inkquote import data/quotes.jsonl

# 随机来一条
python3 -m inkquote random --category book --verified-only

# 搜索
python3 -m inkquote search --q 道德 --json

# 启动 HTTP API
python3 -m inkquote serve --host 127.0.0.1 --port 8765
```

```bash
curl 'http://127.0.0.1:8765/api/random?category=movie'
curl 'http://127.0.0.1:8765/api/quotes?q=希望&limit=5'
curl 'http://127.0.0.1:8765/api/stats'
curl 'http://127.0.0.1:8765/api/export.jsonl' > quotes.jsonl
```

## 数据模型

```json
{
  "id": "3636bad3be6d1c47",
  "text": "千里之行，始于足下。",
  "category": "book",
  "work": "道德经",
  "author": "老子",
  "speaker": "",
  "location": "第六十四章",
  "source_url": "https://zh.wikisource.org/wiki/道德經",
  "license": "public-domain",
  "language": "zh",
  "tags": ["道家", "行动"],
  "retrieved_at": "2026-10-24T21:50:00+08:00",
  "verified": true
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `text` | ✅ | 短语正文，2–300 字 |
| `category` | ✅ | `book` / `internet` / `anime` / `movie` |
| `work` | ✅ | 作品名 |
| `location` | ✅ | **具体**出处：章节、集数、时间戳、URL 片段；写「未知」会被拒绝 |
| `source_url` | 互联网类必填 | 可核对来源链接 |
| `author` / `speaker` | | 作者 / 角色或说话人 |
| `license` | ✅ | 每条单独标注（见下方合规说明） |
| `verified` | | 是否已人工核对；机器抓取的候选默认 `false` |
| `language` / `tags` | | 语言、标签 |
| `id` | 自动 | 由 category+work+location+text 生成，稳定可复现 |

## HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 + 统计 |
| GET | `/api/random` | 随机一条，支持 `category` `tag` `language` `verified=1` |
| GET | `/api/quotes` | 搜索，支持 `q` `category` `tag` `language` `verified=1` `limit` `offset` |
| GET | `/api/quotes/{id}` | 按 id 取 |
| GET | `/api/stats` | 总量/分类/已核对数 |
| GET | `/api/categories` | 分类列表 |
| GET | `/api/export.jsonl` | 导出全部 JSONL |

响应统一 UTF-8 JSON，带 `Access-Control-Allow-Origin: *`，可直接给浏览器/其他服务调用。

```python
import urllib.request, json

with urllib.request.urlopen("http://127.0.0.1:8765/api/random?category=anime") as r:
    quote = json.load(r)["quote"]

print(f"「{quote['text']}」")
print(f"— {quote['author']}《{quote['work']}》· {quote['location']}")
print(quote["source_url"])
```

## 采集内容

### 1. Wikiquote（互联网来源，CC BY-SA 4.0）

```bash
python3 -m inkquote wikiquote --lang zh --page 论语 --limit 30
python3 -m inkquote wikiquote --lang zh --page 小王子 --page 鲁迅 --limit 20
python3 -m inkquote wikiquote --lang zh --page 道德经 --limit 20 --dry-run   # 只看不导入
```

自动解析 `*` 列表行，拆出 `——作者《作品》`，章节标题作为 `location`，来源链接指向对应维基语录页面。

### 2. 字幕（动漫 / 电影）

```bash
python3 -m inkquote srt /path/to/S01E01.ass.srt \
  --work 进击的巨人 --category anime --episode 第1集 \
  --min-chars 6 --max-chars 40 --limit 50
```

输出带 `第1集 00:12:34` 这类时间戳。候选默认 `verified=false`，建议人工挑选后再标 `verified=true`。

### 3. 电子书（TXT / EPUB）

```bash
python3 -m inkquote books /path/to/book.epub --work 某本书 --author 某作者 --limit 50
python3 -m inkquote books /path/to/book.txt  --work 某本书 --author 某作者 --limit 50
```

按章节/标题切分，提取 8–60 字句子，章节名写入 `location`。自动提取只是候选，同样需要人工核对。

### 4. 手动添加

```bash
python3 -m inkquote add \
  --text "不要温和地走进那个良夜。" \
  --category movie --work "星际穿越" --speaker "布兰德教授" \
  --location "影片中多次引用（约 01:52:00）" \
  --source-url "https://www.imdb.com/title/tt0816692/quotes/" \
  --license fair-use-short-quote
```

## 批处理与校验

```bash
python3 -m inkquote validate data/quotes.jsonl   # 校验出处是否齐全
python3 -m inkquote import quotes.jsonl          # 导入/更新（按 id 去重）
python3 -m inkquote export data/all.jsonl        # 导出给其他项目
python3 -m inkquote stats
```

JSONL 每行一条，方便 diff、PR 审核、跨项目同步。

## 合规与版权

- **只存短句片段**，不存整本书/整集字幕/整篇原文；不要用本项目做全文转载。
- 每条自带 `license` 字段：
  - `public-domain`：公版作品（如《论语》《道德经》，古登堡计划公版译本）；
  - `CC-BY-SA-4.0`：来自 Wikiquote，转载/再分发需署名并以相同协议共享；
  - `fair-use-short-quote`：现代作品短引用，需保留作品名、作者、出处，并注意当地合理使用范围；
  - `user-provided`：自行录入/上传的内容，由录入者负责授权。
- `verified=true` 只代表「出处已人工核对」，不代表内容授权状态。
- 移除请求：如果某个权利人认为某条引用不合适，删除对应 JSONL 行并重新导入即可。

## 目录结构

```
inkquote/
├── inkquote/
│   ├── models.py          # Quote 数据模型 + 出处校验
│   ├── store.py           # SQLite / JSONL
│   ├── api.py             # 零依赖只读 HTTP API
│   ├── cli.py             # 命令行
│   └── sources/
│       ├── wikiquote.py   # 维基语录适配器
│       ├── srt.py         # 字幕适配器
│       └── books.py       # TXT / EPUB 适配器
├── data/quotes.jsonl      # 内置种子数据
└── tests/                 # 标准库 unittest，27 个用例
```

## 开发

```bash
python3 -m unittest discover -s tests -v
```

## Roadmap

- [ ] 写入型 API（带 token）与 Web 管理界面
- [ ] 自动/半自动质量打分（长度、去重、出处完整度）
- [ ] 标签体系与主题合集（「离别」「希望」「代码」…）
- [ ] 静态 JSON 数据集定期发布（GitHub Releases）
- [ ] 与「墨读」「墨屏待机」联动：待机图直接拉取当天金句
- [ ] Dockerfile / 一键部署

## License

代码 MIT。数据按每条 `license` 字段分别授权；内置种子数据的来源与许可见 `data/quotes.jsonl` 与上述合规说明。
