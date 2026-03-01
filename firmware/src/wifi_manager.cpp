#include "wifi_manager.h"
#include "ble_service.h"
#include "config.h"
#include <WiFi.h>
#include <Preferences.h>
#include <Arduino.h>

static Preferences prefs;
static char ssid[33] = {0};
static char password[65] = {0};
static uint8_t wifiStatus = 0x00; // Disconnected

void wifi_set_ssid(const char* s) {
    strncpy(ssid, s, sizeof(ssid) - 1);
    ssid[sizeof(ssid) - 1] = '\0';
    // Save to NVS
    prefs.begin("wifi", false);
    prefs.putString("ssid", ssid);
    prefs.end();
}

void wifi_set_password(const char* p) {
    strncpy(password, p, sizeof(password) - 1);
    password[sizeof(password) - 1] = '\0';
    // Save to NVS
    prefs.begin("wifi", false);
    prefs.putString("pass", password);
    prefs.end();
}

void wifi_connect() {
    if (strlen(ssid) == 0) {
        Serial.println("[WiFi] No SSID configured");
        return;
    }

    Serial.printf("[WiFi] Connecting to %s...\n", ssid);
    wifiStatus = 0x01; // Connecting
    ble_notify_wifi_status(wifiStatus);

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_CONNECT_TIMEOUT_MS) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        wifiStatus = 0x02; // Connected
        Serial.printf("[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        wifiStatus = 0x03; // Failed
        Serial.println("[WiFi] Connection failed");
    }

    ble_notify_wifi_status(wifiStatus);
}

void wifi_init() {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);

    // Load saved credentials from NVS
    prefs.begin("wifi", true);
    String savedSSID = prefs.getString("ssid", "");
    String savedPass = prefs.getString("pass", "");
    prefs.end();

    if (savedSSID.length() > 0) {
        strncpy(ssid, savedSSID.c_str(), sizeof(ssid) - 1);
        strncpy(password, savedPass.c_str(), sizeof(password) - 1);
        Serial.printf("[WiFi] Found saved credentials for: %s\n", ssid);
        wifi_connect();
    } else {
        Serial.println("[WiFi] No saved credentials, waiting for BLE config");
    }
}

bool wifi_is_connected() {
    return WiFi.status() == WL_CONNECTED;
}

uint8_t wifi_get_status() {
    // Refresh status based on actual WiFi state
    if (WiFi.status() == WL_CONNECTED) {
        wifiStatus = 0x02;
    } else if (wifiStatus == 0x02) {
        // Was connected but lost connection
        wifiStatus = 0x00;
    }
    return wifiStatus;
}
