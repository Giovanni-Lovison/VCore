# 08.07.25

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox, QGroupBox, QGridLayout, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

class ReadWidget(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        
        # Initialize last measurements for comparison
        self._last_measurements = {
            'voltage': None, 'current': None, 'temperature': None,
            'power': None, 'operating_phases': None,
            'protections': {}
        }
        
        # Store stylesheets as class variables to avoid recreating them on each update
        self._init_stylesheets()
        
        self.init_ui()
        self.populate_devices()
        
        # Timer per aggiornamento dati
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(200)  # ogni 200 ms (aggiornato da 500ms)

    def _init_stylesheets(self):
        """Initialize stylesheets as class variables to avoid recreating them on each update"""
        self.device_group_style = "QGroupBox { font-weight: bold; font-size: 16px; border: 2px solid #007acc; border-radius: 8px; margin-top: 12px; background: #23272e; } QGroupBox::title { color: #007acc; left: 12px; padding: 0 6px; }"
        self.device_combo_style = "QComboBox { font-size: 15px; min-width: 180px; background: #23272e; color: #fff; border: 1px solid #007acc; border-radius: 4px; padding: 6px; }"
        self.refresh_btn_style = "QPushButton { font-size: 18px; background: #23272e; color: #007acc; border: 1px solid #007acc; border-radius: 4px; } QPushButton:hover { background: #007acc; color: #fff; }"
        self.meas_group_style = "QGroupBox { font-weight: bold; font-size: 16px; border: 2px solid #43a047; border-radius: 8px; margin-top: 12px; background: #23272e; } QGroupBox::title { color: #43a047; left: 12px; padding: 0 6px; }"
        self.prot_group_style = "QGroupBox { font-weight: bold; font-size: 16px; border: 2px solid #e53935; border-radius: 8px; margin-top: 12px; background: #23272e; } QGroupBox::title { color: #e53935; left: 12px; padding: 0 6px; }"
        
        # Label styles
        self.voltage_style = "color: #00bcd4;"
        self.current_style = "color: #43a047;"
        self.temp_style = "color: #ff7043;"
        self.power_style = "color: #ffd600;"
        self.phases_style = "color: #b388ff;"
        
        # Protection styles
        self.prot_on_style = "color: #e53935; font-weight: bold;"
        self.prot_off_style = "color: #43a047; font-weight: bold;"

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(18)

        # Device selection group
        device_group = QGroupBox("Device selection")
        device_group.setStyleSheet(self.device_group_style)
        device_layout = QHBoxLayout()
        device_layout.setSpacing(12)
        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet(self.device_combo_style)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedWidth(36)
        self.refresh_btn.setStyleSheet(self.refresh_btn_style)
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        device_layout.addWidget(QLabel("Device:"))
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(self.refresh_btn)
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
        meas_group.setStyleSheet(self.meas_group_style)
        meas_layout = QGridLayout()
        meas_layout.setSpacing(10)
        label_font = QFont("Segoe UI", 13)
        value_font = QFont("Consolas", 16, QFont.Weight.Bold)
        self.voltage_lbl = QLabel("0.00")
        self.voltage_lbl.setFont(value_font)
        self.voltage_lbl.setStyleSheet(self.voltage_style)
        self.current_lbl = QLabel("0.00")
        self.current_lbl.setFont(value_font)
        self.current_lbl.setStyleSheet(self.current_style)
        self.temp_lbl = QLabel("0.00")
        self.temp_lbl.setFont(value_font)
        self.temp_lbl.setStyleSheet(self.temp_style)
        self.power_lbl = QLabel("0.00")
        self.power_lbl.setFont(value_font)
        self.power_lbl.setStyleSheet(self.power_style)
        self.phases_lbl = QLabel("0")
        self.phases_lbl.setFont(value_font)
        self.phases_lbl.setStyleSheet(self.phases_style)
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
        prot_group.setStyleSheet(self.prot_group_style)
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
        devices = getattr(self.manager, 'devices', [])
        
        if not devices:
            # No devices found - show message
            self.device_combo.addItem("No PWM controller found")
            self.device_combo.setEnabled(False)
            return
            
        # Devices found - populate dropdown
        self.device_combo.setEnabled(True)
        for dev in devices:
            name = dev.get('name', 'Unknown')
            addr = dev.get('addr7')
            self.device_combo.addItem(f"{name} (0x{addr:02X})", addr)
        if devices:
            self.device_combo.setCurrentIndex(0)

    def update_data(self):
        device = getattr(self.manager, 'current_device', None)
        
        # Initialize last measurements if not exist
        if not hasattr(self, '_last_measurements') or self._last_measurements is None:
            self._last_measurements = {
                'voltage': None, 'current': None, 'temperature': None,
                'power': None, 'operating_phases': None,
                'protections': {}
            }
            
        def set_prot(lbl, value, current_value):
            if value != current_value:
                if value:
                    lbl.setText("ON")
                    lbl.setStyleSheet(self.prot_on_style)
                    lbl.show()
                else:
                    lbl.setText("OFF")
                    lbl.setStyleSheet(self.prot_off_style)
                    lbl.show()
            return value
                
        if device is not None:
            try:
                measurements = device.get_measurements()
                if measurements:
                    # Update voltage if changed
                    voltage = measurements.get('voltage', 0)
                    if self._last_measurements.get('voltage') != voltage:
                        self.voltage_lbl.setText(f"{voltage:.2f}")
                        self.voltage_lbl.show()
                        self._last_measurements['voltage'] = voltage
                        
                    # Update current if changed
                    current = measurements.get('current', 0)
                    if self._last_measurements.get('current') != current:
                        self.current_lbl.setText(f"{current:.2f}")
                        self.current_lbl.show()
                        self._last_measurements['current'] = current
                        
                    # Update temperature if changed
                    temperature = measurements.get('temperature', 0)
                    if self._last_measurements.get('temperature') != temperature:
                        self.temp_lbl.setText(f"{temperature:.2f}")
                        self.temp_lbl.show()
                        self._last_measurements['temperature'] = temperature
                        
                    # Update power if changed
                    power = measurements.get('power', 0)
                    if self._last_measurements.get('power') != power:
                        self.power_lbl.setText(f"{power:.2f}")
                        self.power_lbl.show()
                        self._last_measurements['power'] = power
                        
                    # Update phases if changed
                    phases = measurements.get('operating_phases', 0)
                    if self._last_measurements.get('operating_phases') != phases:
                        self.phases_lbl.setText(str(phases))
                        self.phases_lbl.show()
                        self._last_measurements['operating_phases'] = phases
                        
                    # Update protection status if changed
                    protections = measurements.get('protections', {})
                    
                    # Ensure protections is initialized in _last_measurements
                    if 'protections' not in self._last_measurements:
                        self._last_measurements['protections'] = {}
                    last_protections = self._last_measurements['protections']
                    
                    otp_val = protections.get('otp', False)
                    last_protections['otp'] = set_prot(self.otp_lbl, otp_val, last_protections.get('otp'))
                    
                    total_ocp_val = protections.get('total_ocp', False)
                    last_protections['total_ocp'] = set_prot(self.total_ocp_lbl, total_ocp_val, last_protections.get('total_ocp'))
                    
                    channel_ocl_val = protections.get('channel_ocl', False)
                    last_protections['channel_ocl'] = set_prot(self.channel_ocl_lbl, channel_ocl_val, last_protections.get('channel_ocl'))
                    
                    ovp_val = protections.get('ovp', False)
                    last_protections['ovp'] = set_prot(self.ovp_lbl, ovp_val, last_protections.get('ovp'))
                    
                    uvp_val = protections.get('uvp', False)
                    last_protections['uvp'] = set_prot(self.uvp_lbl, uvp_val, last_protections.get('uvp'))
                    
                    self._last_measurements['protections'] = last_protections
                else:
                    self._set_na()
                    self._last_measurements = None
            except Exception as e:
                print(f"Errore aggiornamento dati: {e}")
                self._set_na()
                self._last_measurements = None
        else:
            self._set_na()
            self._last_measurements = None

    def _set_na(self):
        """Imposta lo stato N/A (non disponibile) per tutte le etichette"""
        self.voltage_lbl.setText("N/A")
        self.current_lbl.setText("N/A")
        self.temp_lbl.setText("N/A")
        self.power_lbl.setText("N/A")
        self.phases_lbl.setText("N/A")
        
        # Mostra le etichette
        self.voltage_lbl.show()
        self.current_lbl.show()
        self.temp_lbl.show()
        self.power_lbl.show()
        self.phases_lbl.show()
        
        # Imposta le protezioni su N/A
        for lbl in [self.otp_lbl, self.total_ocp_lbl, self.channel_ocl_lbl, self.ovp_lbl, self.uvp_lbl]:
            lbl.setText("N/A")
            lbl.setStyleSheet("color: #7f7f7f; font-weight: normal;")  # Grigio per N/A
            lbl.show()

    def cleanup(self):
        """Clean up resources used by this widget"""
        if hasattr(self, 'data_timer'):
            self.data_timer.stop()
            try:
                self.data_timer.timeout.disconnect()
            except:
                pass
            
        # Clear any stored measurements
        self._last_measurements = None
        
        # Clean signals
        try:
            self.refresh_btn.clicked.disconnect()
        except:
            pass

    def on_device_changed(self, index):
        """Gestisce il cambio del dispositivo selezionato"""
        if index >= 0:
            addr7 = self.device_combo.itemData(index)
            if addr7:
                print(f"Cambio dispositivo a: {self.device_combo.currentText()} (0x{addr7:02X})")
                
                # Reimposta i valori delle misurazioni per il nuovo dispositivo
                self._last_measurements = {
                    'voltage': None, 'current': None, 'temperature': None,
                    'power': None, 'operating_phases': None, 
                    'protections': {}
                }
                
                # Seleziona il nuovo dispositivo tramite il manager
                success = self.manager.select_device(addr7)
                
                # Breve pausa per dare tempo al sistema di stabilizzarsi
                import time
                time.sleep(0.1)
                
                # Aggiorna immediatamente i dati
                self.update_data()
                
                # Debug: Controlla se la selezione del dispositivo ha funzionato
                if not success:
                    print(f"Debug: Selezione fallita per il dispositivo con indirizzo 0x{addr7:02X}")

    def on_refresh_clicked(self):
        """Aggiorna la lista dei dispositivi e riseleziona il dispositivo corrente"""
        current_addr = None
        if self.device_combo.currentIndex() >= 0:
            current_addr = self.device_combo.itemData(self.device_combo.currentIndex())
        
        # Ricarica la lista dei dispositivi
        if hasattr(self.manager, 'rescan_devices'):
            self.manager.rescan_devices()
        
        # Ricarichiamo la lista nel combo
        self.populate_devices()
        
        # Proviamo a riselezionare il dispositivo precedentemente attivo
        if current_addr:
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == current_addr:
                    self.device_combo.setCurrentIndex(i)
                    break
                    
        # Resettiamo i valori delle misurazioni
        self._last_measurements = {
            'voltage': None, 'current': None, 'temperature': None,
            'power': None, 'operating_phases': None,
            'protections': {}
        }
        
        # Aggiorna immediatamente i dati
        self.update_data()
        
class WriteWidget(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Write controls here"))
        self.setLayout(layout)
