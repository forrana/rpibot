#!/usr/bin/env python3
"""
MJPEG Streaming Server for Raspberry Pi Camera

This module provides a simple HTTP server that streams MJPEG video
compatible with web browsers. The server uses multipart/x-mixed-replace
content type for MJPEG streaming.
"""

import threading
import socketserver
from http import server
from io import BytesIO
import time
import queue
import logging
from typing import Optional, Tuple
from queue import Queue


class MJPEGStreamServer:
    """
    MJPEG streaming server that serves camera frames over HTTP.

    This server implements the MJPEG (Motion JPEG) streaming protocol
    using multipart/x-mixed-replace content type, which is widely
    supported by web browsers.
    """

    def __init__(self, port: int = 8000, max_clients: int = 5):
        """
        Initialize the MJPEG streaming server.

        Args:
            port: Port to listen on (default: 8000)
            max_clients: Maximum number of concurrent clients (default: 5)
        """
        self.port = port
        self.max_clients = max_clients
        self.frame_queue = Queue(maxsize=10)  # Queue for frames
        self.server_thread = None
        self.httpd = None
        self.running = False
        self.clients_connected = 0

        # Set up logging
        self.logger = logging.getLogger('MJPEGStreamServer')
        self.logger.setLevel(logging.INFO)

        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def add_frame(self, frame_data: bytes) -> bool:
        """
        Add a frame to the streaming queue.

        Args:
            frame_data: JPEG-encoded frame data

        Returns:
            True if frame was added successfully, False if queue is full
        """
        try:
            if self.frame_queue.qsize() < self.frame_queue.maxsize:
                self.frame_queue.put_nowait(frame_data)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error adding frame to queue: {e}")
            return False

    def start(self) -> bool:
        """
        Start the MJPEG streaming server.

        Returns:
            True if server started successfully, False otherwise
        """
        if self.running:
            self.logger.warning("Server is already running")
            return False

        try:
            # Create and configure the HTTP server
            self.httpd = socketserver.TCPServer(("", self.port), MJPEGRequestHandler)
            self.httpd.allow_reuse_address = True
            self.httpd.request_queue_size = self.max_clients

            # Set the frame queue in the request handler
            MJPEGRequestHandler.frame_queue = self.frame_queue
            MJPEGRequestHandler.server_instance = self

            # Start server in a separate thread
            self.server_thread = threading.Thread(
                target=self.httpd.serve_forever,
                daemon=True
            )
            self.server_thread.start()

            self.running = True
            self.logger.info(f"MJPEG server started on port {self.port}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start MJPEG server: {e}")
            self.running = False
            return False

    def stop(self) -> None:
        """
        Stop the MJPEG streaming server.
        """
        if not self.running:
            return

        try:
            self.running = False
            if self.httpd:
                self.httpd.shutdown()
                self.httpd.server_close()

            if self.server_thread:
                self.server_thread.join(timeout=5)
                if self.server_thread.is_alive():
                    self.logger.warning("Server thread did not terminate cleanly")

            # Clear the frame queue
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                except:
                    break

            self.logger.info("MJPEG server stopped")

        except Exception as e:
            self.logger.error(f"Error stopping MJPEG server: {e}")

    def is_running(self) -> bool:
        """
        Check if the server is running.

        Returns:
            True if server is running, False otherwise
        """
        return self.running

    def get_stream_url(self) -> str:
        """
        Get the URL for the MJPEG stream.

        Returns:
            URL string for the MJPEG stream
        """
        return f"http://localhost:{self.port}/stream.mjpg"

    def get_client_count(self) -> int:
        """
        Get the number of currently connected clients.

        Returns:
            Number of connected clients
        """
        return self.clients_connected


class MJPEGRequestHandler(server.BaseHTTPRequestHandler):
    """
    HTTP request handler for MJPEG streaming.

    This handler serves MJPEG streams to connected clients.
    """

    # Class variables to share state between instances
    frame_queue = None
    server_instance = None

    def do_GET(self) -> None:
        """
        Handle GET requests for MJPEG streaming.
        """
        if self.path == '/stream.mjpg':
            self._handle_stream_request()
        elif self.path == '/status':
            self._handle_status_request()
        else:
            self._handle_404()

    def _handle_stream_request(self) -> None:
        """
        Handle MJPEG stream requests.
        """
        try:
            # Update client count
            if self.server_instance:
                self.server_instance.clients_connected += 1

            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()

            self.logger.info(f"New client connected from {self.client_address[0]}")

            # Stream frames to the client
            last_frame_time = time.time()
            while self.server_instance and self.server_instance.running:
                try:
                    # Get frame from queue with timeout
                    frame_data = self.frame_queue.get(timeout=1.0)

                    # Send frame with MJPEG boundary
                    self._send_frame(frame_data)

                    # Update last frame time
                    last_frame_time = time.time()

                except Exception as e:
                    if isinstance(e, queue.Empty):
                        # No frame available, check if we should continue
                        if time.time() - last_frame_time > 5.0:
                            # No frames for 5 seconds, client might have disconnected
                            break
                        continue
                    else:
                        # Other exception, log and break
                        self.logger.error(f"Error in frame loop: {e}")
                        break

                except (ConnectionResetError, BrokenPipeError):
                    # Client disconnected
                    break

            self.logger.info(f"Client disconnected from {self.client_address[0]}")

        except Exception as e:
            self.logger.error(f"Error in stream handler: {e}")
        finally:
            # Update client count
            if self.server_instance:
                self.server_instance.clients_connected -= 1

    def _send_frame(self, frame_data: bytes) -> None:
        """
        Send a single frame to the client with MJPEG boundaries.

        Args:
            frame_data: JPEG-encoded frame data to send
        """
        try:
            # Send boundary header
            self.wfile.write(b'--FRAME\r\n')
            self.wfile.write(b'Content-Type: image/jpeg\r\n')
            self.wfile.write(f'Content-Length: {len(frame_data)}\r\n'.encode())
            self.wfile.write(b'\r\n')

            # Send frame data
            self.wfile.write(frame_data)
            self.wfile.write(b'\r\n')

            # Flush to ensure immediate delivery
            self.wfile.flush()

        except (ConnectionResetError, BrokenPipeError):
            # Client disconnected during frame send
            raise
        except Exception as e:
            self.logger.error(f"Error sending frame: {e}")

    def _handle_status_request(self) -> None:
        """
        Handle status requests.
        """
        try:
            status_data = {
                'status': 'running' if self.server_instance.running else 'stopped',
                'port': self.server_instance.port if self.server_instance else None,
                'clients_connected': self.server_instance.clients_connected if self.server_instance else 0,
                'queue_size': self.frame_queue.qsize() if self.frame_queue else 0
            }

            response = f"Status: {status_data['status']}\n"
            response += f"Port: {status_data['port']}\n"
            response += f"Clients: {status_data['clients_connected']}\n"
            response += f"Queue: {status_data['queue_size']}\n"

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response.encode())

        except Exception as e:
            self.logger.error(f"Error handling status request: {e}")
            self.send_error(500, f"Internal server error: {e}")

    def _handle_404(self) -> None:
        """
        Handle 404 Not Found requests.
        """
        self.send_error(404, "Not Found")

    def log_message(self, format: str, *args) -> None:
        """
        Override default logging to use our logger.
        """
        if self.server_instance and self.server_instance.logger:
            self.server_instance.logger.info(format % args)
        else:
            # Fallback to default behavior if logger not available
            super().log_message(format, *args)


# Test the streaming server
if __name__ == "__main__":
    import cv2
    import numpy as np

    print("Testing MJPEG Streaming Server...")

    # Create and start the server
    server = MJPEGStreamServer(port=8000)
    if not server.start():
        print("Failed to start server")
        exit(1)

    print(f"Server started. Stream URL: {server.get_stream_url()}")
    print("Press Ctrl+C to stop...")

    # Simulate frame capture (replace with real camera in production)
    try:
        frame_count = 0
        while server.is_running():
            # Create a test frame (blue gradient)
            height, width = 480, 640
            frame = np.zeros((height, width, 3), dtype=np.uint8)

            # Create a simple animation
            blue_value = int(255 * (0.5 + 0.5 * np.sin(frame_count * 0.1)))
            frame[:, :, 0] = blue_value  # Blue channel
            frame[:, :, 1] = 64  # Green channel

            # Add some text
            cv2.putText(frame, f"Test Frame {frame_count}", (50, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Encode as JPEG
            _, jpeg_data = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

            # Add to server
            if not server.add_frame(jpeg_data.tobytes()):
                print("Warning: Frame queue full, frame dropped")

            frame_count += 1
            time.sleep(0.033)  # ~30 FPS

    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop()
        print("Server stopped.")