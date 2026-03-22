import subprocess
import platform

class CameraManager:
    def __init__(self):
        self.available = False
        self.error = None
        self.check_camera()
    
    def check_camera(self):
        """Check if we're on Raspberry Pi and if camera is available"""
        try:
            # Check if we're on Raspberry Pi
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'raspberry pi' in model.lower():
                    self.available = True
                    self.error = None
                    print("Raspberry Pi detected")
                    
                    # Check if camera is enabled
                    try:
                        result = subprocess.run(['vcgencmd', 'get_camera'], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode != 0 or 'detected=0' in result.stdout:
                            self.available = False
                            self.error = "Camera not detected or disabled"
                            print("Camera not detected or disabled")
                        else:
                            print("Camera detected and enabled")
                    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                        self.available = False
                        self.error = f"Camera check failed: {str(e)}"
                        print(f"Camera check failed: {e}")
                else:
                    self.available = False
                    self.error = "Not running on Raspberry Pi"
                    print("Not running on Raspberry Pi")
        except Exception as e:
            self.available = False
            self.error = f"Platform detection failed: {str(e)}"
            print(f"Platform detection failed: {e}")
    
    def get_status(self):
        return {
            "available": self.available,
            "error": self.error
        }
    
    def start_video_stream(self):
        """Start video streaming from Raspberry Pi camera"""
        if not self.available:
            return None, "Camera not available"
        
        try:
            # Try libcamera-vid first (newer Raspberry Pi OS)
            try:
                command = ['libcamera-vid', '-t', '0', '--inline', '--listen', '-o', 'tcp://0.0.0.0:8000']
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return process, "tcp://0.0.0.0:8000"
            except FileNotFoundError:
                # Fallback to raspivid for older systems
                command = ['raspivid', '-t', '0', '-w', '640', '-h', '480', '-fps', '30', '-o', '-']
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return process, None
        except Exception as e:
            self.available = False
            self.error = f"Camera stream error: {str(e)}"
            return None, f"Camera stream error: {str(e)}"