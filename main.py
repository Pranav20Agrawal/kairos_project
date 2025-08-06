# main.py

import sys
import os
import signal # <--- MODIFICATION: Import the signal module
from PySide6.QtWidgets import QApplication, QMessageBox
from src.main_window import KairosMainWindow
from src.logger_config import setup_logging
from src.settings_manager import SettingsManager
from dotenv import load_dotenv

__version__ = "1.0.0"

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    # Configure logging as the very first step
    setup_logging()

    app = QApplication(sys.argv)
    
    # <--- MODIFICATION: Add signal handler for graceful shutdown on Ctrl+C --->
    # This connects the terminal's interrupt signal to Qt's quit signal,
    # which then triggers our _shutdown_application method.
    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())
    # <--- END MODIFICATION --->
    
    # First-Time Setup Check
    settings = SettingsManager()
    if not settings.settings.core.setup_complete or not os.path.exists("voiceprint.npy"):
        msg_box = QMessageBox()
        msg_box.setWindowTitle("K.A.I.R.O.S. First-Time Setup")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setText("Welcome to K.A.I.R.O.S.!\n\nTo get started, you need to enroll your voice.")
        msg_box.setInformativeText(
            "Please run the following command in your terminal from the project's root directory:\n\n"
            "python enroll_voice.py\n\n"
            "The application will now exit. Please run the enrollment script and then start K.A.I.R.O.S. again."
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
        sys.exit(0)

    # Proceed with normal application launch
    app.setQuitOnLastWindowClosed(False)

    window = KairosMainWindow(app_version=__version__)
    window.show()

    # Start the Qt event loop
    sys.exit(app.exec())