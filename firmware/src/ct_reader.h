#pragma once

#include <stdint.h>

// Initialize CT clamp ADC pins
void ct_init();

// Read RMS current in amps for a specific channel
float ct_read_amps(uint8_t channel);

// Read power in watts for a specific channel
float ct_read_watts(uint8_t channel);

// Read all channels into arrays (must be NUM_CHANNELS sized)
void ct_read_all(float* amps, float* watts);
