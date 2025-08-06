# src/api_server.py

import logging
import shutil
from pathlib import Path
from PySide6.QtCore import QThread
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import uvicorn
from typing import Optional
import pyperclip

from src.action_manager import ActionManager

logger = logging.getLogger(__name__)

# --- API Data Models ---
class ActionRequest(BaseModel):
    intent: str
    entity: Optional[str] = None

class ClipboardRequest(BaseModel):
    content: str

# --- FastAPI Application ---
class KairosAPI:
    def __init__(self):
        self.app = FastAPI(title="K.A.I.R.O.S. API", version="1.0")
        self.action_manager: Optional[ActionManager] = None
        self.setup_routes()

    def set_action_manager(self, action_manager: ActionManager):
        """Allows the main thread to pass in the ActionManager instance."""
        self.action_manager = action_manager
        
    def setup_routes(self):
        @self.app.post("/execute_action")
        def execute_action(request: ActionRequest):
            if self.action_manager:
                logger.info(f"API received action: Intent='{request.intent}', Entity='{request.entity}'")
                # Emotion is not available via API, so it defaults to neutral
                self.action_manager.execute_action(f"[{request.intent}]", {"entity": request.entity})
                return {"status": "success", "message": f"Action '{request.intent}' queued for execution."}
            else:
                logger.error("API received action but ActionManager is not available.")
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
            """Gets the content of the PC's clipboard."""
            try:
                content = pyperclip.paste()
                logger.info("API: Fetched clipboard content.")
                return {"status": "success", "content": content}
            except Exception as e:
                logger.error(f"API: Could not read from clipboard: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Could not read from clipboard.")

        @self.app.post("/clipboard")
        def set_clipboard(request: ClipboardRequest):
            """Sets the content of the PC's clipboard."""
            try:
                pyperclip.copy(request.content)
                logger.info("API: Set clipboard content.")
                return {"status": "success", "message": "Clipboard updated."}
            except Exception as e:
                logger.error(f"API: Could not write to clipboard: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Could not write to clipboard.")

kairos_api = KairosAPI()
app = kairos_api.app

# --- Server Worker Thread ---
class ServerWorker(QThread):
    def __init__(self, action_manager: ActionManager, host: str = "0.0.0.0", port: int = 8000):
        super().__init__()
        self.action_manager = action_manager
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None

    def run(self) -> None:
        kairos_api.set_action_manager(self.action_manager)
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="info")
        self.server = uvicorn.Server(config)
        logger.info(f"Starting K.A.I.R.O.S. API server on http://{self.host}:{self.port}")
        self.server.run()
        logger.info("K.A.I.R.O.S. API server has shut down.")

    def stop(self) -> None:
        # <--- MODIFICATION: Graceful shutdown for Uvicorn --->
        if self.server:
            logger.info("Sending shutdown signal to K.A.I.R.O.S. API server...")
            self.server.should_exit = True
        # <--- END MODIFICATION --->