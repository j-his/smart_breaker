#include <Arduino.h>         // Include the core Arduino library to provide basic Arduino functionality
#include "EPD.h"             // Include the EPD library for controlling the electronic ink screen (E-Paper Display)
#include "pic_home.h"        // Include the header file containing image data
// #include "img/device_interface2.h" // Include the header file containing additional image data

uint8_t ImageBW[27200];      // Declare an array of 27200 bytes to store black and white image data

uint8_t ImageTest[27200];
void clear_all();

uint8_t square[4900];
uint8_t square2[4900];

void display_image(uint8_t *image, int x, int y, int w, int h);
void draw_image_to_buffer(uint8_t *image, int x, int y, int w, int h);
void update_screen();

void setup() {
  for(int i = 0; i < 4900; i++) {
    square[i] = 0x00; // 0x00 is BLACK
    square2[i] = 0xFF;
  }
  // Initialization settings, executed once when the program starts
  pinMode(7, OUTPUT);        // Set pin 7 to output mode
  digitalWrite(7, HIGH);     // Set pin 7 to high level to activate the screen power

  pinMode(21, OUTPUT);
  pinMode(17, OUTPUT);
  pinMode(19, OUTPUT);
  pinMode(15, OUTPUT);

  EPD_GPIOInit();            // Initialize the GPIO pin configuration for the EPD electronic ink screen
  Paint_NewImage(ImageBW, EPD_W, EPD_H, Rotation, WHITE); // Create a new image buffer with dimensions EPD_W x EPD_H and a white background
  Paint_Clear(WHITE);        // Clear the image buffer and fill it with white

  /************************ Fast refresh screen operation in partial refresh mode ************************/
  EPD_FastMode1Init();       // Initialize the EPD screen's fast mode 1
  EPD_Display_Clear();       // Clear the screen content
  EPD_Update();              // Update the screen display

  // display_image(gImage_device_interface2, 0, 0, 792, 272);
  delay(1000);
  
  // Center coordinates for a 70x70 square on a 792x272 screen
  // x = (792 - 70) / 2 = 361
  // y = (272 - 70) / 2 = 101
  draw_image_to_buffer(square, 361, 101, 70, 70);
  update_screen();
  delay(1000);
  
  // Add more black squares around the center
  draw_image_to_buffer(square, 261, 101, 70, 70); // Left square
  update_screen();
  digitalWrite(21, HIGH);
  delay(1000);
  digitalWrite(21, LOW);

  draw_image_to_buffer(square, 461, 101, 70, 70); // Right square
  update_screen();
  digitalWrite(17, HIGH);
  delay(1000);
  digitalWrite(17, LOW);

  draw_image_to_buffer(square, 361, 21,  70, 70); // Top square
  update_screen();
  digitalWrite(19, HIGH);
  delay(1000);
  digitalWrite(19, LOW);

  draw_image_to_buffer(square, 361, 181, 70, 70); // Bottom square
  update_screen();
  digitalWrite(15, HIGH);
  delay(1000);
  digitalWrite(15, LOW);
  
  delay(5000);               // Wait for 5000 milliseconds (5 seconds)

  clear_all();               // Call the clear_all function to clear the screen content
}


void loop() {
  // Main loop function, currently does not perform any actions
  // Code that needs to be executed repeatedly can be added here
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

void update_screen() {
    EPD_HW_RESET();
    EPD_Display(ImageBW);      // Display the image stored in the ImageBW array
    EPD_PartUpdate();          // Update part of the screen to show the new content
    EPD_DeepSleep();
}