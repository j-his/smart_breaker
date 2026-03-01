#include "button_handler.h"
#include "config.h"
#include "relay_ctrl.h"
#include <Arduino.h>

static volatile bool buttonPressed[NUM_CHANNELS] = {false};
static unsigned long lastDebounce[NUM_CHANNELS] = {0};

// ISR handlers — set flag only, actual handling in poll
static void IRAM_ATTR onButton0() { buttonPressed[0] = true; }
static void IRAM_ATTR onButton1() { buttonPressed[1] = true; }
static void IRAM_ATTR onButton2() { buttonPressed[2] = true; }
static void IRAM_ATTR onButton3() { buttonPressed[3] = true; }

typedef void (*ISRFunc)();
static const ISRFunc isrFuncs[NUM_CHANNELS] = {onButton0, onButton1, onButton2, onButton3};

void buttons_init() {
    for (int i = 0; i < NUM_CHANNELS; i++) {
        int pin = BUTTON_PINS[i];
        if (pin == 0) {
            // TBD pin — skip initialization
            Serial.printf("[Button] CH%d pin TBD, skipping\n", i);
            continue;
        }
        pinMode(pin, INPUT_PULLUP);
        attachInterrupt(digitalPinToInterrupt(pin), isrFuncs[i], FALLING);
    }
    Serial.println("[Button] Handlers initialized");
}

bool buttons_poll() {
    bool anyHandled = false;
    unsigned long now = millis();

    for (int i = 0; i < NUM_CHANNELS; i++) {
        if (buttonPressed[i] && (now - lastDebounce[i]) > BUTTON_DEBOUNCE_MS) {
            buttonPressed[i] = false;
            lastDebounce[i] = now;
            relay_toggle(i);
            Serial.printf("[Button] CH%d pressed, relay toggled\n", i);
            anyHandled = true;
        } else if (buttonPressed[i]) {
            // Within debounce window, clear the flag
            buttonPressed[i] = false;
        }
    }

    return anyHandled;
}
