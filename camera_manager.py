#!/usr/bin/env python3
"""
Camera manager specifically designed for Raspberry Pi OS.
This version handles the target mismatch issues properly.
"""

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
            try:
                with open('/proc/device-tree/model', 'r') as f:
                    model = f.read()
                    if 'raspberry pi' in model.lower():
                        print("Raspberry Pi detected")
                        self._check_rpi_camera()
                    else:
                        self.available = False
                        self.error = "Not running on Raspberry Pi"
                        print("Not running on Raspberry Pi")
            except FileNotFoundError:
                self.available = False
                self.error = "Not running on Raspberry Pi (no device tree)"
                print("Not running on Raspberry Pi (no device tree)")
        except Exception as e:
            self.available = False
            self.error = f"Platform detection failed: {str(e)}"
            print(f"Platform detection failed: {e}")

    def _check_rpi_camera(self):
        """Check Raspberry Pi camera with proper target handling"""
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

        # Try Raspberry Pi OS specific approach
        self._try_rpi_os_approach()

    def _try_rpi_os_approach(self):
        """Try camera initialization using Raspberry Pi OS specific methods"""
        import os

        # Method 1: Try without setting any target (let system decide)
        print("Trying camera initialization with system default target...")
        try:
            # Clear any existing target environment variable
            os.environ.pop('LIBCAMERA_RPI_TARGET', None)

            test_camera = Picamera2()

            # Try standard configuration
            try:
                config = test_camera.create_video_configuration()
                test_camera.configure(config)
                test_camera.start()
                test_camera.stop()
                test_camera.close()

                self.available = True
                self.error = None
                print("Camera detected and enabled with default configuration")
                return
            except Exception as config_error:
                print(f"Standard configuration failed: {config_error}")

                # Try preview configuration (more likely to work)
                try:
                    config = test_camera.create_preview_configuration()
                    test_camera.configure(config)
                    test_camera.start()
                    test_camera.stop()
                    test_camera.close()

                    self.available = True
                    self.error = None
                    print("Camera detected and enabled with preview configuration")
                    return
                except Exception as preview_error:
                    print(f"Preview configuration also failed: {preview_error}")
                    raise Exception(f"Both configuration methods failed")

        except Exception as e:
            print(f"Default approach failed: {e}")

            # Method 2: Try specific targets if default fails
            self._try_specific_targets()

    def _try_specific_targets(self):
        """Try specific targets if default approach fails"""
        import os

        # Determine which targets to try based on Raspberry Pi model
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'Raspberry Pi 5' in model or 'BCM2712' in model:
                    # Raspberry Pi 5 - try bcm2835 first, then pisp
                    targets_to_try = ['bcm2835', 'pisp']
                else:
                    # Older models - try pisp first, then bcm2835
                    targets_to_try = ['pisp', 'bcm2835']
        except:
            targets_to_try = ['pisp', 'bcm2835']

        last_error = None

        for target in targets_to_try:
            try:
                print(f"Trying camera initialization with {target} target...")
                os.environ['LIBCAMERA_RPI_TARGET'] = target

                test_camera = Picamera2()

                # Try standard configuration for this target
                config = test_camera.create_video_configuration()
                test_camera.configure(config)
                test_camera.start()
                test_camera.stop()
                test_camera.close()

                self.available = True
                self.error = None
                print(f"Camera detected and enabled with {target} target")
                return

            except Exception as target_error:
                print(f"Camera initialization failed with {target} target: {target_error}")
                last_error = target_error
                continue

        # If we get here, all methods failed
        self.available = False
        self.error = f"Camera initialization failed: {last_error}"
        print(f"Camera initialization failed with all methods")

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

# Test the new camera manager
if __name__ == "__main__":
    print("Testing new Raspberry Pi OS camera manager...")
    cm = CameraManager()
    print("Camera status:", cm.get_status())

    if cm.available:
        print("✓ Camera is available!")
    else:
        print(f"✗ Camera not available: {cm.error}")