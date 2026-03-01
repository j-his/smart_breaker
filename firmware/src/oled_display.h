#pragma once

#include <stdint.h>

// Initialize I2C bus and all 4 OLED displays via TCA9548A mux
void oled_init();

// Update a single channel's OLED with current power reading
void oled_update_channel(uint8_t channel, float watts, bool relayOn);

// Update all 4 OLEDs
void oled_update_all(float* watts, bool* relayStates);
