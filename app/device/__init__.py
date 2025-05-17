from .up9512 import UP9512, DeviceConnectionManager

def get_device_instance(device_type, manager, addr7):
    if device_type == "uP9512":
        return DeviceConnectionManager.get_device(manager, addr7)

    return None

DEVICE_MAP = {
    "uP9512": lambda m, a: get_device_instance("uP9512", m, a),
}
