#include "relay_ctrl.h"
#include "config.h"
#include "ble_service.h"
#include <Arduino.h>

static bool relayStates[NUM_CHANNELS] = {true, true, true, true};

void relay_init() {
    for (int i = 0; i < NUM_CHANNELS; i++) {
        pinMode(RELAY_PINS[i], OUTPUT);
        digitalWrite(RELAY_PINS[i], HIGH); // Active HIGH = ON
    }
    Serial.println("[Relay] All channels initialized ON");
}

void relay_set(uint8_t channel, bool on) {
    if (channel >= NUM_CHANNELS) return;

    relayStates[channel] = on;
    digitalWrite(RELAY_PINS[channel], on ? HIGH : LOW);

    Serial.printf("[Relay] CH%d -> %s\n", channel, on ? "ON" : "OFF");

    // Notify BLE client of state change
    ble_notify_breaker_state(relay_get_bitmap());
}

void relay_toggle(uint8_t channel) {
    if (channel >= NUM_CHANNELS) return;
    relay_set(channel, !relayStates[channel]);
}

uint8_t relay_get_bitmap() {
    uint8_t bitmap = 0;
    for (int i = 0; i < NUM_CHANNELS; i++) {
        if (relayStates[i]) {
            bitmap |= (1 << i);
        }
    }
    return bitmap;
}

bool relay_get(uint8_t channel) {
    if (channel >= NUM_CHANNELS) return false;
    return relayStates[channel];
}
