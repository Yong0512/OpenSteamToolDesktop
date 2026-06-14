"""
dll_manager — DLL 版本管理模块

负责：
1. 检查本地 DLL 版本
2. 比较本地版本 vs 远程版本
3. 下载并安装新版本
4. 版本化管理（按版本号建子文件夹）
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from utils.logger import setup_logger
from utils.path_manager import PathManager
from core.github_releases import GitHubReleases, get_latest_release_info
from core.dll_injector import DLLInjector

logger = setup_logger(__name__)

# DLL 目录名称
DLL_DIR_NAME: str = "DLL"

# 版本号正则（匹配 v1.2.3 或 1.2.3）
VERSION_PATTERN: str = r"v?(\d+)\.(\d+)\.(\d+)$"


class DLLManager(QObject):
    """DLL 版本管理器

    目录结构：
        .OpenSteamToolDesktop/
            DLL/
                v1.2.3/
                    OpenSteamTool.dll
                    dwmapi.dll
                    xinput1_4.dll
                v1.2.4/
                    ...
                current -> v1.2.4/  (可选：符号链接或版本文件)

    提供：
    1. 检查本地 DLL 版本
    2. 比较本地版本 vs 远程版本
    3. 下载并安装新版本
    4. 获取当前应使用的 DLL 路径
    """

    # 信号
    download_progress = pyqtSignal(int, int)  # downloaded_bytes, total_bytes
    download_finished = pyqtSignal(bool, str)  # success, message
    version_check_finished = pyqtSignal(bool, str)  # update_available, message

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._github = GitHubReleases()
        self._dll_dir = PathManager.base_dir() / DLL_DIR_NAME
        self._dll_dir.mkdir(parents=True, exist_ok=True)
        self._current_version_file = self._dll_dir / "current_version.json"

        # 连接 GitHub 下载进度信号
        self._github.download_progress.connect(self.download_progress.emit)
        self._github.download_finished.connect(self.download_finished.emit)

    def get_dll_dir(self) -> Path:
        """获取 DLL 根目录"""
        return self._dll_dir

    def get_version_dir(self, version: str) -> Path:
        """获取指定版本的 DLL 目录

        Args:
            version: 版本号，如 "v1.2.3"

        Returns:
            版本目录路径
        """
        # 确保版本号格式正确
        if not version.startswith("v"):
            version = f"v{version}"
        return self._dll_dir / version

    def check_dll_version(self, dll_path: Path) -> str:
        """获取 DLL 文件的版本号

        通过读取 DLL 文件的版本信息资源来获取版本号。
        如果无法获取，则使用文件修改时间作为备选。

        Args:
            dll_path: DLL 文件路径

        Returns:
            版本号字符串，如果无法获取则返回 "unknown"
        """
        if not dll_path.exists():
            return "unknown"

        try:
            # 尝试读取 Windows PE 版本信息
            import pefile
            pe = pefile.PE(str(dll_path))
            if hasattr(pe, "VS_VERSIONINFO"):
                # 从版本资源中提取
                pass  # pefile 版本信息提取较复杂
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Failed to read PE version: {e}")

        # 备选方案：从文件名或同级 version.txt 推断
        version_file = dll_path.parent / "version.txt"
        if version_file.exists():
            try:
                return version_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        # 最终备选：使用文件 MD5 作为标识
        try:
            import hashlib
            md5 = hashlib.md5()
            with open(dll_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5.update(chunk)
            return md5.hexdigest()[:8]  # 取前 8 位作为短标识
        except Exception:
            return "unknown"

    def get_latest_local_version(self) -> str:
        """获取本地已安装的最新版本号

        Returns:
            最新版本号，如果没有安装任何版本则返回 ""
        """
        if not self._dll_dir.exists():
            return ""

        # 查找所有版本目录
        versions = []
        for item in self._dll_dir.iterdir():
            if item.is_dir() and self._is_valid_version_dir(item.name):
                versions.append(item.name)

        if not versions:
            return ""

        # 按版本号排序（降序）
        versions.sort(key=self._parse_version, reverse=True)
        return versions[0]

    def get_current_version(self) -> str:
        """获取当前使用的版本（从 current_version.json 读取）

        Returns:
            当前版本号，如果未设置则返回 ""
        """
        if not self._current_version_file.exists():
            return ""

        try:
            data = json.loads(self._current_version_file.read_text(encoding="utf-8"))
            return data.get("version", "")
        except Exception as e:
            logger.warning(f"Failed to read current version file: {e}")
            return ""

    def set_current_version(self, version: str) -> bool:
        """设置当前使用的版本

        Args:
            version: 版本号

        Returns:
            是否设置成功
        """
        try:
            data = {"version": version}
            self._current_version_file.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
            logger.info(f"Set current version to: {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to set current version: {e}")
            return False

    def get_dll_path(self) -> Path | None:
        """获取当前应使用的 DLL 路径（目录）

        Returns:
            DLL 目录路径（包含 3 个 DLL 的目录），如果未找到则返回 None
        """
        # 优先使用 current_version.json 指定的版本
        current_ver = self.get_current_version()
        if current_ver:
            ver_dir = self.get_version_dir(current_ver)
            if ver_dir.exists() and self._has_required_dlls(ver_dir):
                return ver_dir

        # 回退：使用最新本地版本
        latest_ver = self.get_latest_local_version()
        if latest_ver:
            ver_dir = self.get_version_dir(latest_ver)
            if ver_dir.exists() and self._has_required_dlls(ver_dir):
                return ver_dir

        # 未找到任何版本
        return None

    def _has_required_dlls(self, dll_dir: Path, check_integrity: bool = True) -> bool:
        """检查目录是否包含所需的 DLL 文件
        
        Args:
            dll_dir: DLL 目录路径
            check_integrity: 是否检查文件完整性（文件大小、有效性）
            
        Returns:
            是否包含所有必需的 DLL 且文件完整
        """
        required_dlls = DLLInjector.ALL_DLLS
        for dll_name in required_dlls:
            dll_path = dll_dir / dll_name
            if not dll_path.exists():
                logger.debug(f"Missing DLL: {dll_name} in {dll_dir}")
                return False
            
            # 检查文件完整性
            if check_integrity and not self._is_dll_file_valid(dll_path):
                logger.warning(f"Incomplete or invalid DLL: {dll_name} in {dll_dir}")
                return False
        
        return True

    def _is_dll_file_valid(self, dll_path: Path) -> bool:
        """检查 DLL 文件是否完整有效
        
        验证项目：
        1. 文件大小 > 30KB（避免下载不完整的文件）
        2. 尝试读取 PE 头（如果 pefile 可用）
        3. 文件不以空字节结尾
        
        Args:
            dll_path: DLL 文件路径
            
        Returns:
            文件是否完整有效
        """
        try:
            # 1. 检查文件大小（DLL 应该大于 30KB）
            file_size = dll_path.stat().st_size
            if file_size < 30 * 1024:  # 30KB
                logger.warning(f"DLL file too small: {dll_path.name} ({file_size} bytes)")
                return False
            
            # 2. 尝试读取 PE 头（验证 DLL 格式）
            try:
                import pefile
                pe = pefile.PE(str(dll_path))
                # 检查是否是有效的 DLL（有 IMAGE_FILE_DLL 标志）
                if not (pe.FILE_HEADER.Characteristics & 0x2000):
                    logger.warning(f"Not a valid DLL (missing DLL flag): {dll_path.name}")
                    return False
                logger.debug(f"DLL file valid (PE check passed): {dll_path.name}")
            except ImportError:
                # pefile 未安装，跳过 PE 检查
                logger.debug("pefile not available, skipping PE header check")
            except Exception as e:
                logger.warning(f"Invalid PE header in {dll_path.name}: {e}")
                return False
            
            # 3. 检查文件末尾不是全是空字节
            with open(dll_path, "rb") as f:
                f.seek(-1024, 2)  # 读取最后 1KB
                tail = f.read()
                if tail == b"\x00" * 1024:
                    logger.warning(f"DLL file appears truncated (tail is all zeros): {dll_path.name}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking DLL file {dll_path}: {e}")
            return False

    def check_for_updates(self) -> Tuple[bool, str, Optional[dict]]:
        """检查是否有新版本可用
        
        优先检查本地是否已有最新版本的 DLL，如果有则直接设置为当前版本。
        如果本地版本存在但文件不完整，会触发重新下载。
        
        Returns:
            (是否有更新, 消息, 最新版本信息)
        """
        logger.info("Checking for DLL updates...")
        
        # 获取远程最新版本
        remote_info = self._github.get_latest_release_info()
        if not remote_info:
            return False, "无法获取远程版本信息", None
        
        remote_version = remote_info.get("version", "")
        if not remote_version:
            return False, "远程版本信息不完整", None
        
        # 优先检查：本地是否已有该版本的 DLL 文件（且完整）
        remote_version_dir = self.get_version_dir(remote_version)
        if remote_version_dir.exists():
            if self._has_required_dlls(remote_version_dir, check_integrity=True):
                # 本地已有该版本且文件完整，直接设置为当前版本
                logger.info(f"Local already has complete version {remote_version}, skip download")
                self.set_current_version(remote_version)
                return False, f"本地已有最新版本 {remote_version}", remote_info
            else:
                # 本地有该版本目录但文件不完整，删除并重新下载
                logger.warning(f"Local version {remote_version} exists but files are incomplete, will re-download")
                try:
                    import shutil
                    shutil.rmtree(remote_version_dir)
                    logger.info(f"Removed incomplete version directory: {remote_version_dir}")
                except Exception as e:
                    logger.error(f"Failed to remove incomplete directory: {e}")
                    return True, f"发现版本 {remote_version} 但文件不完整，且无法清理，请手动删除 {remote_version_dir}", remote_info
        
        # 获取本地当前版本
        local_version = self.get_current_version()
        if not local_version:
            local_version = self.get_latest_local_version()
        
        # 比较版本号
        if not local_version:
            return True, f"发现新版本 {remote_version}，点击下载", remote_info
        
        if self._compare_versions(remote_version, local_version) > 0:
            return (
                True,
                f"发现新版本 {remote_version}（当前：{local_version}）",
                remote_info,
            )
        
        return False, f"已是最新版本 {remote_version}", remote_info

    def download_and_install(self, version_info: dict) -> Tuple[bool, str]:
        """下载并安装指定版本的 DLL

        Args:
            version_info: 版本信息字典（来自 get_latest_release_info）

        Returns:
            (是否成功, 消息)
        """
        version = version_info.get("version", "")
        if not version:
            return False, "版本信息不完整"

        logger.info(f"Downloading and installing DLL version {version}...")

        # 创建版本目录
        version_dir = self.get_version_dir(version)
        if version_dir.exists():
            # 已存在，检查是否完整
            if self._has_required_dlls(version_dir):
                logger.info(f"Version {version} already installed")
                self.set_current_version(version)
                return True, f"版本 {version} 已安装"

        version_dir.mkdir(parents=True, exist_ok=True)

        # 获取下载链接
        assets = version_info.get("assets", [])
        if not assets:
            # 如果没有 assets 信息，尝试获取
            download_url = self._github.get_asset_download_url(version)
            if not download_url:
                self.download_finished.emit(False, f"未找到版本 {version} 的下载链接")
                return False, f"未找到版本 {version} 的下载链接"
        else:
            # 使用第一个 ZIP asset
            download_url = assets[0].get("browser_download_url", "")
            if not download_url:
                self.download_finished.emit(False, "下载链接为空")
                return False, "下载链接为空"

        # 下载 ZIP 文件
        zip_path = version_dir / "download.zip"
        success = self._github.download_asset(
            download_url,
            zip_path,
            progress_callback=self._on_download_progress,
        )

        if not success:
            self.download_finished.emit(False, "下载失败，请检查网络连接")
            return False, "下载失败，请检查网络连接"

        # 解压 DLL 文件
        extracted = self._github.extract_dll_from_zip(zip_path, version_dir)
        if not extracted:
            self.download_finished.emit(False, "解压失败，ZIP 文件中未找到 DLL")
            return False, "解压失败，ZIP 文件中未找到 DLL"

        # 验证必需的 DLL 是否存在
        if not self._has_required_dlls(version_dir):
            missing = [
                dll for dll in DLLInjector.ALL_DLLS
                if not (version_dir / dll).exists()
            ]
            msg = f"解压后缺少必需的 DLL：{', '.join(missing)}"
            self.download_finished.emit(False, msg)
            return False, msg

        # 写入版本信息文件
        version_info_file = version_dir / "version.txt"
        try:
            version_info_file.write_text(version, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write version.txt: {e}")

        # 设置当前版本
        self.set_current_version(version)

        # 清理下载的 ZIP
        try:
            zip_path.unlink()
        except Exception:
            pass

        logger.info(f"Successfully installed DLL version {version}")
        # 发射下载完成信号
        self.download_finished.emit(True, f"成功安装版本 {version}")
        return True, f"成功安装版本 {version}"

    def _on_download_progress(self, downloaded: int, total: int):
        """下载进度回调"""
        self.download_progress.emit(downloaded, total)

    @staticmethod
    def _is_valid_version_dir(name: str) -> bool:
        """检查目录名是否为有效的版本号"""
        match = re.match(VERSION_PATTERN, name)
        return match is not None

    @staticmethod
    def _parse_version(version_str: str) -> tuple:
        """解析版本号为元组（用于比较）"""
        match = re.match(VERSION_PATTERN, version_str)
        if match:
            return tuple(int(x) for x in match.groups())
        return (0, 0, 0)

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """比较两个版本号

        Returns:
            -1: v1 < v2
             0: v1 == v2
             1: v1 > v2
        """
        p1 = DLLManager._parse_version(v1)
        p2 = DLLManager._parse_version(v2)
        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
        else:
            return 0

    def close(self):
        """清理资源"""
        if self._github:
            self._github.close()


def check_dll_version(dll_path: Path) -> str:
    """检查 DLL 版本的便捷函数"""
    manager = DLLManager()
    return manager.check_dll_version(dll_path)


def get_latest_local_version(dll_dir: Path) -> str:
    """获取本地最新版本的便捷函数"""
    manager = DLLManager()
    return manager.get_latest_local_version()


def download_and_install_dll(target_dir: Path) -> bool:
    """下载并安装最新 DLL 的便捷函数"""
    manager = DLLManager()
    update_available, msg, version_info = manager.check_for_updates()
    if not update_available or not version_info:
        return False
    success, _ = manager.download_and_install(version_info)
    return success
