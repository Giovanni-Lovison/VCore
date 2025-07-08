# 08.07.25

from .base import I2CDevice

class IR35201(I2CDevice):
    DEVICE_NAME = "IR35201"

    # PMBus Commands from datasheet
    CMD_READ_VOUT = 0x8B
    CMD_READ_IOUT = 0x8C
    CMD_READ_POUT = 0x96
    CMD_READ_TEMPERATURE_1 = 0x8D
    CMD_STATUS_BYTE = 0x78
    CMD_STATUS_WORD = 0x79
    CMD_STATUS_VOUT = 0x7A
    CMD_STATUS_IOUT = 0x7B
    CMD_STATUS_TEMPERATURE = 0x7D
    CMD_STATUS_MFR_SPECIFIC = 0x80

    def get_measurements(self):
        """Return a dict with voltage, current, power, and temperature."""
        try:
            reads = self.read_registers([
                self.CMD_READ_VOUT, 
                self.CMD_READ_IOUT, 
                self.CMD_READ_POUT, 
                self.CMD_READ_TEMPERATURE_1
            ])

            if not reads or len(reads) < 4:
                return { "voltage": 0.0, "current": 0.0, "power": 0.0, "temperature": 0.0 }

            # Using resolution from datasheet as LSB for I2C
            voltage = reads[0] * 0.0156  # 15.6mV
            current = reads[1] * 1.0      # 1A
            power = reads[2] * 0.5        # 0.5W
            temperature = reads[3] * 1.0  # 1°C

            return {
                "voltage": voltage,
                "current": current,
                "power": power,
                "temperature": temperature
            }
        
        except (TypeError, IndexError):
            return { "voltage": 0.0, "current": 0.0, "power": 0.0, "temperature": 0.0 }

    def get_protection_status(self):
        """Return a dict with protection flags."""
        try:
            status = self.read_registers([
                self.CMD_STATUS_BYTE,
                self.CMD_STATUS_WORD,
                self.CMD_STATUS_VOUT,
                self.CMD_STATUS_IOUT,
                self.CMD_STATUS_TEMPERATURE,
                self.CMD_STATUS_MFR_SPECIFIC
            ])

            if not status or len(status) < 6:
                return {}

            s_byte = status[0]
            s_word_high = (status[1] >> 8) & 0xFF
            s_vout = status[2]
            s_iout = status[3]
            s_temp = status[4]
            s_mfr = status[5]

            prot = {}
            prot['ovp_fault'] = bool(s_vout & 0x80) or bool(s_byte & 0x20)
            prot['ovp_warning'] = bool(s_vout & 0x40)
            prot['uvp_fault'] = bool(s_vout & 0x10)
            prot['uvp_warning'] = bool(s_vout & 0x20)
            
            prot['ocp_fault'] = bool(s_iout & 0x80) or bool(s_byte & 0x10)
            prot['ocp_warning'] = bool(s_iout & 0x20)

            prot['otp_fault'] = bool(s_temp & 0x80) or bool(s_byte & 0x04)
            prot['otp_warning'] = bool(s_temp & 0x40)
            
            prot['vin_uvlo'] = bool(s_byte & 0x08)
            
            prot['power_good_neg'] = not bool(s_word_high & 0x08)
            
            prot['driver_fault'] = bool(s_mfr & 0x04)
            prot['unpopulated_phase_fault'] = bool(s_mfr & 0x02)
            prot['external_otp_fault'] = bool(s_mfr & 0x01)

            return prot
        except (TypeError, IndexError):
            return {}
