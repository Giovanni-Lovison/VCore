from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox, QGroupBox, QGridLayout, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

class ReadWidget(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.init_ui()
        self.populate_devices()
        # Timer per aggiornamento dati
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(500)  # ogni 500 ms

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(18)

        # Device selection group
        device_group = QGroupBox("Device selection")
        device_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 16px; border: 2px solid #007acc; border-radius: 8px; margin-top: 12px; background: #23272e; } QGroupBox::title { color: #007acc; left: 12px; padding: 0 6px; }")
        device_layout = QHBoxLayout()
        device_layout.setSpacing(12)
        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet("QComboBox { font-size: 15px; min-width: 180px; background: #23272e; color: #fff; border: 1px solid #007acc; border-radius: 4px; padding: 6px; }")
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedWidth(36)
        self.refresh_btn.setStyleSheet("QPushButton { font-size: 18px; background: #23272e; color: #007acc; border: 1px solid #007acc; border-radius: 4px; } QPushButton:hover { background: #007acc; color: #fff; }")
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setStyleSheet("QPushButton { font-size: 15px; background: #23272e; color: #ffb300; border: 1px solid #ffb300; border-radius: 4px; } QPushButton:hover { background: #ffb300; color: #23272e; }")
        device_layout.addWidget(QLabel("Device:"))
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(self.refresh_btn)
        device_layout.addWidget(self.pause_btn)
        device_group.setLayout(device_layout)
        main_layout.addWidget(device_group)

        # Divider
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setFrameShadow(QFrame.Shadow.Sunken)
        divider1.setStyleSheet("color: #007acc;")
        main_layout.addWidget(divider1)

        # Measurements group
        meas_group = QGroupBox("Measurements")
        meas_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 16px; border: 2px solid #43a047; border-radius: 8px; margin-top: 12px; background: #23272e; } QGroupBox::title { color: #43a047; left: 12px; padding: 0 6px; }")
        meas_layout = QGridLayout()
        meas_layout.setSpacing(10)
        label_font = QFont("Segoe UI", 13)
        value_font = QFont("Consolas", 16, QFont.Weight.Bold)
        self.voltage_lbl = QLabel("0.00")
        self.voltage_lbl.setFont(value_font)
        self.voltage_lbl.setStyleSheet("color: #00bcd4;")
        self.current_lbl = QLabel("0.00")
        self.current_lbl.setFont(value_font)
        self.current_lbl.setStyleSheet("color: #43a047;")
        self.temp_lbl = QLabel("0.00")
        self.temp_lbl.setFont(value_font)
        self.temp_lbl.setStyleSheet("color: #ff7043;")
        self.power_lbl = QLabel("0.00")
        self.power_lbl.setFont(value_font)
        self.power_lbl.setStyleSheet("color: #ffd600;")
        self.phases_lbl = QLabel("0")
        self.phases_lbl.setFont(value_font)
        self.phases_lbl.setStyleSheet("color: #b388ff;")
        meas_layout.addWidget(QLabel("Voltage (V):"), 0, 0)
        meas_layout.addWidget(self.voltage_lbl, 0, 1)
        meas_layout.addWidget(QLabel("Current (A):"), 1, 0)
        meas_layout.addWidget(self.current_lbl, 1, 1)
        meas_layout.addWidget(QLabel("Temp (°C):"), 2, 0)
        meas_layout.addWidget(self.temp_lbl, 2, 1)
        meas_layout.addWidget(QLabel("Power (W):"), 3, 0)
        meas_layout.addWidget(self.power_lbl, 3, 1)
        meas_layout.addWidget(QLabel("Phases:"), 4, 0)
        meas_layout.addWidget(self.phases_lbl, 4, 1)
        for i in range(5):
            meas_layout.itemAtPosition(i, 0).widget().setFont(label_font)
        meas_group.setLayout(meas_layout)
        main_layout.addWidget(meas_group)

        # Divider
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setFrameShadow(QFrame.Shadow.Sunken)
        divider2.setStyleSheet("color: #43a047;")
        main_layout.addWidget(divider2)

        # Protection status group
        prot_group = QGroupBox("Protection status")
        prot_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 16px; border: 2px solid #e53935; border-radius: 8px; margin-top: 12px; background: #23272e; } QGroupBox::title { color: #e53935; left: 12px; padding: 0 6px; }")
        prot_layout = QGridLayout()
        prot_layout.setSpacing(10)
        prot_label_font = QFont("Segoe UI", 13)
        prot_value_font = QFont("Consolas", 15, QFont.Weight.Bold)
        self.otp_lbl = QLabel("-")
        self.otp_lbl.setFont(prot_value_font)
        self.total_ocp_lbl = QLabel("-")
        self.total_ocp_lbl.setFont(prot_value_font)
        self.channel_ocl_lbl = QLabel("-")
        self.channel_ocl_lbl.setFont(prot_value_font)
        self.ovp_lbl = QLabel("-")
        self.ovp_lbl.setFont(prot_value_font)
        self.uvp_lbl = QLabel("-")
        self.uvp_lbl.setFont(prot_value_font)
        prot_layout.addWidget(QLabel("OTP:"), 0, 0)
        prot_layout.addWidget(self.otp_lbl, 0, 1)
        prot_layout.addWidget(QLabel("Total OCP:"), 1, 0)
        prot_layout.addWidget(self.total_ocp_lbl, 1, 1)
        prot_layout.addWidget(QLabel("Channel OCL:"), 2, 0)
        prot_layout.addWidget(self.channel_ocl_lbl, 2, 1)
        prot_layout.addWidget(QLabel("OVP:"), 3, 0)
        prot_layout.addWidget(self.ovp_lbl, 3, 1)
        prot_layout.addWidget(QLabel("UVP:"), 4, 0)
        prot_layout.addWidget(self.uvp_lbl, 4, 1)
        for i in range(5):
            prot_layout.itemAtPosition(i, 0).widget().setFont(prot_label_font)
        prot_group.setLayout(prot_layout)
        main_layout.addWidget(prot_group)

        # Filler
        main_layout.addStretch(1)
        self.setLayout(main_layout)

    def populate_devices(self):
        self.device_combo.clear()
        for dev in getattr(self.manager, 'devices', []):
            name = dev.get('name', 'Unknown')
            addr = dev.get('addr7')
            self.device_combo.addItem(f"{name} (0x{addr:02X})", addr)
        if getattr(self.manager, 'devices', []):
            self.device_combo.setCurrentIndex(0)

    def update_data(self):
        device = getattr(self.manager, 'current_device', None)
        def set_prot(lbl, value):
            if value:
                lbl.setText("ON")
                lbl.setStyleSheet("color: #e53935; font-weight: bold;")
                lbl.show()
            else:
                lbl.setText("OFF")
                lbl.setStyleSheet("color: #43a047; font-weight: bold;")
                lbl.show()
        if device is not None:
            try:
                measurements = device.get_measurements()
                if measurements:
                    self.voltage_lbl.setText(f"{measurements.get('voltage', 0):.2f}")
                    self.voltage_lbl.show()
                    self.current_lbl.setText(f"{measurements.get('current', 0):.2f}")
                    self.current_lbl.show()
                    self.temp_lbl.setText(f"{measurements.get('temperature', 0):.2f}")
                    self.temp_lbl.show()
                    self.power_lbl.setText(f"{measurements.get('power', 0):.2f}")
                    self.power_lbl.show()
                    self.phases_lbl.setText(str(measurements.get('operating_phases', 0)))
                    self.phases_lbl.show()
                    protections = measurements.get('protections', {})
                    set_prot(self.otp_lbl, protections.get('otp', False))
                    set_prot(self.total_ocp_lbl, protections.get('total_ocp', False))
                    set_prot(self.channel_ocl_lbl, protections.get('channel_ocl', False))
                    set_prot(self.ovp_lbl, protections.get('ovp', False))
                    set_prot(self.uvp_lbl, protections.get('uvp', False))
                else:
                    self._set_na()
            except Exception as e:
                print(f"Errore aggiornamento dati: {e}")
                self._set_na()
        else:
            self._set_na()

    def _set_na(self):
        self.voltage_lbl.hide()
        self.current_lbl.hide()
        self.temp_lbl.hide()
        self.power_lbl.hide()
        self.phases_lbl.hide()
        for lbl in [self.otp_lbl, self.total_ocp_lbl, self.channel_ocl_lbl, self.ovp_lbl, self.uvp_lbl]:
            lbl.hide()

class WriteWidget(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Write controls here"))
        self.setLayout(layout)
