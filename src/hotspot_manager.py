# src/hotspot_manager.py
import subprocess
import logging
import sys
import time

logger = logging.getLogger(__name__)

def is_hotspot_active():
    """
    Checks if the Windows Mobile Hotspot is active using multiple detection methods.
    Returns True if hotspot is active, False otherwise.
    """
    if sys.platform != "win32":
        return False
    
    # Method 1: Check for Microsoft Hosted Network Virtual Adapter
    try:
        # This is the most reliable method - checks if the hosted network is started
        command1 = 'netsh wlan show hostednetwork | findstr "Status"'
        result1 = subprocess.run(
            command1, shell=True, capture_output=True, text=True, 
            check=False, creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if "Started" in result1.stdout:
            logger.info("Hotspot detected as active via netsh method.")
            return True
            
    except Exception as e:
        logger.debug(f"Method 1 failed: {e}")

    # Method 2: Check for the default hotspot IP configuration
    try:
        command2 = 'ipconfig | findstr "192.168.137"'
        result2 = subprocess.run(
            command2, shell=True, capture_output=True, text=True,
            check=False, creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if "192.168.137" in result2.stdout:
            logger.info("Hotspot detected as active via IP method.")
            return True
            
    except Exception as e:
        logger.debug(f"Method 2 failed: {e}")

    # Method 3: PowerShell method (simplified)
    try:
        command3 = 'Get-NetAdapter | Where-Object {$_.InterfaceDescription -like "*Microsoft Hosted Network Virtual Adapter*" -and $_.Status -eq "Up"}'
        result3 = subprocess.run(
            ["powershell", "-Command", command3],
            capture_output=True, text=True, check=False, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result3.stdout.strip():
            logger.info("Hotspot detected as active via PowerShell method.")
            return True
            
    except Exception as e:
        logger.debug(f"Method 3 failed: {e}")

    logger.info("Hotspot is not active (all methods returned negative).")
    return False

def open_hotspot_settings():
    """
    Opens Windows Mobile Hotspot settings page.
    Returns True if successful, False otherwise.
    """
    if sys.platform != "win32":
        logger.warning("Hotspot management is only supported on Windows.")
        return False
        
    try:
        logger.info("Opening Windows Mobile Hotspot settings...")
        subprocess.run(["start", "ms-settings:network-mobilehotspot"], shell=True, check=True)
        return True
    except Exception as e:
        logger.error(f"Failed to open hotspot settings: {e}")
        return False

def wait_for_hotspot_activation(timeout_seconds=30, check_interval=2):
    """
    Waits for the hotspot to become active, checking every few seconds.
    Returns True if hotspot becomes active within timeout, False otherwise.
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        if is_hotspot_active():
            return True
        time.sleep(check_interval)
    
    return False