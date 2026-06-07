from __future__ import annotations

import logging
import sys
from datetime import datetime

from utils.path_manager import PathManager


def _get_log_file() -> str:
    logs_dir = PathManager.logs_dir()
    date_str = datetime.now().strftime("%Y-%m-%d")
    return str(logs_dir / f"{date_str}.log")

def setup_logger(name: str, level: int | str | None = None) -> logging.Logger:
    if level is None:
        from config import LOG_LEVEL
        level = getattr(logging, LOG_LEVEL, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        log_path = _get_log_file()
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        print(f"警告：无法创建日志文件: {e}")

    return logger

def set_log_level(logger: logging.Logger, level: int) -> None:
    logger.setLevel(level)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(level)

LOG_DIR: str = str(PathManager.logs_dir())
LOG_FILE: str = _get_log_file()

LOG_LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
