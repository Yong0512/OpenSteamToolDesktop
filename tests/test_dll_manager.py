"""
测试用例 2: 测试 DLLManager 类

测试目标：
- 获取 DLL 目录
- 获取当前版本
- 检查更新
- 下载并安装 DLL
- 版本比较逻辑
- 版本目录管理
"""

import pytest
import json
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from core.dll_manager import DLLManager, DLL_DIR_NAME, VERSION_PATTERN


class TestDLLManager:
    """DLLManager 类测试用例"""

    @pytest.fixture
    def manager(self, tmp_path):
        """创建 DLLManager 实例，使用临时目录"""
        # 不 Mock __init__，而是创建真实实例但替换部分属性
        import sys
        from PyQt6.QtCore import QObject

        # 创建真实实例（会调用 QObject.__init__）
        mgr = DLLManager()

        # 替换 _dll_dir 和 _current_version_file 到临时目录
        mgr._dll_dir = tmp_path / DLL_DIR_NAME
        mgr._dll_dir.mkdir(parents=True, exist_ok=True)
        mgr._current_version_file = mgr._dll_dir / "current_version.json"

        # Mock _github 以避免真实网络请求
        mgr._github = Mock()

        yield mgr
        mgr.close()

    # ===== 测试 2.1: 获取 DLL 目录 =====
    def test_get_dll_dir(self, manager):
        """测试 2.1: 获取 DLL 根目录"""
        result = manager.get_dll_dir()
        assert result == manager._dll_dir

    # ===== 测试 2.2: 获取版本目录 =====
    def test_get_version_dir(self, manager):
        """测试 2.2: 获取指定版本的 DLL 目录"""
        # 测试带 v 前缀
        result = manager.get_version_dir("v1.2.3")
        assert result == manager._dll_dir / "v1.2.3"

        # 测试不带 v 前缀（应自动添加）
        result = manager.get_version_dir("1.2.3")
        assert result == manager._dll_dir / "v1.2.3"

    # ===== 测试 2.3: 获取当前版本 (未设置) =====
    def test_get_current_version_not_set(self, manager):
        """测试 2.3: 未设置当前版本时返回空字符串"""
        result = manager.get_current_version()
        assert result == ""

    # ===== 测试 2.4: 获取当前版本 (已设置) =====
    def test_get_current_version_set(self, manager):
        """测试 2.4: 已设置当前版本时返回版本号"""
        # 写入版本文件
        version_data = {"version": "v1.2.3"}
        manager._current_version_file.write_text(
            json.dumps(version_data),
            encoding="utf-8",
        )

        result = manager.get_current_version()
        assert result == "v1.2.3"

    # ===== 测试 2.5: 获取当前版本 (文件损坏) =====
    def test_get_current_version_corrupt_file(self, manager):
        """测试 2.5: 版本文件损坏时返回空字符串"""
        # 写入无效 JSON
        manager._current_version_file.write_text("not json", encoding="utf-8")

        result = manager.get_current_version()
        assert result == ""

    # ===== 测试 2.6: 设置当前版本 =====
    def test_set_current_version(self, manager):
        """测试 2.6: 成功设置当前版本"""
        result = manager.set_current_version("v1.2.3")

        assert result is True
        assert manager._current_version_file.exists()

        # 验证文件内容
        data = json.loads(manager._current_version_file.read_text(encoding="utf-8"))
        assert data["version"] == "v1.2.3"

    # ===== 测试 2.7: 获取本地最新版本 (无版本) =====
    def test_get_latest_local_version_none(self, manager):
        """测试 2.7: 本地未安装任何版本时返回空字符串"""
        result = manager.get_latest_local_version()
        assert result == ""

    # ===== 测试 2.8: 获取本地最新版本 (有版本) =====
    def test_get_latest_local_version_with_versions(self, manager):
        """测试 2.8: 本地有多个版本时返回最新版本"""
        # 创建版本目录
        (manager._dll_dir / "v1.0.0").mkdir()
        (manager._dll_dir / "v1.2.3").mkdir()
        (manager._dll_dir / "v1.2.0").mkdir()
        (manager._dll_dir / "not_a_version").mkdir()  # 应被忽略

        result = manager.get_latest_local_version()
        assert result == "v1.2.3"

    # ===== 测试 2.9: 版本比较逻辑 =====
    def test_compare_versions(self, manager):
        """测试 2.9: 版本号比较逻辑"""
        # v1 > v2
        assert manager._compare_versions("v1.2.3", "v1.2.2") == 1
        assert manager._compare_versions("v2.0.0", "v1.9.9") == 1

        # v1 == v2
        assert manager._compare_versions("v1.2.3", "v1.2.3") == 0
        assert manager._compare_versions("1.2.3", "v1.2.3") == 0  # 无 v 前缀

        # v1 < v2
        assert manager._compare_versions("v1.2.2", "v1.2.3") == -1
        assert manager._compare_versions("v1.0.0", "v1.0.1") == -1

    # ===== 测试 2.10: 解析版本号 =====
    def test_parse_version(self, manager):
        """测试 2.10: 版本号解析为元组"""
        assert manager._parse_version("v1.2.3") == (1, 2, 3)
        assert manager._parse_version("1.2.3") == (1, 2, 3)
        assert manager._parse_version("invalid") == (0, 0, 0)

    # ===== 测试 2.11: 检查更新 (有新版本) =====
    def test_check_for_updates_new_version(self, manager):
        """测试 2.11: 远程有新版本"""
        # Mock GitHubReleases.get_latest_release_info
        manager._github.get_latest_release_info.return_value = {
            "version": "v1.2.3",
            "tag_name": "v1.2.3",
            "assets": [],
        }

        # 本地无版本
        update_available, msg, version_info = manager.check_for_updates()

        assert update_available is True
        assert "v1.2.3" in msg
        assert version_info["version"] == "v1.2.3"

    # ===== 测试 2.12: 检查更新 (已是最新) =====
    def test_check_for_updates_latest(self, manager):
        """测试 2.12: 本地已是最新版本"""
        # Mock GitHubReleases.get_latest_release_info
        manager._github.get_latest_release_info.return_value = {
            "version": "v1.2.3",
            "tag_name": "v1.2.3",
            "assets": [],
        }

        # 设置本地版本为 v1.2.3
        manager.set_current_version("v1.2.3")

        update_available, msg, version_info = manager.check_for_updates()

        assert update_available is False
        assert "最新" in msg

    # ===== 测试 2.13: 检查更新 (API 失败) =====
    def test_check_for_updates_api_fails(self, manager):
        """测试 2.13: 无法获取远程版本信息"""
        manager._github.get_latest_release_info.return_value = None

        update_available, msg, version_info = manager.check_for_updates()

        assert update_available is False
        assert "无法获取" in msg
        assert version_info is None

    # ===== 测试 2.14: 下载并安装 (首次安装) =====
    def test_download_and_install_first_time(self, manager, tmp_path):
        """测试 2.14: 首次下载并安装 DLL"""
        version_info = {
            "version": "v1.2.3",
            "assets": [
                {
                    "name": "OpenSteamTool-x64.zip",
                    "browser_download_url": "https://example.com/download.zip",
                }
            ],
        }

        # Mock 下载成功
        zip_path = manager.get_version_dir("v1.2.3") / "download.zip"
        manager._github.download_asset.return_value = True

        # Mock ZIP 提取
        def mock_extract(zip_path, extract_dir):
            # 创建模拟的 DLL 文件
            extract_dir.mkdir(parents=True, exist_ok=True)
            (extract_dir / "OpenSteamTool.dll").write_bytes(b"fake")
            (extract_dir / "dwmapi.dll").write_bytes(b"fake")
            (extract_dir / "xinput1_4.dll").write_bytes(b"fake")
            return ["OpenSteamTool.dll", "dwmapi.dll", "xinput1_4.dll"]

        manager._github.extract_dll_from_zip.side_effect = mock_extract

        # 执行下载安装
        success, msg = manager.download_and_install(version_info)

        assert success is True
        assert "v1.2.3" in msg
        assert manager.get_current_version() == "v1.2.3"

    # ===== 测试 2.15: 下载并安装 (版本已存在且完整) =====
    def test_download_and_install_already_installed(self, manager):
        """测试 2.15: 版本已安装且完整，跳过下载"""
        version_info = {
            "version": "v1.2.3",
            "assets": [],
        }

        # 创建已安装的版本目录和 DLL 文件
        version_dir = manager.get_version_dir("v1.2.3")
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "OpenSteamTool.dll").write_bytes(b"fake")
        (version_dir / "dwmapi.dll").write_bytes(b"fake")
        (version_dir / "xinput1_4.dll").write_bytes(b"fake")

        success, msg = manager.download_and_install(version_info)

        assert success is True
        assert "已安装" in msg

    # ===== 测试 2.16: 下载并安装 (下载失败) =====
    def test_download_and_install_download_fails(self, manager):
        """测试 2.16: 下载失败"""
        version_info = {
            "version": "v1.2.3",
            "assets": [
                {"name": "test.zip", "browser_download_url": "url"},
            ],
        }

        manager._github.download_asset.return_value = False

        success, msg = manager.download_and_install(version_info)

        assert success is False
        assert "下载失败" in msg

    # ===== 测试 2.17: 下载并安装 (ZIP 中无 DLL) =====
    def test_download_and_install_no_dll_in_zip(self, manager):
        """测试 2.17: ZIP 文件中未找到 DLL"""
        version_info = {
            "version": "v1.2.3",
            "assets": [
                {"name": "test.zip", "browser_download_url": "url"},
            ],
        }

        manager._github.download_asset.return_value = True
        manager._github.extract_dll_from_zip.return_value = []  # 无 DLL

        success, msg = manager.download_and_install(version_info)

        assert success is False
        assert "未找到 DLL" in msg

    # ===== 测试 2.18: 下载并安装 (缺少必需 DLL) =====
    def test_download_and_install_missing_required_dll(self, manager):
        """测试 2.18: 解压后缺少必需的 DLL"""
        version_info = {
            "version": "v1.2.3",
            "assets": [],
        }

        manager._github.download_asset.return_value = True

        # 只提取了部分 DLL
        def mock_extract(zip_path, extract_dir):
            extract_dir.mkdir(parents=True, exist_ok=True)
            (extract_dir / "OpenSteamTool.dll").write_bytes(b"fake")
            # 缺少 dwmapi.dll 和 xinput1_4.dll
            return ["OpenSteamTool.dll"]

        manager._github.extract_dll_from_zip.side_effect = mock_extract

        success, msg = manager.download_and_install(version_info)

        assert success is False
        assert "缺少" in msg

    # ===== 测试 2.19: 获取 DLL 路径 (有当前版本) =====
    def test_get_dll_path_with_current_version(self, manager):
        """测试 2.19: 获取当前应使用的 DLL 路径（有当前版本）"""
        # 设置当前版本
        manager.set_current_version("v1.2.3")

        # 创建版本目录和 DLL
        version_dir = manager.get_version_dir("v1.2.3")
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "OpenSteamTool.dll").write_bytes(b"fake")
        (version_dir / "dwmapi.dll").write_bytes(b"fake")
        (version_dir / "xinput1_4.dll").write_bytes(b"fake")

        result = manager.get_dll_path()
        assert result == version_dir

    # ===== 测试 2.20: 获取 DLL 路径 (无当前版本，回退最新) =====
    def test_get_dll_path_fallback_to_latest(self, manager):
        """测试 2.20: 无当前版本时回退到最新本地版本"""
        # 创建最新版本目录
        version_dir = manager.get_version_dir("v1.2.3")
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "OpenSteamTool.dll").write_bytes(b"fake")
        (version_dir / "dwmapi.dll").write_bytes(b"fake")
        (version_dir / "xinput1_4.dll").write_bytes(b"fake")

        result = manager.get_dll_path()
        assert result == version_dir

    # ===== 测试 2.21: 获取 DLL 路径 (无任何版本) =====
    def test_get_dll_path_no_versions(self, manager):
        """测试 2.21: 无任何版本时返回空路径"""
        result = manager.get_dll_path()
        assert result == Path()

    # ===== 测试 2.22: 检查 DLL 版本 (文件不存在) =====
    def test_check_dll_version_file_not_exists(self, manager):
        """测试 2.22: DLL 文件不存在时返回 'unknown'"""
        result = manager.check_dll_version(Path("nonexistent.dll"))
        assert result == "unknown"

    # ===== 测试 2.23: 有效版本目录名验证 =====
    def test_is_valid_version_dir(self, manager):
        """测试 2.23: 版本目录名验证"""
        # 有效目录名
        assert manager._is_valid_version_dir("v1.2.3") is True
        assert manager._is_valid_version_dir("1.2.3") is True
        assert manager._is_valid_version_dir("v0.0.1") is True
        assert manager._is_valid_version_dir("v999.999.999") is True

        # 无效目录名
        assert manager._is_valid_version_dir("v1.2") is False  # 只有 2 段
        assert manager._is_valid_version_dir("invalid") is False
        assert manager._is_valid_version_dir("v1.2.3.4") is False  # 4 段
        assert manager._is_valid_version_dir("not_a_version") is False
        assert manager._is_valid_version_dir("") is False
