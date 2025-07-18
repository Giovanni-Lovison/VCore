# 08.07.25

import json
import time
import random

class MockSerial:
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.port = args[0] if args else kwargs.get('port', 'COM1')
        self._in_waiting = 0
        self.last_command = None
        self._buffer = []
        self._selected_device = None
        self._paused = True
        
    @property
    def in_waiting(self):
        if self._buffer:
            return len(self._buffer[0])
        return 0
    
    def write(self, data):
        try:
            cmd = json.loads(data.decode())
            self.last_command = cmd
            response = None
            
            if cmd.get('action') == 'get_devices':
                response = {
                    "action": "get_devices",
                    "devices": [0x25, 0x3C],
                    "names": ["uP9512", "SSD1306"]
                }
                
            elif cmd.get('action') == 'resume':
                self._paused = False
                response = {
                    "action": "resume",
                    "status": "OK"
                }

            elif cmd.get('action') == 'pause':
                self._paused = True
                response = {
                    "action": "pause",
                    "status": "OK"
                }

            elif cmd.get('action') == 'select':
                self._selected_device = cmd.get('addr')
                response = {
                    "action": "select",
                    "status": "OK",
                    "name": "uP9512" if cmd.get('addr') == 0x25 else "SSD1306",
                    "addr": cmd.get('addr')
                }

            elif cmd.get('action') == 'get_status':
                response = {
                    "action": "get_status",
                    "status": "OK",
                    "uptime": int(time.time()) % 10000,
                    "max_phases": 8,
                    "operating_phases": self._selected_device and 4 or 8
                }

            elif cmd.get('action') == 'set_lcs_phases':
                lcs_config = cmd.get("config", {})
                response = {
                    "action": "set_lcs_phases",
                    "status": "OK",
                    "message": f"Mock LCS phases set for {len(lcs_config)} states."
                }

            elif cmd.get('action') == 'bulk_rw':
                if 'writes' in cmd:
                    response = {
                        "action": "bulk_rw", 
                        "status": "OK"
                    }

                elif 'reads' in cmd:
                    values = []
                    for reg in cmd['reads']:
                        if self._selected_device == 0x25:  # uP9512
                            if reg == 0x35:
                                values.append(0x00)
                            elif reg == 0x3B:
                                values.append(0x04)
                            elif reg == 0x2D:
                                base = 120
                                values.append(max(0, min(0xFF, base + random.randint(-2, 2))))
                            elif reg == 0x2C:
                                base = 9
                                values.append(max(0, min(0xFF, base + random.randint(-2, 2))))
                            elif reg == 0x2E:
                                base = 79
                                values.append(max(0, min(0xFF, base + random.randint(-1, 1))))
                            elif reg == 0x25:
                                values.append(0xFE)
                            elif reg == 0x3D:
                                base = 9
                                values.append(max(0, min(0xFF, base + random.randint(-1, 1))))
                            elif reg == 0x3C:
                                values.append(0x0F)
                            elif reg == 0x07 or reg == 0x08 or reg == 0x09:
                                values.append(0x77)
                            elif reg == 0x23:
                                values.append(0x00)
                            else:
                                values.append(0x00)
                        elif self._selected_device == 0x3C:
                            values.append(0x3C)
                        else:
                            values.append(0x42)
                    
                    response = {
                        "action": "bulk_rw",
                        "status": "OK",
                        "values": values
                    }
                    
            if response:
                self._buffer.append(json.dumps(response).encode() + b'\n')
                
            return len(data)
        except Exception as e:
            print(f"Mock serial error: {e}")
            return 0
    
    def read(self, size=1):
        if self._buffer:
            data = self._buffer[0][:size]
            self._buffer[0] = self._buffer[0][size:]
            if not self._buffer[0]:
                self._buffer.pop(0)
            return data
        return b''
        
    def close(self):
        self.is_open = False
        
    def flush(self):
        self._buffer.clear()
