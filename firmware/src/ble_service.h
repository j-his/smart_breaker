#pragma once

#include <NimBLEDevice.h>

// Initialize BLE peripheral with EnergyAI service
void ble_init();

// Update breaker state characteristic and notify connected client
void ble_notify_breaker_state(uint8_t bitmap);

// Update WiFi status characteristic and notify connected client
void ble_notify_wifi_status(uint8_t status);

// Check if a BLE client is connected
bool ble_is_connected();
