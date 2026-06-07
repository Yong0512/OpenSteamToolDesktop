import os
import sys

from core.dll_injector import DLLInjector, InjectStatus
from core.steam_detector import SteamDetector, SteamStatus
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SteamBridge:

    def __init__(self):
        self._steam_path = ""
        self._lua_dir = ""

        self._dll_source_dir = self._get_default_dll_source_dir()
        self._detector = SteamDetector()
        self._injector = DLLInjector()
        logger.debug("SteamBridge initializing...")
        self._detect_steam()

        if self._dll_source_dir and os.path.isdir(self._dll_source_dir):
            self._injector.set_dll_source_dir(self._dll_source_dir)
            logger.info(f"Using built-in DLL source directory: {self._dll_source_dir}")
        else:
            logger.warning(f"Built-in DLL source directory not found: {self._dll_source_dir}")

    def _get_default_dll_source_dir(self) -> str:

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
            dll_dir = os.path.join(base_dir, "open_steam_tool")
            if os.path.isdir(dll_dir):
                return dll_dir

        if hasattr(sys, '__compiled__'):

            base_dir = os.path.dirname(os.path.abspath(__file__))
            dll_dir = os.path.join(base_dir, "open_steam_tool")
            if os.path.isdir(dll_dir):
                return dll_dir

            exe_dir = os.path.dirname(sys.executable)
            dll_dir = os.path.join(exe_dir, "open_steam_tool")
            if os.path.isdir(dll_dir):
                return dll_dir

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        dll_dir = os.path.join(project_root, "open_steam_tool")
        return dll_dir

    def _detect_steam(self):
        logger.debug("Detecting Steam installation...")

        result = self._detector.detect()
        if result.status == SteamStatus.INSTALLED:
            self._steam_path = result.path
            self._lua_dir = os.path.join(result.path, "config", "lua")
            self._injector.set_steam_path(result.path)
            logger.info(f"Steam path: {result.path}")
            logger.debug(f"Lua directory: {self._lua_dir}")

            from core.app_state import app_state, STEAM_PATH
            app_state.set(STEAM_PATH, self._steam_path)
        else:
            logger.warning(f"Steam not found: {result.message}")

    def set_dll_source_dir(self, path: str):
        logger.info(f"Setting DLL source directory: {path}")
        if not os.path.isdir(path):
            logger.warning(f"DLL source directory not found: {path}")
        self._dll_source_dir = path
        self._injector.set_dll_source_dir(path)

    def set_dll_path(self, path: str):
        logger.debug(f"set_dll_path called (alias for set_dll_source_dir): {path}")
        self.set_dll_source_dir(path)

    def get_dll_path(self) -> str:
        return self._dll_source_dir

    def inject(self) -> tuple[bool, str]:
        if not self._dll_source_dir or not os.path.isdir(self._dll_source_dir):
            logger.error("Cannot inject: DLL source directory not set or not found")
            return False, f"内置注入源目录未找到：{self._dll_source_dir}。请确保 open_steam_tool 目录存在且包含所需的文件。"

        logger.info(f"Starting DLL injection from: {self._dll_source_dir}")
        self._injector.set_dll_source_dir(self._dll_source_dir)
        result = self._injector.deploy_dlls()
        logger.debug(f"Deploy result: {result.status}, {result.message}")

        if result.status == InjectStatus.SUCCESS or result.status == InjectStatus.DLL_ALREADY_DEPLOYED:
            logger.debug("Creating Lua directory...")
            lua_result = self._injector.create_lua_dir()
            logger.info(f"Injection successful: {result.message}；{lua_result.message}")
            return True, result.message + "；" + lua_result.message

        logger.error(f"Injection failed: {result.message}")
        return False, result.message

    def verify_injection(self) -> tuple[bool, str]:
        logger.debug("Verifying injection status...")
        result = self._injector.verify_injection()
        logger.debug(f"Verification result: {result.status}, {result.message}")

        if result.status == InjectStatus.SUCCESS:
            return True, result.message
        else:
            return False, result.message

    def disconnect(self) -> tuple[bool, str]:
        logger.info("Starting full uninstallation...")
        msg_parts = []

        result = self._injector.uninstall_dlls()
        msg_parts.append(result.message)
        logger.debug(f"Uninstall DLLs: {result.status}")

        log_result = self._injector.clean_logs()
        if log_result.status == InjectStatus.SUCCESS:
            msg_parts.append("日志已清理")
        else:
            msg_parts.append(f"日志清理: {log_result.message}")

        lua_result = self._injector.clean_lua_configs()
        if lua_result.status == InjectStatus.SUCCESS:
            msg_parts.append("游戏配置已清理")
        else:
            msg_parts.append(f"配置清理: {lua_result.message}")

        msg = "；".join(msg_parts)
        if result.status == InjectStatus.SUCCESS:
            logger.info(f"Disconnect successful: {msg}")
            return True, msg

        logger.error(f"Disconnect failed: {msg}")
        return False, msg

    def is_connected(self) -> bool:
        result = self._injector.verify_injection()
        return result.status == InjectStatus.SUCCESS

    def is_deployed(self) -> bool:
        if not self._steam_path:
            return False
        all_deployed, _ = self._injector.check_dlls_deployed()
        return all_deployed

    def get_steam_path(self) -> str:
        if self._steam_path:
            return self._steam_path
        from core.app_state import app_state, STEAM_PATH
        return str(app_state.get(STEAM_PATH, ""))

    def get_opensteamtool_log_dir(self) -> str:
        if not self._steam_path:
            return ""
        return os.path.join(self._steam_path, "opensteamtool")

    def get_default_lua_dir(self) -> str:
        if not self._steam_path:
            return ""
        return os.path.join(self._steam_path, "config", "lua")

    def redetect_steam(self):
        self._detect_steam()
