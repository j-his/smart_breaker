#include "oled_display.h"
#include "config.h"
#include <Wire.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>

static Adafruit_SSD1306* displays[NUM_CHANNELS] = {nullptr};
static bool initialized = false;

// Select TCA9548A mux channel
static void tca_select(uint8_t channel) {
    if (channel > 7) return;
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(1 << channel);
    Wire.endTransmission();
}

void oled_init() {
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000); // 400kHz I2C

    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
        tca_select(i);
        displays[i] = new Adafruit_SSD1306(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);

        if (!displays[i]->begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
            Serial.printf("[OLED] CH%d init failed\n", i);
            delete displays[i];
            displays[i] = nullptr;
            continue;
        }

        displays[i]->clearDisplay();
        displays[i]->setTextSize(1);
        displays[i]->setTextColor(SSD1306_WHITE);
        displays[i]->setCursor(0, 0);
        displays[i]->printf("CH%d Ready", i);
        displays[i]->display();

        Serial.printf("[OLED] CH%d initialized\n", i);
    }

    initialized = true;
}

void oled_update_channel(uint8_t channel, float watts, bool relayOn) {
    if (channel >= NUM_CHANNELS || !displays[channel]) return;

    tca_select(channel);
    Adafruit_SSD1306* d = displays[channel];

    d->clearDisplay();

    // Line 1: Channel label + relay state
    d->setTextSize(1);
    d->setCursor(0, 0);
    d->printf("CH%d %s", channel, relayOn ? "[ON]" : "[OFF]");

    // Line 2: Power reading (large font)
    d->setTextSize(2);
    d->setCursor(0, 12);
    if (watts >= 1000) {
        d->printf("%.1fkW", watts / 1000.0f);
    } else {
        d->printf("%.0fW", watts);
    }

    d->display();
}

void oled_update_all(float* watts, bool* relayStates) {
    if (!initialized) return;
    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
        oled_update_channel(i, watts[i], relayStates[i]);
    }
}
