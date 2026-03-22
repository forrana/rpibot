document.addEventListener('DOMContentLoaded', function() {
    const buttons = document.querySelectorAll('button[data-command]');
    const powerBtn = document.getElementById('powerBtn');
    const statusText = document.getElementById('statusText');
    const statusElement = document.querySelector('.status');
    const connectionControl = document.getElementById('connectionControl');
    const retryBtn = document.getElementById('retryBtn');
    const cameraSection = document.getElementById('cameraSection');
    const cameraStatus = document.getElementById('cameraStatus');
    const videoContainer = document.getElementById('videoContainer');
    const videoFeed = document.getElementById('videoFeed');
    const startCameraBtn = document.getElementById('startCameraBtn');
    const cameraError = document.getElementById('cameraError');
    let isPowerOn = false;
    let isConnected = false;
    let isCameraAvailable = false;
    let videoStream = null;

    // Initialize power button to OFF state
    powerBtn.textContent = 'OFF';
    powerBtn.classList.add('off');

    // Check connection status
    checkConnectionStatus();

    // Check camera status
    checkCameraStatus();

    // Start camera button
    startCameraBtn.addEventListener('click', startVideoStream);

    // Add click event listeners to all buttons
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            if (!isConnected) {
                statusText.textContent = 'Not connected to device';
                statusElement.classList.add('disconnected');
                statusElement.classList.remove('connected');
                return;
            }
            const command = this.getAttribute('data-command');
            sendCommand(command);
        });
    });

    // Power button toggle
    powerBtn.addEventListener('click', function() {
        if (!isConnected) {
            statusText.textContent = 'Not connected to device';
            statusElement.classList.add('disconnected');
            statusElement.classList.remove('connected');
            return;
        }
        if (isPowerOn) {
            sendCommand('0');
            this.textContent = 'OFF';
            this.classList.add('off');
        } else {
            sendCommand('1');
            this.textContent = 'ON';
            this.classList.remove('off');
        }
        isPowerOn = !isPowerOn;
    });

    // Retry connection button
    retryBtn.addEventListener('click', function() {
        retryConnection();
    });

    // Keyboard event listener
    document.addEventListener('keydown', function(event) {
        // Only handle key presses when focused on the document body
        if (event.target.tagName !== 'BODY') return;

        const key = event.key.toUpperCase();
        let command = null;

        // Map keys to commands
        switch(key) {
            case 'W': command = 'W'; break;
            case 'A': command = 'A'; break;
            case 'S': command = 'S'; break;
            case 'D': command = 'D'; break;
            case 'X': command = 'X'; break;
        }

        if (command) {
            event.preventDefault();
            if (isConnected) {
                sendCommand(command);

                // Visual feedback - highlight the corresponding button
                const button = document.querySelector(`button[data-command="${command}"]`);
                if (button) {
                    button.style.transform = 'scale(0.95)';
                    button.style.boxShadow = '0 0 10px rgba(255, 255, 255, 0.7)';

                    setTimeout(() => {
                        button.style.transform = '';
                        button.style.boxShadow = '';
                    }, 200);
                }
            } else {
                statusText.textContent = 'Not connected to device';
                statusElement.classList.add('disconnected');
                statusElement.classList.remove('connected');
            }
        }
    });

    // Check connection status
    function checkConnectionStatus() {
        fetch('/connection_status')
        .then(response => response.json())
        .then(data => {
            isConnected = data.connected;
            updateConnectionStatus(data);
        })
        .catch(error => {
            console.error('Error checking connection:', error);
            statusText.textContent = 'Error checking connection';
            statusElement.classList.add('disconnected');
            connectionControl.style.display = 'block';
        });
    }

    // Retry connection
    function retryConnection() {
        statusText.textContent = 'Connecting...';
        statusElement.classList.remove('connected', 'disconnected');

        fetch('/retry_connection', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            isConnected = data.connected;
            updateConnectionStatus(data);
        })
        .catch(error => {
            console.error('Error retrying connection:', error);
            statusText.textContent = 'Connection failed';
            statusElement.classList.add('disconnected');
            connectionControl.style.display = 'block';
        });
    }

    // Update connection status UI
    function updateConnectionStatus(data) {
        if (data.connected) {
            statusText.textContent = 'Connected to device';
            statusElement.classList.add('connected');
            statusElement.classList.remove('disconnected');
            connectionControl.style.display = 'none';
        } else {
            statusText.textContent = data.error || 'Connection failed';
            statusElement.classList.add('disconnected');
            statusElement.classList.remove('connected');
            connectionControl.style.display = 'block';
        }
    }

    // Check camera status
    function checkCameraStatus() {
        fetch('/camera_status')
        .then(response => response.json())
        .then(data => {
            isCameraAvailable = data.available;
            updateCameraStatus(data);
        })
        .catch(error => {
            console.error('Error checking camera:', error);
            cameraStatus.textContent = 'Error checking camera';
            cameraStatus.classList.add('unavailable');
        });
    }

    // Periodically check camera status
    setInterval(checkCameraStatus, 5000);

    // Update camera status UI
    function updateCameraStatus(data) {
        cameraSection.style.display = 'block';

        if (data.available) {
            cameraStatus.textContent = 'Camera available';
            cameraStatus.classList.add('available');
            cameraStatus.classList.remove('unavailable');
            startCameraBtn.style.display = 'block';
            stopCameraBtn.style.display = 'none';
            cameraError.style.display = 'none';
        } else {
            cameraStatus.textContent = 'Camera not available';
            cameraStatus.classList.add('unavailable');
            cameraStatus.classList.remove('available');
            startCameraBtn.style.display = 'none';
            stopCameraBtn.style.display = 'none';

            if (data.error) {
                cameraError.textContent = `Error: ${data.error}`;
                cameraError.style.display = 'block';
            }
        }

        // Update streaming status
        if (data.streaming) {
            startCameraBtn.style.display = 'none';
            stopCameraBtn.style.display = 'inline-block';
        }
    }

    // Start video stream
    function startVideoStream() {
        if (!isCameraAvailable) {
            cameraError.textContent = 'Camera not available';
            cameraError.style.display = 'block';
            return;
        }

        cameraStatus.textContent = 'Starting camera...';
        cameraStatus.classList.remove('available', 'unavailable');

        fetch('/video_feed')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Set up video feed with ffmpeg stream
                videoContainer.style.display = 'block';
                videoFeed.src = data.stream_url;
                videoFeed.autoplay = true;
                videoFeed.controls = false;
                videoFeed.load();

                cameraStatus.textContent = 'Camera streaming';
                cameraStatus.classList.add('available');
                cameraStatus.classList.remove('unavailable');
            } else {
                throw new Error(data.error || 'Failed to start stream');
            }
        })
        .catch(error => {
            console.error('Error starting video stream:', error);
            cameraStatus.textContent = 'Camera stream error';
            cameraStatus.classList.add('unavailable');
            cameraStatus.classList.remove('available');
            cameraError.textContent = `Error: ${error.message}`;
            cameraError.style.display = 'block';
        });
    }

    // Stop video stream
    function stopVideoStream() {
        fetch('/stop_video', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                cameraStatus.textContent = 'Camera stopped';
                cameraStatus.classList.remove('available', 'unavailable');
                videoContainer.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error stopping video stream:', error);
        });
    }

    // Add stop button
    const stopCameraBtn = document.createElement('button');
    stopCameraBtn.id = 'stopCameraBtn';
    stopCameraBtn.className = 'camera-btn';
    stopCameraBtn.textContent = 'Stop Camera';
    stopCameraBtn.style.display = 'none';
    stopCameraBtn.style.marginLeft = '10px';

    startCameraBtn.parentNode.insertBefore(stopCameraBtn, startCameraBtn.nextSibling);

    stopCameraBtn.addEventListener('click', stopVideoStream);

    // Send command to server
    function sendCommand(command) {
        fetch('/send_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({command: command})
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                statusText.textContent = `Sent: ${command}`;
                statusElement.classList.add('connected');
                statusElement.classList.remove('disconnected');
            } else {
                statusText.textContent = `Error: ${data.message}`;
                statusElement.classList.add('disconnected');
                statusElement.classList.remove('connected');

                // If connection was lost, update connection status
                if (data.error_type === 'connection_lost') {
                    isConnected = false;
                    connectionControl.style.display = 'block';
                }
            }
        })
        .catch(error => {
            statusText.textContent = `Error: ${error.message}`;
            statusElement.classList.add('disconnected');
            statusElement.classList.remove('connected');
            isConnected = false;
            connectionControl.style.display = 'block';
        });
    }
});