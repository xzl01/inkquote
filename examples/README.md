# ESP32 / ESP8266 示例

两种用法：

| 示例 | 用法 | 适合 |
|---|---|---|
| [`esp32_random_quote`](esp32_random_quote/esp32_random_quote.ino) | 联网请求 `/api/random` | 设备有 Wi-Fi，想每次换一条 |
| [`esp32_offline_daily`](esp32_offline_daily/esp32_offline_daily.ino) | 把 `static/quotes.json` 放进 LittleFS | 离线、每天固定一条 |

## 数据准备

仓库里的 `static/` 已生成好（50 条、minified，全量约 18.9 KB）：

```bash
python3 -m inkquote pack static       # 重新生成
```

也可以直接从 GitHub 拉：

```
https://raw.githubusercontent.com/xzl01/inkquote/main/static/quotes.json
https://raw.githubusercontent.com/xzl01/inkquote/main/static/book.json
...
```

## 依赖

- ArduinoJson **7.x**（示例使用 `JsonDocument`；v6 请换成 `DynamicJsonDocument`）
- ESP32：`WiFi.h` + `HTTPClient.h`（Arduino-ESP32 core 自带）
- ESP8266：`ESP8266WiFi.h` + `ESP8266HTTPClient.h`

## 内存建议

- 单条 `/api/random` 约 400–600 B；用 `fields=text,work,author,location` 可再省一半。
- 全量 `quotes.json` 目前约 18.9 KB，ESP32 无压力；ESP8266 建议按分类拉取或分页。
- 数据变大后不要一次把整个数组放进 JSON 文档：用 `/api/quotes?limit=20&offset=...` 分页，或把数据按分类拆文件。
- 内网用 HTTP 即可；HTTPS 会多占十几 KB RAM，需要在 `WiFiClientSecure` 里设置证书/指纹。
