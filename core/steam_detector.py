import os
import winreg
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)

class SteamStatus(Enum):
    NOT_INSTALLED = auto()
    INSTALLED = auto()
    PATH_INVALID = auto()
    REGISTRY_ERROR = auto()
    UNKNOWN_ERROR = auto()

@dataclass
class SteamDetectionResult:
    status: SteamStatus
    path: Optional[str] = None
    message: str = ""

class SteamDetector:

    STEAM_EXE = "Steam.exe"

    REG_PATH_64BIT = r"SOFTWARE\Valve\Steam"

    REG_PATH_32BIT = r"SOFTWARE\WOW6432Node\Valve\Steam"

    REG_VALUE_NAME = "InstallPath"

    DEFAULT_PATHS = [
        r"C:\Program Files (x86)\Steam",
        r"C:\Program Files\Steam",
        r"C:\Steam",
    ]

    COMMON_CUSTOM_PATHS = [
        r"D:\Steam",
        r"D:\Program Files (x86)\Steam",
        r"D:\Program Files\Steam",
        r"E:\Steam",
        r"E:\Program Files (x86)\Steam",
        r"E:\Program Files\Steam",
        r"F:\Steam",
    ]

    def _verify_steam_path(self, path: str) -> bool:
        if not path or not isinstance(path, str):
            return False

        normalized_path = os.path.normpath(path.strip())

        if not os.path.isdir(normalized_path):
            return False

        steam_exe_path = os.path.join(normalized_path, self.STEAM_EXE)
        return os.path.isfile(steam_exe_path)

    def _detect_from_registry(self) -> Optional[str]:
        registry_locations = [
            (winreg.HKEY_CURRENT_USER, self.REG_PATH_64BIT),
            (winreg.HKEY_LOCAL_MACHINE, self.REG_PATH_64BIT),
            (winreg.HKEY_LOCAL_MACHINE, self.REG_PATH_32BIT),
        ]

        for root_key, sub_path in registry_locations:
            try:
                with winreg.OpenKey(root_key, sub_path, 0, winreg.KEY_READ) as key:
                    install_path, _ = winreg.QueryValueEx(key, self.REG_VALUE_NAME)
                    if install_path and self._verify_steam_path(install_path):
                        return install_path
            except OSError:
                continue

        return None

    def _detect_from_default_paths(self) -> Optional[str]:
        for path in self.DEFAULT_PATHS:
            if self._verify_steam_path(path):
                return path
        return None

    def _detect_from_custom_paths(self) -> Optional[str]:
        for path in self.COMMON_CUSTOM_PATHS:
            if self._verify_steam_path(path):
                return path
        return None

    def detect(self) -> SteamDetectionResult:
        logger.debug("Starting Steam detection...")

        from core.app_state import app_state, STEAM_PATH
        manual_path = str(app_state.get(STEAM_PATH, ""))
        if manual_path and os.path.isdir(manual_path):
            logger.info(f"Steam path from global state: {manual_path}")
            return SteamDetectionResult(
                status=SteamStatus.INSTALLED,
                path=manual_path,
                message=f"使用已设置的 Steam 路径: {manual_path}",
            )

        try:

            logger.debug("  Checking registry...")
            registry_path = self._detect_from_registry()
            if registry_path:
                logger.info(f"Steam detected via registry: {registry_path}")
                return SteamDetectionResult(
                    status=SteamStatus.INSTALLED,
                    path=registry_path,
                    message=f"通过注册表检测到 Steam 安装路径: {registry_path}"
                )

            logger.debug("  Checking default paths...")
            default_path = self._detect_from_default_paths()
            if default_path:
                logger.info(f"Steam detected via default path: {default_path}")
                return SteamDetectionResult(
                    status=SteamStatus.INSTALLED,
                    path=default_path,
                    message=f"通过默认目录检测到 Steam 安装路径: {default_path}"
                )

            logger.debug("  Checking custom paths...")
            custom_path = self._detect_from_custom_paths()
            if custom_path:
                logger.info(f"Steam detected via custom path: {custom_path}")
                return SteamDetectionResult(
                    status=SteamStatus.INSTALLED,
                    path=custom_path,
                    message=f"通过自定义路径检测到 Steam 安装路径: {custom_path}"
                )

            logger.warning("Steam not detected in any location")
            return SteamDetectionResult(
                status=SteamStatus.NOT_INSTALLED,
                message="未检测到 Steam 客户端安装。请确认 Steam 已正确安装。"
            )

        except PermissionError as e:
            logger.error(f"Registry access denied: {e}")
            return SteamDetectionResult(
                status=SteamStatus.REGISTRY_ERROR,
                message=f"注册表访问权限不足: {str(e)}。请以管理员身份运行程序。"
            )
        except OSError as e:
            logger.error(f"OS error during detection: {e}")
            return SteamDetectionResult(
                status=SteamStatus.UNKNOWN_ERROR,
                message=f"系统错误: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unknown error during detection: {e}")
            return SteamDetectionResult(
                status=SteamStatus.UNKNOWN_ERROR,
                message=f"检测过程中发生未知错误: {str(e)}"
            )

    def is_steam_running(self) -> bool:
        logger.debug("Checking if Steam is running...")
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self.STEAM_EXE}"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=0x08000000,
            )
            if self.STEAM_EXE.lower() in result.stdout.lower():
                logger.debug("Steam process found")
                return True
        except Exception as e:
            logger.warning(f"Error checking Steam process: {e}")

        logger.debug("Steam process not found")
        return False

    def kill_steam(self) -> tuple[bool, str]:
        logger.info("Killing Steam process...")
        if not self.is_steam_running():
            logger.debug("Steam is not running, no need to kill")
            return True, "Steam 未在运行"

        try:
            import subprocess
            logger.debug(f"Running taskkill for {self.STEAM_EXE}...")
            result = subprocess.run(
                ["taskkill", "/F", "/IM", self.STEAM_EXE],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=0x08000000,
            )
            if result.returncode == 0:
                logger.info("Steam process killed successfully")
                return True, "Steam 已强制关闭"
            else:
                logger.error(f"Failed to kill Steam: {result.stderr}")
                return False, f"无法关闭 Steam: {result.stderr}"

        except subprocess.TimeoutExpired:
            logger.error("Timeout when killing Steam process")
            return False, "关闭 Steam 超时，请手动关闭"
        except Exception as e:
            logger.error(f"Error killing Steam: {e}")
            return False, f"关闭 Steam 时发生错误: {str(e)}"
