#include <Arduino.h>         // Include the core Arduino library to provide basic Arduino functionality
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "EPD.h"             // Include the EPD library for controlling the electronic ink screen (E-Paper Display)
#undef WHITE
#undef BLACK
#define WHITE 0xFF
#define BLACK 0x00
#include "pic_home.h"        // Include the header file containing image data
// #include "img/device_interface2.h" // Include the header file containing additional image data

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Preferences.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

#define DEFAULT_SERVER_URL "http://192.168.0.208:8000/"


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

String deviceName = "EnergyAI-????";

Preferences preferences;

String wifiSsid = "";
String wifiPass = "";
uint8_t wifiStatus = 0x00; // 0=disconnected, 1=connecting, 2=connected, 3=failed
unsigned long lastWifiCheck = 0;

void updateBreakerStateBLE();
void updateWifiStateBLE();
void connectToWiFi();

// --------- Pin Configuration ----------
const int ctPins[4] = {8, 14, 16, 18};
const int buttonPins[4] = {1, 2, 4, 6};
const int relayPins[4] = {15, 17, 19, 21};

// --------- Button & Relay State ----------
volatile bool relayState[4] = {false, false, false, false};
int buttonState[4] = {HIGH, HIGH, HIGH, HIGH};
int lastButtonReading[4] = {HIGH, HIGH, HIGH, HIGH};
unsigned long lastDebounceTime[4] = {0, 0, 0, 0};
unsigned long debounceDelay = 50;

volatile bool needEpdUpdate = false;
unsigned long lastEpdRefresh = 0;
const unsigned long EPD_MIN_INTERVAL = 2000; // Minimum 2s between EPD refreshes
volatile bool needBrkSave = false; // Deferred NVS save flag for button presses
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
        preferences.putString("ssid", wifiSsid);
        connectToWiFi();
      }
    }
};

class WifiPassCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      if (value.length() > 0) {
        wifiPass = value.c_str();
        preferences.putString("pass", wifiPass);
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
          
          uint8_t stateBitmap = 0;
          for(int i = 0; i < 4; i++) {
              if(relayState[i]) stateBitmap |= (1 << i);
          }
          preferences.putUChar("brkStat", stateBitmap);

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
    wifiStatus = 0x00;
    updateWifiStateBLE();
    return;
  }
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  wifiStatus = 0x01; // connecting
  updateWifiStateBLE();
  lastWifiCheck = millis();
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

uint8_t ImageTest[27200];
void clear_all();

uint8_t square[4900];
uint8_t square2[4900];

void display_image(uint8_t *image, int x, int y, int w, int h);
void draw_image_to_buffer(uint8_t *image, int x, int y, int w, int h);
void update_screen();

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
          
          if (buttonState[i] == LOW) {
            relayState[i] = !relayState[i];
            digitalWrite(relayPins[i], relayState[i] ? HIGH : LOW);
            
            needBrkSave = true;  // Defer NVS write to main loop (needs more stack)
            
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
    tcaSelect(t);
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

  preferences.begin("app", false);
  wifiSsid = preferences.getString("ssid", "");
  wifiPass = preferences.getString("pass", "");
  uint8_t savedBrkStat = preferences.getUChar("brkStat", 0);

  for (int i = 0; i < 4; i++) {
    relayState[i] = (savedBrkStat & (1 << i)) ? true : false;
    pinMode(buttonPins[i], INPUT_PULLUP);
    pinMode(relayPins[i], OUTPUT);
    digitalWrite(relayPins[i], relayState[i] ? HIGH : LOW);
  }

  WiFi.mode(WIFI_STA);
  String macStr = WiFi.macAddress();
  macStr.replace(":", "");
  deviceName = "EnergyAI-" + macStr.substring(8);
  
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  BLEDevice::init(deviceName.c_str());
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

  updateBreakerStateBLE();
  connectToWiFi();

  EPD_GPIOInit();            // Initialize the GPIO pin configuration for the EPD electronic ink screen
  Paint_NewImage(ImageBW, EPD_W, EPD_H, Rotation, WHITE); // Create a new image buffer with dimensions EPD_W x EPD_H and a white background
  Paint_Clear(WHITE);        // Clear the image buffer and fill it with white

  /************************ Fast refresh screen operation in partial refresh mode ************************/
  EPD_FastMode1Init();       // Initialize the EPD screen's fast mode 1
  EPD_Display_Clear();       // Clear the screen content
  EPD_Update();              // Update the screen display

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
    preferences.remove("ssid");
    preferences.remove("pass");
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
    uint8_t stateBitmap = 0;
    for (int i = 0; i < 4; i++) {
      if (relayState[i]) stateBitmap |= (1 << i);
    }
    preferences.putUChar("brkStat", stateBitmap);
    updateBreakerStateBLE();
  }

  if (wifiStatus == 0x01) {
    if (WiFi.status() == WL_CONNECTED) {
      wifiStatus = 0x02; // connected
      updateWifiStateBLE();
      needEpdUpdate = true;
    } else if (millis() - lastWifiCheck > 15000) { // 15s timeout
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
      Irms[ch] = ((Vrms / BURDEN) * TURNS)-1.75;

      Serial.print("CT");
      Serial.print(ch);
      Serial.print(": ");
      Serial.print(Irms[ch], 3);
      Serial.print(" A   ");
    }
    Serial.println();

    static unsigned int postCounter = 0;
    postCounter++;
    if (wifiStatus == 0x02 && postCounter >= 10) {
      postCounter = 0;
      
      HTTPClient http;
      http.begin(String(DEFAULT_SERVER_URL) + "api/sensor");
      http.addHeader("Content-Type", "application/json");

      struct tm timeinfo;
      char timeStr[32] = "1970-01-01T00:00:00Z";
      if(getLocalTime(&timeinfo, 10)) {
          strftime(timeStr, sizeof(timeStr), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
      }

      String payload = "{";
      payload += "\"device_id\": \"" + deviceName + "\",";
      payload += "\"timestamp\": \"" + String(timeStr) + "\",";
      payload += "\"channels\": [";
      for(int i=0; i<4; i++) {
          float current = Irms[i] < 0 ? 0 : Irms[i];
          payload += "{ \"channel_id\": " + String(i) + ", \"current_amps\": " + String(current, 2) + " }";
          if(i < 3) payload += ",";
      }
      payload += "]}";

      int httpCode = http.POST(payload);
      if (httpCode > 0) {
        Serial.printf("POST success: %d\n", httpCode);
      } else {
        Serial.printf("POST failed: %s\n", http.errorToString(httpCode).c_str());
      }
      http.end();
    }

    // Update Screens
    for (uint8_t t = 0; t < 4; t++) {
      tcaSelect(t);
      displays[t].clearDisplay();
      
      String currentStr = String(Irms[t], 2) + "A";
      
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

// Full update using fast-mode LUT — always drives all pixels correctly
// No old-vs-new buffer comparison needed, so toggling ON/OFF always works
void update_screen() {
    EPD_FastMode1Init();        // Load fast waveform LUT (includes HW reset)
    EPD_Display(ImageBW);       // Write image to new frame registers
    EPD_Update();               // Full waveform — drives every pixel to match buffer
    EPD_DeepSleep();
}