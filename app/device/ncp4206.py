from .base import I2CDevice

class NCP4206(I2CDevice):
    DEVICE_NAME = "NCP4206"
    DEFAULT_ADDR = 0x20

    # SMBus/PMBus command codes (from datasheet)
    CMD_READ_VOUT = 0x8B
    CMD_READ_IOUT = 0x8C
    CMD_READ_POUT = 0x96
    CMD_STATUS_BYTE = 0x78
    CMD_STATUS_WORD = 0x79
    CMD_STATUS_VOUT = 0x7A
    CMD_STATUS_IOUT = 0x7B
    CMD_VOUT_COMMAND = 0x21
    CMD_PHASE_STATUS = 0xFC

    def get_measurements(self):
        """Return a dict with voltage, current, power, and status. Defaults to 0.0/False if not present."""
        try:
            vout = self.read_registers([self.CMD_READ_VOUT])
            iout = self.read_registers([self.CMD_READ_IOUT])
            pout = self.read_registers([self.CMD_READ_POUT])
            status = self.read_registers([self.CMD_STATUS_BYTE])
            return {
                "voltage": float(vout[0]) if vout else 0.0,
                "current": float(iout[0]) if iout else 0.0,
                "power": float(pout[0]) if pout else 0.0,
                "status": status[0] if status else False
            }
        except Exception:
            return {
                "voltage": 0.0,
                "current": 0.0,
                "power": 0.0,
                "status": False
            }

    def get_phase_count(self):
        """Return the number of active phases (from PHASE STATUS register 0xFC)."""
        try:
            phase_status = self.read_registers([self.CMD_PHASE_STATUS])
            if phase_status:
                # Bits 0-5: Phase 1-6 enabled
                return sum(1 for i in range(6) if phase_status[0] & (1 << i))
            return 0
        except Exception:
            return 0

    def get_protection_status(self):
        """Return a dict with main protection flags (OVP, OCP, POWER_GOOD, ecc)."""
        try:
            status_byte = self.read_registers([self.CMD_STATUS_BYTE])
            status_word = self.read_registers([self.CMD_STATUS_WORD])
            status_vout = self.read_registers([self.CMD_STATUS_VOUT])
            status_iout = self.read_registers([self.CMD_STATUS_IOUT])
            phase_count = self.get_phase_count()
            prot = {}

            if status_byte:
                sb = status_byte[0]
                prot["busy"] = bool(sb & 0x80)
                prot["off"] = bool(sb & 0x40)
                prot["ovp"] = bool(sb & 0x20)
                prot["ocp"] = bool(sb & 0x10)
                prot["cml"] = bool(sb & 0x02)
                
            if status_word and len(status_word) >= 2:
                sw = status_word[0] | (status_word[1] << 8)
                prot["power_good"] = not bool(sw & (1 << 11))  # Bit 11 HIGH = not power good
            if status_vout:
                sv = status_vout[0]
                prot["vout_over_warning"] = bool(sv & 0x40)
                prot["vout_under_warning"] = bool(sv & 0x20)

            if status_iout:
                si = status_iout[0]
                prot["iout_overcurrent"] = bool(si & 0x80)
                prot["iout_overcurrent_warning"] = bool(si & 0x20)
                prot["pout_overpower_warning"] = bool(si & 0x01)

            prot["active_phases"] = phase_count
            return prot
        
        except Exception:
            return {}