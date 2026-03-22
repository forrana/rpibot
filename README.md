# Device Controller Web Interface

A web-based control panel for device management with serial communication and optional Raspberry Pi camera support.

## Features

- **Web-based Control Panel**: Control your device through a browser interface
- **Serial Communication**: Send commands to devices via `/dev/ttyUSB0` at 9600 baud
- **Arrow Controls**: W/S/A/D commands for movement control
- **Power Control**: ON/OFF toggle functionality
- **Keyboard Shortcuts**: Use W, A, S, D, X keys for quick control
- **Raspberry Pi Camera Support**: Automatic detection and video streaming (when running on RPI)
- **Connection Management**: Automatic reconnection and error handling
- **Responsive Design**: Works on desktop and mobile devices

## Commands

| Button | Command | Keyboard | Description |
|--------|---------|----------|-------------|
| ↑ | W | W | Move Up |
| ↓ | S | S | Move Down |
| ← | A | A | Move Left |
| → | D | D | Move Right |
| STOP | X | X | Emergency Stop |
| ON/OFF | 1/0 | - | Power Toggle |

## Requirements

### Python Dependencies
```bash
fastapi==0.115.0
uvicorn==0.32.0
pyserial==3.5
jinja2==3.1.4
```

### Raspberry Pi Camera (Optional)
- Raspberry Pi with camera module
- Camera enabled in `raspi-config`
- Either `libcamera-vid` (RPi OS Bullseye+) or `raspivid` (older versions)

## Installation

```bash
cd web_server
pip install -r requirements.txt
```

## Running the Application

```bash
python3 app.py
```

Then open your browser to: `http://localhost:5000`

## Configuration

### Serial Port
- Default: `/dev/ttyUSB0`
- Baud rate: 9600
- To change, modify `serial_manager.py`

### Camera
- Automatically detected on Raspberry Pi
- Stream resolution: 640x480 @ 30fps
- Uses H.264 encoding
- **Troubleshooting**: If you get "Unexpected target reported" errors, the application will automatically try different configuration approaches and target settings. For Raspberry Pi OS, you can also try:
  ```bash
  # Update your system
  sudo apt update && sudo apt upgrade
  
  # Enable camera interface
  sudo raspi-config
  # Then go to Interface Options -> Camera -> Enable
  
  # Test camera directly (use rpicam-hello on Bookworm, libcamera-hello on older versions)
  rpicam-hello --timeout 5000 || libcamera-hello --timeout 5000
  
  # If you still have issues, try setting the target explicitly
  export LIBCAMERA_RPI_TARGET=bcm2835  # or pisp
  ```

  **For Raspberry Pi 5 users**: The application automatically detects Raspberry Pi 5 and tries the appropriate target first. If you encounter issues:
  1. Ensure your system is up to date: `sudo apt update && sudo apt upgrade`
  2. Check camera detection: `vcgencmd get_camera`
  3. Test with: `libcamera-hello --timeout 5000`
  4. Try running with debug: `LIBCAMERA_LOG_LEVELS=*:DEBUG python3 app.py`

## Project Structure

```
web_server/
├── app.py                  # Main FastAPI application
├── camera_manager.py       # Camera detection and streaming
├── serial_manager.py       # Serial communication handling
├── version.py              # Version information and history
├── static/                 # CSS and JavaScript files
│   ├── style.css           # Styling
│   └── script.js           # Frontend logic
├── templates/              # HTML templates
│   └── index.html          # Main interface
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── LICENSE.md              # License information
```

## Version Information

The project includes version tracking in `version.py`:

- Current version: `1.0.0`
- Version history with release notes
- Build information tracking
- API for accessing version data

You can access version information via:
- `/version` API endpoint
- Version displayed in the web interface header

## Keyboard Controls

- **W**: Move Up
- **A**: Move Left
- **S**: Move Down
- **D**: Move Right
- **X**: Emergency Stop

*Note: Keyboard controls only work when the page is focused*

## Error Handling

The application handles various error conditions:
- Serial port not available
- Device disconnection during operation
- Camera not detected (on RPI)
- Connection timeouts
- I/O errors

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile browsers (iOS Safari, Android Chrome)
- Requires JavaScript enabled

## Development

To modify the frontend:
- Edit files in `static/` for CSS/JS
- Edit files in `templates/` for HTML
- Restart the server to see changes

## License

MIT License - See [LICENSE.md](LICENSE.md) for details

## Support

For issues or questions, please open a GitHub issue.

---

*Built with FastAPI and pure JavaScript/CSS (no frontend frameworks)*