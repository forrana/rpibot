# Version information for Device Controller Web Interface
# This file is used for version tracking and release management

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)

# Version history and release notes
VERSION_HISTORY = {
    "1.0.0": {
        "date": "2024-02-20",
        "changes": [
            "Initial release with core functionality",
            "Serial communication via /dev/ttyUSB0",
            "Arrow controls with W/S/A/D commands",
            "Power ON/OFF toggle",
            "Keyboard shortcuts (W, A, S, D, X)",
            "Raspberry Pi camera support",
            "Connection error handling",
            "Responsive web interface"
        ],
        "breaking": []
    }
}

# Build information (will be updated by build scripts)
BUILD_INFO = {
    "build_number": "dev",
    "build_date": "2024-02-20",
    "git_commit": "unknown",
    "python_version": "3.8+"
}

def get_version():
    """Return the current version string"""
    return __version__

def get_version_info():
    """Return the version as a tuple (major, minor, patch)"""
    return __version_info__

def get_full_version():
    """Return full version information including build details"""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "build_info": BUILD_INFO,
        "version_history": VERSION_HISTORY
    }

def get_latest_changes():
    """Return the changes for the latest version"""
    latest_version = max(VERSION_HISTORY.keys())
    return VERSION_HISTORY[latest_version]