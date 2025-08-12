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
    log_format = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(name)s (%(filename)s:%(lineno)d) - %(message)s"
    )

    # FIX: Added encoding='utf-8' to both handlers to prevent Unicode errors on Windows
    file_handler = RotatingFileHandler(
        "kairos.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)

    # Also set the encoding for the console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # This check prevents adding handlers multiple times if the function is called again
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    logging.info("=" * 50)
    logging.info("Logging configured. K.A.I.R.O.S. session starting.")
    logging.info("=" * 50)