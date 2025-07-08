# 08.07.25

import time
from serial.tools import list_ports
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer, Qt

from app.manager import I2CManager
from app.windows import ReadWidget

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
        
        # Setup manager
        print(f"[{time.time()}] Finding serial port")
        self.port = self.find_port()
        
        # Check if a port was found
        if self.port:
            print(f"[{time.time()}] Initializing I2CManager with port: {self.port}")
            self.manager = I2CManager(self.port, developer_mode=developer)
            self.no_device = False
        else:
            print(f"[{time.time()}] No device found, showing connection prompt")
            self.manager = None
            self.no_device = True
        
        # Setup UI 
        print(f"[{time.time()}] Setting up UI")
        self.setup_ui()
        self.DEFAULT_VALUES = []
        print(f"[{time.time()}] MainWindow initialization complete")

    def setup_ui(self):
        print(f"[{time.time()}] Creating UI components")
        # Create central widget if it doesn't exist
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        if self.no_device:
            self.setup_no_device_ui(layout)

        else:
            self.tab_widget = QTabWidget()
            self.read_widget = ReadWidget(self.manager)
            self.tab_widget.addTab(self.read_widget, "Read")
            layout.addWidget(self.tab_widget)
            
            # Start runtime updates
            if hasattr(self, 'runtime_timer') and self.runtime_timer:
                self.runtime_timer.stop()
                
            self.runtime_timer = QTimer()
            self.runtime_timer.timeout.connect(self.update_runtime)
            self.runtime_timer.start(1000)
            
            # Update window title
            self.setWindowTitle("VCore Monitor - Read")
        
        central.setLayout(layout)
        print(f"[{time.time()}] UI setup complete")
        
    def setup_no_device_ui(self, layout):
        """Setup UI for when no device is connected"""
        message_container = QWidget()
        message_layout = QVBoxLayout(message_container)
        
        # Add icon or image
        icon_label = QLabel()
        icon_label.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_layout.addWidget(icon_label)
        
        # Add message text
        message_label = QLabel("No CH340 Device Found")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("font-size: 18pt; color: #e74c3c; margin: 20px;")
        message_layout.addWidget(message_label)
        
        # Add instructions
        instructions_label = QLabel("Please connect your VCore monitoring device and restart the application.")
        instructions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions_label.setStyleSheet("font-size: 12pt; margin: 10px;")
        message_layout.addWidget(instructions_label)
        
        # Add status label for automatic scanning
        self.scan_status_label = QLabel("Scanning for device...")
        self.scan_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scan_status_label.setStyleSheet("font-size: 10pt; color: #3498db; margin: 5px;")
        message_layout.addWidget(self.scan_status_label)
        
        # Add refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                padding: 10px 20px;
                font-size: 14pt;
                min-width: 150px;
                margin: 20px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_connection)
        
        refresh_btn_container = QWidget()
        refresh_btn_layout = QHBoxLayout(refresh_btn_container)
        refresh_btn_layout.addStretch()
        refresh_btn_layout.addWidget(refresh_btn)
        refresh_btn_layout.addStretch()
        message_layout.addWidget(refresh_btn_container)
        
        # Add message to main layout with stretches for vertical centering
        layout.addStretch(1)
        layout.addWidget(message_container)
        layout.addStretch(1)
        
        # Start automatic scanning timer
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.auto_scan_for_device)
        self.scan_timer.start(2000)  # Scan every 2 seconds
        
    def auto_scan_for_device(self):
        """Automatically scan for CH340 devices"""
        if not hasattr(self, '_scan_dots'):
            self._scan_dots = 0
        
        self._scan_dots = (self._scan_dots + 1) % 4
        dots = "." * self._scan_dots
        self.scan_status_label.setText(f"Scanning for device{dots.ljust(3)}")
        
        # Try to find the port
        self.port = self.find_port()
        
        if self.port:
            self.scan_timer.stop()
            self.scan_status_label.setText("Device found! Connecting...")
            self.scan_status_label.setStyleSheet("font-size: 10pt; color: #2ecc71; margin: 5px; font-weight: bold;")
            
            # Give user a moment to see the success message before connecting
            QTimer.singleShot(1000, self.restart_application)
    
    def restart_application(self):
        """Reconnect to the device without fully restarting the application"""
        print(f"[{time.time()}] Device found, reconnecting...")
        
        try:
            # Stop scan timer
            if hasattr(self, 'scan_timer'):
                self.scan_timer.stop()
                self.scan_timer = None
                
            # Initialize manager with found port
            self.manager = I2CManager(self.port, developer_mode=developer)
            self.no_device = False
            
            # Clear existing UI
            if self.layout():
                # Remove all widgets from layout
                while self.layout().count():
                    item = self.layout().takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                        
            # Recreate UI
            self.setup_ui()
            
            print(f"[{time.time()}] Successfully reconnected to device")

        except Exception as e:
            print(f"[{time.time()}] Error reconnecting: {e}")
            QMessageBox.critical(self, "Error Connecting", f"Could not connect to device: {e}")
            self.no_device = True

    def refresh_connection(self):
        """Attempt to refresh the connection to the device"""
        print(f"[{time.time()}] Manually attempting to reconnect to CH340 device")
        self.port = self.find_port()
        
        if self.port:
            print(f"[{time.time()}] Device found at {self.port}, connecting...")
            QMessageBox.information(self, "Success", "Device found! Connecting now.")
            
            # Connect to the device
            self.restart_application()
        else:
            QMessageBox.warning(self, "No Device Found", "No CH340 device was found. Please check the connection and try again.")

    def update_runtime(self):
        """Update runtime in window title"""
        try:
            if self.manager is None:
                self.setWindowTitle("VCore Monitor - No Device")
                return
                
            # Only update every 1 second to reduce communication overhead
            current_time = time.time()
            if not hasattr(self, '_last_runtime_update') or current_time - self._last_runtime_update >= 1.0:
                self._last_runtime_update = current_time
                
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
        else:
            print(f"[{time.time()}] No CH340 device found")
            return None
    
    def closeEvent(self, event):
        """Handle application close with proper resource cleanup"""
        try:
            # Stop monitoring
            self.is_monitoring = False
            
            # Stop all timers
            if hasattr(self, 'timer'):
                self.timer.stop()
                try:
                    self.timer.timeout.disconnect()
                except:
                    pass
                self.timer = None
            
            # Stop runtime timer
            if hasattr(self, 'runtime_timer'):
                self.runtime_timer.stop()
                try:
                    self.runtime_timer.timeout.disconnect()
                except:
                    pass
                self.runtime_timer = None
                
            # Stop scan timer if it exists
            if hasattr(self, 'scan_timer'):
                self.scan_timer.stop()
                try:
                    self.scan_timer.timeout.disconnect()
                except:
                    pass
                self.scan_timer = None
            
            # Close manager and clean up resources
            if hasattr(self, 'manager') and self.manager is not None:
                self.manager.close()
                self.manager = None
                
            # Clean up widgets to ensure proper Qt resource cleanup
            if hasattr(self, 'read_widget'):
                if hasattr(self.read_widget, 'data_timer'):
                    self.read_widget.data_timer.stop()
                    try:
                        self.read_widget.data_timer.timeout.disconnect()
                    except:
                        pass
                self.read_widget = None
                
            time.sleep(0.05) 
            
        except Exception as e:
            print(f"Error during close: {e}")
        finally:
            import gc
            gc.collect()
            
            event.accept()

if __name__ == '__main__':
    print(f"[{time.time()}] Application starting")

    def clean_exit():
        try:
            if 'window' in globals():
                window.close()
            if 'app' in globals():
                app.quit()
        except Exception as e:
            print(f"Error during exit: {e}")

    try:
        app = QApplication([])
        print(f"[{time.time()}] Creating main window")
        window = MainWindow()
        print(f"[{time.time()}] Showing window")
        window.show()

        app.aboutToQuit.connect(clean_exit)
        app.exec()
    except KeyboardInterrupt:
        clean_exit()
    except Exception as e:
        print(f"Error: {e}")
        clean_exit()