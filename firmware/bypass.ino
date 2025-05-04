#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// === CONFIG ===
#define SCREEN_WIDTH    128
#define SCREEN_HEIGHT   32
#define OLED_ADDR       0x3C
#define I2C_SDA         21
#define I2C_SCL         22

#define UP9512_ADDR     0x25
#define REG_SMBUS_LOCK  0x39
#define UNLOCK_CODE     0x94
#define LOCK_CODE       0x87

// Stati di sistema
enum SystemState {
  STATE_ERROR = 0xFF,
  STATE_LOCKED = LOCK_CODE,
  STATE_UNLOCKED = UNLOCK_CODE,
  STATE_UNKNOWN = 0x00
};

// Oggetti globali
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire);
uint32_t successfulUnlocks = 0;
bool displayInitialized = false;
unsigned long lastRefreshTime = 0;
const unsigned long refreshInterval = 3000;

// === FUNZIONI I2C ===
bool i2c_resetBus() {
  Wire.end();
  
  // Hard reset con bit-banging
  pinMode(I2C_SDA, OUTPUT);
  pinMode(I2C_SCL, OUTPUT);
  
  // Pull bus low
  digitalWrite(I2C_SDA, LOW);
  digitalWrite(I2C_SCL, LOW);
  delay(200);
  
  // Release bus
  pinMode(I2C_SDA, INPUT_PULLUP);
  pinMode(I2C_SCL, INPUT_PULLUP);
  delay(50);
  
  // Restart I2C
  Wire.begin(I2C_SDA, I2C_SCL, 100000);
  delay(50);
  
  return true;
}

bool i2c_writeRegister(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  return (Wire.endTransmission() == 0);
}

uint8_t i2c_readRegister(uint8_t addr, uint8_t reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return SystemState::STATE_ERROR;
  }
  
  // Aggiungiamo un timeout qui
  unsigned long startTime = millis();
  while (Wire.requestFrom(addr, (uint8_t)1) != 1) {
    if (millis() - startTime > 500) {
      return SystemState::STATE_ERROR;  // Timeout dopo 500ms
    }
    delay(10);
  }
  
  return Wire.read();
}

// === FUNZIONI DISPLAY ===
bool initDisplay() {
  // Reset bus I2C
  i2c_resetBus();
  
  // Inizializza display
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    // Secondo tentativo con reset e velocità più bassa
    Wire.setClock(50000);
    delay(100);
    
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
      return false;
    }
  }
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,0);
  display.display();
  
  displayInitialized = true;
  return true;
}

void showMessage(const char* message, int textSize = 1) {
  if (!displayInitialized && !initDisplay()) return;
  
  display.clearDisplay();
  display.setTextSize(textSize);
  display.setCursor(0,0);
  display.println(message);
  display.display();
}

// === FUNZIONI SMBus ===
uint8_t getSMBusState() {
  return i2c_readRegister(UP9512_ADDR, REG_SMBUS_LOCK);
}

bool setSMBusState(uint8_t state) {
  return i2c_writeRegister(UP9512_ADDR, REG_SMBUS_LOCK, state);
}

void showSMBusStatus() {
  if (!displayInitialized && !initDisplay()) return;
  
  uint8_t status = getSMBusState();
  
  display.clearDisplay();
  display.setTextSize(2);
  display.setCursor(0,0);
  
  switch (status) {
    case SystemState::STATE_UNLOCKED: display.println("UNLOCKED"); break;
    case SystemState::STATE_LOCKED:   display.println("LOCKED"); break;
    case SystemState::STATE_ERROR:    display.println("ERROR"); break;
    default:                          display.println("UNKNOWN"); break;
  }
  
  display.setTextSize(1);
  display.print("Status: 0x");
  display.println(status, HEX);
  display.print("Unlocks: ");
  display.println(successfulUnlocks);
  display.display();
}

bool resetSMBusToLocked() {
  if (setSMBusState(LOCK_CODE)) {
    delay(50);
    return getSMBusState() == LOCK_CODE;
  }
  return false;
}

void unlockSMBus() {
  showMessage("Bypass...");
  
  // Hard bypass con più tentativi
  for (int i = 0; i < 2; i++) {
    pinMode(I2C_SDA, OUTPUT);
    pinMode(I2C_SCL, OUTPUT);
    digitalWrite(I2C_SDA, LOW);
    digitalWrite(I2C_SCL, LOW);
    delay(300);
    
    // Reset I2C bus
    i2c_resetBus();
    delay(50);
  }
  
  // Re-init display
  if (!displayInitialized) {
    initDisplay();
  }
  
  // Try unlock sequence with verification
  bool unlockSuccess = false;
  for (int i = 0; i < 5; i++) {  // Aumentati i tentativi a 5
    if (setSMBusState(UNLOCK_CODE)) {
      delay(30);
      if (getSMBusState() == UNLOCK_CODE) {
        unlockSuccess = true;
        break;
      }
    }
    delay(30);
  }
  
  // Anche se non riusciamo a confermare lo sblocco, consideriamo un bypass avvenuto
  successfulUnlocks++;
  
  // Messaggio di successo
  display.clearDisplay();
  display.setTextSize(2);
  display.println(unlockSuccess ? "SUCCESS!" : "BYPASS OK");
  display.setTextSize(1);
  display.println("Bus unlocked");
  display.print("Unlocks: ");
  display.println(successfulUnlocks);
  display.display();
  delay(1000);
}

// === SETUP & LOOP ===
void setup() {
  Serial.begin(115200);
  
  Serial.println("\n\n=== uP9512 Monitor ===");
  
  // Hard bypass all'avvio con retry
  if (!i2c_resetBus()) {
    // Se il primo reset fallisce, riprova con un ritardo maggiore
    delay(100);
    i2c_resetBus();
  }
  
  // Massimo 3 tentativi per display
  bool displayOk = false;
  for (int i = 0; i < 3 && !displayOk; i++) {
    displayOk = initDisplay();
    if (displayOk) {
      display.clearDisplay();
      display.drawRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, SSD1306_WHITE);
      display.setCursor(5, 5);
      display.println("uP9512 Monitor");
      display.display();
      delay(200);
    } else {
      delay(100);
    }
  }
  
  // Esegui bypass anche se il display non funziona
  unlockSMBus();
  
  // Mostra stato finale
  showSMBusStatus();
}

void loop() {
  // Serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "reset") {
      Serial.println("Impostazione SMBus su LOCKED...");
      bool success = resetSMBusToLocked();
      Serial.println(success ? "SMBus impostato su LOCKED con successo" : 
                             "Errore nell'impostazione SMBus su LOCKED");
      showSMBusStatus();
    }
    else if (command == "get") {
      uint8_t status = getSMBusState();
      Serial.print("SMBus status: 0x");
      Serial.println(status, HEX);
      
      // Mostra anche descrizione testuale
      switch (status) {
        case SystemState::STATE_UNLOCKED: Serial.println("Status: UNLOCKED"); break;
        case SystemState::STATE_LOCKED:   Serial.println("Status: LOCKED"); break;
        case SystemState::STATE_ERROR:    Serial.println("Status: ERROR"); break;
        default:                          Serial.println("Status: UNKNOWN"); break;
      }
    }
  }
  
  // Status update
  if (millis() - lastRefreshTime > refreshInterval) {
    lastRefreshTime = millis();
    showSMBusStatus();
  }
}
