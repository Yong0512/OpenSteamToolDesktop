from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from enum import Enum, auto

from utils.logger import setup_logger

logger = setup_logger(__name__)
class InjectStatus(Enum):
    SUCCESS = auto()
    STEAM_NOT_FOUND = auto()
    DLL_SOURCE_NOT_FOUND = auto()
    DLL_ALREADY_DEPLOYED = auto()
    DEPLOY_FAILED = auto()
    VERIFICATION_FAILED = auto()
    UNINSTALL_FAILED = auto()
    UNKNOWN_ERROR = auto()

@dataclass
class InjectResult:
    status: InjectStatus
    message: str = ""
    details: list[str] | None = None

class DLLInjector:

    DWM_DLL = "dwmapi.dll"
    XINPUT_DLL = "xinput1_4.dll"
    CORE_DLL = "OpenSteamTool.dll"
    ALL_DLLS = (CORE_DLL, DWM_DLL, XINPUT_DLL)

    LUA_DIR_RELATIVE = "config/lua"

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
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return False, list(self.ALL_DLLS)

        missing = []
        for dll_name in self.ALL_DLLS:
            dll_path = os.path.join(self._steam_path, dll_name)
            if not os.path.isfile(dll_path):
                missing.append(dll_name)

        return len(missing) == 0, missing

    def check_lua_dir(self) -> bool:
        if not self._steam_path:
            return False
        lua_dir = os.path.join(self._steam_path, self.LUA_DIR_RELATIVE)
        return os.path.isdir(lua_dir)

    def deploy_dlls(self) -> InjectResult:
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
        return False

    def verify_injection(self) -> InjectResult:
        if not self._steam_path or not os.path.isdir(self._steam_path):
            return InjectResult(
                status=InjectStatus.STEAM_NOT_FOUND,
                message="Steam 目录未找到",
            )

        for dll_name in self.ALL_DLLS:
            if self._is_module_loaded_in_steam(dll_name):
                return InjectResult(
                    status=InjectStatus.SUCCESS,
                    message=f"OpenSteamTool 已激活（{dll_name} 已加载到 Steam 进程）",
                )

        log_dir = os.path.join(self._steam_path, self.LOG_DIR)
        if os.path.isdir(log_dir):
            for log_file in self.LOG_FILES:
                if os.path.isfile(os.path.join(log_dir, log_file)):
                    return InjectResult(
                        status=InjectStatus.SUCCESS,
                        message=f"OpenSteamTool 已激活（检测到日志: {log_file}）",
                    )

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
                    failed_count += 1

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
