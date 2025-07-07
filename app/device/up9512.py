import time
from typing import Dict, List, Optional, Union

from .base import I2CDevice

class UP9512(I2CDevice):
    _instance_count = 0

    # Device-specific default values
    DEFAULT_VALUES = {
        'phases': {
            'LCS0': 8,  # 8-phase default
            'LCS1': 6,  # 6-phase default
            'LCS2': 4,  # 4-phase default
            'LCS3': 2,  # 2-phase default
            'LCS4': 1   # 1-phase default
        },
        'protections': {
            'total_ocp': 100,  # 100% default
            'vr_shutdown': 254, # 2.04V default (0xFE)
            'enables': {
                'total_ocp': True,
                'channel_ocl': True,
                'ovp': True,
                'uvp': True
            }
        }
    }

    # Device-specific constants
    V_LSB = 0.01                # 10mV per step
    I_LSB = 0.01                # 10mV per step 
    T_LSB = 0.008               # 8mV per step
    R_SHUNT = 0.003             # 3mΩ
    T_SENS = 0.0127             # V/°C

    # Register definitions - Consolidated
    VOUT_REG = 0x2D             # Voltage output register
    IOUT_REG = 0x2C             # Current output register
    TEMP_REG = 0x2E             # Temperature register
    IOUT_AVG_REG = 0x3D         # Average output current
    
    # Phase control registers
    IICP0_1_REG = 0x07          # LCS0 and LCS1 phase control
    IICP2_3_REG = 0x08          # LCS2 and LCS3 phase control  
    IICP4_REG = 0x09            # LCS4 phase control
    
    # Protection registers
    PROT_IND2_REG = 0x35        # Per-phase OCL status
    PROT_IND_REG = 0x3B         # Global protection status + phase monitoring
    MISC1_REG = 0x3C            # Protection enables
    TOTAL_OCP_REG = 0x23        # Total OCP threshold
    VR_SHDN_REG = 0x25          # Thermal shutdown threshold

    # Current Balance Control register
    CB_CTRL_REG = 0x12

    # Phase control bit positions
    PHASE_CONFIG = {
        'LCS0': (0x07, 0x70),  # (reg, mask << 4)
        'LCS1': (0x07, 0x07),  # (reg, mask)
        'LCS2': (0x08, 0x70),  # (reg, mask << 4)
        'LCS3': (0x08, 0x07),  # (reg, mask)
        'LCS4': (0x09, 0x70),  # (reg, mask << 4)
    }

    # Phase values mapping
    PHASE_VALUES = {
        1: 0b000,
        2: 0b001,
        3: 0b010,
        4: 0b011,
        5: 0b100,
        6: 0b101,
        7: 0b110,
        8: 0b111
    }

    # Total OCP threshold values
    TOTAL_OCP_VALUES = {
        100: 0b000,  # Default
        110: 0b001,
        120: 0b010,
        130: 0b011,
        140: 0b100,
        150: 0b101,
        160: 0b110,
        170: 0b111
    }

    def __init__(self, manager, addr7: int):
        print(f"[{time.time()}] Initializing UP9512 for address 0x{addr7:02X}")
        super().__init__(manager, addr7)
        self.max_phase: int = 8
    
    def get_current_balance_status(self):
        """Read current balance enable status"""
        value = self.read_registers([self.CB_CTRL_REG])
        if not value:
            return None
        return bool(value[0] & 0x80)  # Check bit 7
        
    def read_registers(self, registers):
        """Override to ensure hex values"""
        try:
            if not registers:
                print(f"[{time.time()}] Warning: Empty register list")
                return None
                
            reg_list = [reg if isinstance(reg, int) else int(str(reg), 16) for reg in registers]
            return super().read_registers(reg_list)
        except Exception as e:
            print(f"[{time.time()}] Register conversion error: {e}, registers: {registers}")
            return None

    def get_protection_status(self):
        """Read all protection indicators with correct bit mappings"""
        values = self.read_registers([self.PROT_IND_REG, self.PROT_IND2_REG])
        if not values or len(values) != 2:
            return None
            
        prot_ind, prot_ind2 = values
        
        # Get operating phase number from OP_PH_MON bits [2:0]
        op_phase_mon = prot_ind & 0x07  # Mask bits [2:0]
        phase_map = {
            0b000: 1,
            0b001: 2, 
            0b010: 3,
            0b011: 4,
            0b100: 5,
            0b101: 6,
            0b110: 7,
            0b111: 8
        }
        operating_phases = phase_map.get(op_phase_mon, 0)  # Use mapping, default to 0 if invalid
        
        # Protection status bits [7:3]
        return {
            "otp": bool(prot_ind & (1 << 7)),           # Over Temperature Protection
            "total_ocp": bool(prot_ind & (1 << 6)),     # Total Over Current Protection
            "channel_ocl": bool(prot_ind & (1 << 5)),   # Channel Over Current Limit
            "ovp": bool(prot_ind & (1 << 4)),           # Over Voltage Protection
            "uvp": bool(prot_ind & (1 << 3)),           # Under Voltage Protection
            "operating_phases": operating_phases,       # Number of operating phases
            "phase_ocl_status": [                       # Per-phase OCL status
                bool(prot_ind2 & (1 << i)) 
                for i in range(8)
            ]
        }
    
    def get_protection_config(self):
        """Read protection configuration"""
        values = self.read_registers([self.MISC1_REG])
        if not values:
            return None
            
        misc1 = values[0]
        return {
            "total_ocp_enabled": bool(misc1 & (1 << 3)),
            "channel_ocl_enabled": bool(misc1 & (1 << 2)),
            "ovp_enabled": bool(misc1 & (1 << 1)),
            "uvp_enabled": bool(misc1 & (1 << 0))
        }
    
    def get_measurements(self) -> Optional[Dict[str, Union[float, int, List[bool]]]]:
        """Read measurements in a single bulk transaction"""
        try:
            registers = [
                self.PROT_IND2_REG,     # 0x35 - Per-phase OCL status
                self.PROT_IND_REG,      # 0x3B - Global protection + phase mon
                self.VOUT_REG,          # 0x2D - Voltage output
                self.IOUT_REG,          # 0x2C - Current output
                self.TEMP_REG,          # 0x2E - Temperature
                self.VR_SHDN_REG,       # 0x25 - VR shutdown
                self.IOUT_AVG_REG,      # 0x3D - Average current
                self.MISC1_REG          # 0x3C - Protection enables
            ]
            
            values = self.read_registers(registers)
            if not values or len(values) < 8:
                return None
                
            prot_ind2 = values[0]  # OCL status per fase
            prot_ind = values[1]   # Protection status globale
            
            measurements = {
                "voltage": values[2] * self.V_LSB,
                "current": (values[3] * self.I_LSB) / self.R_SHUNT,
                "temperature": (values[4] * self.T_LSB) / self.T_SENS,
                "vr_shutdown": values[5] * 0.008,
                "power": ((values[6] * self.I_LSB) / self.R_SHUNT) * (values[2] * self.V_LSB)
            }
            
            misc1 = values[7]
            
            active_protections = {}
            if misc1 & (1 << 3):  # Total OCP enabled
                active_protections['total_ocp'] = bool(prot_ind & (1 << 6))
            if misc1 & (1 << 2):  # Channel OCL enabled
                active_protections['channel_ocl'] = bool(prot_ind & (1 << 5))
                active_protections['channel_ocl_status'] = [
                    bool(prot_ind2 & (1 << i)) for i in range(8)
                ]
            if misc1 & (1 << 1):  # OVP enabled
                active_protections['ovp'] = bool(prot_ind & (1 << 4))
            if misc1 & (1 << 0):  # UVP enabled
                active_protections['uvp'] = bool(prot_ind & (1 << 3))
            active_protections['otp'] = bool(prot_ind & (1 << 7))
            
            op_phase_mon = prot_ind & 0x07
            phase_map = {
                0b000: 1, 0b001: 2, 0b010: 3, 0b011: 4,
                0b100: 5, 0b101: 6, 0b110: 7, 0b111: 8
            }
            measurements["operating_phases"] = phase_map.get(op_phase_mon, 0)
            
            measurements["protections"] = active_protections
            return measurements
            
        except Exception as e:
            print(f"Error processing measurements: {e}")
            return None

    def get_phase_config(self):
        """Read current phase configuration"""
        values = self.read_registers([self.IICP0_1_REG, self.IICP2_3_REG, self.IICP4_REG])
        if not values:
            return None
            
        result = {}
        result['LCS0'] = (values[0] >> 4) & 0x07
        result['LCS1'] = values[0] & 0x07
        result['LCS2'] = (values[1] >> 4) & 0x07
        result['LCS3'] = values[1] & 0x07
        result['LCS4'] = (values[2] >> 4) & 0x07
        
        for lcs in result:
            for phases, value in self.PHASE_VALUES.items():
                if value == result[lcs]:
                    result[lcs] = phases
                    break
        
        return result

    def get_protection_thresholds(self):
        """Read current protection thresholds"""
        values = self.read_registers([self.TOTAL_OCP_REG, self.VR_SHDN_REG])
        if not values:
            return None
            
        total_ocp = values[0] & 0x07
        ocp_percent = 100
        for percent, value in self.TOTAL_OCP_VALUES.items():
            if value == total_ocp:
                ocp_percent = percent
                break
                
        return {
            "total_ocp_percent": ocp_percent,
            "thermal_shutdown_mv": (values[1] * 8)  # 8mV per step
        }
