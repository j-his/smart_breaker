#pragma once

// Set WiFi credentials (from BLE write)
void wifi_set_ssid(const char* ssid);
void wifi_set_password(const char* password);

// Connect to WiFi using stored credentials
void wifi_connect();

// Initialize WiFi and attempt auto-connect from NVS
void wifi_init();

// Check if WiFi is connected
bool wifi_is_connected();

// Get current WiFi status byte (0x00-0x03)
uint8_t wifi_get_status();
