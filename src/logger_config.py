# src/logger_config.py

import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logging():
    """
    Configures the root logger for the entire application.
    - Logs DEBUG and higher to the console.
    - Logs INFO and higher to a rotating file ('kairos.log').
    """

    # Define the format for our log messages for maximum context
    log_format = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(name)s (%(filename)s:%(lineno)d) - %(message)s"
    )

    # --- Setup Rotating File Handler ---
    # This handler writes log messages to a file.
    # RotatingFileHandler will keep the log file from growing infinitely.
    # It creates backups once the file reaches a certain size.
    # maxBytes=5*1024*1024 means the log file will rotate after 5 MB.
    # backupCount=3 means it will keep the 3 most recent log files.
    file_handler = RotatingFileHandler(
        "kairos.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(logging.INFO)  # Log INFO and higher levels to the file
    file_handler.setFormatter(log_format)

    # --- Setup Console/Stream Handler ---
    # This handler prints log messages to the standard output (your console)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(
        logging.DEBUG
    )  # Show more detailed (DEBUG) messages in the console during development
    console_handler.setFormatter(log_format)

    # Get the root logger. All other loggers in the app will inherit from this.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set the lowest level to capture all messages

    # IMPORTANT: Avoid adding handlers multiple times if this function is ever called again
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    # Log the initialization of the logging system itself
    logging.info("=" * 50)
    logging.info("Logging configured. K.A.I.R.O.S. session starting.")
    logging.info("=" * 50)
