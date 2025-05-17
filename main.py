import os
import time
from serial.tools import list_ports
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer, Qt

from app.manager import I2CManager
from app.windows import ReadWidget, WriteWidget

developer = False 

class MainWindow(QMainWindow):
    def __init__(self):
        print(f"[{time.time()}] Starting MainWindow initialization")
        super().__init__()
        self.setWindowTitle("VCore Monitor - Read")
        self.setMinimumSize(600, 780)
        self.runtime = "00:00:00"
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                background: #2b2b2b;
            }
            QTabBar::tab {
                background: #323232;
                color: #ffffff;
                padding: 8px 20px;
                border: 1px solid #3a3a3a;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #404040;
                border-bottom: 2px solid #007acc;
            }
            QTabBar::tab:hover {
                background: #404040;
            }
            QGroupBox {
                background-color: #323232;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 24px;
                color: #ffffff;
            }
            QGroupBox::title {
                color: #007acc;
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0098ff;
            }
            QPushButton:pressed {
                background-color: #005c99;
            }
            QPushButton:disabled {
                background-color: #4d4d4d;
                color: #999999;
            }
            QCheckBox {
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QComboBox {
                background-color: #323232;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                padding: 4px;
                border-radius: 3px;
            }
            QComboBox:drop-down {
                border: none;
            }
            QComboBox:down-arrow {
                image: none;
            }
            QSpinBox {
                background-color: #323232;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                padding: 4px;
                border-radius: 3px;
            }
        """)
        
        # Setup logs directory
        print(f"[{time.time()}] Setting up logs directory")
        self.log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        if os.path.exists(self.log_dir):
            for f in os.listdir(self.log_dir):
                file_path = os.path.join(self.log_dir, f)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f'Error deleting {file_path}: {e}')
                    
        else:
            os.makedirs(self.log_dir)
        
        # Setup manager
        print(f"[{time.time()}] Finding serial port")
        port = self.find_port()
        print(f"[{time.time()}] Initializing I2CManager with port: {port}")
        self.manager = I2CManager(port, developer_mode=developer)
        
        # Setup UI 
        print(f"[{time.time()}] Setting up UI")
        self.setup_ui()
        self.DEFAULT_VALUES = []
        print(f"[{time.time()}] MainWindow initialization complete")

    def setup_ui(self):
        print(f"[{time.time()}] Creating UI components")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Consider lazy loading of tabs
        self.tab_widget = QTabWidget()
        
        # Load both tabs immediately instead of lazy loading
        self.read_widget = ReadWidget(self.manager)
        self.write_widget = WriteWidget(self.manager)
        
        self.tab_widget.addTab(self.read_widget, "Read")
        self.tab_widget.addTab(self.write_widget, "Write")
        
        layout.addWidget(self.tab_widget)
        central.setLayout(layout)
        
        # Start runtime updates 
        self.runtime_timer = QTimer()
        self.runtime_timer.timeout.connect(self.update_runtime)
        self.runtime_timer.start(100)
        print(f"[{time.time()}] UI setup complete")

    def load_default_values(self):
        """Carica i valori di default nei controlli"""
        try:
            # Aggiorna i controlli nella write widget
            write_widget = self.write_widget
            
            # Imposta fasi
            for lcs, phases in self.DEFAULT_VALUES['phases'].items():
                if lcs in write_widget.phase_spinboxes:
                    write_widget.phase_spinboxes[lcs].setValue(phases)
            
            # Imposta protezioni
            write_widget.total_ocp_combo.setCurrentText(f"{self.DEFAULT_VALUES['protections']['total_ocp']}%")
            write_widget.vr_shdn_spin.setValue(self.DEFAULT_VALUES['protections']['vr_shutdown'])
            
            for key, enabled in self.DEFAULT_VALUES['protections']['enables'].items():
                if key in write_widget.prot_enables:
                    write_widget.prot_enables[key].setChecked(enabled)
                    
        except Exception as e:
            print(f"Error loading default values: {e}")

    def update_runtime(self):
        """Update runtime in window title"""
        try:
            status_cmd = {"action": "get_status"}
            self.manager.send_command(status_cmd)
            status = self.manager.wait_response("get_status")
            
            title_parts = ["VCore Monitor - Read"]
            
            if status and "uptime" in status:
                uptime = status["uptime"]
                hours = uptime // 3600
                minutes = (uptime % 3600) // 60
                seconds = uptime % 60
                self.runtime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                title_parts.append(f"Runtime: {self.runtime}")

            self.setWindowTitle(" - ".join(title_parts))

        except Exception as e:
            print(f"Runtime update error: {e}")

    def find_port(self):
        print(f"[{time.time()}] Scanning for COM ports")
        for port in list_ports.comports():
            if 'CH340' in port.description:
                print(f"[{time.time()}] Found CH340 device at {port.device}")
                return port.device
            
        if developer:
            print(f"[{time.time()}] Developer mode: Using mock port COM1")
            return "COM1"
        
        raise Exception("CH340 device not found")
    
    def closeEvent(self, event):
        """Handle application close"""
        try:
            # Prima fermiamo il monitoring
            self.is_monitoring = False
            
            # Fermiamo subito il timer e aspettiamo che finisca
            if hasattr(self, 'timer'):
                self.timer.stop()
                self.timer.timeout.disconnect()
            
            # Fermiamo il runtime timer
            if hasattr(self, 'runtime_timer'):
                self.runtime_timer.stop()
                self.runtime_timer.timeout.disconnect()
            
            # Reset the log file on close
            self.current_log_file = None
            
            # Poi chiudiamo il manager
            if hasattr(self, 'manager'):
                self.manager.close()
                
            # Sleep briefly to ensure all operations complete
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error during close: {e}")
        finally:
            event.accept()

if __name__ == '__main__':
    print(f"[{time.time()}] Application starting")
    app = QApplication([])
    print(f"[{time.time()}] Creating main window")
    window = MainWindow()
    print(f"[{time.time()}] Showing window")
    window.show()
    
    def clean_exit():
        #print(f"[{time.time()}] Clean exit initiated")
        window.close()
        app.quit()
    
    app.aboutToQuit.connect(clean_exit)
    
    try:
        app.exec()
    except KeyboardInterrupt:
        clean_exit()
    except Exception as e:
        print(f"Error: {e}")
        clean_exit()
