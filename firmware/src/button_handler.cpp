#include "button_handler.h"
#include "config.h"
#include "relay_ctrl.h"
#include <Wire.h>
#include <Arduino.h>

// Previous button states and debounce timestamps
static bool lastState[NUM_CHANNELS] = {true, true, true, true}; // HIGH = released (pull-up)
static unsigned long lastDebounce[NUM_CHANNELS] = {0};

// Deselect all TCA9548A mux channels so we talk to PCF8574 directly
static void tca_deselect() {
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(0x00);
    Wire.endTransmission();
}

// Read all 8 pins from PCF8574 (we use P0-P3 for buttons)
static uint8_t pcf8574_read() {
    tca_deselect();
    Wire.requestFrom((uint8_t)PCF8574_ADDR, (uint8_t)1);
    if (Wire.available()) {
        return Wire.read();
    }
    return 0xFF; // All high = no buttons pressed
}

void buttons_init() {
    // Write 0xFF to set all pins as inputs with pull-ups
    tca_deselect();
    Wire.beginTransmission(PCF8574_ADDR);
    Wire.write(0xFF);
    Wire.endTransmission();
    Serial.printf("[Button] PCF8574 at 0x%02X initialized (I2C buttons P0-P3)\n", PCF8574_ADDR);
}

bool buttons_poll() {
    bool anyHandled = false;
    unsigned long now = millis();

    uint8_t pins = pcf8574_read();

    for (int i = 0; i < NUM_CHANNELS; i++) {
        bool currentState = (pins >> i) & 0x01; // true = HIGH (released), false = LOW (pressed)

        // Detect falling edge (released → pressed)
        if (!currentState && lastState[i] && (now - lastDebounce[i]) > BUTTON_DEBOUNCE_MS) {
            lastDebounce[i] = now;
            relay_toggle(i);
            Serial.printf("[Button] CH%d pressed (I2C), relay toggled\n", i);
            anyHandled = true;
        }

        lastState[i] = currentState;
    }

    return anyHandled;
}
