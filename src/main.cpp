#include <WiFi.h>

#include "secrets.h"  // WIFI_SSID / WIFI_PASS

static void scanAndReport() {
  Serial.println("Scanning nearby networks...");
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    Serial.println("  (no networks found)");
    return;
  }
  for (int i = 0; i < n; i++) {
    Serial.printf("  %2d) %-32s ch%-3d %4d dBm  %s\n", i + 1,
                  WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i),
                  WiFi.encryptionType(i) == WIFI_AUTH_OPEN ? "OPEN" : "SECURED");
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);  // รอ USB CDC พร้อมก่อน ไม่งั้นบรรทัดแรกๆ จะหาย

  Serial.println();
  Serial.println("=== ESP32-S3 WiFi Test ===");
  Serial.printf("STA MAC : %s\n", WiFi.macAddress().c_str());
  Serial.printf("AP  MAC : %s\n", WiFi.softAPmacAddress().c_str());

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("Connecting to \"%s\"", WIFI_SSID);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(">>> CONNECTED");
    Serial.printf("IP      : %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("Gateway : %s\n", WiFi.gatewayIP().toString().c_str());
    Serial.printf("Subnet  : %s\n", WiFi.subnetMask().toString().c_str());
    Serial.printf("DNS     : %s\n", WiFi.dnsIP().toString().c_str());
    Serial.printf("RSSI    : %d dBm\n", WiFi.RSSI());
    Serial.printf("Channel : %d\n", WiFi.channel());
  } else {
    Serial.printf(">>> FAILED (status=%d)\n", WiFi.status());
    scanAndReport();
  }
}

void loop() {
  static unsigned long last = 0;
  if (millis() - last > 5000) {
    last = millis();
    Serial.printf("[%lus] status=%d  RSSI=%d dBm  IP=%s\n", millis() / 1000,
                  WiFi.status(), WiFi.RSSI(),
                  WiFi.localIP().toString().c_str());
  }
}
