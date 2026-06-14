import os
import winreg
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


class SteamStatus(Enum):
    """Steam 客户端检测状态枚举"""
    NOT_INSTALLED = auto()      # 未检测到 Steam 安装
    INSTALLED = auto()          # 已检测到 Steam 安装
    PATH_INVALID = auto()       # 检测到路径但 Steam.exe 不存在
    REGISTRY_ERROR = auto()     # 注册表访问出错
    UNKNOWN_ERROR = auto()      # 未知错误


@dataclass
class SteamDetectionResult:
    """Steam 检测结果数据类
    
    Attributes:
        status: 检测状态
        path: Steam 安装路径（仅当 status 为 INSTALLED 时有效）
        message: 详细描述信息
    """
    status: SteamStatus
    path: Optional[str] = None
    message: str = ""


class SteamDetector:
    """Steam 客户端检测器
    
    通过多种方式检测 Windows 系统上 Steam 客户端的安装状态：
    1. Windows 注册表（64位和32位路径）
    2. 默认安装目录
    3. 常见自定义安装路径
    
    兼容 Windows 7/8/10/11
    """
    
    # Steam 可执行文件名
    STEAM_EXE = "Steam.exe"
    
    # 64位系统注册表路径
    REG_PATH_64BIT = r"SOFTWARE\Valve\Steam"
    # 32位系统/WOW64注册表路径
    REG_PATH_32BIT = r"SOFTWARE\WOW6432Node\Valve\Steam"
    
    # 注册表中存储安装路径的键名
    REG_VALUE_NAME = "InstallPath"
    
    # 默认安装目录列表
    DEFAULT_PATHS = [
        r"C:\Program Files (x86)\Steam",      # 64位系统默认路径
        r"C:\Program Files\Steam",              # 32位系统默认路径
        r"C:\Steam",                            # 根目录安装（较少见）
    ]
    
    # 常见自定义安装路径（用户可能选择的其他分区）
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
        """验证给定路径是否包含有效的 Steam.exe
        
        Args:
            path: 要验证的目录路径
            
        Returns:
            路径有效且包含 Steam.exe 返回 True
        """
        if not path or not isinstance(path, str):
            return False
        
        # 规范化路径
        normalized_path = os.path.normpath(path.strip())
        
        # 检查目录是否存在
        if not os.path.isdir(normalized_path):
            return False
        
        # 检查 Steam.exe 是否存在
        steam_exe_path = os.path.join(normalized_path, self.STEAM_EXE)
        return os.path.isfile(steam_exe_path)
    
    def _detect_from_registry(self) -> Optional[str]:
        """从 Windows 注册表检测 Steam 安装路径
        
        检测顺序：
        1. HKEY_CURRENT_USER\\SOFTWARE\\Valve\\Steam（当前用户配置）
        2. HKEY_LOCAL_MACHINE\\SOFTWARE\\Valve\\Steam（64位系统全局配置）
        3. HKEY_LOCAL_MACHINE\\SOFTWARE\\WOW6432Node\\Valve\\Steam（32位兼容层）
        
        Returns:
            有效的 Steam 安装路径，未找到返回 None
        """
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
        """从默认安装目录检测 Steam
        
        Returns:
            有效的 Steam 安装路径，未找到返回 None
        """
        for path in self.DEFAULT_PATHS:
            if self._verify_steam_path(path):
                return path
        return None
    
    def _detect_from_custom_paths(self) -> Optional[str]:
        """从常见自定义路径检测 Steam
        
        Returns:
            有效的 Steam 安装路径，未找到返回 None
        """
        for path in self.COMMON_CUSTOM_PATHS:
            if self._verify_steam_path(path):
                return path
        return None
    
    def detect(self) -> SteamDetectionResult:
        """执行完整的 Steam 检测流程
        
        按以下优先级进行检测：
        1. 全局 AppState 中用户手动设置的路径（最高优先级）
        2. Windows 注册表
        3. 默认安装目录
        4. 常见自定义安装路径
        
        Returns:
            SteamDetectionResult 包含检测状态和路径信息
        """
        logger.debug("Starting Steam detection...")

        # 优先使用全局状态中手动设置的路径
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
            # 第二步：尝试从注册表读取
            logger.debug("  Checking registry...")
            registry_path = self._detect_from_registry()
            if registry_path:
                logger.info(f"Steam detected via registry: {registry_path}")
                return SteamDetectionResult(
                    status=SteamStatus.INSTALLED,
                    path=registry_path,
                    message=f"通过注册表检测到 Steam 安装路径: {registry_path}"
                )
            
            # 第二步：检查默认安装目录
            logger.debug("  Checking default paths...")
            default_path = self._detect_from_default_paths()
            if default_path:
                logger.info(f"Steam detected via default path: {default_path}")
                return SteamDetectionResult(
                    status=SteamStatus.INSTALLED,
                    path=default_path,
                    message=f"通过默认目录检测到 Steam 安装路径: {default_path}"
                )
            
            # 第三步：检查常见自定义路径
            logger.debug("  Checking custom paths...")
            custom_path = self._detect_from_custom_paths()
            if custom_path:
                logger.info(f"Steam detected via custom path: {custom_path}")
                return SteamDetectionResult(
                    status=SteamStatus.INSTALLED,
                    path=custom_path,
                    message=f"通过自定义路径检测到 Steam 安装路径: {custom_path}"
                )
            
            # 未检测到 Steam
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
        """检查 Steam 进程是否正在运行
        
        使用 psutil 或 subprocess 查询进程
        
        Returns:
            Steam 正在运行返回 True
        """
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
        """强制关闭 Steam 进程
        
        Returns:
            (成功状态, 消息)
        """
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
