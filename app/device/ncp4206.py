# 08.07.25

from .base import I2CDevice

class NCP4206(I2CDevice):
    DEVICE_NAME = "NCP4206"

    CMD_READ_VOUT = 0x8B
    CMD_READ_IOUT = 0x8C
    CMD_READ_POUT = 0x96
    CMD_STATUS_BYTE = 0x78
    CMD_STATUS_WORD = 0x79
    CMD_STATUS_VOUT = 0x7A
    CMD_STATUS_IOUT = 0x7B
    CMD_VOUT_COMMAND = 0x21
    CMD_PHASE_STATUS = 0xFC

    CMD_READ_TEMP = 0x2E
    CMD_READ_VOUT_ADC = 0x2D
    CMD_READ_IOUT_ADC = 0x2C
    CMD_READ_IOUT_AVG = 0x3D
    CMD_PROTECTION_INDICATOR = 0x3B
    CMD_PROTECTION_INDICATOR2 = 0x35

    def get_measurements(self):
        """Return a dict with voltage, current, power, and status. Defaults to 0.0/False if not present."""
        try:
            # Use ADC readings for more precise values, 10mV/step
            vout = self.read_registers([self.CMD_READ_VOUT_ADC])
            iout = self.read_registers([self.CMD_READ_IOUT_ADC])
            iout_avg = self.read_registers([self.CMD_READ_IOUT_AVG])
            temp = self.read_registers([self.CMD_READ_TEMP])
            
            # Power is not directly available from a single register in the new doc, calculate it
            voltage = float(vout[0]) * 0.01 if vout else 0.0
            current = float(iout[0]) * 0.01 if iout else 0.0
            power = voltage * current

            return {
                "voltage": voltage,
                "current": current,
                "power": power,
                "avg_current": float(iout_avg[0]) * 0.01 if iout_avg else 0.0,
                "temperature": float(temp[0]) * 0.008 if temp else 0.0 # 8mV/step
            }
        
        except Exception:
            return {
                "voltage": 0.0,
                "current": 0.0,
                "power": 0.0,
                "avg_current": 0.0,
                "temperature": 0.0
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
        """Return a dict with main protection flags using specific device registers."""
        try:
            prot_ind = self.read_registers([self.CMD_PROTECTION_INDICATOR])
            prot_ind2 = self.read_registers([self.CMD_PROTECTION_INDICATOR2])
            phase_count = self.get_phase_count()
            prot = {}

            if prot_ind:
                pi = prot_ind[0]
                prot["otp"] = bool(pi & 0x80)
                prot["total_ocp"] = bool(pi & 0x40)
                prot["channel_ocl"] = bool(pi & 0x20)
                prot["ovp"] = bool(pi & 0x10)
                prot["uvp"] = bool(pi & 0x08)
                # Bits 2:0 are operating phase number, already covered by get_phase_count

            if prot_ind2:
                pi2 = prot_ind2[0]
                prot["phase8_ocl"] = bool(pi2 & 0x80)
                prot["phase7_ocl"] = bool(pi2 & 0x40)
                prot["phase6_ocl"] = bool(pi2 & 0x20)
                prot["phase5_ocl"] = bool(pi2 & 0x10)
                prot["phase4_ocl"] = bool(pi2 & 0x08)
                prot["phase3_ocl"] = bool(pi2 & 0x04)
                prot["phase2_ocl"] = bool(pi2 & 0x02)
                prot["phase1_ocl"] = bool(pi2 & 0x01)

            prot["active_phases"] = phase_count
            return prot
        
        except Exception:
            return {}