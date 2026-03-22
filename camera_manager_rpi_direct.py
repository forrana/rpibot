#!/usr/bin/env python3
"""
Direct Raspberry Pi camera manager that bypasses picamera2 entirely.
Uses libcamera-vid and ffmpeg directly for maximum compatibility.
"""

import subprocess
import platform
import io
import threading
import time
import os
import signal

class CameraManagerDirect:
    def __init__(self):
        self.available = False
        self.error = None
        self.stream_process = None
        self.streaming = False
        self.stream_port = 8000
        self.camera_cmd = None  # Will be set in check_camera()
        self.check_camera()

    def check_camera(self):
        """Check if camera is available using direct libcamera tools"""
        try:
            # Check if we're on Raspberry Pi
            try:
                with open('/proc/device-tree/model', 'r') as f:
                    model = f.read()
                    if 'raspberry pi' not in model.lower():
                        self.available = False
                        self.error = "Not running on Raspberry Pi"
                        print("Not running on Raspberry Pi")
                        return
            except FileNotFoundError:
                self.available = False
                self.error = "Not running on Raspberry Pi (no device tree)"
                print("Not running on Raspberry Pi (no device tree)")
                return

            # Check if rpicam-vid is available (Bookworm) or libcamera-vid (older versions)
            camera_cmds = ['rpicam-vid', 'libcamera-vid']
            camera_cmd = None

            for cmd in camera_cmds:
                try:
                    result = subprocess.run([cmd, '--version'],
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         timeout=5)
                    if result.returncode == 0:
                        camera_cmd = cmd
                        print(f"Using {cmd} for camera capture")
                        break
                except Exception:
                    continue

            if camera_cmd is None:
                self.available = False
                self.error = "No compatible camera command found (tried rpicam-vid and libcamera-vid)"
                print("No compatible camera command found")
                return

            # Store the detected camera command for later use
            self.camera_cmd = camera_cmd

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

            # Test camera with the detected command
            try:
                # Use a temporary file instead of /dev/null to avoid format issues
                test_cmd = f"{camera_cmd} -t 1000 --nopreview --codec h264 --width 640 --height 480 --framerate 30 -o test.h264"
                result = subprocess.run(test_cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     timeout=5,
                                     shell=True)

                # Clean up test file
                if os.path.exists('test.h264'):
                    os.remove('test.h264')
                if result.returncode == 0:
                    self.available = True
                    self.error = None
                    print("Camera detected and enabled using libcamera-vid")
                else:
                    error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                    self.available = False
                    self.error = f"Camera test failed: {error_msg}"
                    print(f"Camera test failed: {error_msg}")
            except subprocess.TimeoutExpired:
                self.available = False
                self.error = "Camera test timed out"
                print("Camera test timed out")
            except Exception as e:
                self.available = False
                self.error = f"Camera test failed: {str(e)}"
                print(f"Camera test failed: {e}")

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
        """Start video streaming using libcamera-vid and ffmpeg"""
        if not self.available:
            return None, "Camera not available"

        if self.streaming:
            return None, "Camera already streaming"

        try:
            # Start the detected camera command to capture raw video
            # Use raw output and let ffmpeg handle the encoding
            camera_cmd_str = (
                f"{self.camera_cmd} -t 0 --width 640 --height 480 "
                f"--framerate 30 --nopreview --raw"
            )

            # Start ffmpeg to encode and serve via UDP
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'rawvideo',  # Raw video input
                '-pixel_format', 'yuv420p',  # Common pixel format
                '-video_size', '640x480',  # Match camera resolution
                '-framerate', '30',  # Match camera framerate
                '-i', 'pipe:',  # Input from pipe
                '-c:v', 'libx264',  # Encode with x264
                '-preset', 'ultrafast',  # Low latency
                '-tune', 'zerolatency',  # Minimize latency
                '-f', 'mpegts',
                f'udp://localhost:{self.stream_port}'
            ]

            # Use shell=True for proper stdout handling
            self.camera_process = subprocess.Popen(camera_cmd_str,
                                                stdout=subprocess.PIPE,
                                                shell=True)
            self.stream_process = subprocess.Popen(ffmpeg_cmd,
                                                stdin=self.camera_process.stdout)

            # Give processes time to start
            time.sleep(3)

            # Check if processes are still running
            if self.camera_process.poll() is not None or self.stream_process.poll() is not None:
                error = "Stream processes failed to start"
                self.stop_video_stream()
                return None, error

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

        # Terminate camera process first
        if hasattr(self, 'camera_process') and self.camera_process:
            try:
                os.killpg(os.getpgid(self.camera_process.pid), signal.SIGTERM)
                self.camera_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.camera_process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                self.camera_process = None

        # Then terminate ffmpeg process
        if self.stream_process:
            try:
                os.killpg(os.getpgid(self.stream_process.pid), signal.SIGTERM)
                self.stream_process.wait(timeout=3)
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
        # Additional cleanup for camera process if it exists
        if hasattr(self, 'camera_process') and self.camera_process:
            try:
                os.killpg(os.getpgid(self.camera_process.pid), signal.SIGTERM)
                self.camera_process.wait(timeout=2)
            except:
                pass
            finally:
                self.camera_process = None

# Test the direct camera manager
if __name__ == "__main__":
    print("Testing direct Raspberry Pi camera manager...")
    cm = CameraManagerDirect()
    print("Camera status:", cm.get_status())

    if cm.available:
        print("✓ Camera is available!")
        print("Starting stream test...")
        _, error = cm.start_video_stream()
        if error:
            print(f"Stream start failed: {error}")
        else:
            print("Stream started successfully!")
            time.sleep(5)  # Let it run for 5 seconds
            cm.stop_video_stream()
            print("Stream stopped.")
    else:
        print(f"✗ Camera not available: {cm.error}")