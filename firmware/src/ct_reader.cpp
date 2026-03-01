#include "ct_reader.h"
#include "config.h"
#include <Arduino.h>

void ct_init() {
    for (int i = 0; i < NUM_CHANNELS; i++) {
        pinMode(CT_PINS[i], INPUT);
    }
    // Set ADC resolution to 12-bit
    analogReadResolution(12);
    Serial.println("[CT] ADC pins initialized");
}

float ct_read_amps(uint8_t channel) {
    if (channel >= NUM_CHANNELS) return 0.0f;

    int pin = CT_PINS[channel];
    float sumSquares = 0.0f;

    // Sample over approximately 1 AC cycle at 60Hz (~16.7ms)
    // With CT_SAMPLES = 1000, each sample takes ~16.7us
    for (int i = 0; i < CT_SAMPLES; i++) {
        int raw = analogRead(pin);
        float voltage = (float)raw * ADC_VREF / ADC_RESOLUTION;
        float centered = voltage - CT_MIDPOINT_V;
        sumSquares += centered * centered;
    }

    float vRms = sqrtf(sumSquares / CT_SAMPLES);

    // Convert voltage RMS to current RMS
    // I_secondary = V_rms / R_burden
    // I_primary = I_secondary * turns_ratio
    float iRms = (vRms / CT_BURDEN_R) * CT_TURNS_RATIO;

    // Filter out noise floor (readings below 0.1A are noise)
    if (iRms < 0.1f) iRms = 0.0f;

    return iRms;
}

float ct_read_watts(uint8_t channel) {
    return ct_read_amps(channel) * MAINS_VOLTAGE;
}

void ct_read_all(float* amps, float* watts) {
    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
        amps[i] = ct_read_amps(i);
        watts[i] = amps[i] * MAINS_VOLTAGE;
    }
}
