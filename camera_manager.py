import subprocess
import platform
import io
import threading
import time

try:
    # Try picamera2 first (for Raspberry Pi Camera Module 3 and newer systems)
    try:
        from picamera2 import Picamera2
        PICAMERA2_AVAILABLE = True
        PICAMERA_AVAILABLE = False
        print("Using picamera2 library")
    except ImportError:
        # Fallback to picamera for older systems
        from picamera import PiCamera
        from picamera.array import PiRGBArray
        PICAMERA2_AVAILABLE = False
        PICAMERA_AVAILABLE = True
        print("Using picamera library")
except ImportError:
    PICAMERA2_AVAILABLE = False
    PICAMERA_AVAILABLE = False
    print("No camera library available")

class CameraManager:
    def __init__(self):
        self.available = False
        self.error = None
        self.camera = None
        self.stream = None
        self.streaming = False
        self.check_camera()

    def check_camera(self):
        """Check if we're on Raspberry Pi and if camera is available"""
        try:
            # Check if we're on Raspberry Pi
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'raspberry pi' in model.lower():
                    print("Raspberry Pi detected")

                    # Check if any camera library is available
                    if not (PICAMERA2_AVAILABLE or PICAMERA_AVAILABLE):
                        self.available = False
                        self.error = "No camera library available (picamera or picamera2)"
                        print("No camera library available")
                        return

                    # Try to initialize camera based on available library
                    try:
                        if PICAMERA2_AVAILABLE:
                            test_camera = Picamera2()
                            config = test_camera.create_video_configuration()
                            test_camera.configure(config)
                            test_camera.start()
                            test_camera.stop()
                            test_camera.close()
                        else:  # PICAMERA_AVAILABLE
                            test_camera = PiCamera()
                            test_camera.close()

                        self.available = True
                        self.error = None
                        print("Camera detected and enabled")
                    except Exception as e:
                        self.available = False
                        self.error = f"Camera initialization failed: {str(e)}"
                        print(f"Camera initialization failed: {e}")
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
            "error": self.error,
            "streaming": self.streaming
        }

    def start_video_stream(self):
        """Start video streaming from Raspberry Pi camera"""
        if not self.available:
            return None, "Camera not available"

        if self.streaming:
            return None, "Camera already streaming"

        try:
            if PICAMERA2_AVAILABLE:
                return self._start_picamera2_stream()
            else:  # PICAMERA_AVAILABLE
                return self._start_picamera_stream()

        except Exception as e:
            self.stop_video_stream()
            self.available = False
            self.error = f"Camera stream error: {str(e)}"
            return None, f"Camera stream error: {str(e)}"

    def _start_picamera2_stream(self):
        """Start video stream using picamera2"""
        try:
            from picamera2 import Picamera2

            # Initialize camera
            self.camera = Picamera2()
            config = self.camera.create_video_configuration(
                main={"format": 'XRGB8888', "size": (640, 480)},
                controls={"FrameRate": 30}
            )
            self.camera.configure(config)
            self.camera.start()

            self.streaming = True

            def capture_frames():
                while self.streaming:
                    try:
                        # Get frame from camera
                        im = self.camera.capture_array()

                        # Convert to JPEG
                        import cv2
                        import numpy as np
                        _, jpeg = cv2.imencode('.jpg', cv2.cvtColor(im, cv2.COLOR_RGB2BGR))

                        yield jpeg.tobytes()
                    except Exception as e:
                        print(f"Frame capture error: {e}")
                        break

            return capture_frames(), None

        except ImportError:
            return None, "Required libraries not available (opencv-python, numpy)"
        except Exception as e:
            self.stop_video_stream()
            return None, f"picamera2 stream error: {str(e)}"

    def _start_picamera_stream(self):
        """Start video stream using picamera (legacy)"""
        try:
            from picamera import PiCamera

            # Initialize camera
            self.camera = PiCamera()
            self.camera.resolution = (640, 480)
            self.camera.framerate = 30

            # Create stream
            self.stream = io.BytesIO()
            self.streaming = True

            # Start capturing frames
            def capture_frames():
                for frame in self.camera.capture_continuous(self.stream, 'jpeg', use_video_port=True):
                    # Return the current frame
                    self.stream.seek(0)
                    yield self.stream.read()

                    # Reset stream for next frame
                    self.stream.seek(0)
                    self.stream.truncate()

                    # Exit if streaming stopped
                    if not self.streaming:
                        break

            return capture_frames(), None

        except Exception as e:
            self.stop_video_stream()
            return None, f"picamera stream error: {str(e)}"

    def stop_video_stream(self):
        """Stop the video stream"""
        self.streaming = False
        if self.camera:
            try:
                if PICAMERA2_AVAILABLE:
                    self.camera.stop()
                self.camera.close()
                self.camera = None
            except:
                pass
        if self.stream:
            try:
                self.stream.close()
                self.stream = None
            except:
                pass
        print("Camera stream stopped")