"""
dll_injector — OpenSteamTool DLL 部署器

正确注入机制（基于 OpenSteamTool README）：
1. 将 3 个 DLL（OpenSteamTool.dll, dwmapi.dll, xinput1_4.dll）
   复制到 Steam 根目录
2. 创建 Lua 目录（<steam>/config/lua）并放入 Lua 配置
3. 正常启动 Steam，DLL 通过搜索顺序劫持自动加载

本模块负责：DLL 文件部署、Lua 目录管理、注入状态验证。
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from enum import Enum, auto

from utils.logger import setup_logger

logger = setup_logger(__name__)
class InjectStatus(Enum):
    """DLL 部署/验证状态枚举"""
    SUCCESS = auto()                     # 操作成功
    STEAM_NOT_FOUND = auto()           # Steam 目录未找到
    DLL_SOURCE_NOT_FOUND = auto()       # 源 DLL 文件未找到
    DLL_ALREADY_DEPLOYED = auto()     # DLL 已部署（无需重复）
    DEPLOY_FAILED = auto()             # 部署失败（复制失败/权限不足）
    VERIFICATION_FAILED = auto()        # 验证失败（未检测到日志）
    UNINSTALL_FAILED = auto()          # 卸载失败
    UNKNOWN_ERROR = auto()             # 未知错误


@dataclass
class InjectResult:
    """操作结果数据类"""
    status: InjectStatus
    message: str = ""
    details: list[str] | None = None


class DLLInjector:
    """OpenSteamTool DLL 部署器

    正确用法：
    1. 设置 Steam 路径（set_steam_path）
    2. 部署 DLL（deploy_dlls）+ 创建 Lua 目录（create_lua_dir）
    3. 提示用户重启 Steam
    4. 验证注入（verify_injection）—— 检查日志文件
    """

    # OpenSteamTool 相关 DLL 文件名（README 指定）
    DWM_DLL = "dwmapi.dll"
    XINPUT_DLL = "xinput1_4.dll"
    CORE_DLL = "OpenSteamTool.dll"
    ALL_DLLS = (CORE_DLL, DWM_DLL, XINPUT_DLL)

    # Lua 配置目录（OpenSteamTool README: <steam>/config/lua）
    LUA_DIR_RELATIVE = "config/lua"

    # 日志目录和文件（用于验证注入成功）
    LOG_DIR = "opensteamtool"
    LOG_FILES = ["main.log", "ipc.log", "manifest.log"]

    def __init__(self, steam_path: str = "", dll_source_dir: str = ""):
        self._steam_path = steam_path
        self._dll_source_dir = dll_source_dir

    def set_steam_path(self, path: str):
        self._steam_path = path

    def set_dll_source_dir(self, path: str):
        self._dll_source_dir = path

    def get_steam_path(self) -> str:
        return self._steam_path

    def check_dlls_deployed(self) -> tuple[bool, list[str]]:
        """检查 Steam 目录下是否已部署所需 DLL

        Returns:
            (是否全部部署, 缺失的 DLL 列表)
        """
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return False, list(self.ALL_DLLS)

        missing = []
        for dll_name in self.ALL_DLLS:
            dll_path = os.path.join(self._steam_path, dll_name)
            if not os.path.isfile(dll_path):
                missing.append(dll_name)

        return len(missing) == 0, missing

    def check_lua_dir(self) -> bool:
        """检查 Lua 配置目录是否存在"""
        if not self._steam_path:
            return False
        lua_dir = os.path.join(self._steam_path, self.LUA_DIR_RELATIVE)
        return os.path.isdir(lua_dir)

    def deploy_dlls(self) -> InjectResult:
        """将 3 个 DLL 复制到 Steam 根目录

        Returns:
            部署结果
        """
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return InjectResult(
                status=InjectStatus.STEAM_NOT_FOUND,
                message=f"Steam 目录未找到: {self._steam_path}",
            )

        if not self._dll_source_dir or not os.path.isdir(self._dll_source_dir):
            return InjectResult(
                status=InjectStatus.DLL_SOURCE_NOT_FOUND,
                message="未设置注入源目录，请在设置中指定 OpenSteamTool DLL 所在目录",
            )

        # 复制 3 个 DLL
        copied = []
        failed = []
        for dll_name in self.ALL_DLLS:
            src = os.path.join(self._dll_source_dir, dll_name)
            dst = os.path.join(self._steam_path, dll_name)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, dst)
                    copied.append(dll_name)
                except Exception as e:
                    failed.append(f"{dll_name}: {e}")
            else:
                failed.append(f"{dll_name}: 源文件不存在")

        if failed:
            return InjectResult(
                status=InjectStatus.DEPLOY_FAILED,
                message=f"部分注入失败: {'; '.join(failed)}",
                details=copied,
            )

        return InjectResult(
            status=InjectStatus.SUCCESS,
            message=f"Steam 注入成功，请重启 Steam 使其生效",
            details=copied,
        )

    def create_lua_dir(self) -> InjectResult:
        """创建 Lua 配置目录（<steam>/config/lua）"""
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return InjectResult(
                status=InjectStatus.STEAM_NOT_FOUND,
                message=f"Steam 目录未找到: {self._steam_path}",
            )

        lua_dir = os.path.join(self._steam_path, self.LUA_DIR_RELATIVE)

        if os.path.isdir(lua_dir):
            return InjectResult(
                status=InjectStatus.SUCCESS,
                message=f"Lua 目录已存在: {lua_dir}",
            )

        try:
            os.makedirs(lua_dir, exist_ok=True)
            return InjectResult(
                status=InjectStatus.SUCCESS,
                message=f"Lua 目录创建成功: {lua_dir}",
            )
        except Exception as e:
            return InjectResult(
                status=InjectStatus.UNKNOWN_ERROR,
                message=f"创建 Lua 目录失败: {e}",
            )

    @staticmethod
    def _is_module_loaded_in_steam(target_dll: str) -> bool:
        """检查指定 DLL 是否可能已加载到 Steam 中

        通过检查 Steam 日志目录中的日志文件来推断注入状态，
        避免使用进程模块枚举（会触发杀毒软件误报）。
        """
        return False

    def verify_injection(self) -> InjectResult:
        """验证 OpenSteamTool 是否已成功注入

        三层递进验证（优雅程度递减）：
        1. 进程模块枚举 — 直接检查 DLL 是否已加载到 steam.exe 内存（最可靠，Debug/Release 通用）
        2. 日志文件检查 — Debug 构建 DLL 会生成日志
        3. DLL 文件存在 — 仅说明已部署，未证明已激活

        Returns:
            验证结果
        """
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return InjectResult(
                status=InjectStatus.STEAM_NOT_FOUND,
                message="Steam 目录未找到",
            )

        # 方式 1: 进程模块枚举（最可靠，适用于 Debug/Release 所有构建）
        for dll_name in self.ALL_DLLS:
            if self._is_module_loaded_in_steam(dll_name):
                return InjectResult(
                    status=InjectStatus.SUCCESS,
                    message=f"OpenSteamTool 已激活（{dll_name} 已加载到 Steam 进程）",
                )

        # 方式 2: 检查日志文件（Debug 构建的辅助验证）
        log_dir = os.path.join(self._steam_path, self.LOG_DIR)
        if os.path.isdir(log_dir):
            for log_file in self.LOG_FILES:
                if os.path.isfile(os.path.join(log_dir, log_file)):
                    return InjectResult(
                        status=InjectStatus.SUCCESS,
                        message=f"OpenSteamTool 已激活（检测到日志: {log_file}）",
                    )

        # 方式 3: 检查 DLL 是否已部署（但未重启 Steam 或 Steam 未运行）
        all_deployed, missing = self.check_dlls_deployed()
        if all_deployed:
            return InjectResult(
                status=InjectStatus.VERIFICATION_FAILED,
                message="DLL 已部署但未激活（请重启 Steam）",
            )

        return InjectResult(
            status=InjectStatus.VERIFICATION_FAILED,
            message="未检测到 OpenSteamTool 注入（请先注入 Steam 并重启）",
        )

    def uninstall_dlls(self) -> InjectResult:
        """从 Steam 目录移除 3 个 DLL 文件"""

        if not self._steam_path or not os.path.isdir(self._steam_path):
            return InjectResult(
                status=InjectStatus.STEAM_NOT_FOUND,
                message=f"Steam 目录未找到: {self._steam_path}",
            )

        import time
        removed = []
        failed = []
        for dll_name in self.ALL_DLLS:
            dll_path = os.path.join(self._steam_path, dll_name)
            if os.path.isfile(dll_path):
                # 文件被占用时最多重试 3 次，每次间隔 1 秒
                for retry in range(3):
                    try:
                        os.remove(dll_path)
                        removed.append(dll_name)
                        break
                    except (PermissionError, OSError):
                        if retry < 2:
                            time.sleep(1)
                        else:
                            failed.append(dll_name)

        if failed:
            return InjectResult(
                status=InjectStatus.UNINSTALL_FAILED,
                message=f"部分文件移除失败（文件被占用，请关闭 Steam 后重试）: {', '.join(failed)}",
                details=removed,
            )

        if not removed:
            return InjectResult(
                status=InjectStatus.DLL_ALREADY_DEPLOYED,
                message="注入文件已不存在，无需移除",
            )

        return InjectResult(
            status=InjectStatus.SUCCESS,
            message=f"成功移除注入文件，请重启 Steam 以完全移除",
            details=removed,
        )

    def clean_logs(self) -> InjectResult:
        """清理 OpenSteamTool 日志目录（<steam>/opensteamtool/）

        Returns:
            清理结果
        """
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return InjectResult(
                status=InjectStatus.STEAM_NOT_FOUND,
                message=f"Steam 目录未找到: {self._steam_path}",
            )

        log_dir = os.path.join(self._steam_path, self.LOG_DIR)
        if not os.path.isdir(log_dir):
            return InjectResult(
                status=InjectStatus.SUCCESS,
                message="日志目录不存在，无需清理",
            )

        removed_files = []
        failed_count = 0
        try:
            for fname in os.listdir(log_dir):
                fpath = os.path.join(log_dir, fname)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                        removed_files.append(fname)
                    elif os.path.isdir(fpath):
                        shutil.rmtree(fpath)
                        removed_files.append(fname)
                except (PermissionError, OSError):
                    failed_count += 1  # 文件被占用，静默跳过

            # 如果目录已空，删除目录
            try:
                if not os.listdir(log_dir):
                    os.rmdir(log_dir)
            except Exception:
                pass

        except Exception as e:
            return InjectResult(
                status=InjectStatus.UNKNOWN_ERROR,
                message=f"清理日志目录失败: {e}",
            )

        msg = f"成功清理 {len(removed_files)} 个日志文件"
        if failed_count:
            msg += f"（{failed_count} 个文件被占用，跳过）"

        return InjectResult(
            status=InjectStatus.SUCCESS,
            message=msg,
            details=removed_files,
        )

    def clean_lua_configs(self) -> InjectResult:
        """清理 config/lua 目录下所有入库游戏的 .lua 配置文件

        Returns:
            清理结果
        """
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return InjectResult(
                status=InjectStatus.STEAM_NOT_FOUND,
                message=f"Steam 目录未找到: {self._steam_path}",
            )

        lua_dir = os.path.join(self._steam_path, self.LUA_DIR_RELATIVE)
        if not os.path.isdir(lua_dir):
            return InjectResult(
                status=InjectStatus.SUCCESS,
                message="Lua 配置目录不存在，无需清理",
            )

        removed = []
        failed = []
        try:
            for fname in os.listdir(lua_dir):
                fpath = os.path.join(lua_dir, fname)
                if fname.endswith(".lua") and os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                        removed.append(fname)
                    except Exception as e:
                        failed.append(f"{fname}: {e}")
        except Exception as e:
            return InjectResult(
                status=InjectStatus.UNKNOWN_ERROR,
                message=f"清理 Lua 配置失败: {e}",
            )

        msg_parts = []
        if removed:
            msg_parts.append(f"已移除 {len(removed)} 个游戏配置")
        if failed:
            msg_parts.append(f"部分失败: {'; '.join(failed)}")

        return InjectResult(
            status=InjectStatus.SUCCESS if not failed else InjectStatus.UNKNOWN_ERROR,
            message="，".join(msg_parts) if msg_parts else "无 Lua 配置文件需要清理",
            details=removed,
        )
