import os
import serial
import json
import time 
import threading
from queue import Queue, Empty
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

from .devices import DEVICE_MAP
from .mock_serial import MockSerial


class I2CManager(QObject):
    device_changed = pyqtSignal()
    
    def __init__(self, port=None, developer_mode=False):
        super().__init__()
        """
        Initialize I2C Manager using 7-bit addressing.
        The protocol automatically handles the conversion to 8-bit addresses
        by shifting the address left by 1 and adding the R/W bit.
        """
        try:
            if developer_mode:
                self.ser = MockSerial(port)
            else:
                self.ser = serial.Serial(port, 115200, timeout=0.05, write_timeout=0.1)
        except Exception as e:
            print(f"Serial init error: {e}")
            if developer_mode:
                self.ser = MockSerial(port)
            else:
                raise
        self.response_queue = Queue()
        self.lock = threading.Lock()
        self.running = True
        self.is_paused = True
        
        # Create logs directory if it doesn't exist
        self.log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Open log file in logs directory
        log_path = os.path.join(self.log_dir, 'i2c_log.json')
        self.log_file = open(log_path, 'a')

        # Start listener thread
        self.listener_thread = threading.Thread(target=self._listener, daemon=True)
        self.listener_thread.start()
        
        # Initialize devices
        self.devices = []
        self.current_device = None
        self.is_active = False
        self._initialize()
    
    def _initialize(self):
        """Initialize device list with retries"""
        max_retries = 2
        for attempt in range(max_retries):
            time.sleep(0.5)
            self.devices = self.get_devices()
            if self.devices:
                print(f"Found devices: {self.devices}")

                # Auto-select first device
                if self.devices:
                    first_dev = self.devices[0]
                    print(f"Auto-selecting first device: {first_dev}")
                    self.select_device(first_dev['addr7'])
                return
            
        self.devices = []
    
    def log_communication(self, direction, data):
        """Log communication to JSON file with check"""
        try:
            if hasattr(self, 'log_file') and not self.log_file.closed:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "direction": direction,
                    "data": data
                }
                self.log_file.write(json.dumps(entry) + '\n')
                self.log_file.flush()
        except:
            pass
    
    def send_command(self, cmd):
        """Track pause state when sending commands"""
        if cmd.get("action") == "pause":
            self.is_paused = True
        elif cmd.get("action") == "resume":
            self.is_paused = False
        if cmd.get("action") == "resume":
            self.is_active = True
        elif cmd.get("action") == "pause":
            self.is_active = False
        with self.lock:
            cmd_str = json.dumps(cmd) + '\n'
            self.log_communication("TX", cmd)
            self.ser.write(cmd_str.encode())
    
    def wait_response(self, action, timeout=0.05):
        """Wait for specific response with logging"""
        start = time.time()
        stored_responses = []
        
        while time.time() - start < timeout:
            try:
                response = self.response_queue.get(timeout=0.001)
                
                if response.get("action") == action:
                    while stored_responses:
                        self.response_queue.put(stored_responses.pop(0))
                    return response
                else:
                    stored_responses.append(response)
            except Empty:
                continue
                
        print(f"Timeout waiting for '{action}' response")
        while stored_responses:
            self.response_queue.put(stored_responses.pop(0))
        return None
    
    def _listener(self):
        """Serial listener with detailed logging"""
        buffer = ""
        while self.running:
            if not self.ser.is_open:
                time.sleep(0.1)
                continue
                
            try:
                if self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting)
                    if data:
                        decoded = data.decode(errors='ignore')
                        buffer += decoded
                        #self.log_communication("RAW_RX", decoded)
                        
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            try:
                                response = json.loads(line.strip())
                                self.log_communication("PARSED_RX", response)
                                self.response_queue.put(response)
                            except json.JSONDecodeError:
                                pass
                            
            except serial.SerialException as e:
                print(f"Serial error: {e}")
            except Exception as e:
                print(f"Listener error: {e}")
    
    def rescan_devices(self):
        self.send_command({"action": "scan"})
        return self.wait_response("scan")
    
    def select_device(self, addr7):
        """Select device and create appropriate device instance"""
        if self.is_paused:
            self.send_command({"action": "resume"})
            response = self.wait_response("resume")
            if response and response.get("status") == "OK":
                self.is_paused = False
        
        # Now select the device
        self.send_command({"action": "select", "addr": addr7})
        response = self.wait_response("select")

        if response and response.get("status") == "OK":
            device_name = response.get("name")
            if device_name in DEVICE_MAP:
                self.current_device = DEVICE_MAP[device_name](self, addr7)
                print(f"Selected {device_name} at address 0x{addr7:02X}")
                self.device_changed.emit()
                return True
        
        print(f"Failed to select device: {response}")
        self.current_device = None
        return False

    def bulk_rw(self, reads=None, writes=None):
        """Improved bulk read/write with better thread safety"""
        if not self.running:
            return None
            
        cmd = {"action": "bulk_rw"}
        if reads:
            cmd["reads"] = reads
            hex_reads = [f"0x{reg:02X}" for reg in reads]
            #print(f"\n[I2C READ] Registers: {hex_reads}")
            
        if writes:
            cmd["writes"] = writes
            hex_writes = [f"reg: 0x{w['reg']:02X}, value: 0x{w['value']:02X}" for w in writes]
            #print(f"\n[I2C WRITE] {hex_writes}")
            
        try:
            self.send_command(cmd)
            response = self.wait_response("bulk_rw", timeout=1.0)
            
            if response:
                if "values" in response:
                    hex_values = [f"0x{val:02X}" for val in response["values"]]
                    #print(f"[I2C READ] Values: {hex_values}")
                    
                if "write_status" in response:
                    status = "OK" if response["write_status"] == 0 else f"ERROR ({response['write_status']})"
                    #print(f"[I2C WRITE] Status: {status}")
                
            
            if not response:
                print("No response from device")
                return None
                
            if response.get("status") == "PAUSED":
                print("Device is paused")
                return None
                
            return response
                
        except Exception as e:
            print(f"Bulk RW error: {e}")
            return None

    def monitor(self):
        """Monitoraggio valori in modalità console"""
        print("Starting monitor mode...")
        self.send_command({"action": "resume"})
        
        try:
            while True:
                if self.current_device:
                    measurements = self.current_device.get_measurements()

        except KeyboardInterrupt:
            print("\nStopping monitor...")
        finally:
            print("Pausing I2C communication...")
            self.send_command({"action": "pause"})
            time.sleep(0.01)
    
    def _send_pause(self):
        """Send pause command directly without logging"""
        try:
            if self.ser and self.ser.is_open:
                cmd_str = json.dumps({"action": "pause"}) + '\n'
                self.ser.write(cmd_str.encode())
                time.sleep(0.01)
        except:
            pass
    
    def close(self):
        """Improved close with better resource management"""
        try:
            self._send_pause()
            
            # 2. Ferma il thread
            self.running = False
            
            # 3. Aspetta il thread
            if hasattr(self, 'listener_thread'):
                self.listener_thread.join(timeout=0.5)
            
            # 4. Chiudi la seriale 
            if hasattr(self, 'ser') and self.ser and self.ser.is_open:
                self.ser.close()
            
            # 5. Chiudi il log per ultimo
            if hasattr(self, 'log_file') and not self.log_file.closed:
                self.log_file.close()
                
        except Exception as e:
            print(f"Error during close: {e}")
            try:
                if hasattr(self, 'log_file') and not self.log_file.closed:
                    self.log_file.close()
            except:
                pass

    def get_device_info(self, addr7):
        """Get device name from firmware"""
        self.send_command({"action": "get_status"})
        response = self.wait_response("get_status")
        if response:
            return response.get("device_name", "Unknown")
        return "Unknown"
    
    def get_devices(self):
        """Get list of devices from firmware"""
        self.send_command({"action": "get_devices"})
        for _ in range(3): 
            response = self.wait_response("get_devices", timeout=1)
            if response and 'devices' in response and 'names' in response:
                return [
                    {"addr7": addr, "name": name} 
                    for addr, name in zip(
                        response["devices"],
                        response["names"]
                    )
                ]
            
            time.sleep(0.5)  # Wait before retry
        return []
    
    def list_devices(self):
        """Display available I2C devices with names"""
        print("\nAvailable I2C devices:")
        print("----------------------")
        for i, dev in enumerate(self.devices):
            addr = dev['addr7']
            name = dev.get('name', 'Unknown')
            print(f"{i}: {name:<15} (Address: 0x{addr:02X})")
        return self.devices
    
    def interactive_select(self):
        """Let user select a device by name or number"""
        devices = self.list_devices()
        if not devices:
            print("No devices found!")
            return False
            
        while True:
            try:
                choice = input("\nSelect device by number or name (or 'q' to quit): ").strip()
                if choice.lower() == 'q':
                    return False
                
                # Try to match by number
                try:
                    idx = int(choice)
                    if 0 <= idx < len(devices):
                        self.select_device(devices[idx]['addr7'])
                        print(f"Selected {devices[idx].get('name', 'Unknown')} at address 0x{devices[idx]['addr7']:02X}")
                        return True
                    
                except ValueError:
                    matches = [(i, dev) for i, dev in enumerate(devices) if choice.lower() in dev.get('name', '').lower()]
                    
                    if len(matches) == 1:
                        idx, dev = matches[0]
                        self.select_device(dev['addr7'])
                        print(f"Selected {dev.get('name', 'Unknown')} at address 0x{dev['addr7']:02X}")
                        return True
                    
                    elif len(matches) > 1:
                        print("Multiple matches found. Please be more specific or use the number:")
                        for i, dev in matches:
                            print(f"{i}: {dev.get('name', 'Unknown')} (Address: 0x{dev['addr7']:02X})")
                    else:
                        print("Device not found! Please try again.")
                        
            except Exception as e:
                print(f"Error: {e}")
                print("Please enter a valid number or name")
    
    def write_register(self, reg, value):
        """Write single register wrapper"""
        response = self.bulk_rw(writes=[{"reg": reg, "value": value}])
        return response and response.get("status") == "OK"
        
    def read_register(self, reg):
        """Read single register wrapper"""
        response = self.bulk_rw(reads=[reg])
        return response["values"][0] if response and "values" in response else None
