"""OpenSteamToolDesktop 应用程序入口。

启动流程：
    1. 崩溃诊断初始化（faulthandler + Windows Dump）
    2. Qt 消息处理器安装
    3. 主题/配置加载
    4. 版本更新检查
    5. Steam Bridge + GameManager 初始化
    6. 主窗口创建与显示
"""
from __future__ import annotations

import io
import logging
import os
import sys
import traceback
from pathlib import Path

import faulthandler

# ── 崩溃诊断全开 ──────────────────────────────────────────────

from utils.path_manager import PathManager

# PyInstaller windowed 模式下 sys.stderr 为 None，faulthandler 需要先重定向
_logs_dir = PathManager.logs_dir()

if sys.stderr is None:
    _stderr_path = _logs_dir / "stderr.log"
    sys.stderr = open(str(_stderr_path), "a", encoding="utf-8")

faulthandler.enable(all_threads=True, file=sys.stderr)

# 崩溃日志处理器
_crash_handler: logging.FileHandler | None = None
from config import CRASH_LOG_ENABLED
if CRASH_LOG_ENABLED:
    _crash_handler = logging.FileHandler(
        str(PathManager.crash_log_path()), mode="a", encoding="utf-8"
    )
    _crash_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s"
    ))

# ── Qt 初始化 ─────────────────────────────────────────────────

from PyQt6.QtCore import QEvent, QObject, Qt, QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication

# 屏蔽 QFluentWidgets Pro 推广提示
_old_stdout = sys.stdout
sys.stdout = io.StringIO()
from qfluentwidgets import setTheme, setThemeColor, Theme
sys.stdout = _old_stdout

from config import (
    APP_NAME, APP_VERSION, DEFAULT_THEME_COLOR, DEFAULT_THEME_MODE, LUA_DIR_RELATIVE,
)
from core.config_manager import ConfigManager
from core.game_manager import LuaGameManager
from core.steam_bridge import SteamBridge
from gui.main_window import MainWindow
from utils.logger import setup_logger


def _qt_message_handler(
    msg_type: QtMsgType,
    context: QtMsgType,  # type: ignore[override]
    msg: str,
) -> None:
    """捕获所有 Qt 内部日志 → Python logger + crash.log 文件"""
    qt_logger = logging.getLogger("Qt")
    type_map = {
        QtMsgType.QtDebugMsg: qt_logger.debug,
        QtMsgType.QtInfoMsg: qt_logger.info,
        QtMsgType.QtWarningMsg: qt_logger.warning,
        QtMsgType.QtCriticalMsg: qt_logger.critical,
        QtMsgType.QtFatalMsg: qt_logger.critical,
    }
    handler_fn = type_map.get(msg_type, qt_logger.warning)
    context_info = getattr(context, 'file', '') or ''
    line_info = getattr(context, 'line', 0) or 0
    func_info = getattr(context, 'function', '') or ''
    handler_fn("[Qt] %s (file=%s, line=%s, func=%s)", msg, context_info, line_info, func_info)

    if _crash_handler is not None:
        try:
            _crash_handler.emit(logging.LogRecord(
                name="Qt", level=logging.WARNING,
                pathname=context_info, lineno=line_info,
                msg=f"[Qt {msg_type.name}] {msg}", args=(),
                exc_info=None,
            ))
        except Exception:
            pass


class _SafeApplication(QApplication):
    """全局异常拦截：Qt 事件回调异常不传播到 Qt 层导致闪退"""

    def notify(self, receiver: QObject, event: QEvent) -> bool:
        try:
            return super().notify(receiver, event)
        except Exception as e:
            tb = traceback.format_exc()
            crash_logger = logging.getLogger("App.CrashGuard")
            crash_logger.critical(
                "Unhandled exception in Qt event loop: %s\n  receiver=%s\n  event=%s",
                e, receiver, event, exc_info=True,
            )
            if _crash_handler is not None:
                try:
                    _crash_handler.emit(logging.LogRecord(
                        name="App.CrashGuard", level=logging.CRITICAL,
                        pathname="Qt-EventLoop", lineno=0,
                        msg=f"{e}\n{tb}", args=(),
                        exc_info=None,
                    ))
                except Exception:
                    pass
            return False


def main() -> None:
    """应用程序主入口"""
    qInstallMessageHandler(_qt_message_handler)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = _SafeApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    logger = setup_logger(__name__)
    logger.info("=" * 60)
    logger.info("Application starting... %s v%s", APP_NAME, APP_VERSION)
    logger.info("=" * 60)

    # 全局异常钩子
    def _global_excepthook(exc_type, exc_value, exc_tb):
        logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _global_excepthook

    # ── 配置 ──
    logger.debug("Initializing ConfigManager...")
    config_manager = ConfigManager()
    logger.debug("Config loaded from: %s", config_manager.config_file)

    # ── 主题（固定暗色） ──
    logger.info("Setting theme mode: dark (forced)")
    setTheme(Theme.DARK)

    theme_color = config_manager.get("theme_color", DEFAULT_THEME_COLOR)
    logger.info("Setting theme color: %s", theme_color)
    setThemeColor(theme_color)

    # ── 核心模块 ──
    logger.debug("Initializing SteamBridge...")
    bridge = SteamBridge()
    logger.debug("Steam path detected: %s", bridge.get_steam_path() or 'Not found')
    logger.info("Using built-in DLL directory: %s", bridge.get_dll_path())

    lua_dir = ""
    steam_path = bridge.get_steam_path()
    if steam_path:
        lua_dir = os.path.join(steam_path, LUA_DIR_RELATIVE)
        logger.debug("Lua directory set to: %s", lua_dir)
    else:
        logger.warning("Steam path not found, Lua directory not set")
    game_manager = LuaGameManager(lua_dir)

    # ── 主窗口 ──
    logger.debug("Creating MainWindow...")
    window = MainWindow(bridge, game_manager, config_manager)

    window_effect = config_manager.get("window_effect", "none")
    logger.debug("Window effect: %s", window_effect)
    window.apply_window_effect(window_effect)

    screen = QApplication.primaryScreen()
    if screen:
        sg = screen.availableGeometry()
        window.move(
            (sg.width() - window.width()) // 2,
            (sg.height() - window.height()) // 2,
        )
        logger.debug("Window positioned at: (%d, %d)",
                     (sg.width() - window.width()) // 2,
                     (sg.height() - window.height()) // 2)

    window.show()
    logger.info("Application started successfully")

    # ── 版本检查（延迟到事件循环启动后执行）────────
    from core.version_checker import check_for_updates
    from gui.network_error_dialog import NetworkErrorDialog
    from gui.upgrade_dialog import UpgradeDialog
    from PyQt6.QtCore import QTimer

    def _do_version_check():
        logger.info("Checking for updates...")
        try:
            release, error_msg = check_for_updates()
        except Exception as e:
            logger.warning("更新检查异常，跳过: %s", e)
            return

        if error_msg:
            # 网络错误：非阻塞提示，用户可选择退出或继续
            dlg = NetworkErrorDialog(error_msg, window)
            dlg.exit_requested.connect(app.exit)
            dlg.exec()

        elif release is not None:
            logger.info("发现新版本 v%s，显示升级对话框", release.version)
            UpgradeDialog(release, window).exec()

    QTimer.singleShot(500, _do_version_check)

    exit_code = app.exec()

    # ── 清理 ──
    logger.info("Application shutting down...")
    try:
        window.shutdown()
    except Exception as e:
        logger.warning("Final shutdown error: %s", e)

    try:
        from gui.home_page import _executor
        _executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass

    # 刷新 404 缓存到磁盘
    try:
        from utils.http_client import save_404_cache_now
        save_404_cache_now()
    except Exception:
        pass

    logger.info("Application exited")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
