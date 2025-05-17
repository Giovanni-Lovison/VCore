class I2CDevice:
    def __init__(self, manager, addr7):
        self.manager = manager
        self.addr7 = addr7
    
    def read_registers(self, registers):
        """Read multiple registers in a single operation"""
        reg_list = [int(reg) for reg in registers]
        response = self.manager.bulk_rw(reads=reg_list)
        return response["values"]

    def write_registers(self, reg_value_pairs):
        """Write multiple register-value pairs"""
        writes = [{"reg": reg, "value": val} for reg, val in reg_value_pairs]
        return self.manager.bulk_rw(writes=writes)

    def get_measurements(self):
        """Must be implemented by each device"""
        raise NotImplementedError
