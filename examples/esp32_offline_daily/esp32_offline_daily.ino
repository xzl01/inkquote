// ESP32 + InkQuote：离线「每日一句」
// 把 static/quotes.json 上传到 LittleFS；每天按 UTC 天数取同一条，
// 与 API 的 /api/daily 算法一致：index = days_since_1970 % 总数。
#include <LittleFS.h>
#include <ArduinoJson.h>
#include <time.h>

const char* QUOTES_FILE = "/quotes.json";
JsonDocument doc;  // ArduinoJson 7；v6 用 DynamicJsonDocument doc(32768)

void setup() {
  Serial.begin(115200);
  if (!LittleFS.begin(true)) {
    Serial.println("LittleFS 挂载失败");
    return;
  }
  File f = LittleFS.open(QUOTES_FILE, "r");
  if (!f) {
    Serial.printf("找不到 %s（用 pio run -t uploadfs 上传）\n", QUOTES_FILE);
    return;
  }
  DeserializationError err = deserializeJson(doc, f);
  f.close();
  if (err) {
    Serial.printf("JSON 解析失败：%s\n", err.c_str());
    return;
  }
  JsonArray arr = doc.as<JsonArray>();
  Serial.printf("已加载 %u 条金句\n", (unsigned)arr.size());

  // 需要正确时间；先联网 NTP 一次，之后 RTC 会保持
  configTime(0, 0, "pool.ntp.org");
}

void loop() {
  JsonArray arr = doc.as<JsonArray>();
  if (arr.size() == 0) {
    delay(60000);
    return;
  }
  time_t now = time(nullptr);
  if (now < 1600000000) {  // 时间还没同步
    delay(1000);
    return;
  }
  uint32_t day = now / 86400;  // UTC 天数
  JsonObject q = arr[day % arr.size()];

  Serial.println("--------------------------------");
  Serial.printf("「%s」\n", q["text"].as<const char*>());
  Serial.printf("— %s《%s》 · %s\n",
                q["author"].as<const char*>(),
                q["work"].as<const char*>(),
                q["location"].as<const char*>());
  if (!q["source_url"].isNull()) {
    Serial.printf("来源：%s\n", q["source_url"].as<const char*>());
  }
  delay(3600000UL);  // 每小时检查一次，跨天自动换
}
