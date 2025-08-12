# src/workers/discovery_worker.py

import socket
import time
import json
import logging
from PySide6.QtCore import QThread

logger = logging.getLogger(__name__)

def get_local_ip():
    """Finds the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class DiscoveryWorker(QThread):
    """
    A worker that periodically broadcasts the PC's IP address over UDP
    so the mobile app can discover it automatically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.broadcast_port = 8888 # Port for discovery
        self.broadcast_interval = 1 # seconds

    def run(self):
        logger.info("DiscoveryWorker started. Broadcasting IP address...")
        
        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Enable broadcasting mode
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        while self.running:
            try:
                ip_address = get_local_ip()
                message = json.dumps({
                    "kairos_pc": True,
                    "ip": ip_address
                })
                
                # Broadcast the message to the entire network
                # '<broadcast>' is a special address for broadcasting
                sock.sendto(message.encode('utf-8'), ('<broadcast>', self.broadcast_port))
                
                time.sleep(self.broadcast_interval)
            except Exception as e:
                logger.error(f"Error in DiscoveryWorker: {e}", exc_info=True)
                time.sleep(5) # Wait longer on error

    def stop(self):
        self.running = False
        logger.info("DiscoveryWorker stop signal received.")