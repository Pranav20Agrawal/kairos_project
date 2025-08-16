# src/workers/system_indexer_worker.py

import os
import json
import logging
from pathlib import Path
from PySide6.QtCore import QThread

logger = logging.getLogger(__name__)

# Standard Windows Start Menu locations
START_MENU_PATHS = [
    Path(os.environ['APPDATA']) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
    Path(os.environ['ALLUSERSPROFILE']) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs',
]

# Common user folders we want to make accessible
USER_FOLDER_NAMES = [
    "Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos"
]

class SystemIndexerWorker(QThread):
    """
    A worker that scans the system for applications and common folders
    to create a searchable index for the Action Manager.
    """
    INDEX_FILE = "system_index.json"

    def run(self):
        """Scan the system and build the index."""
        logger.info("System Indexer Worker started. Building knowledge index...")
        index = {
            "applications": {},
            "folders": {}
        }

        # 1. Index Applications from Start Menu
        for path in START_MENU_PATHS:
            for root, _, files in os.walk(path):
                for name in files:
                    if name.endswith(('.lnk', '.url')):
                        app_name = Path(name).stem.lower()
                        # We store the full path to the shortcut
                        full_path = str(Path(root) / name)
                        if app_name not in index["applications"]:
                            index["applications"][app_name] = full_path

        # 2. Index Common User Folders
        user_profile = Path.home()
        for folder_name in USER_FOLDER_NAMES:
            folder_path = user_profile / folder_name
            if folder_path.exists():
                index["folders"][folder_name.lower()] = str(folder_path)

        # 3. Save the index to a file
        try:
            with open(self.INDEX_FILE, 'w') as f:
                json.dump(index, f, indent=4)
            logger.info(f"Successfully built and saved system index to '{self.INDEX_FILE}'. "
                        f"Found {len(index['applications'])} applications and {len(index['folders'])} folders.")
        except Exception as e:
            logger.error(f"Failed to save system index: {e}")