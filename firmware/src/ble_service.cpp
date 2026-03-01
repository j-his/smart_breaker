#include "ble_service.h"
#include "config.h"
#include "wifi_manager.h"
#include "relay_ctrl.h"
#include <Arduino.h>

static NimBLECharacteristic* pBreakerStateChar = nullptr;
static NimBLECharacteristic* pWifiStatusChar = nullptr;
static bool clientConnected = false;

// --- Server Callbacks ---

class ServerCallbacks : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* pServer) override {
        clientConnected = true;
        Serial.println("[BLE] Client connected");
    }

    void onDisconnect(NimBLEServer* pServer) override {
        clientConnected = false;
        Serial.println("[BLE] Client disconnected, restarting advertising");
        NimBLEDevice::startAdvertising();
    }
};

// --- Characteristic Callbacks ---

class WiFiSSIDCallback : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* pChar) override {
        std::string value = pChar->getValue();
        if (!value.empty()) {
            wifi_set_ssid(value.c_str());
            Serial.printf("[BLE] WiFi SSID received: %s\n", value.c_str());
        }
    }
};

class WiFiPasswordCallback : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* pChar) override {
        std::string value = pChar->getValue();
        if (!value.empty()) {
            wifi_set_password(value.c_str());
            Serial.println("[BLE] WiFi password received");
            // Trigger connection after both creds are set
            wifi_connect();
        }
    }
};

class BreakerCmdCallback : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* pChar) override {
        std::string value = pChar->getValue();
        if (value.length() >= 2) {
            uint8_t channel = (uint8_t)value[0];
            bool on = value[1] != 0;
            Serial.printf("[BLE] Breaker command: CH%d -> %s\n", channel, on ? "ON" : "OFF");
            relay_set(channel, on);
        }
    }
};

// --- Public API ---

void ble_init() {
    // Build device name from MAC address last 4 hex chars
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    char deviceName[20];
    snprintf(deviceName, sizeof(deviceName), "%s-%02X%02X",
             DEVICE_NAME_PREFIX, mac[4], mac[5]);

    Serial.printf("[BLE] Initializing as %s\n", deviceName);

    NimBLEDevice::init(deviceName);
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);

    NimBLEServer* pServer = NimBLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());

    // Create primary service
    NimBLEService* pService = pServer->createService(SERVICE_UUID);

    // WiFi SSID (Write)
    NimBLECharacteristic* pSSIDChar = pService->createCharacteristic(
        WIFI_SSID_CHAR_UUID,
        NIMBLE_PROPERTY::WRITE
    );
    pSSIDChar->setCallbacks(new WiFiSSIDCallback());

    // WiFi Password (Write)
    NimBLECharacteristic* pPassChar = pService->createCharacteristic(
        WIFI_PASS_CHAR_UUID,
        NIMBLE_PROPERTY::WRITE
    );
    pPassChar->setCallbacks(new WiFiPasswordCallback());

    // WiFi Status (Read + Notify)
    pWifiStatusChar = pService->createCharacteristic(
        WIFI_STATUS_CHAR_UUID,
        NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY
    );
    uint8_t initWifiStatus = 0x00;
    pWifiStatusChar->setValue(&initWifiStatus, 1);

    // Breaker State (Read + Notify)
    pBreakerStateChar = pService->createCharacteristic(
        BREAKER_STATE_UUID,
        NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY
    );
    uint8_t initState = 0x0F; // All on by default
    pBreakerStateChar->setValue(&initState, 1);

    // Breaker Command (Write)
    NimBLECharacteristic* pCmdChar = pService->createCharacteristic(
        BREAKER_CMD_UUID,
        NIMBLE_PROPERTY::WRITE
    );
    pCmdChar->setCallbacks(new BreakerCmdCallback());

    pService->start();

    // Start advertising
    NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->start();

    Serial.println("[BLE] Advertising started");
}

void ble_notify_breaker_state(uint8_t bitmap) {
    if (pBreakerStateChar) {
        pBreakerStateChar->setValue(&bitmap, 1);
        if (clientConnected) {
            pBreakerStateChar->notify();
        }
    }
}

void ble_notify_wifi_status(uint8_t status) {
    if (pWifiStatusChar) {
        pWifiStatusChar->setValue(&status, 1);
        if (clientConnected) {
            pWifiStatusChar->notify();
        }
    }
}

bool ble_is_connected() {
    return clientConnected;
}
