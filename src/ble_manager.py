# src/ble_manager.py
import asyncio
import logging
from typing import Optional
import sys
import platform

logger = logging.getLogger(__name__)

KAIROS_SERVICE_UUID = "0000FEA0-0000-1000-8000-00805F9B34FB"
COMMAND_CHARACTERISTIC_UUID = "0000FEA1-0000-1000-8000-00805F9B34FB"


class BleManager:
    """
    Manages BLE server functionality. 
    Note: Windows doesn't have native Python BLE server support.
    This implementation provides a mock server for development/testing.
    """
    def __init__(self):
        self.server_task: Optional[asyncio.Task] = None
        self.command_value = "idle"
        self.is_running = False

    async def _start_ble_server(self):
        """Mock BLE server for development purposes."""
        try:
            system = platform.system()
            logger.info(f"Starting BLE Manager on {system}")
            
            if system == "Windows":
                logger.warning("Windows BLE server mode is not supported through Python.")
                logger.warning("This is a mock implementation for development purposes.")
                logger.info("To implement actual BLE server on Windows, consider:")
                logger.info("1. Using Windows BLE APIs through win32 libraries")
                logger.info("2. Using a separate BLE dongle with Linux VM")
                logger.info("3. Using Windows UWP APIs")
            elif system == "Linux":
                logger.info("Linux detected. For actual BLE server, install:")
                logger.info("pip install bluez-peripheral")
                logger.info("This would require BlueZ and proper permissions.")
            elif system == "Darwin":  # macOS
                logger.info("macOS detected. BLE peripheral mode has limited support.")
            
            self.is_running = True
            logger.info("Mock BLE server started. Simulating 'KAIROS_PC' advertisement.")
            
            # Keep the mock server running
            while self.is_running:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("BLE server task cancelled.")
        except Exception as e:
            logger.error(f"Failed to start BLE server: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("Mock BLE server stopped.")

    def start(self):
        """Starts the BLE server in a background async loop."""
        if self.server_task is None or self.server_task.done():
            logger.info("Initializing BLE Manager...")
            self.server_task = asyncio.create_task(self._start_ble_server())
        else:
            logger.warning("BLE Manager is already running.")

    def stop(self):
        """Stops the BLE server task."""
        if self.server_task and not self.server_task.done():
            self.is_running = False
            self.server_task.cancel()
            logger.info("BLE Manager stopped.")
        self.server_task = None

    def set_command(self, command: str):
        """Updates the command value (mock implementation)."""
        logger.info(f"Mock BLE: Setting command to '{command}'")
        self.command_value = command
        # In a real implementation, this would notify connected clients
        logger.info(f"Mock BLE: Would notify clients of command change to '{command}'")


# Factory function to create appropriate BLE manager
def create_ble_manager():
    """Creates the appropriate BLE manager based on the operating system."""
    system = platform.system()
    
    if system == "Linux":
        try:
            # Try to import and use real Linux BLE manager
            return _create_linux_ble_manager()
        except Exception as e:
            logger.warning(f"Failed to create Linux BLE manager: {e}")
    
    # Fall back to mock manager
    logger.info("Using mock BLE manager")
    return BleManager()


def _create_linux_ble_manager():
    """Creates a real BLE manager for Linux if bluez-peripheral is available."""
    try:
        # Dynamic import to avoid linting errors
        import importlib
        gatt_module = importlib.import_module('bluez_peripheral.gatt')
        advert_module = importlib.import_module('bluez_peripheral.advert')
        
        Service = gatt_module.Service
        Characteristic = gatt_module.Characteristic
        Advertisement = advert_module.Advertisement
        
        class LinuxBleManager:
            def __init__(self):
                self.command_value = "idle"
                self.is_running = False
                self.service = None
                self.advertisement = None

            def start(self):
                """Starts the real BLE server."""
                if not self.server_task or self.server_task.done():
                    self.server_task = asyncio.create_task(self._start_real_ble_server())

            def stop(self):
                """Stops the real BLE server."""
                if self.server_task and not self.server_task.done():
                    self.is_running = False
                    self.server_task.cancel()

            def set_command(self, command: str):
                """Updates the command value and notifies clients."""
                logger.info(f"Real BLE: Setting command to '{command}'")
                self.command_value = command
                # In real implementation, would notify connected clients

            async def _start_real_ble_server(self):
                """Real BLE server implementation."""
                try:
                    # Create GATT service
                    self.service = Service(KAIROS_SERVICE_UUID, True)
                    
                    # Create characteristic
                    async def read_command():
                        return self.command_value.encode()
                        
                    command_char = Characteristic(
                        COMMAND_CHARACTERISTIC_UUID,
                        ["read", "notify"],
                        read_command
                    )
                    
                    self.service.add_characteristic(command_char)
                    
                    # Create advertisement
                    self.advertisement = Advertisement(
                        "KAIROS_PC",
                        [KAIROS_SERVICE_UUID],
                        0x0340,  # Generic computer
                        60  # Advertisement interval
                    )
                    
                    # Start the server
                    await self.service.register()
                    await self.advertisement.register()
                    
                    logger.info("Real Linux BLE server started successfully!")
                    self.is_running = True
                    
                    while self.is_running:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(f"Real BLE server error: {e}")
                finally:
                    self.is_running = False
        
        logger.info("Using real Linux BLE manager")
        return LinuxBleManager()
        
    except ImportError:
        raise ImportError("bluez-peripheral not available")