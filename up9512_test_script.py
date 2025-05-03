import serial
import json
import time 
import threading
from queue import Queue, Empty
from serial.tools import list_ports

class I2CManager:
    def __init__(self, port):
        """
        Initialize I2C Manager using 7-bit addressing.
        The protocol automatically handles the conversion to 8-bit addresses
        by shifting the address left by 1 and adding the R/W bit.
        """
        self.ser = serial.Serial(port, 115200, timeout=0.05, write_timeout=0.1)
        self.response_queue = Queue()
        self.lock = threading.Lock()
        self.running = True
        
        # Add conversion constants
        self.V_LSB = 0.01  # V per bit
        self.I_LSB = 0.01  # V per bit
        self.R_SHUNT = 0.003  # 3mΩ
        self.T_LSB = 0.008  # V per bit
        self.T_SENS = 0.0127  # V/°C

        # Start listener thread
        self.listener_thread = threading.Thread(target=self._listener, daemon=True)
        self.listener_thread.start()
        
        # Initialize devices
        self.devices = []
        self.current_device = None
        self._initialize()
    
    def _initialize(self):
        """Initialize device list with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            time.sleep(1)  # Wait for ESP32 to be ready
            self.devices = self.get_devices()
            if self.devices:
                print(f"Found {len(self.devices)} devices on attempt {attempt + 1}")
                return
            print(f"Attempt {attempt + 1}: No devices found, retrying...")
            
        print("Warning: No devices found after all retries")
        self.devices = []
    
    def send_command(self, cmd):
        with self.lock:
            cmd_str = json.dumps(cmd) + '\n'
            #print(f"Serial TX: {cmd_str}", end='')
            self.ser.write(cmd_str.encode())
    
    def wait_response(self, action, timeout=0.5):
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = self.response_queue.get_nowait()
                print(f"Received response: {response}")
                
                if response.get("action") == action:
                    return response
            except Empty:
                continue
        return None
    
    def _listener(self):
        buffer = ""
        while self.running:
            try:
                data = self.ser.read(self.ser.in_waiting or 1)
                if data:
                    #print(f"Serial RX: {data.decode(errors='ignore')}", end='')
                    buffer += data.decode(errors='ignore')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        self.response_queue.put(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            except:
                pass
    
    def rescan_devices(self):
        self.send_command({"action": "scan"})
        return self.wait_response("scan")
    
    def select_device(self, addr7):
        self.send_command({"action": "select", "addr": addr7})
        return self.wait_response("select")
    
    def bulk_rw(self, reads=None, writes=None):
        cmd = {"action": "bulk_rw"}
        if reads: cmd["reads"] = reads
        if writes: cmd["writes"] = writes
        self.send_command(cmd)
        return self.wait_response("bulk_rw")
    
    def monitor(self, interval=0.1):
        self.send_command({"action": "resume"})
        try:
            while True:
                start = time.time()
                # Read VOUT (0x2D), IOUT (0x2C), TEMP (0x2E)
                data = self.bulk_rw(reads=[0x2D, 0x2C, 0x2E])
                if data and "values" in data:
                    values = data["values"]
                    vout = values[0] * self.V_LSB
                    iout = (values[1] * self.I_LSB) / self.R_SHUNT
                    temp = (values[2] * self.T_LSB) / self.T_SENS
                    power = vout * iout
                    
                    print(f"V: {vout:.2f}V  I: {iout:.2f}A  T: {temp:.1f}°C  P: {power:.1f}W")
                    #print(f"Read time: {data.get('timing_us', 0)}us")
                    
                elapsed = time.time() - start
                if elapsed < interval:
                    time.sleep(interval - elapsed)
        except KeyboardInterrupt:
            self.send_command({"action": "pause"})
    
    def close(self):
        self.running = False
        self.ser.close()
    
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
        for _ in range(3):  # Try up to 3 times to get response
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
                    # Try to match by name
                    matches = [(i, dev) for i, dev in enumerate(devices) 
                             if choice.lower() in dev.get('name', '').lower()]
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

def find_ch340_port():
    for port in list_ports.comports():
        if 'CH340' in port.description:
            return port.device
    raise Exception("CH340 device not found")

if __name__ == "__main__":
    try:
        port = find_ch340_port()
        manager = I2CManager(port)
        
        print("\nI2C Device Scanner")
        print("=================")
        
        # Let user select device
        if manager.interactive_select():
            print("\nStarting monitor (Ctrl+C to stop)...")
            manager.monitor()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'manager' in locals():
            manager.close()