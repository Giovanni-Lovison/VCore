from app.device.up9512 import UP9512
from app.device.ncp4206 import NCP4206

DEVICE_MAP = {
    "uP9512": lambda m, a: UP9512(m, a),
    "NCP4206": lambda m, a: NCP4206(m, a),
}
