#pragma once

// Initialize e-ink display pins
void eink_init();

// Update e-ink with current power overview
// totalWatts: total power consumption
// channelWatts: array of NUM_CHANNELS watts readings
// wifiOk: whether WiFi is connected
// bleConnected: whether BLE client is connected
void eink_update_overview(float totalWatts, float* channelWatts,
                          bool wifiOk, bool bleConnected);
