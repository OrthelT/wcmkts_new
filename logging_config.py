import logging
import os
from logging.handlers import RotatingFileHandler

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

def setup_logging(name="app", log_file="wcmkts_app.log", level=logging.INFO, max_bytes=5*1024*1024, backup_count=3):
    """Set up logging configuration with a rotating file handler and a stream handler.

    All log files are routed to the project's ./logs/ directory unless an
    absolute path is provided (e.g. tests using tmpdir).

    Args:
        name: The name of the logger.
        log_file: The name of the log file.
        level: The level of the logger.
        max_bytes: The maximum size of the log file.
        backup_count: The number of backup log files.

    Returns:
        logger: The logger object.

    Example usage:
    from logging_config import setup_logging
    setup_logging()
    """
    logger = logging.getLogger(name)
    # Clear existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s "
                                    "[%(filename)s:%(lineno)d %(funcName)s()] "
                                    "%(message)s")

    # Route log files to ./logs/ unless an absolute path is given
    os.makedirs(LOGS_DIR, exist_ok=True)
    if os.path.isabs(log_file):
        log_path = log_file
    else:
        log_file = os.path.basename(log_file)
        log_path = os.path.join(LOGS_DIR, log_file)

    # Create and add rotating file handler
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Create and add stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.setLevel(level)
    return logger