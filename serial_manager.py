import serial
import threading

class SerialManager:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.lock = threading.Lock()
        self.connected = False
        self.error = None

    def connect(self):
        """Initialize serial connection"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            if self.ser and self.ser.is_open:
                # Send initial OFF command when connecting
                with self.lock:
                    self.ser.write(b'0')
                self.connected = True
                self.error = None
                print("Serial connection established")
                print("Sent initial OFF command")
            else:
                self.connected = False
                self.error = "Port opened but not accessible"
        except serial.SerialException as e:
            self.connected = False
            self.error = str(e)
            print(f"Error opening serial port: {e}")
            self.ser = None
        except Exception as e:
            self.connected = False
            self.error = str(e)
            print(f"Unexpected error: {e}")
            self.ser = None

    def get_status(self):
        return {
            "connected": self.connected,
            "error": self.error
        }

    def send_command(self, command):
        """Send command through serial connection"""
        if not self.connected or not self.ser or not self.ser.is_open:
            return False, "Serial port not available"

        try:
            with self.lock:
                self.ser.write(command.encode())
            return True, "Command sent successfully"
        except serial.SerialTimeoutException as e:
            self.connected = False
            self.error = f"Serial timeout: {str(e)}"
            return False, f"Serial timeout error: {str(e)}"
        except OSError as e:
            if e.errno == 5:  # Input/output error
                self.connected = False
                self.error = "Device disconnected or I/O error"
                return False, "Device disconnected or I/O error"
            else:
                return False, f"I/O error: {str(e)}"
        except serial.SerialException as e:
            self.connected = False
            self.error = f"Serial communication error: {str(e)}"
            return False, f"Serial communication error: {str(e)}"
        except Exception as e:
            return False, str(e)

    def reconnect(self):
        """Close and reconnect serial connection"""
        self.disconnect()
        self.connect()

    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print("Serial connection closed")
            except Exception as e:
                print(f"Error closing serial port: {e}")
        self.ser = None
        self.connected = False