import subprocess
import platform
import io
import threading
import time
import os
import signal

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
    print("Using picamera2 library")
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("picamera2 library not available")

class CameraManager:
    def __init__(self):
        self.available = False
        self.error = None
        self.camera = None
        self.stream_process = None
        self.streaming = False
        self.stream_port = 8000
        self.check_camera()

    def check_camera(self):
        """Check if we're on Raspberry Pi and if camera is available"""
        try:
            # Check if we're on Raspberry Pi
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'raspberry pi' in model.lower():
                    print("Raspberry Pi detected")

                    # Check if picamera2 is available
                    if not PICAMERA2_AVAILABLE:
                        self.available = False
                        self.error = "picamera2 library not available"
                        print("picamera2 library not available")
                        return

                    # Check if ffmpeg is available
                    try:
                        subprocess.run(['ffmpeg', '-version'],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     check=True)
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        self.available = False
                        self.error = "ffmpeg not installed"
                        print("ffmpeg not installed")
                        return

                    # Try to initialize camera
                    try:
                        test_camera = Picamera2()
                        config = test_camera.create_video_configuration()
                        test_camera.configure(config)
                        test_camera.start()
                        test_camera.stop()
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
            "streaming": self.streaming,
            "stream_url": f"http://localhost:{self.stream_port}/stream.mjpg" if self.streaming else None
        }

    def start_video_stream(self):
        """Start video streaming using ffmpeg"""
        if not self.available:
            return None, "Camera not available"

        if self.streaming:
            return None, "Camera already streaming"

        try:
            # Start ffmpeg process to capture from camera and stream as MJPEG
            cmd = [
                'ffmpeg',
                '-f', 'v4l2',
                '-input_format', 'h264',
                '-video_size', '640x480',
                '-framerate', '15',
                '-i', '/dev/video0',
                '-c:v', 'copy',
                '-f', 'mpegts',
                '-codec:v', 'mpeg1video',
                '-b:v', '800k',
                '-bf', '0',
                '-r', '15',
                '-f', 'mpegts',
                'udp://localhost:1234'
            ]

            self.stream_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            # Give ffmpeg time to start
            time.sleep(3)

            # Check if process is still running
            if self.stream_process.poll() is not None:
                error = self.stream_process.stderr.read().decode()
                self.stop_video_stream()
                return None, f"ffmpeg failed to start: {error}"

            self.streaming = True
            return None, "Stream started successfully"

        except Exception as e:
            self.stop_video_stream()
            return None, f"Failed to start stream: {str(e)}"

    def stop_video_stream(self):
        """Stop the video stream"""
        if not self.streaming:
            return

        self.streaming = False

        if self.stream_process:
            try:
                # Terminate the process group
                os.killpg(os.getpgid(self.stream_process.pid), signal.SIGTERM)
                self.stream_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.stream_process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                self.stream_process = None

        print("Camera stream stopped")

    def __del__(self):
        """Cleanup on object destruction"""
        self.stop_video_stream()