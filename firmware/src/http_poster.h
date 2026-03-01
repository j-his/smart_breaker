#pragma once

#include <stdint.h>

// Initialize HTTP poster (reads server URL from NVS or uses default)
void http_init();

// Post sensor readings to backend /api/sensor
// Returns true if POST was successful
bool http_post_sensor(float* amps, uint8_t numChannels);

// Set the backend server URL
void http_set_server_url(const char* url);
