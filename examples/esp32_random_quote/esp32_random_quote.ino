// ESP32 / ESP8266 + InkQuote：联网取一条带出处的随机金句
// 依赖：ArduinoJson 7.x
#if defined(ESP8266)
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#else
#include <WiFi.h>
#include <HTTPClient.h>
#endif
#include <ArduinoJson.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";

// InkQuote 服务地址（局域网内运行 `python3 -m inkquote serve --host 0.0.0.0`）
// fields 只取需要的字段，减少 JSON 内存与流量；verified=1 只要人工核对过的
const char* API_URL =
    "http://192.168.1.10:8765/api/random?verified=1"
    "&fields=text,work,author,location,source_url";

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    return;
  }

#if defined(ESP8266)
  WiFiClient client;
  HTTPClient http;
  http.begin(client, API_URL);
#else
  HTTPClient http;
  http.begin(API_URL);
#endif
  http.setTimeout(8000);

  int code = http.GET();
  if (code == 200) {
    // 单条响应很小，直接 getString() 即可；不要在这里同时解析全量数据
    String payload = http.getString();
    JsonDocument doc;  // ArduinoJson 7：自动扩容；v6 用 DynamicJsonDocument doc(1024)
    DeserializationError err = deserializeJson(doc, payload);
    if (!err) {
      JsonObject q = doc["quote"];
      Serial.println("--------------------------------");
      Serial.printf("「%s」\n", q["text"].as<const char*>());
      Serial.printf("— %s《%s》 · %s\n",
                    q["author"].as<const char*>(),
                    q["work"].as<const char*>(),
                    q["location"].as<const char*>());
      if (!q["source_url"].isNull()) {
        Serial.printf("来源：%s\n", q["source_url"].as<const char*>());
      }
      Serial.printf("id=%s\n", q["id"].as<const char*>());
    } else {
      Serial.printf("JSON 解析失败：%s\n", err.c_str());
    }
  } else {
    Serial.printf("HTTP %d\n", code);
  }
  http.end();

  delay(60000);  // 一分钟一条；按需调整
}
