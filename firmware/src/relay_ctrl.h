#pragma once

#include <stdint.h>

// Initialize relay GPIO pins (all ON by default)
void relay_init();

// Set a specific relay channel on or off
void relay_set(uint8_t channel, bool on);

// Toggle a relay channel
void relay_toggle(uint8_t channel);

// Get current state bitmap (bit 0 = CH0, etc.)
uint8_t relay_get_bitmap();

// Get state of a specific channel
bool relay_get(uint8_t channel);
