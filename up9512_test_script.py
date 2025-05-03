import serial
import time
import json
from serial.tools import list_ports

class I2CManager:
    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.1, write_timeout=0.2)
        time.sleep(2)  # Critico per l'inizializzazione
        self.devices = []
        self.current_device = None
        self._initialize()
        
    def _send_command(self, cmd):
        self.ser.reset_input_buffer()
        self.ser.write((json.dumps(cmd) + '\n').encode())
        return self._get_response()
        
    def _get_response(self):
        buffer = ""
        start = time.time()
        while time.time() - start < 0.3:  # Timeout aumentato
            buffer += self.ser.read(self.ser.in_waiting or 1).decode(errors='ignore')
            if '\n' in buffer:
                line, _, buffer = buffer.partition('\n')
                try:
                    return json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
        return None
        
    def _initialize(self):
        response = self._send_command({"action": "scan"})
        if response and response.get("status") == "OK":
            self.devices = response.get("devices", [])
        else:
            raise RuntimeError("Inizializzazione fallita")
            
    def rescan_devices(self):
        response = self._send_command({"action": "scan"})
        if response and response.get("status") == "OK":
            self.devices = response.get("devices", [])
            print("Dispositivi rilevati:", self.devices)
            return True
        return False
            
    def select_device(self, addr7):
        response = self._send_command({"action": "select", "addr": addr7})
        if response and response.get("status") == "OK":
            self.current_device = addr7
            print(f"Selezionato dispositivo 0x{addr7:02X}")
            return True
        print("Selezione fallita")
        return False
        
    def bulk_rw(self, reads=None, writes=None):
        cmd = {"action": "bulk_rw"}
        if reads: cmd["reads"] = reads
        if writes: cmd["writes"] = writes
        print(f"Sending: {json.dumps(cmd)}")  # Debug output
        response = self._send_command(cmd)
        print(f"Response: {json.dumps(response)}")  # Debug output
        return response if response and response.get("status") == "OK" else None
        
    def read_sensors(self):
        result = self.bulk_rw(reads=[0x2D, 0x2C, 0x2E])
        if not result: 
            print("No response from device")
            return None
            
        values = result.get("values", [])
        if not values:
            print(f"No values in response: {result}")
            return None
            
        if len(values) != 3:
            print(f"Wrong number of values: got {len(values)}, expected 3")
            return None
            
        # Use same scaling factors as working code
        vout = values[0] * 0.01  # V_LSB
        iout = (values[1] * 0.01) / 0.003  # I_LSB / R_SHUNT
        temp = (values[2] * 0.008) / 0.0127  # T_LSB / T_SENS
        
        print(f"Raw values: {[hex(v) for v in values]}")
        return {
            'voltage': vout,
            'current': iout,
            'temperature': temp
        }
        
    def monitor(self):
        print("Starting monitoring (Press Ctrl+C to stop)...")
        readings_count = 0
        try:
            while True:
                data = self.read_sensors()
                if data:
                    readings_count += 1
                    print(f"\r[{readings_count}] V: {data['voltage']:.2f}V | I: {data['current']:.2f}A | T: {data['temperature']:.1f}°C")
                time.sleep(0.5)  # Slower update rate for debugging
        except KeyboardInterrupt:
            print("\nMonitoring terminated")
        finally:
            self.ser.close()

def find_ch340():
    for port in list_ports.comports():
        if 'CH340' in port.description:
            print(f"Trovato {port.device}")
            return port.device
    raise RuntimeError("Porta CH340 non trovata")

if __name__ == "__main__":
    try:
        port = find_ch340()
        manager = I2CManager(port)
        
        # Esempio interattivo
        manager.rescan_devices()
        if manager.devices:
            print("Dispositivi disponibili:")
            for idx, dev in enumerate(manager.devices):
                print(f"{idx+1}. {dev['name']} (0x{dev['addr7']:02X})")
                
            selection = input("Seleziona dispositivo (numero o indirizzo esadecimale): ")
            try:
                addr = int(selection, 16) if 'x' in selection else manager.devices[int(selection)-1]['addr7']
                manager.select_device(addr)
                manager.monitor()
            except:
                print("Selezione non valida")
    except Exception as e:
        print(f"Errore: {e}")