import logging
import os
import sys
from pathlib import Path
from typing import ClassVar

# ANSI escape codes for terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"


class ColorFormatter(logging.Formatter):
    """Custom logging formatter that adds ANSI colors based on log level."""

    LEVEL_COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD + RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, RESET)
        orig_levelname = record.levelname

        # Colorize levelname
        record.levelname = f"{color}{orig_levelname}{RESET}"

        # Format the record
        result = super().format(record)

        # Restore original levelname
        record.levelname = orig_levelname
        return result


def setup_logger(name: str = "app") -> logging.Logger:
    """Configures and returns a custom logger with color support for console and raw file logs."""
    logger = logging.getLogger(name)

    # Avoid adding handlers repeatedly if already configured
    if logger.handlers:
        return logger

    # Resolve log level from environment variable
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)
    logger.setLevel(level)

    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 1. Console Handler (Colorized)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = ColorFormatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Non-colorized, raw logs)
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Fallback if logs directory cannot be created on Windows
        print(f"Warning: Could not create file log handler: {e}", file=sys.stderr)

    return logger
