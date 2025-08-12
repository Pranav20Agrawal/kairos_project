# src/api_server.py

import logging
import shutil
from pathlib import Path
import json
import asyncio
import os
from PySide6.QtCore import QThread
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn
from typing import Optional, TYPE_CHECKING
import pyperclip

from src import bluetooth_manager

if TYPE_CHECKING:
    from src.action_manager import ActionManager

logger = logging.getLogger(__name__)

clipboard_update_callback = None
notification_callback = None
text_command_callback = None

class ActionRequest(BaseModel):
    intent: str
    entity: Optional[str] = None

class ClipboardRequest(BaseModel):
    content: str

class TextCommandRequest(BaseModel):
    command: str

class KairosAPI:
    def __init__(self):
        self.app = FastAPI(title="K.A.I.R.O.S. API", version="1.0")
        self.action_manager: Optional['ActionManager'] = None
        self.active_websocket: Optional[WebSocket] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.setup_routes()

    def set_action_manager(self, action_manager: 'ActionManager'):
        self.action_manager = action_manager

    async def send_prepare_handoff(self):
        if self.active_websocket:
            logger.info("Sending 'prepare_handoff' command to mobile.")
            payload = {"type": "prepare_handoff"}
            try:
                await self.active_websocket.send_text(json.dumps(payload))
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")

    async def send_clipboard_update(self, text: str):
        if self.active_websocket:
            logger.info(f"Sending clipboard update to mobile: '{text[:30]}...'")
            payload = {"type": "clipboard_update", "content": text}
            try:
                await self.active_websocket.send_text(json.dumps(payload))
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")

    async def send_browser_handoff(self, url: str):
        if self.active_websocket:
            logger.info(f"Sending browser handoff to mobile: '{url}'")
            payload = {"type": "browser_handoff", "url": url}
            try:
                await self.active_websocket.send_text(json.dumps(payload))
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")

    async def send_file_start(self, file_path: str, page_number: int = 1):
        if self.active_websocket:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            logger.info(f"Initiating file transfer for {file_name} ({file_size} bytes) at page {page_number}")
            payload = {
                "type": "file_start",
                "file_name": file_name,
                "file_size": file_size,
                "page_number": page_number,
            }
            await self.active_websocket.send_text(json.dumps(payload))

    async def send_file_chunk(self, chunk: bytes):
        if self.active_websocket:
            await self.active_websocket.send_bytes(chunk)

    async def send_file_end(self):
        if self.active_websocket:
            logger.info("File transfer complete.")
            payload = {"type": "file_end"}
            await self.active_websocket.send_text(json.dumps(payload))

    async def send_spotify_handoff(self, state: dict):
        if self.active_websocket:
            logger.info(f"Sending Spotify handoff to mobile: {state['track_name']}")
            payload = {
                "type": "spotify_handoff",
                "state": state
            }
            try:
                await self.active_websocket.send_text(json.dumps(payload))
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
    
    async def send_headset_handoff(self, headset_name: str):
        if self.active_websocket:
            logger.info(f"Sending headset handoff command for '{headset_name}'")
            payload = {
                "type": "headset_handoff",
                "headset_name": headset_name
            }
            await self.active_websocket.send_text(json.dumps(payload))

    def setup_routes(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket = websocket
            logger.info("Mobile client connected via WebSocket.")
            try:
                while True:
                    data = await websocket.receive_text()
                    logger.info(f"Received WebSocket message from mobile: {data}")
                    try:
                        message = json.loads(data)
                        msg_type = message.get("type")

                        if msg_type == "clipboard_update":
                            content = message.get("content", "")
                            logger.info("Received clipboard from mobile. Updating PC clipboard.")
                            pyperclip.copy(content)
                            if callable(clipboard_update_callback):
                                clipboard_update_callback(content)
                        
                        elif msg_type == "notification_update":
                            logger.info("Received notification from mobile.")
                            if callable(notification_callback):
                                notification_callback(message)
                        
                        elif msg_type == "headset_handoff_to_pc":
                            logger.info("Received headset handoff command from mobile.")
                            headset_name = message.get("headset_name")
                            if headset_name and self.action_manager:
                                self.action_manager.speaker_worker.speak(f"Please connect to {headset_name}")
                                bluetooth_manager.connect_to_bluetooth_device(headset_name)

                    except json.JSONDecodeError:
                        logger.warning("Received non-JSON WebSocket message.")
            except WebSocketDisconnect:
                logger.info("Mobile client disconnected from WebSocket.")
                self.active_websocket = None

        @self.app.post("/process_text_command")
        def process_text_command(request: TextCommandRequest):
            logger.info(f"API received text command: '{request.command}'")
            if callable(text_command_callback):
                text_command_callback(request.command)
                return {"status": "success", "message": "Command received for processing."}
            else:
                logger.error("Text command received but no callback is registered.")
                raise HTTPException(status_code=503, detail="Text command handler not initialized.")
        
        @self.app.post("/execute_action")
        def execute_action(request: ActionRequest):
            if self.action_manager:
                if request.intent == "HEADSET_HANDOFF_TO_PC":
                    logger.info("Executing headset handoff TO PC.")
                    bluetooth_manager.connect_to_bluetooth_device(request.entity)
                    return {"status": "success", "message": "Headset handoff to PC initiated."}
                
                self.action_manager.execute_action(f"[{request.intent}]", {"entity": request.entity})
                return {"status": "success", "message": f"Action '{request.intent}' queued for execution."}
            else:
                raise HTTPException(status_code=503, detail="ActionManager not initialized.")

        @self.app.post("/upload_file")
        async def upload_file(file: UploadFile = File(...)):
            if not self.action_manager:
                raise HTTPException(status_code=503, detail="ActionManager not initialized.")
            uploads_dir = Path("uploads")
            uploads_dir.mkdir(exist_ok=True)
            safe_filename = Path(file.filename).name
            destination_path = uploads_dir / safe_filename
            try:
                with destination_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                self.action_manager.set_last_received_file(destination_path)
                logger.info(f"Successfully received and saved file to '{destination_path}'")
                return {"status": "success", "filename": safe_filename, "path": str(destination_path)}
            except Exception as e:
                logger.error(f"Failed to save uploaded file '{safe_filename}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Failed to save file.")

        @self.app.get("/clipboard")
        def get_clipboard():
            try:
                content = pyperclip.paste()
                logger.info("API: Fetched clipboard content.")
                return {"status": "success", "content": content}
            except Exception as e:
                logger.error(f"API: Could not read from clipboard: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Could not read from clipboard.")

        @self.app.post("/clipboard")
        def set_clipboard(request: ClipboardRequest):
            try:
                pyperclip.copy(request.content)
                logger.info("API: Set clipboard content.")
                return {"status": "success", "message": "Clipboard updated."}
            except Exception as e:
                logger.error(f"API: Could not write to clipboard: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Could not write to clipboard.")

kairos_api = KairosAPI()
app = kairos_api.app

class ServerWorker(QThread):
    def __init__(self, action_manager: 'ActionManager', host: str = "0.0.0.0", port: int = 8000):
        super().__init__()
        self.action_manager = action_manager
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None

    def run(self) -> None:
        # --- FIX APPLIED HERE ---
        # Create a new event loop for this background thread
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # 'RuntimeError: There is no current event loop...'
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        kairos_api.loop = loop
        # --- END FIX ---
        
        kairos_api.set_action_manager(self.action_manager)
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info", loop="asyncio")
        self.server = uvicorn.Server(config)
        
        logger.info(f"Starting K.A.I.R.O.S. API server on http://{self.host}:{self.port}")
        # Uvicorn's run is blocking, so it will keep the thread alive.
        # We run it within the loop context we've established.
        loop.run_until_complete(self.server.serve())
        logger.info("K.A.I.R.O.S. API server has shut down.")

    def stop(self) -> None:
        if self.server:
            logger.info("Sending shutdown signal to K.A.I.R.O.S. API server...")
            self.server.should_exit = True