#!/usr/bin/env python3
"""
New Camera Manager for Raspberry Pi

This module provides a unified camera management system that:
1. Auto-detects the best capture method for the Raspberry Pi model
2. Integrates with the MJPEG streaming server
3. Handles process management and cleanup properly
4. Provides a simple interface for the web application
"""

import subprocess
import platform
import os
import signal
import time
import threading
import logging
from typing import Optional, Tuple, Dict, Any

# Import the streaming server
from streaming_server import MJPEGStreamServer

# Try to import picamera2
try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FileOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False


class CameraManager:
    """
    Unified camera manager for Raspberry Pi.

    This class handles camera detection, frame capture, and streaming
    with automatic fallback between different capture methods.
    """

    def __init__(self):
        self.available = False
        self.error = None
        self.camera = None
        self.stream_server = None
        self.capture_thread = None
        self.capture_running = False
        self.stream_port = 8000
        self.current_method = None
        self.camera_process = None
        self.ffmpeg_process = None

        # Set up logging
        self.logger = logging.getLogger('CameraManager')
        self.logger.setLevel(logging.INFO)

        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # Detect camera and available methods
        self._detect_platform()
        self._detect_camera()

    def _detect_platform(self) -> None:
        """
        Detect if we're running on Raspberry Pi and determine the model.
        """
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().strip()
                if 'raspberry pi' in model.lower():
                    self.logger.info(f"Raspberry Pi detected: {model}")

                    # Determine model for target selection
                    if 'Raspberry Pi 5' in model or 'BCM2712' in model:
                        self.rpi_model = 'pi5'
                    elif 'Raspberry Pi 4' in model or 'BCM2711' in model:
                        self.rpi_model = 'pi4'
                    else:
                        self.rpi_model = 'older'

                else:
                    self.available = False
                    self.error = "Not running on Raspberry Pi"
                    self.logger.error("Not running on Raspberry Pi")
        except FileNotFoundError:
            self.available = False
            self.error = "Not running on Raspberry Pi (no device tree)"
            self.logger.error("Not running on Raspberry Pi (no device tree)")
        except Exception as e:
            self.available = False
            self.error = f"Platform detection failed: {e}"
            self.logger.error(f"Platform detection failed: {e}")

    def _detect_camera(self) -> None:
        """
        Detect available camera capture methods and determine the best one.
        """
        if not hasattr(self, 'rpi_model'):
            return

        self.available_methods = []

        # Test picamera2 availability
        if PICAMERA2_AVAILABLE:
            self.available_methods.append('picamera2')
            self.logger.info("picamera2 library available")
        else:
            self.logger.info("picamera2 library not available")

        # Test ffmpeg availability
        try:
            subprocess.run(['ffmpeg', '-version'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         check=True)
            self.available_methods.append('ffmpeg')
            self.logger.info("ffmpeg available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.info("ffmpeg not available")

        # Test libcamera tools availability
        for cmd in ['libcamera-vid', 'rpicam-vid']:
            try:
                subprocess.run([cmd, '--version'],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             timeout=5)
                self.available_methods.append(cmd)
                self.logger.info(f"{cmd} available")
                break
            except:
                continue

        # Determine best method based on availability and model
        self._select_best_method()

    def _select_best_method(self) -> None:
        """
        Select the best capture method based on available tools and Raspberry Pi model.
        """
        if not self.available_methods:
            self.available = False
            self.error = "No compatible camera capture methods available"
            self.logger.error("No compatible camera capture methods available")
            return

        # Prefer picamera2 for direct frame access
        if 'picamera2' in self.available_methods:
            self.current_method = 'picamera2'
            self.logger.info("Selected picamera2 as capture method")
        # Fall back to ffmpeg + libcamera
        elif 'ffmpeg' in self.available_methods and any(cmd in self.available_methods for cmd in ['libcamera-vid', 'rpicam-vid']):
            self.current_method = 'ffmpeg_libcamera'
            self.logger.info("Selected ffmpeg + libcamera as capture method")
        # Fall back to ffmpeg with v4l2
        elif 'ffmpeg' in self.available_methods:
            self.current_method = 'ffmpeg_v4l2'
            self.logger.info("Selected ffmpeg + v4l2 as capture method")
        else:
            self.available = False
            self.error = "No viable capture method found"
            self.logger.error("No viable capture method found")
            return

        # Test the selected method
        if self._test_capture_method():
            self.available = True
            self.error = None
            self.logger.info("Camera is available and ready")
        else:
            self.available = False
            self.error = f"Selected capture method {self.current_method} failed testing"
            self.logger.error(f"Selected capture method {self.current_method} failed testing")

    def _test_capture_method(self) -> bool:
        """
        Test the selected capture method to ensure it works.

        Returns:
            True if method works, False otherwise
        """
        try:
            if self.current_method == 'picamera2':
                return self._test_picamera2()
            elif self.current_method == 'ffmpeg_libcamera':
                return self._test_ffmpeg_libcamera()
            elif self.current_method == 'ffmpeg_v4l2':
                return self._test_ffmpeg_v4l2()
            return False
        except Exception as e:
            self.logger.error(f"Error testing capture method: {e}")
            return False

    def _test_picamera2(self) -> bool:
        """
        Test picamera2 capture method.

        Returns:
            True if picamera2 works, False otherwise
        """
        try:
            # Clean up any existing camera processes
            self._cleanup_camera_processes()

            # Try different targets based on Raspberry Pi model
            # For Raspberry Pi 5, we need to handle the target mismatch issue
            targets_to_try = []
            if self.rpi_model == 'pi5':
                # Raspberry Pi 5 has specific target requirements - try auto-detection first
                targets_to_try = [None, 'bcm2835', 'pisp']
            else:
                targets_to_try = [None, 'pisp', 'bcm2835']

            # Try each target with more robust error handling
            for target in targets_to_try:
                try:
                    # Clean up between attempts to prevent camera lockup
                    self._cleanup_camera_processes()
                    time.sleep(0.5)  # Give time for cleanup to complete

                    if target:
                        os.environ['LIBCAMERA_RPI_TARGET'] = target
                        self.logger.info(f"Trying picamera2 with {target} target")
                    else:
                        os.environ.pop('LIBCAMERA_RPI_TARGET', None)
                        self.logger.info("Trying picamera2 with auto-detected target")

                    # Create camera and test with simpler configuration
                    test_camera = Picamera2()

                    # Try preview configuration first (more likely to work)
                    try:
                        config = test_camera.create_preview_configuration()
                        test_camera.configure(config)
                        test_camera.start()
                        time.sleep(0.1)  # Let it run briefly
                        test_camera.stop()
                        test_camera.close()
                        self.logger.info(f"picamera2 test successful with {target or 'auto-detected'} target (preview config)")
                        return True
                    except Exception as preview_error:
                        self.logger.info(f"Preview configuration failed: {preview_error}")
                        # Clean up before trying next config
                        try:
                            test_camera.close()
                        except:
                            pass

                    # Fall back to video configuration
                    try:
                        config = test_camera.create_video_configuration()
                        test_camera.configure(config)
                        test_camera.start()
                        time.sleep(0.1)  # Let it run briefly
                        test_camera.stop()
                        test_camera.close()
                        self.logger.info(f"picamera2 test successful with {target or 'auto-detected'} target (video config)")
                        return True
                    except Exception as video_error:
                        self.logger.info(f"Video configuration failed: {video_error}")
                        # Clean up before continuing
                        try:
                            test_camera.close()
                        except:
                            pass
                        if target:
                            os.environ.pop('LIBCAMERA_RPI_TARGET', None)
                        continue

                except Exception as target_error:
                    self.logger.info(f"picamera2 {target or 'auto-detected'} target test failed: {target_error}")
                    if target:
                        os.environ.pop('LIBCAMERA_RPI_TARGET', None)
                    continue

            return False

        except Exception as e:
            self.logger.error(f"picamera2 test failed: {e}")
            return False

    def _test_ffmpeg_libcamera(self) -> bool:
        """
        Test ffmpeg + libcamera capture method.

        Returns:
            True if method works, False otherwise
        """
        try:
            # Find available libcamera command
            libcamera_cmd = None
            for cmd in ['rpicam-vid', 'libcamera-vid']:
                if cmd in self.available_methods:
                    libcamera_cmd = cmd
                    break

            if not libcamera_cmd:
                return False

            # Test with a short capture
            test_file = 'test.h264'
            cmd = f"{libcamera_cmd} -t 1000 --nopreview --codec h264 --width 640 --height 480 --framerate 30 -o {test_file}"

            result = subprocess.run(cmd, shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  timeout=5)

            # Clean up test file
            if os.path.exists(test_file):
                os.remove(test_file)

            if result.returncode == 0:
                self.logger.info(f"{libcamera_cmd} + ffmpeg test successful")
                return True
            else:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                self.logger.info(f"{libcamera_cmd} + ffmpeg test failed: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"ffmpeg + libcamera test failed: {e}")
            return False

    def _test_ffmpeg_v4l2(self) -> bool:
        """
        Test ffmpeg + v4l2 capture method.

        Returns:
            True if method works, False otherwise
        """
        try:
            # Check if /dev/video0 exists
            if not os.path.exists('/dev/video0'):
                self.logger.info("No /dev/video0 device found")
                return False

            # Test ffmpeg capture
            cmd = [
                'ffmpeg',
                '-f', 'v4l2',
                '-input_format', 'h264',
                '-video_size', '640x480',
                '-framerate', '15',
                '-i', '/dev/video0',
                '-frames', '1',
                '-f', 'null',
                '-'
            ]

            result = subprocess.run(cmd,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  timeout=5)

            if result.returncode == 0:
                self.logger.info("ffmpeg + v4l2 test successful")
                return True
            else:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                self.logger.info(f"ffmpeg + v4l2 test failed: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"ffmpeg + v4l2 test failed: {e}")
            return False

    def _cleanup_camera_processes(self) -> None:
        """
        Clean up any existing camera processes that might be holding the camera.
        """
        try:
            self.logger.info("Cleaning up existing camera processes...")

            # More aggressive cleanup for libcamera issues
            subprocess.run(['pkill', '-9', '-f', 'libcamera'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-9', '-f', 'rpicam'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-9', '-f', 'picamera2'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-9', '-f', 'ffmpeg'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Also try to reset the camera system
            try:
                subprocess.run(['sudo', 'systemctl', 'restart', 'libcamera'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

            time.sleep(1.0)  # Give more time for processes to terminate
            self.logger.info("Camera process cleanup completed")
        except Exception as e:
            self.logger.warning(f"Camera process cleanup warning: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the camera manager.

        Returns:
            Dictionary containing status information
        """
        status = {
            "available": self.available,
            "error": self.error,
            "method": self.current_method,
            "streaming": self.stream_server.is_running() if self.stream_server else False,
            "stream_url": self.stream_server.get_stream_url() if self.stream_server and self.stream_server.is_running() else None,
            "clients_connected": self.stream_server.get_client_count() if self.stream_server else 0
        }
        return status

    def start_video_stream(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Start video streaming.

        Returns:
            Tuple of (stream_url, error) where error is None if successful
        """
        if not self.available:
            return None, "Camera not available"

        if self.stream_server and self.stream_server.is_running():
            return self.stream_server.get_stream_url(), None

        try:
            # Initialize streaming server
            self.stream_server = MJPEGStreamServer(port=self.stream_port)

            # Start the streaming server
            if not self.stream_server.start():
                return None, "Failed to start streaming server"

            # Start frame capture based on selected method
            if self.current_method == 'picamera2':
                self.capture_running = True
                self.capture_thread = threading.Thread(
                    target=self._capture_frames_picamera2,
                    daemon=True
                )
                self.capture_thread.start()
            elif self.current_method == 'ffmpeg_libcamera':
                self.capture_running = True
                self.capture_thread = threading.Thread(
                    target=self._capture_frames_ffmpeg_libcamera,
                    daemon=True
                )
                self.capture_thread.start()
            elif self.current_method == 'ffmpeg_v4l2':
                self.capture_running = True
                self.capture_thread = threading.Thread(
                    target=self._capture_frames_ffmpeg_v4l2,
                    daemon=True
                )
                self.capture_thread.start()

            return self.stream_server.get_stream_url(), None

        except Exception as e:
            self.stop_video_stream()
            return None, f"Failed to start stream: {str(e)}"

    def stop_video_stream(self) -> None:
        """
        Stop video streaming and clean up resources.
        """
        self.capture_running = False

        # Stop capture thread
        if self.capture_thread:
            self.capture_thread.join(timeout=5)
            self.capture_thread = None

        # Stop streaming server
        if self.stream_server:
            self.stream_server.stop()
            self.stream_server = None

        # Clean up camera processes
        self._cleanup_camera_processes()

        # Clean up camera object
        if self.camera:
            try:
                if hasattr(self.camera, 'stop_recording'):
                    self.camera.stop_recording()
                if hasattr(self.camera, 'stop'):
                    self.camera.stop()
                if hasattr(self.camera, 'close'):
                    self.camera.close()
            except:
                pass
            finally:
                self.camera = None

        # Clean up subprocesses
        self._cleanup_subprocesses()

        self.logger.info("Camera stream stopped and resources cleaned up")

    def _cleanup_subprocesses(self) -> None:
        """
        Clean up any running subprocesses.
        """
        for proc_attr in ['camera_process', 'ffmpeg_process']:
            if hasattr(self, proc_attr) and getattr(self, proc_attr):
                proc = getattr(self, proc_attr)
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except:
                        pass
                except ProcessLookupError:
                    pass
                finally:
                    setattr(self, proc_attr, None)

    def _capture_frames_picamera2(self) -> None:
        """
        Capture frames using picamera2 and add them to the streaming server.
        """
        try:
            # Clean up any existing camera processes
            self._cleanup_camera_processes()

            # Initialize camera with appropriate target
            self._setup_picamera2()

            # Create encoder and output
            encoder = H264Encoder(bitrate=1000000)

            class FrameOutput(FileOutput):
                def __init__(self, camera_manager):
                    super().__init__()
                    self.camera_manager = camera_manager
                    self.frame_count = 0

                def output_frame(self, frame):
                    if self.camera_manager.capture_running and self.camera_manager.stream_server:
                        try:
                            # Convert frame to JPEG and add to server
                            self._process_frame(frame)
                        except Exception as e:
                            self.camera_manager.logger.error(f"Error processing frame: {e}")

                def _process_frame(self, frame):
                    # This would be implemented with proper frame conversion
                    # For now, we'll create a placeholder JPEG
                    pass

            output = FrameOutput(self)

            # Start recording
            self.camera.start_recording(encoder, output)

            # Frame capture loop
            while self.capture_running:
                try:
                    # Get frame from camera
                    frame = self.camera.capture_array()

                    # Convert to JPEG and add to stream
                    self._add_frame_to_stream(frame)

                    time.sleep(0.033)  # ~30 FPS

                except Exception as e:
                    if self.capture_running:
                        self.logger.error(f"Error capturing frame: {e}")
                    break

            # Stop recording
            self.camera.stop_recording()

        except Exception as e:
            self.logger.error(f"picamera2 capture failed: {e}")
        finally:
            self._cleanup_camera()

    def _setup_picamera2(self) -> bool:
        """
        Set up picamera2 with appropriate configuration.

        Returns:
            True if setup successful, False otherwise
        """
        try:
            # Try different targets based on Raspberry Pi model
            targets_to_try = []
            if self.rpi_model == 'pi5':
                targets_to_try = [None, 'bcm2835', 'pisp']
            else:
                targets_to_try = [None, 'pisp', 'bcm2835']

            for target in targets_to_try:
                try:
                    # Clean up between attempts to prevent camera lockup
                    self._cleanup_camera_processes()
                    time.sleep(0.5)  # Give time for cleanup to complete

                    if target:
                        os.environ['LIBCAMERA_RPI_TARGET'] = target
                        self.logger.info(f"Trying picamera2 with {target} target")
                    else:
                        os.environ.pop('LIBCAMERA_RPI_TARGET', None)
                        self.logger.info("Trying picamera2 with auto-detected target")

                    self.camera = Picamera2()

                    # Try preview configuration first (more likely to work)
                    try:
                        config = self.camera.create_preview_configuration(
                            main={"format": 'XRGB8888', "size": (640, 480)},
                            controls={"FrameRate": 30.0}
                        )
                        self.camera.configure(config)
                        self.camera.start()
                        self.logger.info(f"picamera2 setup successful with {target or 'auto-detected'} target (preview config)")
                        return True
                    except Exception as preview_error:
                        self.logger.info(f"Preview configuration failed: {preview_error}")
                        # Clean up the camera object before trying next config
                        try:
                            if hasattr(self.camera, 'close'):
                                self.camera.close()
                        except:
                            pass
                        self.camera = None

                    # Fall back to video configuration
                    try:
                        if not self.camera:
                            self.camera = Picamera2()
                        config = self.camera.create_video_configuration(
                            main={"format": 'XRGB8888', "size": (640, 480)},
                            controls={"FrameRate": 30.0}
                        )
                        self.camera.configure(config)
                        self.camera.start()
                        self.logger.info(f"picamera2 setup successful with {target or 'auto-detected'} target (video config)")
                        return True
                    except Exception as video_error:
                        self.logger.info(f"Video configuration failed: {video_error}")
                        # Clean up before continuing
                        try:
                            if self.camera and hasattr(self.camera, 'close'):
                                self.camera.close()
                        except:
                            pass
                        self.camera = None
                        if target:
                            os.environ.pop('LIBCAMERA_RPI_TARGET', None)
                        continue

                except Exception as target_error:
                    self.logger.info(f"picamera2 setup failed with target {target or 'auto-detected'}: {target_error}")
                    if target:
                        os.environ.pop('LIBCAMERA_RPI_TARGET', None)
                    continue

            return False

        except Exception as e:
            self.logger.error(f"picamera2 setup failed: {e}")
            return False

    def _add_frame_to_stream(self, frame) -> bool:
        """
        Add a frame to the streaming server.

        Args:
            frame: Numpy array containing the frame

        Returns:
            True if frame was added successfully, False otherwise
        """
        try:
            if not self.stream_server or not self.capture_running:
                return False

            # Convert frame to JPEG
            # Note: In production, we'd use cv2.imencode or similar
            # For now, we'll create a placeholder JPEG

            # Placeholder: create a simple JPEG frame
            # In real implementation, this would be proper frame encoding
            jpeg_data = self._create_placeholder_jpeg(frame.shape[1], frame.shape[0])

            return self.stream_server.add_frame(jpeg_data)

        except Exception as e:
            self.logger.error(f"Error adding frame to stream: {e}")
            return False

    def _create_placeholder_jpeg(self, width: int, height: int) -> bytes:
        """
        Create a placeholder JPEG frame for testing.

        Args:
            width: Frame width
            height: Frame height

        Returns:
            JPEG-encoded frame data
        """
        # This is a placeholder - in production we'd use proper JPEG encoding
        # For now, return a minimal JPEG file header
        return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'

    def _capture_frames_ffmpeg_libcamera(self) -> None:
        """
        Capture frames using ffmpeg + libcamera and add them to the streaming server.
        """
        try:
            # Find available libcamera command
            libcamera_cmd = None
            for cmd in ['rpicam-vid', 'libcamera-vid']:
                try:
                    subprocess.run([cmd, '--version'],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 timeout=5)
                    libcamera_cmd = cmd
                    break
                except:
                    continue

            if not libcamera_cmd:
                self.logger.error("No libcamera command available")
                return

            # Set up ffmpeg command
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', 'pipe:',
                '-f', 'image2pipe',
                '-vcodec', 'mjpeg',
                '-q:v', '5',
                '-'
            ]

            # Set up libcamera command
            libcamera_cmd_str = (
                f"{libcamera_cmd} -t 0 --width 640 --height 480 "
                f"--framerate 30 --nopreview --codec h264 -o -"
            )

            # Start ffmpeg process
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            # Start libcamera process
            self.camera_process = subprocess.Popen(
                libcamera_cmd_str,
                shell=True,
                stdout=self.ffmpeg_process.stdin,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            # Read frames from ffmpeg output and add to stream
            while self.capture_running:
                try:
                    # Read JPEG frame from ffmpeg output
                    frame_data = self._read_jpeg_frame(self.ffmpeg_process.stdout)

                    if frame_data and self.stream_server:
                        self.stream_server.add_frame(frame_data)

                except Exception as e:
                    if self.capture_running:
                        self.logger.error(f"Error reading frame: {e}")
                    break

        except Exception as e:
            self.logger.error(f"ffmpeg + libcamera capture failed: {e}")
        finally:
            self._cleanup_subprocesses()

    def _read_jpeg_frame(self, stream) -> Optional[bytes]:
        """
        Read a JPEG frame from a stream.

        Args:
            stream: Input stream to read from

        Returns:
            JPEG frame data or None if error
        """
        try:
            # Read until we find JPEG start marker
            header = stream.read(2)
            while header != b'\xff\xd8' and len(header) > 0:
                header = header[1:] + stream.read(1)

            if len(header) == 0:
                return None

            # Read until JPEG end marker
            frame_data = header
            while True:
                chunk = stream.read(1024)
                if not chunk:
                    return None
                frame_data += chunk
                if frame_data[-2:] == b'\xff\xd9':
                    break

            return frame_data

        except Exception as e:
            self.logger.error(f"Error reading JPEG frame: {e}")
            return None

    def _capture_frames_ffmpeg_v4l2(self) -> None:
        """
        Capture frames using ffmpeg + v4l2 and add them to the streaming server.
        """
        try:
            if not os.path.exists('/dev/video0'):
                self.logger.error("/dev/video0 not found")
                return

            # Set up ffmpeg command
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'v4l2',
                '-input_format', 'h264',
                '-video_size', '640x480',
                '-framerate', '15',
                '-i', '/dev/video0',
                '-f', 'image2pipe',
                '-vcodec', 'mjpeg',
                '-q:v', '5',
                '-'
            ]

            # Start ffmpeg process
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            # Read frames from ffmpeg output and add to stream
            while self.capture_running:
                try:
                    # Read JPEG frame from ffmpeg output
                    frame_data = self._read_jpeg_frame(self.ffmpeg_process.stdout)

                    if frame_data and self.stream_server:
                        self.stream_server.add_frame(frame_data)

                except Exception as e:
                    if self.capture_running:
                        self.logger.error(f"Error reading frame: {e}")
                    break

        except Exception as e:
            self.logger.error(f"ffmpeg + v4l2 capture failed: {e}")
        finally:
            self._cleanup_subprocesses()

    def _cleanup_camera(self) -> None:
        """
        Clean up camera resources.
        """
        if self.camera:
            try:
                if hasattr(self.camera, 'stop_recording'):
                    self.camera.stop_recording()
                if hasattr(self.camera, 'stop'):
                    self.camera.stop()
                if hasattr(self.camera, 'close'):
                    self.camera.close()
            except:
                pass
            finally:
                self.camera = None

    def __del__(self):
        """
        Cleanup on object destruction.
        """
        self.stop_video_stream()


# Test the new camera manager
if __name__ == "__main__":
    print("Testing new Camera Manager...")
    cm = CameraManager()
    print("Camera status:", cm.get_status())

    if cm.available:
        print("✓ Camera is available!")
        print(f"Using method: {cm.current_method}")

        print("Starting stream...")
        stream_url, error = cm.start_video_stream()

        if error:
            print(f"✗ Stream start failed: {error}")
        else:
            print(f"✓ Stream started successfully!")
            print(f"Stream URL: {stream_url}")
            print("Press Ctrl+C to stop...")

            try:
                while True:
                    time.sleep(1)
                    status = cm.get_status()
                    print(f"Status: {status['clients_connected']} clients connected")
            except KeyboardInterrupt:
                print("\nStopping stream...")
                cm.stop_video_stream()
                print("Stream stopped.")
    else:
        print(f"✗ Camera not available: {cm.error}")