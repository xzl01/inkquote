# 采集规范

## 出处字段的最低要求

| category | 必须 | 建议 |
|---|---|---|
| book | `work` + `location`（章节/页码/篇名） | `author`、`source_url`（Wikisource / 出版社页面） |
| internet | `work` + `location` + `source_url` | `author`、`retrieved_at` |
| anime | `work` + `location`（第几集 + 时间戳） | `speaker`、字幕来源、`source_url` |
| movie | `work` + `location`（场次/时间戳） | `speaker`、`source_url` |

`location` 写「未知」「某处」会被 `models.Quote.validate()` 拒绝。

## verified 的语义

- `false`：自动抓取/自动提取的候选，尚未人工核对；
- `true`：人工核对过作品、章节/时间戳和文字，**不是**授权状态。

## 自动采集的局限

- Wikiquote 的页面格式并不统一，解析器只处理 `*` 列表行和 `——作者《作品》` 形式；
- 字幕按「字符数 + 时长」过滤，只能得到候选，需要人工挑选有意义的台词；
- 电子书按句子切分，会把叙述句也带进来，同样需要人工筛选。

## 去重与 id

id 由 `category + work + location + text` 的 SHA-1 前 16 位生成；同一句子在不同出处会保留为两条，方便追溯。

## 提交数据

1. 在 `data/quotes.jsonl` 追加行（或新建 `data/collections/*.jsonl`）；
2. 运行 `python3 -m inkquote validate data/quotes.jsonl` 确认无误；
3. PR 说明数据来源与授权状态。
