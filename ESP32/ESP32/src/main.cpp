#include <Arduino.h>         // Include the core Arduino library to provide basic Arduino functionality
#include <SPI.h>
#include <Wire.h>
#include <string.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "EPD.h"             // Include the EPD library for controlling the electronic ink screen (E-Paper Display)
#undef WHITE
#undef BLACK
#define WHITE 0xFF
#define BLACK 0x00
#include "pic_home.h"        // Include the header file containing image data
// #include "img/device_interface2.h" // Include the header file containing additional image data
#include "boot.h"            // Boot screen bitmap

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

#define DEFAULT_SERVER_URL "http://192.168.137.1:8000"

// How often to POST sensor data to backend (milliseconds)
#define SENSOR_POST_INTERVAL 5000

#define SERVICE_UUID        "12340001-1234-5678-9ABC-FEDCBA987654"
#define CHAR_UUID_WIFI_SSID "12340002-1234-5678-9ABC-FEDCBA987654"
#define CHAR_UUID_WIFI_PASS "12340003-1234-5678-9ABC-FEDCBA987654"
#define CHAR_UUID_WIFI_STAT "12340004-1234-5678-9ABC-FEDCBA987654"
#define CHAR_UUID_BRK_STAT  "12340005-1234-5678-9ABC-FEDCBA987654"
#define CHAR_UUID_BRK_CMD   "12340006-1234-5678-9ABC-FEDCBA987654"

BLEServer* pServer = NULL;
BLECharacteristic* pCharWifiStat = NULL;
BLECharacteristic* pCharBrkStat = NULL;

bool deviceConnected = false;
bool oldDeviceConnected = false;

String wifiSsid = "LAPTOPOFYANG";
String wifiPass = "y1234567";
uint8_t wifiStatus = 0x00; // 0=disconnected, 1=connecting, 2=connected, 3=failed
unsigned long lastWifiCheck = 0;

// Latest Irms values shared between sensor read and HTTP post
double lastIrms[4] = {0, 0, 0, 0};
unsigned long lastSensorPost = 0;

void updateBreakerStateBLE();
void updateWifiStateBLE();
void connectToWiFi();
void postSensorData();

// --------- Pin Configuration ----------
const int ctPins[4] = {8, 18, 14, 16};
const int buttonPins[4] = {6, 1, 4, 2};
const int relayPins[4] = {17, 21, 19, 15};

// --------- Button & Relay State ----------
volatile bool relayState[4] = {false, false, false, false};
int buttonState[4] = {HIGH, HIGH, HIGH, HIGH};
int lastButtonReading[4] = {HIGH, HIGH, HIGH, HIGH};
unsigned long lastDebounceTime[4] = {0, 0, 0, 0};
unsigned long debounceDelay = 50;

volatile bool needEpdUpdate = false;
unsigned long lastEpdRefresh = 0;
const unsigned long EPD_MIN_INTERVAL = 2000; // Minimum 2s between EPD refreshes
volatile bool needBrkSave = false; // Deferred BLE notify flag for button presses
volatile bool enterPairingMode = false; // Set by button combo hold

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
    };
    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      BLEDevice::startAdvertising();
    }
};

class WifiSsidCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      if (value.length() > 0) {
        wifiSsid = value.c_str();
        connectToWiFi();
      }
    }
};

class WifiPassCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      if (value.length() > 0) {
        wifiPass = value.c_str();
        connectToWiFi();
      }
    }
};

class BrkCmdCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      if (value.length() >= 2) {
        uint8_t channel = value[0];
        uint8_t state = value[1];
        if (channel < 4) {
          relayState[channel] = (state == 1);
          digitalWrite(relayPins[channel], relayState[channel] ? HIGH : LOW);

          needEpdUpdate = true;
          updateBreakerStateBLE();
        }
      }
    }
};

void updateBreakerStateBLE() {
  if (pCharBrkStat) {
    uint8_t stateBitmap = 0;
    for (int i = 0; i < 4; i++) {
      if (relayState[i]) {
        stateBitmap |= (1 << i);
      }
    }
    pCharBrkStat->setValue(&stateBitmap, 1);
    pCharBrkStat->notify();
  }
}

void updateWifiStateBLE() {
  if (pCharWifiStat) {
    pCharWifiStat->setValue(&wifiStatus, 1);
    pCharWifiStat->notify();
  }
}

void connectToWiFi() {
  if (wifiSsid == "") {
    Serial.println("WiFi SSID is empty, aborting connection.");
    wifiStatus = 0x00;
    updateWifiStateBLE();
    return;
  }
  Serial.print("Connecting to WiFi SSID: ");
  Serial.println(wifiSsid);
  // Do not print wifiPass for security usually, but I'll print its length or content for debug
  Serial.print("Password: ");
  Serial.println(wifiPass);
  
  WiFi.disconnect(true, true); // Force disconnect before attempting to connect again
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  wifiStatus = 0x01; // connecting
  updateWifiStateBLE();
  lastWifiCheck = millis();
}

// --------- HTTP POST sensor data to backend ----------
void postSensorData() {
  if (wifiStatus != 0x02) return; // Only post when WiFi is connected

  HTTPClient http;
  String url = String(DEFAULT_SERVER_URL) + "/api/sensor";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Build JSON matching backend's SensorReading schema
  String json = "{\"device_id\":\"getmogged-pro-9000\",\"channels\":[";
  for (int i = 0; i < 4; i++) {
    if (i > 0) json += ",";
    json += "{\"channel_id\":" + String(i) + ",\"current_amps\":" + String(lastIrms[i], 3) + "}";
  }
  json += "]}";

  int httpCode = http.POST(json);
  if (httpCode > 0) {
    Serial.print("POST /api/sensor -> ");
    Serial.println(httpCode);
  } else {
    Serial.print("POST failed: ");
    Serial.println(http.errorToString(httpCode));
  }
  http.end();
}


#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET    -1
#define TCAADDR       0x70

Adafruit_SSD1306 displays[4] = {
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET),
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET),
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET),
  Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET)
};

const uint8_t tcaMap[4] = {2, 0, 3, 1};

void tcaSelect(uint8_t i) {
  if (i > 7) return;
  Wire.beginTransmission(TCAADDR);
  Wire.write(1 << i);
  Wire.endTransmission();
}

// 4 blocks distributed horizontally across the 792 pixel width
// 792 / 4 = 198 pixels per block.
// Center of each block for a 70px square is: (198 - 70) / 2 = 64
const int relayX[4] = {64, 262, 460, 658};
const int relayY[4] = {101, 101, 101, 101};

// --------- CT Parameters ----------
const float BURDEN = 100.0;     // ohms
const float TURNS  = 2000.0;    // CT ratio
const float ADC_REF = 3.3;
const int   ADC_MAX = 4095;

uint8_t ImageBW[27200];      // Declare an array of 27200 bytes to store black and white image data
uint8_t ImageBW_Prev[27200]; // Previous frame buffer for partial refresh comparison

bool epdFirstUpdate = true;
int  epdPartialCount = 0;
const int EPD_FULL_REFRESH_EVERY = 10; // Full refresh every N partial updates to clear ghosting

uint8_t ImageTest[27200];
void clear_all();

uint8_t square[4900];
uint8_t square2[4900];

void display_image(uint8_t *image, int x, int y, int w, int h);
void draw_image_to_buffer(uint8_t *image, int x, int y, int w, int h);
void update_screen();
void oledSynthwaveStartup();

void buttonTask(void *pvParameters) {
  unsigned long comboHoldStart = 0;
  bool comboTriggered = false;
  const unsigned long COMBO_HOLD_MS = 3000; // Hold 3 seconds

  for(;;) {
    // --- Detect button 1+2 held simultaneously ---
    bool btn1Held = (digitalRead(buttonPins[0]) == LOW);
    bool btn2Held = (digitalRead(buttonPins[1]) == LOW);
    if (btn1Held && btn2Held) {
      if (comboHoldStart == 0) {
        comboHoldStart = millis();
        comboTriggered = false;
      } else if (!comboTriggered && (millis() - comboHoldStart >= COMBO_HOLD_MS)) {
        comboTriggered = true;
        enterPairingMode = true;
      }
    } else {
      comboHoldStart = 0;
      comboTriggered = false;
    }

    // --- Normal per-button toggle logic ---
    for (int i = 0; i < 4; i++) {
      int reading = digitalRead(buttonPins[i]);

      if (reading != lastButtonReading[i]) {
        lastDebounceTime[i] = millis();
      }

      if ((millis() - lastDebounceTime[i]) > debounceDelay) {
        if (reading != buttonState[i]) {
          buttonState[i] = reading;

          if ((i == 0 && buttonState[i] == LOW) || i > 0) {
            relayState[i] = !relayState[i];
            digitalWrite(relayPins[i], relayState[i] ? HIGH : LOW);

            needBrkSave = true;  // Defer BLE notify to main loop (needs more stack)

            needEpdUpdate = true;
          }
        }
      }
      lastButtonReading[i] = reading;
    }
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

void setup() {
  Serial.begin(9600);
  Wire.begin(3, 9); // Initialize I2C with SDA=3, SCL=9 for the TCA9548A multiplexer

  analogReadResolution(12);   // 12-bit resolution

  for (int i = 0; i < 4; i++) {
    analogSetPinAttenuation(ctPins[i], ADC_11db);
  }

  for (uint8_t t=0; t<4; t++) {
    tcaSelect(tcaMap[t]);
    // Address 0x3C for most 128x32 OLEDs
    if(!displays[t].begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
      Serial.print("SSD1306 allocation failed for screen ");
      Serial.println(t);
    } else {
      displays[t].clearDisplay();
      displays[t].setTextColor(SSD1306_WHITE);
      displays[t].setTextSize(2);
      displays[t].setCursor(0, 0);
      displays[t].print("Screen ");
      displays[t].println(t + 1);
      displays[t].display();
    }
  }

  for(int i = 0; i < 4900; i++) {
    square[i] = 0x00; // 0x00 is BLACK
    square2[i] = 0xFF;
  }
  // Initialization settings, executed once when the program starts
  pinMode(7, OUTPUT);        // Set pin 7 to output mode
  digitalWrite(7, HIGH);     // Set pin 7 to high level to activate the screen power

  for (int i = 0; i < 4; i++) {
    relayState[i] = false;
    pinMode(buttonPins[i], INPUT_PULLUP);
    pinMode(relayPins[i], OUTPUT);
    digitalWrite(relayPins[i], LOW);
  }

  BLEDevice::init("getmogged-pro-9000");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);

  BLECharacteristic *pCharWifiSsid = pService->createCharacteristic(
                                         CHAR_UUID_WIFI_SSID,
                                         BLECharacteristic::PROPERTY_WRITE
                                       );
  pCharWifiSsid->setCallbacks(new WifiSsidCallbacks());

  BLECharacteristic *pCharWifiPass = pService->createCharacteristic(
                                         CHAR_UUID_WIFI_PASS,
                                         BLECharacteristic::PROPERTY_WRITE
                                       );
  pCharWifiPass->setCallbacks(new WifiPassCallbacks());

  pCharWifiStat = pService->createCharacteristic(
                      CHAR_UUID_WIFI_STAT,
                      BLECharacteristic::PROPERTY_READ |
                      BLECharacteristic::PROPERTY_NOTIFY
                    );
  pCharWifiStat->addDescriptor(new BLE2902());

  pCharBrkStat = pService->createCharacteristic(
                     CHAR_UUID_BRK_STAT,
                     BLECharacteristic::PROPERTY_READ |
                     BLECharacteristic::PROPERTY_NOTIFY
                   );
  pCharBrkStat->addDescriptor(new BLE2902());

  BLECharacteristic *pCharBrkCmd = pService->createCharacteristic(
                                       CHAR_UUID_BRK_CMD,
                                       BLECharacteristic::PROPERTY_WRITE
                                     );
  pCharBrkCmd->setCallbacks(new BrkCmdCallbacks());

  pService->start();
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMaxPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.println("=============================");
  Serial.println("BLE ADVERTISING STARTED");
  Serial.println("Device name: getmogged-pro-9000");
  Serial.print("Service UUID: ");
  Serial.println(SERVICE_UUID);
  Serial.println("=============================");
  updateBreakerStateBLE();
  connectToWiFi();

  EPD_GPIOInit();            // Initialize the GPIO pin configuration for the EPD electronic ink screen
  Paint_NewImage(ImageBW, EPD_W, EPD_H, Rotation, WHITE); // Create a new image buffer with dimensions EPD_W x EPD_H and a white background
  Paint_Clear(WHITE);        // Clear the image buffer and fill it with white

  /************************ Fast refresh screen operation in partial refresh mode ************************/
  EPD_FastMode1Init();       // Initialize the EPD screen's fast mode 1
  EPD_Display_Clear();       // Clear the screen content
  EPD_Update();              // Update the screen display

  // Display boot screen
  EPD_ShowPicture(0, 0, 792, 272, gImage_boot, BLACK);
  update_screen();
  oledSynthwaveStartup(); // Synthwave animation runs for ~2.6s while EPD shows boot logo
  Paint_Clear(WHITE);

  // Trigger first draw in loop()
  needEpdUpdate = true;

  xTaskCreatePinnedToCore(
    buttonTask,
    "ButtonTask",
    4096,
    NULL,
    1,
    NULL,
    0
  );
}


void loop() {
  // Handle BLE pairing mode triggered by holding buttons 1+2 for 3s
  if (enterPairingMode) {
    enterPairingMode = false;
    Serial.println("Entering BLE pairing mode...");

    // Clear stored WiFi credentials
    wifiSsid = "";
    wifiPass = "";
    WiFi.disconnect();
    wifiStatus = 0x00;
    updateWifiStateBLE();

    // Restart BLE advertising
    BLEDevice::startAdvertising();
    Serial.println("BLE advertising restarted");

    needEpdUpdate = true;
  }

  // Handle deferred NVS save + BLE notify from button task
  if (needBrkSave) {
    needBrkSave = false;
    updateBreakerStateBLE();
  }

  if (wifiStatus == 0x01) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("WiFi connected!");
      Serial.print("IP Address: ");
      Serial.println(WiFi.localIP());
      wifiStatus = 0x02; // connected
      updateWifiStateBLE();
      needEpdUpdate = true;
    } else if (millis() - lastWifiCheck > 15000) { // 15s timeout
      Serial.println("WiFi connection timeout!");
      Serial.print("Status: ");
      Serial.println(WiFi.status());
      wifiStatus = 0x03; // failed
      updateWifiStateBLE();
      needEpdUpdate = true;
    }
  }

  // Main loop function — rate-limit EPD refreshes
  if (needEpdUpdate && (millis() - lastEpdRefresh >= EPD_MIN_INTERVAL)) {
    needEpdUpdate = false;
    lastEpdRefresh = millis();

    // Clear the buffer
    Paint_Clear(WHITE);

    // --- WiFi status indicator (top-left) ---
    const char* wifiStr;
    if (wifiStatus == 0x01)      wifiStr = "WiFi: Connecting...";
    else if (wifiStatus == 0x02) wifiStr = "WiFi: Connected";
    else if (wifiStatus == 0x03) wifiStr = "WiFi: Failed";
    else if (wifiSsid == "")     wifiStr = "BLE Pairing Ready";
    else                         wifiStr = "WiFi: Disconnected";
    EPD_ShowString(10, 5, wifiStr, 16, BLACK);

    // Show IP address beside WiFi status if connected
    if (wifiStatus == 0x02) {
      String ipStr = "IP: " + WiFi.localIP().toString();
      EPD_ShowString(10, 24, ipStr.c_str(), 16, BLACK);
    }

    // WiFi status icon (filled/hollow circle, top-right)
    if (wifiStatus == 0x02) {
      EPD_DrawCircle(760, 15, 10, BLACK, 1);  // Filled = connected
    } else {
      EPD_DrawCircle(760, 15, 10, BLACK, 0);  // Hollow = not connected
    }

    // Separator line below WiFi bar
    EPD_DrawLine(0, 44, 791, 44, BLACK);

    // --- Draw relay blocks with labels ---
    const char* relayLabels[4] = {"CH1", "CH2", "CH3", "CH4"};
    for (int i = 0; i < 4; i++) {
      // Channel label above the square (48px font, 24px char width)
      int labelW = 3 * 24; // "CHx" = 72px wide at 48px font
      int labelX = relayX[i] + (70 - labelW) / 2;
      EPD_ShowString(labelX, relayY[i] - 55, relayLabels[i], 48, BLACK);

      // Relay state: filled rectangle = ON, outlined rectangle = OFF
      if (relayState[i]) {
        EPD_DrawRectangle(relayX[i], relayY[i], relayX[i] + 70, relayY[i] + 70, BLACK, 1);
      } else {
        EPD_DrawRectangle(relayX[i], relayY[i], relayX[i] + 70, relayY[i] + 70, BLACK, 0);
      }

      // ON/OFF label below the square (24px font)
      const char* stStr = relayState[i] ? "ON" : "OFF";
      int stLen = relayState[i] ? 2 : 3;
      int stW = stLen * 12; // 12px per char at size 24
      int stX = relayX[i] + (70 - stW) / 2;
      EPD_ShowString(stX, relayY[i] + 78, stStr, 24, BLACK);
    }
    update_screen();
  }

  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 1000) {
    lastUpdate = millis();

    const int samples = 2000;
    double sum[4] = {0,0,0,0};

    for (int i = 0; i < samples; i++) {
      for (int ch = 0; ch < 4; ch++) {
        int raw = analogRead(ctPins[ch]);

        // Center around midpoint (1.65V ≈ 2048 ADC counts)
        double voltage = (raw - (ADC_MAX / 2.0)) * (ADC_REF / ADC_MAX);

        sum[ch] += voltage * voltage;
      }
    }

    double Irms[4];
    for (int ch = 0; ch < 4; ch++) {
      double Vrms = sqrt(sum[ch] / samples);

      // Convert voltage to primary current
      Irms[ch] = ((Vrms / BURDEN) * TURNS)-2.75;

      // Clamp negative readings to zero
      if (Irms[ch] < 0) Irms[ch] = 0;

      // Store for HTTP posting
      lastIrms[ch] = Irms[ch];

      Serial.print("CT");
      Serial.print(ch);
      Serial.print(": ");
      Serial.print(Irms[ch], 3);
      Serial.print(" A   ");
    }
    Serial.println();

    // Update Screens
    for (uint8_t t = 0; t < 4; t++) {
      tcaSelect(tcaMap[t]);
      displays[t].clearDisplay();

      String currentStr = relayState[t] ? String(Irms[t], 2) + "A" : "0.00A";

      displays[t].setTextSize(3);

      // Calculate text width to center it (approx. 12 pixels per character for size 2)
      int textWidth = currentStr.length() * 12;
      int x = (SCREEN_WIDTH - textWidth) / 2;

      // Center vertically as well (height is approx 16 pixels for size 2, on a 32px high screen)
      int y = (SCREEN_HEIGHT - 16) / 2;

      displays[t].setCursor(x, y);
      displays[t].print(currentStr);

      // Display the small screen/breaker number in the bottom left corner
      displays[t].setTextSize(1);
      displays[t].setCursor(0, SCREEN_HEIGHT - 8); // Size 1 text is 8 pixels high
      displays[t].print(t + 1);

      displays[t].display();
    }
  }

  // --------- POST sensor data to backend every SENSOR_POST_INTERVAL ms ----------
  if (wifiStatus == 0x02 && (millis() - lastSensorPost >= SENSOR_POST_INTERVAL)) {
    lastSensorPost = millis();
    postSensorData();
  }
}

void clear_all() {
  // Function to clear the screen content
  EPD_FastMode1Init();       // Initialize the EPD screen's fast mode 1
  EPD_Display_Clear();       // Clear the screen content
  EPD_Update();              // Update the screen display
}

void display_image(uint8_t *image, int x, int y, int w, int h) {
    uint8_t * temp = (uint8_t *)malloc(w * h * sizeof(uint8_t));

    // Use && to ensure the entire sprite is within BOTH width and height bounds
    if(x + w <= 792 && y + h <= 272) {

      EPD_GPIOInit();            // Reinitialize the GPIO pin configuration for the EPD electronic ink screen
      EPD_FastMode1Init();

      // Corrected loop to iterate correctly over x/y coordinates and array indices
      for(int j = 0; j < h; j++) {
        for(int i = 0; i < w; i++) {
          // Draw at coordinate (x+i, y+j) reading from standard row-major 1D array
          Paint_SetPixel(x + i, y + j, image[j * w + i]);
        }
      }

      EPD_Display(ImageBW);      // Display the image stored in the ImageBW array

      //EPD_FastUpdate();          // Perform a fast update to refresh the screen
      EPD_DeepSleep();           // Set the screen to deep sleep mode to save power
    }

    free(temp); // Free the dynamically allocated memory
}

void draw_image_to_buffer(uint8_t *image, int x, int y, int w, int h) {
    if(x + w <= 792 && y + h <= 272) {
      for(int j = 0; j < h; j++) {
        for(int i = 0; i < w; i++) {
          Paint_SetPixel(x + i, y + j, image[j * w + i]);
        }
      }
    }
}

// Update screen using partial refresh where possible.
// After deep sleep the display RAM is lost, so we must always re-send the
// previous frame (ImageBW_Prev) into the OLD registers before the new frame.
// EPD_PartUpdate (0xDC) then only drives pixels that differ — much faster.
// A full EPD_Update (0xF7) is done on the first call and every
// EPD_FULL_REFRESH_EVERY partial updates to prevent ghosting build-up.
void update_screen() {
    EPD_FastMode1Init();        // HW reset (required after deep sleep) + temperature load

    if (epdFirstUpdate || epdPartialCount >= EPD_FULL_REFRESH_EVERY) {
        // Full waveform refresh — clears ghosting.
        // EPD_Display_Clear primes old registers to all-black (0x00) so
        // EPD_Update drives every pixel from a known black baseline to its
        // target state, fully eliminating any ghost residue.
        EPD_Display_Clear();        // old=0x00 (black), new=0xFF (white)
        EPD_Display(ImageBW);       // overwrite new frame with actual content
        EPD_Update();               // full waveform: all pixels black → target
        epdFirstUpdate = false;
        epdPartialCount = 0;
    } else {
        // Partial refresh — only re-drives changed pixels
        EPD_DisplayOld(ImageBW_Prev);   // Tell controller what is currently shown
        EPD_Display(ImageBW);           // Write the new frame
        EPD_PartUpdate();               // Drive only changed pixels (fast)
        epdPartialCount++;
    }

    memcpy(ImageBW_Prev, ImageBW, sizeof(ImageBW_Prev));  // Remember what we just showed
    EPD_DeepSleep();
}

// Synthwave startup animation across all 4 OLED screens.
// The screens are treated as one continuous 512x32 display.
//
// Phase 1 (~1.3s): A 4px scan bar with a glow fringe sweeps left→right.
// Phase 2 (~1.0s): A perspective grid materialises — horizontal lines appear
//   bottom→horizon, then vertical convergence lines fan out from the vanishing
//   point at the centre of the combined display.  Stars fade in above the horizon.
// Phase 3 (~0.4s): Neon strobe pulses via invertDisplay.
void oledSynthwaveStartup() {
    const int W = 128, H = 32, N = 4;
    const int TOTAL_W = W * N;  // 512 px
    const int HORIZON_Y = 13;

    // ---- Phase 1: Vertical scan bar sweeps across all four screens ----
    // Core is 4 px wide; ±3 px fringe draws every-other-row for a glow effect.
    for (int barX = -6; barX <= TOTAL_W + 6; barX += 4) {
        for (int s = 0; s < N; s++) {
            int sStart = s * W;
            tcaSelect(tcaMap[s]);
            displays[s].clearDisplay();
            for (int dx = -3; dx < 7; dx++) {
                int lx = (barX + dx) - sStart;
                if (lx < 0 || lx >= W) continue;
                if (dx >= 0 && dx < 4) {
                    for (int y = 0; y < H; y++)
                        displays[s].drawPixel(lx, y, SSD1306_WHITE);
                } else {
                    for (int y = 0; y < H; y += 2)
                        displays[s].drawPixel(lx, y, SSD1306_WHITE);
                }
            }
            displays[s].display();
        }
        delay(10);
    }

    // ---- Phase 2: Perspective grid materialises ----
    // Horizontal lines compressed toward the horizon = depth illusion.
    const int hGridY[6] = {31, 27, 23, 20, 17, 15};
    const int nH = 6;

    // Vertical lines converge to a single vanishing point at the midpoint of
    // the combined display (global x=256, y=HORIZON_Y).
    const int VP_GX   = TOTAL_W / 2;  // 256
    const int vBotX[9] = {0, 64, 128, 192, 256, 320, 384, 448, 511};
    const int nV = 9;
    // Reveal from the centre line outward so it fans open symmetrically.
    const int vRevealOrder[9] = {4, 3, 5, 2, 6, 1, 7, 0, 8};

    // Stars: base x positions; each screen offsets by 31 px so the sky
    // looks different across the four panels.
    const int starBaseX[8] = {  5, 18, 35, 52, 68, 83, 100, 119};
    const int starBaseY[8] = {  3,  8,  2,  6,  10,  4,   9,   1};

    for (int step = 0; step < nV; step++) {
        for (int s = 0; s < N; s++) {
            int sStart = s * W;
            tcaSelect(tcaMap[s]);
            displays[s].clearDisplay();

            // Horizon line — always present
            displays[s].drawLine(0, HORIZON_Y, W - 1, HORIZON_Y, SSD1306_WHITE);

            // Horizontal grid lines (revealed bottom → horizon, one per step)
            for (int i = 0; i < nH && i <= step; i++)
                displays[s].drawLine(0, hGridY[i], W - 1, hGridY[i], SSD1306_WHITE);

            // Vertical convergence lines (centre-outward reveal).
            // Coordinates are global; Adafruit GFX clips out-of-bounds pixels.
            for (int vi = 0; vi <= step; vi++) {
                int v  = vRevealOrder[vi];
                displays[s].drawLine(VP_GX    - sStart, HORIZON_Y,
                                     vBotX[v] - sStart, 31,
                                     SSD1306_WHITE);
            }

            // Stars fade in above the horizon, staggered across steps
            for (int i = 0; i < 8; i++) {
                if (step > i / 2) {
                    int sx = (starBaseX[i] + s * 31) % W;
                    displays[s].drawPixel(sx, starBaseY[i], SSD1306_WHITE);
                }
            }

            displays[s].display();
        }
        delay(100);
    }

    // ---- Phase 3: Neon strobe pulses ----
    for (int flash = 0; flash < 4; flash++) {
        bool inv = (flash % 2 == 0);
        for (int s = 0; s < N; s++) {
            tcaSelect(tcaMap[s]);
            displays[s].invertDisplay(inv);
        }
        delay(inv ? 55 : 90);
    }
    // Leave display in normal (non-inverted) mode with grid still visible
    for (int s = 0; s < N; s++) {
        tcaSelect(tcaMap[s]);
        displays[s].invertDisplay(false);
    }
    delay(150);
}
