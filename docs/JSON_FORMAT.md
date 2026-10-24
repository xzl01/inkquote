# JSON 格式（ESP / 嵌入式友好）

## 1. 单个 JSON 数组（`quotes.json`）

默认 **minified**（无空格/换行），适合 ESP32 / ESP8266 一次拉取：

```json
[{"id":"...","text":"千里之行，始于足下。","category":"book","work":"道德经","author":"老子","speaker":"","location":"第六十四章","source_url":"https://zh.wikisource.org/wiki/道德經","license":"public-domain","language":"zh","tags":["道家","行动"],"retrieved_at":"2026-10-24T21:50:00+08:00","verified":true}]
```

需要人读时用 `--pretty`：

```bash
python3 -m inkquote export quotes.json --pretty
```

## 2. JSONL（`quotes.jsonl`）

一行一条，适合 diff、PR、增量同步；ESP 不适合直接解析 JSONL，建议用数组。

## 3. 字段投影（减小体积）

API 支持 `fields` 参数，只返回需要的字段：

```
GET /api/random?fields=text,work,author,location,source_url
```

ESP 上建议只取 `text,work,author,location`，单条约 250–350 B。

## 4. 静态数据集（`static/`）

仓库内已生成，可直接给 ESP 拉取或放进 LittleFS：

| 文件 | 内容 | 体积（当前 21 条） |
|---|---|---|
| `static/quotes.json` | 全部，minified JSON 数组 | 18.9 KB |
| `static/book.json` | 书本分类 | 12.1 KB |
| `static/internet.json` | 互联网分类 | 3.3 KB |
| `static/anime.json` | 动漫分类 | 1.2 KB |
| `static/movie.json` | 电影分类 | 2.2 KB |
| `static/manifest.json` | 版本、条数、字段、文件清单 | 0.8 KB |
| `static/quotes.jsonl` | JSONL 备份 | 20.2 KB |

Raw URL：

```
https://raw.githubusercontent.com/xzl01/inkquote/main/static/quotes.json
https://raw.githubusercontent.com/xzl01/inkquote/main/static/book.json
```

重新生成：

```bash
python3 -m inkquote pack static              # 全部
python3 -m inkquote pack static --verified-only   # 只导出已核对条目
```

## 5. API 导出

| 请求 | 返回 |
|---|---|
| `GET /api/export.json` | 全部，minified JSON 数组（`minified=0` 可缩进） |
| `GET /api/export.json?category=anime&verified=1` | 过滤后的数组 |
| `GET /api/export.jsonl` | JSONL |
| `GET /api/daily?date=2026-10-24` | `{"date":"...","quote":{...}}` |
| `GET /api/quotes?limit=20&offset=0` | 分页对象 `{"total","limit","offset","items"}` |

## 6. 每日一句算法

服务端 `/api/daily` 与 ESP 离线实现一致：

```
day_number = (date - 1970-01-01) 的天数
index      = day_number % 条目数
```

条目按 `category, work, id` 排序。ESP 上 `day_number = time(nullptr) / 86400`（UTC），
用 NTP 校时后与服务器同一天会得到同一条。

## 7. ESP 内存注意

- 单条随机响应（默认全字段）约 400–600 B；`fields` 投影后更小。
- 全量数组当前约 18.9 KB；数据增长后建议：
  - 按分类拆文件；
  - 用 `/api/quotes?limit=20&offset=...` 分页；
  - 或只在设备上存 `static/anime.json` 这种子集。
- ArduinoJson 7 的 `JsonDocument` 会自动扩容；ESP8266 内存紧张时改用 `DynamicJsonDocument` 并设置固定容量。
- ESP 内网建议 HTTP；HTTPS 会多占 RAM 并需要证书。
