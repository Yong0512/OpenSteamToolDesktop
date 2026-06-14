"""
日志模块
========

基于标准库 ``logging``，同时输出到控制台和文件。
日志目录通过 ``PathManager`` 管理，支持切换到 Steam 安装目录。

.. code-block:: python

    from utils.logger import setup_logger

    logger = setup_logger(__name__)
    logger.info("Hello, world!")
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

from utils.path_manager import PathManager


def _get_log_file() -> str:
    """获取当前日志文件路径（惰性计算，支持运行时切换目录）"""
    logs_dir = PathManager.logs_dir()
    date_str = datetime.now().strftime("%Y-%m-%d")
    return str(logs_dir / f"{date_str}.log")


def setup_logger(name: str, level: int | str | None = None) -> logging.Logger:
    """设置日志器，同时输出到控制台和文件

    Args:
        name: 日志器名称（通常使用 ``__name__``）
        level: 日志级别，默认使用 ``config.LOG_LEVEL``

    Returns:
        配置好的 :class:`logging.Logger` 实例
    """
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
    """动态设置日志级别

    Args:
        logger: 目标日志器
        level: 日志级别（``logging.DEBUG`` 等整数常量）
    """
    logger.setLevel(level)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(level)


# 兼容旧代码：保留模块级属性
LOG_DIR: str = str(PathManager.logs_dir())
LOG_FILE: str = _get_log_file()

LOG_LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
