#pragma once

// Initialize button GPIO pins with interrupts
void buttons_init();

// Poll for debounced button presses (call from loop at ~10ms tick)
// Returns true if any button was pressed and handled
bool buttons_poll();
