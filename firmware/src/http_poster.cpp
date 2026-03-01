#include "http_poster.h"
#include "config.h"
#include "wifi_manager.h"
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Arduino.h>
#include <Preferences.h>

static char serverURL[128];
static char deviceId[20];

void http_init() {
    // Build device ID from MAC
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(deviceId, sizeof(deviceId), "%s-%02X%02X",
             DEVICE_NAME_PREFIX, mac[4], mac[5]);

    // Load server URL from NVS or use default
    Preferences prefs;
    prefs.begin("http", true);
    String saved = prefs.getString("url", DEFAULT_SERVER_URL);
    prefs.end();
    strncpy(serverURL, saved.c_str(), sizeof(serverURL) - 1);

    Serial.printf("[HTTP] Initialized, posting to %s as %s\n", serverURL, deviceId);
}

void http_set_server_url(const char* url) {
    strncpy(serverURL, url, sizeof(serverURL) - 1);
    serverURL[sizeof(serverURL) - 1] = '\0';
    Preferences prefs;
    prefs.begin("http", false);
    prefs.putString("url", serverURL);
    prefs.end();
}

bool http_post_sensor(float* amps, uint8_t numChannels) {
    if (!wifi_is_connected()) {
        Serial.println("[HTTP] WiFi not connected, skipping POST");
        return false;
    }

    // Build JSON payload matching backend Pydantic model
    StaticJsonDocument<512> doc;
    doc["device_id"] = deviceId;

    JsonArray channels = doc.createNestedArray("channels");
    for (uint8_t i = 0; i < numChannels && i < NUM_CHANNELS; i++) {
        JsonObject ch = channels.createNestedObject();
        ch["channel_id"] = i;
        ch["current_amps"] = serialized(String(amps[i], 2));
    }

    char jsonBuffer[512];
    serializeJson(doc, jsonBuffer, sizeof(jsonBuffer));

    // POST to backend
    HTTPClient http;
    String url = String(serverURL) + "/api/sensor";
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(HTTP_TIMEOUT_MS);

    int httpCode = http.POST(jsonBuffer);
    http.end();

    if (httpCode >= 200 && httpCode < 300) {
        Serial.printf("[HTTP] POST OK (%d)\n", httpCode);
        return true;
    } else {
        Serial.printf("[HTTP] POST failed (%d)\n", httpCode);
        return false;
    }
}
