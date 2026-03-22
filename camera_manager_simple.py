#!/usr/bin/env python3
"""
Simple camera manager using only picamera2 library.
No ffmpeg dependency, direct UDP streaming.
"""

import subprocess
import platform
import io
import threading
import time
import os
import signal
import socket
import numpy as np

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FileOutput
    PICAMERA2_AVAILABLE = True
    print("Using picamera2 library")
except ImportError as e:
    PICAMERA2_AVAILABLE = False
    print(f"picamera2 library not available: {e}")

class CameraManagerSimple:
    def __init__(self):
        self.available = False
        self.error = None
        self.camera = None
        self.stream_socket = None
        self.stream_thread = None
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

            # Check if picamera2 is available
            if not PICAMERA2_AVAILABLE:
                self.available = False
                self.error = "picamera2 library not available"
                print("picamera2 library not available")
                return

            # Try to initialize camera with proper target handling
            self._try_camera_initialization()

        except Exception as e:
            self.available = False
            self.error = f"Platform detection failed: {str(e)}"
            print(f"Platform detection failed: {e}")

    def _try_camera_initialization(self):
        """Try different approaches to initialize the camera"""
        import os

        # Try without setting any target first
        try:
            print("Trying camera initialization with default settings...")
            # Clear any existing target environment variable
            os.environ.pop('LIBCAMERA_RPI_TARGET', None)

            test_camera = Picamera2()
            config = test_camera.create_video_configuration()
            test_camera.configure(config)
            test_camera.start()
            test_camera.stop()
            test_camera.close()

            self.available = True
            self.error = None
            print("Camera detected and enabled with default configuration")
            return

        except Exception as e:
            print(f"Default configuration failed: {e}")

            # Try specific targets
            targets_to_try = ['pisp', 'bcm2835']

            for target in targets_to_try:
                try:
                    print(f"Trying camera initialization with {target} target...")
                    os.environ['LIBCAMERA_RPI_TARGET'] = target

                    test_camera = Picamera2()
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
                    continue

            # If we get here, all methods failed
            self.available = False
            self.error = "Camera initialization failed with all methods"
            print("Camera initialization failed with all methods")

    def get_status(self):
        return {
            "available": self.available,
            "error": self.error,
            "streaming": self.streaming,
            "stream_url": f"http://localhost:{self.stream_port}/stream.mjpg" if self.streaming else None
        }

    def start_video_stream(self):
        """Start video streaming using picamera2 UDP output"""
        if not self.available:
            return None, "Camera not available"

        if self.streaming:
            return None, "Camera already streaming"

        try:
            # Create UDP socket for streaming
            self.stream_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Initialize camera
            self.camera = Picamera2()
            config = self.camera.create_video_configuration()
            self.camera.configure(config)

            # Create H264 encoder with UDP output
            encoder = H264Encoder(bitrate=1000000)

            # Custom output that sends to UDP
            class UDPOutput(FileOutput):
                def __init__(self, sock, addr):
                    super().__init__()
                    self.sock = sock
                    self.addr = addr

                def output_frame(self, frame):
                    # Send each frame via UDP
                    self.sock.sendto(frame, self.addr)

            output = UDPOutput(self.stream_socket, ('localhost', self.stream_port))

            # Start recording to UDP
            self.camera.start_recording(encoder, output)

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

        try:
            if self.camera:
                self.camera.stop_recording()
                self.camera.close()
                self.camera = None
        except:
            pass

        try:
            if self.stream_socket:
                self.stream_socket.close()
                self.stream_socket = None
        except:
            pass

        print("Camera stream stopped")

    def __del__(self):
        """Cleanup on object destruction"""
        self.stop_video_stream()

# Test the simple camera manager
if __name__ == "__main__":
    print("Testing simple picamera2 manager...")
    cm = CameraManagerSimple()
    print("Camera status:", cm.get_status())

    if cm.available:
        print("✓ Camera is available!")
        print("Starting stream test...")
        _, error = cm.start_video_stream()
        if error:
            print(f"Stream start failed: {error}")
        else:
            print("Stream started successfully!")
            print("Press Ctrl+C to stop...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                cm.stop_video_stream()
                print("Stream stopped.")
    else:
        print(f"✗ Camera not available: {cm.error}")