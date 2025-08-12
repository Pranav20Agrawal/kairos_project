# src/wifi_manager.py
import subprocess
import time
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

def get_current_connection() -> Optional[str]:
    """Gets the SSID of the currently connected Wi-Fi network."""
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'interfaces'],
            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in result.stdout.split('\n'):
            if "SSID" in line and ":" in line and "BSSID" not in line:
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    logger.info(f"Currently connected to: {ssid}")
                    return ssid
        logger.info("Not connected to any Wi-Fi network.")
        return None
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Failed to get current Wi-Fi connection: {e}")
        return None

def connect_to_wifi(ssid: str, timeout_seconds: int = 20) -> bool:
    """Attempts to connect to a given Wi-Fi SSID and waits for completion."""
    logger.info(f"Attempting to connect to Wi-Fi network: '{ssid}'")
    try:
        subprocess.run(
            ['netsh', 'wlan', 'connect', f'name="{ssid}"'],
            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Wait and check for successful connection
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if get_current_connection() == ssid:
                logger.info(f"Successfully connected to '{ssid}'.")
                return True
            time.sleep(1)
            
        logger.error(f"Connection to '{ssid}' timed out after {timeout_seconds} seconds.")
        return False
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Failed to connect to Wi-Fi network '{ssid}': {e.stderr}")
        return False

def disconnect_wifi() -> bool:
    """Disconnects from the current Wi-Fi network."""
    logger.info("Disconnecting from current Wi-Fi network...")
    try:
        interfaces_output = subprocess.run(
            ['netsh', 'wlan', 'show', 'interfaces'],
            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
        ).stdout
        
        interface_name = None
        for line in interfaces_output.split('\n'):
            if "Name" in line and ":" in line:
                interface_name = line.split(":", 1)[1].strip()
                break

        if not interface_name:
            logger.warning("Could not find an active Wi-Fi interface to disconnect.")
            return False

        subprocess.run(
            ['netsh', 'wlan', 'disconnect', f'interface="{interface_name}"'],
            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        logger.info("Successfully disconnected from Wi-Fi.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Failed to disconnect from Wi-Fi: {e}")
        return False