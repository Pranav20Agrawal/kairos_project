# src/bluetooth_manager.py
import subprocess
import logging

logger = logging.getLogger(__name__)

def get_active_audio_device_name() -> str | None:
    """
    Gets the name of the currently active audio playback device on Windows.
    """
    try:
        command = "Get-CimInstance -ClassName Win32_SoundDevice | Where-Object { $_.Default -eq $true } | Select-Object -ExpandProperty Name"
        
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        device_name = result.stdout.strip()
        
        if device_name:
            logger.info(f"Detected active audio device: '{device_name}'")
            return device_name
        else:
            logger.warning("Could not determine the active audio device.")
            return None
            
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Failed to get active audio device: {e}")
        return None

def connect_to_bluetooth_device(device_name: str) -> bool:
    """
    Opens the Windows Bluetooth settings page to prompt the user for connection.
    A fully silent, programmatic connection is very complex and unreliable on Windows.
    This is the most robust approach.
    """
    logger.info(f"Opening Bluetooth settings to connect to '{device_name}'...")
    try:
        # This command opens the "Bluetooth & devices" settings page directly.
        subprocess.run(["start", "ms-settings:bluetooth"], shell=True, check=True)
        return True
    except Exception as e:
        logger.error(f"Failed to open Bluetooth settings: {e}")
        return False