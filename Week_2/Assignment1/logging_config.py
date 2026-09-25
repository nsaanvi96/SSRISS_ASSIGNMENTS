utf-8import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"


def get_logger(name: str = "web_monitor") -> logging.Logger:
    """
    Return a logger that writes to both the console and a log file.
    Calling this multiple times with the same name returns the same logger.
    """
    logger = logging.getLogger(name)

    
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_DIR / "web_monitor.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
