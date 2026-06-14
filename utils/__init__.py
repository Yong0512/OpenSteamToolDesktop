"""
OpenSteamToolDesktop 工具模块
==============================

提供日志、HTTP 客户端、异步线程 Worker 和封面下载等通用工具。

Public API
----------
.. autosummary::
   :toctree: generated/

   AsyncWorker
   setup_logger
   get
   get_json
   get_bytes
   get_text
   is_404_cached
   download_cover
   CoverCache
"""

from __future__ import annotations

from utils.async_worker import AsyncWorker
from utils.download_cover import CoverCache, download_cover
from utils.http_client import get, get_bytes, get_json, get_text, is_404_cached
from utils.logger import setup_logger

__all__ = [
    "AsyncWorker",
    "CoverCache",
    "download_cover",
    "get",
    "get_bytes",
    "get_json",
    "get_text",
    "is_404_cached",
    "setup_logger",
]
