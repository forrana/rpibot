from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from fastapi.websockets import WebSocket
from fastapi.middleware.cors import CORSMiddleware
from camera_manager import CameraManager
from serial_manager import SerialManager
from version import get_version, get_full_version

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Initialize managers
serial_manager = SerialManager()

# Try the simple picamera2 manager first (no ffmpeg dependency)
try:
    from camera_manager_simple import CameraManagerSimple
    camera_manager = CameraManagerSimple()
    print("Using simple picamera2 camera manager")

    # If simple manager fails, fall back to direct manager
    if not camera_manager.available:
        print("Simple camera manager failed, trying direct manager...")
        try:
            from camera_manager_rpi_direct import CameraManagerDirect
            camera_manager = CameraManagerDirect()
            print("Using direct Raspberry Pi camera manager")
        except ImportError:
            print("Direct camera manager not available, trying regular manager...")
            from camera_manager import CameraManager
            camera_manager = CameraManager()

except ImportError:
    print("Simple camera manager not available, trying direct manager...")
    try:
        from camera_manager_rpi_direct import CameraManagerDirect
        camera_manager = CameraManagerDirect()
        print("Using direct Raspberry Pi camera manager")
    except ImportError:
        print("Direct camera manager not available, using regular manager")
        from camera_manager import CameraManager
        camera_manager = CameraManager()

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": get_version(),
        "full_version": get_full_version()
    })

@app.get('/version')
async def version_info():
    """Return version information"""
    return JSONResponse(get_full_version())

@app.get('/connection_status')
async def get_connection_status():
    return JSONResponse(serial_manager.get_status())

@app.post('/retry_connection')
async def retry_connection():
    serial_manager.reconnect()
    return JSONResponse(serial_manager.get_status())

@app.post('/send_command')
async def send_command(request: Request):
    data = await request.json()
    command = data.get('command')

    if not command:
        return JSONResponse({'status': 'error', 'message': 'No command provided'}, status_code=400)

    success, message = serial_manager.send_command(command)

    if success:
        return JSONResponse({'status': 'success', 'command': command})
    else:
        # Check if connection was lost
        if "connection_lost" in message.lower() or not serial_manager.connected:
            return JSONResponse({'status': 'error', 'message': message, 'error_type': 'connection_lost'}, status_code=500)
        else:
            return JSONResponse({'status': 'error', 'message': message}, status_code=500)

@app.get('/camera_status')
async def get_camera_status():
    return JSONResponse(camera_manager.get_status())

@app.get('/video_feed')
async def video_feed():
    """Get video stream URL"""
    if not camera_manager.available:
        return JSONResponse({"error": "Camera not available"}, status_code=404)

    # Start the stream
    _, error = camera_manager.start_video_stream()

    if error:
        return JSONResponse({"error": error}, status_code=500)

    # Return the stream URL
    status = camera_manager.get_status()
    return JSONResponse({
        "status": "success",
        "stream_url": status["stream_url"]
    })

@app.post('/stop_video')
async def stop_video():
    """Stop the video stream"""
    camera_manager.stop_video_stream()
    return JSONResponse({"status": "success", "message": "Video stream stopped"})

if __name__ == '__main__':
    serial_manager.connect()
    uvicorn.run(app, host='0.0.0.0', port=5000)