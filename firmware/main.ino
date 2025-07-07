#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>
#include <map>

// === CONFIG ===
#define OLED_ADDR       0x3C
#define SCREEN_WIDTH    128
#define SCREEN_HEIGHT   32

#define I2C_DISP_SDA    21
#define I2C_DISP_SCL    22
#define I2C_DEV_SDA     32
#define I2C_DEV_SCL     33

#define BULK_BUFFER_SIZE 64
#define JSON_CAPACITY 128

struct KnownDevice {
    uint8_t addr;
    const char* name;
};

struct Device {
    uint8_t addr7;
    String name;
};
Device devices[16];

struct DeviceState {
    uint8_t addr;
    bool isPresent;
    const char* name;
};

// Struttura per la signature di un dispositivo
struct DeviceSignature {
    const char* name;
    const uint8_t* registers;
    const uint8_t* expected_values;
    uint8_t num_regs;
};

// Tabella di signature
const DeviceSignature DEVICE_SIGNATURES[] = {
    {"NCP4206", {0x99, 0x9A}, {0xFF, 0xFF}, 2},             // MFR_ID, MFR_MODEL 
    {"uP9512", {0x27, 0x00}, {0xFF, 0xFF}, 2},              // Vendor ID, Device ID
};
const size_t NUM_SIGNATURES = sizeof(DEVICE_SIGNATURES)/sizeof(DeviceSignature);

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire);
bool displayInitialized = false;

enum DisplayMode {
    MODE_UPTIME,
    MODE_I2C_MONITOR
};

DisplayMode current_display_mode = MODE_UPTIME;
unsigned long last_display_update = 0;

struct {
    uint32_t total_ops = 0;
    uint32_t total_time_us = 0;
    uint32_t avg_time_us = 0;
    uint32_t last_update = 0;
    uint32_t reads_per_second = 0;
    uint32_t writes_per_second = 0;
    uint32_t writes_per_minute = 0;
    uint32_t total_reads = 0;
    uint32_t total_writes = 0;
    uint32_t last_reads = 0;
    uint32_t last_writes = 0;
} metrics;

uint8_t current_device_idx = 0;
uint8_t num_devices = 0;
DeviceState currentDevice;

// === FUNZIONI I2C ===
String identify_device_by_registers(uint8_t addr) {
    for (size_t i = 0; i < NUM_SIGNATURES; i++) {
        bool match = true;
        for (uint8_t j = 0; j < DEVICE_SIGNATURES[i].num_regs; j++) {
            uint8_t reg = DEVICE_SIGNATURES[i].registers[j];
            uint8_t expected = DEVICE_SIGNATURES[i].expected_values[j];
            uint8_t value = i2c_readRegister(addr, reg);
            if (value != expected) {
                match = false;
                break;
            }
        }
        if (match) {
            return DEVICE_SIGNATURES[i].name;
        }
    }
    return "Unknown";
}

void scan_i2c_bus() {
    num_devices = 0;
    for(uint8_t addr = 1; addr < 127; addr++) {
        Wire1.beginTransmission(addr);
        if(Wire1.endTransmission() == 0) {
            if(num_devices < 16) {
                devices[num_devices].addr7 = addr;
                devices[num_devices].name = identify_device_by_registers(addr);
                num_devices++;
            }
        }
    }
}

void add_devices_to_response(JsonDocument& res) {
    JsonArray arr = res.createNestedArray("devices");
    JsonArray names = res.createNestedArray("names");
    for(uint8_t i=0; i<num_devices; i++) {
        arr.add(devices[i].addr7);
        names.add(devices[i].name);
    }
}

bool i2c_resetBus() {
    Wire1.end();
  
    pinMode(I2C_DEV_SDA, OUTPUT);
    pinMode(I2C_DEV_SCL, OUTPUT);
    digitalWrite(I2C_DEV_SDA, LOW);
    digitalWrite(I2C_DEV_SCL, LOW);
    delay(200);

    pinMode(I2C_DEV_SDA, INPUT_PULLUP);
    pinMode(I2C_DEV_SCL, INPUT_PULLUP);
    delay(50);

    Wire1.begin(I2C_DEV_SDA, I2C_DEV_SCL, 400000);
    delay(50);

    return true;
}

bool i2c_writeRegister(uint8_t addr, uint8_t reg, uint8_t value) {
    Wire1.beginTransmission(addr);
    Wire1.write(reg);
    Wire1.write(value);
    uint8_t result = Wire1.endTransmission();
    
    if(result != 0) {
        Serial.print("I2C Write Error: ");
        switch(result) {
            case 1: Serial.println("data too long"); break;
            case 2: Serial.println("NACK on address"); break; 
            case 3: Serial.println("NACK on data"); break;
            case 4: Serial.println("other error"); break;
            default: Serial.println("unknown error"); break;
        }
        Wire1.flush();
        return false;
    }

    return true;
}

uint8_t i2c_readRegister(uint8_t addr, uint8_t reg) {
    Wire1.beginTransmission(addr);
    Wire1.write(reg);

    if (Wire1.endTransmission(false) != 0) {
        return 0xFF;  // Error value
    }
  
    unsigned long startTime = micros();
    while (Wire1.requestFrom(addr, (uint8_t)1) != 1) {
        if (micros() - startTime > 1000) {
            Wire1.flush();
            return 0xFF;  // Error value
        }
    }
  
    return Wire1.read();
}

void handle_bulk_rw(JsonDocument& cmd, JsonDocument& res) {
    uint32_t start_time = micros();
    uint8_t addr = currentDevice.addr;
    bool success = true;
    uint32_t op_count = 0;

    if(cmd.containsKey("reads")) {
        JsonArray reads = cmd["reads"].as<JsonArray>();
        success = handle_bulk_reads(reads, res, addr, op_count);
        if(success) {
            metrics.total_reads += reads.size();
        }
    }
    
    if(success && cmd.containsKey("writes")) {
        JsonArray writes = cmd["writes"].as<JsonArray>();
        success = handle_bulk_writes(writes, addr, op_count);
        if(success) {
            metrics.total_writes += writes.size();
        }
    }
    
    uint32_t elapsed = micros() - start_time;
    metrics.total_time_us += elapsed;
    metrics.total_ops += op_count;
    
    if (metrics.total_ops > 0) {
        metrics.avg_time_us = metrics.total_time_us / metrics.total_ops;
    }
    
    current_display_mode = MODE_I2C_MONITOR;
    update_display_stats();
    
    res["status"] = success ? "OK" : "ERROR";
    res["timing_us"] = elapsed;
    res["op_count"] = op_count;
}

bool handle_bulk_reads(const JsonArray& reads, JsonDocument& res, uint8_t addr, uint32_t& op_count) {
    size_t count = min(reads.size(), (size_t)BULK_BUFFER_SIZE);
    uint8_t buffer[BULK_BUFFER_SIZE];
    op_count += count;
    
    for(size_t i = 0; i < count; i++) {
        buffer[i] = i2c_readRegister(addr, reads[i].as<uint8_t>());
        if(buffer[i] == 0xFF) {
            return false;
        }
    }
    
    JsonArray values = res.createNestedArray("values");
    for(size_t i = 0; i < count; i++) {
        values.add(buffer[i]);
    }
    return true;
}

bool handle_bulk_writes(const JsonArray& writes, uint8_t addr, uint32_t& op_count) {
    op_count += writes.size();
    for(JsonVariant v : writes) {
        if(!i2c_writeRegister(addr, v["reg"].as<uint8_t>(), v["value"].as<uint8_t>())) {
            return false;
        }
    }
    return true;
}

// === FUNZIONI DISPLAY ===
bool initDisplay() {
    Wire.begin(I2C_DISP_SDA, I2C_DISP_SCL, 100000);
    
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR, false, false)) {
        return false;
    }
    
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0,0);
    display.println("STARTING...");
    display.display();
    
    displayInitialized = true;
    return true;
}

void showMessage(const char* message, int textSize = 1) {
    display.clearDisplay();
    display.setTextSize(textSize);
    display.setCursor(0,0);
    display.println(message);
    display.display();
}

void showUptimeWithStatus() {
    unsigned long uptime = millis() / 1000;
    int hours = uptime / 3600;
    int mins = (uptime % 3600) / 60;
    int secs = uptime % 60;
    
    display.clearDisplay();
    display.setTextSize(2);
    display.setCursor(0,0);
    display.printf("%02d:%02d:%02d", hours, mins, secs);
    display.display();
}

void update_display_stats() {
    uint32_t now = millis();
    if(now - last_display_update < 250) return;
    last_display_update = now;
    
    display.clearDisplay();
    
    if(current_display_mode == MODE_UPTIME) {
        showUptimeWithStatus();
    } else if(current_display_mode == MODE_I2C_MONITOR) {
        if(currentDevice.isPresent) {
            // Riga 1: Nome dispositivo (sinistra) e tempo medio (destra)
            display.setTextSize(1);
            display.setCursor(0,0);
            display.printf("%s", currentDevice.name);
            display.setCursor(70,0);
            display.printf("%luus", metrics.avg_time_us);
            
            // Linea verticale di separazione
            display.drawFastVLine(64, 8, 24, SSD1306_WHITE);
            
            // Colonna sinistra: Letture/secondo
            display.setTextSize(2);
            display.setCursor(0,12);
            display.printf("%lu", metrics.reads_per_second);
            
            // Colonna destra: Scritture/minuto
            display.setTextSize(2);
            display.setCursor(70,12);
            display.printf("%lu", metrics.writes_per_minute);
            
        } else {
            display.setTextSize(2);
            display.setCursor(0,8);
            display.println("NO DEV");
        }
    }
    
    display.display();
}

bool detectDevice() {
    if(currentDevice.isPresent) return true;
    showMessage("SEARCHING...", 1);
    
    uint8_t attempts = 0;
    uint8_t found_devices = 0;
    
    while(found_devices == 0 && attempts < 5) {
        delay(100);
        
        for(const auto& known : KNOWN_DEVICES) {
            Wire1.beginTransmission(known.addr);
            if(Wire1.endTransmission() == 0) {
                found_devices++;
                currentDevice.addr = known.addr;
                currentDevice.isPresent = true;
                currentDevice.name = known.name;
                break;
            }
        }
        
        if(found_devices == 0) {
            delay(100);
            attempts++;
        }
    }
    
    return found_devices > 0;
}

// === SETUP ===
void setup() {    
    Serial.begin(115200);
    Wire1.begin(I2C_DEV_SDA, I2C_DEV_SCL, 400000);
    initDisplay();
    
    if (detectDevice()) {
        i2c_resetBus();
        showUptimeWithStatus();
    }
}

// === LOOP ===
void handle_scan_command(JsonDocument& cmd, JsonDocument& res) {
    scan_i2c_bus();
    add_devices_to_response(res);
}

void handle_get_devices_command(JsonDocument& cmd, JsonDocument& res) {
    if(num_devices == 0) {
        scan_i2c_bus();
    }
    add_devices_to_response(res);
}

void handle_select_command(JsonDocument& cmd, JsonDocument& res) {
    uint8_t target = cmd["addr"];
    bool found = false;
    for(uint8_t i=0; i<num_devices; i++) {
        if(devices[i].addr7 == target) {
            current_device_idx = i;
            found = true;
            res["selected"] = devices[i].addr7;
            res["name"] = devices[i].name;
            res["status"] = "OK";
            break;
        }
    }
    if(!found) {
        res["status"] = "ERROR";
        res["error"] = "Device not found";
    }
}

void handle_bulk_rw_command(JsonDocument& cmd, JsonDocument& res) {
    current_display_mode = MODE_I2C_MONITOR;
    handle_bulk_rw(cmd, res);
}

void handle_pause_command(JsonDocument& cmd, JsonDocument& res) {
    current_display_mode = MODE_UPTIME;
    res["status"] = "OK";
}

void handle_resume_command(JsonDocument& cmd, JsonDocument& res) {
    current_display_mode = MODE_I2C_MONITOR;
    update_display_stats();
    res["status"] = "OK";
}

void handle_switch_command(JsonDocument& cmd, JsonDocument& res) {
    if(num_devices > 0) {
        current_device_idx = (current_device_idx + 1) % num_devices;
        res["selected"] = devices[current_device_idx].addr7;
        res["name"] = devices[current_device_idx].name;
    }
}

void handle_status_command(JsonDocument& cmd, JsonDocument& res) {
    res["ops"] = metrics.total_ops;
    res["avg_time_us"] = metrics.avg_time_us;
    res["uptime"] = millis() / 1000;
}

using CommandHandler = void (*)(JsonDocument&, JsonDocument&);
std::map<String, CommandHandler> command_handlers = {
    {"scan", handle_scan_command},
    {"get_devices", handle_get_devices_command},
    {"select", handle_select_command},
    {"bulk_rw", handle_bulk_rw_command},
    {"pause", handle_pause_command},
    {"resume", handle_resume_command},
    {"switch", handle_switch_command},
    {"get_status", handle_status_command}
};

void processJsonCommand(const char* json_str) {
    StaticJsonDocument<JSON_CAPACITY> cmd, res;
    
    if(deserializeJson(cmd, json_str)) {
        res["status"] = "ERROR";
        res["error"] = "Invalid JSON";
        serializeJson(res, Serial);
        Serial.println();
        return;
    }

    const char* action = cmd["action"];
    res["action"] = action;

    auto handler = command_handlers.find(action);
    if(handler != command_handlers.end()) {
        handler->second(cmd, res);
    } else {
        res["status"] = "ERROR";
        res["error"] = "Unknown command";
    }

    serializeJson(res, Serial);
    Serial.println();
}

void loop() {
    static String jsonBuffer;
    
    while(Serial.available()) {
        char c = Serial.read();
        if(c == '\n') {
            if(!jsonBuffer.isEmpty() && jsonBuffer[0] == '{') {
                processJsonCommand(jsonBuffer.c_str());
                jsonBuffer.clear();
            }
            jsonBuffer.clear();
        } else {
            if(jsonBuffer.length() < JSON_CAPACITY) {
                jsonBuffer += c;
            }
        }
    }

    update_display_stats();
    
    uint32_t now = millis();
    if(now - metrics.last_update >= 1000) {
        metrics.reads_per_second = (metrics.total_reads - metrics.last_reads);
        metrics.writes_per_second = (metrics.total_writes - metrics.last_writes);
        metrics.writes_per_minute = metrics.writes_per_second * 60;
        
        metrics.last_reads = metrics.total_reads;
        metrics.last_writes = metrics.total_writes;
        metrics.last_update = now;
    }
}