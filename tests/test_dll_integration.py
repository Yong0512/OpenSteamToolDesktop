"""
测试用例 3: 集成测试 - 测试完整流程

测试目标：
- SteamBridge 集成 DLLManager
- 启动时 DLL 检查流程
- DLL 下载与安装完整流程
- 版本管理完整流程
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from core.dll_manager import DLLManager
from core.steam_bridge import SteamBridge


class TestDLLIntegration:
    """DLL 管理集成测试用例"""

    @pytest.fixture
    def mock_steam_bridge(self):
        """创建 Mock SteamBridge（不调用真实 __init__）"""
        with patch.object(SteamBridge, '__init__', return_value=None):
            bridge = SteamBridge()
            bridge._dll_manager = Mock(spec=DLLManager)
            bridge._dll_source_dir = ""
            bridge._steam_path = "C:\\Program Files (x86)\\Steam"
            yield bridge

    # ===== 测试 3.1: SteamBridge 检查 DLL 更新 =====
    def test_steam_bridge_check_for_dll_updates(self, mock_steam_bridge):
        """测试 3.1: SteamBridge.check_for_dll_updates() 正确调用 DLLManager"""
        # 设置 Mock 返回值
        expected_result = (True, "发现新版本 v1.2.3", {"version": "v1.2.3"})
        mock_steam_bridge._dll_manager.check_for_updates.return_value = expected_result

        # 执行
        result = mock_steam_bridge.check_for_dll_updates()

        # 验证
        assert result == expected_result
        mock_steam_bridge._dll_manager.check_for_updates.assert_called_once()

    # ===== 测试 3.2: SteamBridge 下载并安装 DLL =====
    def test_steam_bridge_download_and_install(self, mock_steam_bridge):
        """测试 3.2: SteamBridge.download_and_install_latest_dll() 完整流程"""
        # Mock check_for_updates 返回有更新
        mock_steam_bridge._dll_manager.check_for_updates.return_value = (
            True,
            "发现新版本",
            {"version": "v1.2.3"},
        )

        # Mock download_and_install 返回成功
        mock_steam_bridge._dll_manager.download_and_install.return_value = (
            True,
            "成功安装版本 v1.2.3",
        )

        # Mock _update_dll_source_from_manager
        mock_steam_bridge._update_dll_source_from_manager = Mock()

        # 执行
        success, msg = mock_steam_bridge.download_and_install_latest_dll()

        # 验证
        assert success is True
        assert "v1.2.3" in msg
        mock_steam_bridge._dll_manager.check_for_updates.assert_called_once()
        mock_steam_bridge._dll_manager.download_and_install.assert_called_once_with(
            {"version": "v1.2.3"}
        )
        mock_steam_bridge._update_dll_source_from_manager.assert_called_once()

    # ===== 测试 3.3: SteamBridge 下载并安装 (无更新) =====
    def test_steam_bridge_download_no_update(self, mock_steam_bridge):
        """测试 3.3: 无可用更新时返回失败"""
        # Mock check_for_updates 返回无更新
        mock_steam_bridge._dll_manager.check_for_updates.return_value = (
            False,
            "已是最新版本",
            None,
        )

        # 执行
        success, msg = mock_steam_bridge.download_and_install_latest_dll()

        # 验证
        assert success is False
        assert "最新" in msg

    # ===== 测试 3.4: 更新 DLL 源目录 =====
    def test_update_dll_source_from_manager(self, mock_steam_bridge):
        """测试 3.4: _update_dll_source_from_manager 正确更新路径"""
        # 设置 Mock DLLManager.get_dll_path 返回值
        mock_dll_path = Mock()
        mock_dll_path.exists.return_value = True
        mock_dll_path.__str__ = Mock(return_value="C:\\dll\\v1.2.3")
        mock_steam_bridge._dll_manager.get_dll_path.return_value = mock_dll_path

        # Mock injector
        mock_steam_bridge._injector = Mock()
        mock_steam_bridge._injector.set_dll_source_dir = Mock()

        # 执行
        mock_steam_bridge._update_dll_source_from_manager()

        # 验证
        mock_steam_bridge._dll_manager.get_dll_path.assert_called_once()
        mock_steam_bridge._injector.set_dll_source_dir.assert_called_once_with(
            "C:\\dll\\v1.2.3"
        )

    # ===== 测试 3.5: 获取 DLLManager 实例 =====
    def test_get_dll_manager(self, mock_steam_bridge):
        """测试 3.5: get_dll_manager() 返回正确的实例"""
        result = mock_steam_bridge.get_dll_manager()
        assert result == mock_steam_bridge._dll_manager

    # ===== 测试 3.6: 版本不匹配检查 (封装测试) =====
    def test_check_dll_version_mismatch(self, mock_steam_bridge):
        """测试 3.6: check_dll_version_mismatch() 正确封装 DLLInjector"""
        # Mock injector
        mock_steam_bridge._injector = Mock()
        mock_steam_bridge._injector.check_dll_version_mismatch.return_value = (
            True,
            ["OpenSteamTool.dll"],
        )

        # 执行
        mismatch, dlls = mock_steam_bridge.check_dll_version_mismatch()

        # 验证
        assert mismatch is True
        assert "OpenSteamTool.dll" in dlls

    # ===== 测试 3.7: 完整流程 - 检测更新 → 下载 → 安装 → 更新注入器 =====
    @patch('core.dll_manager.GitHubReleases')
    def test_full_workflow_check_download_install(self, mock_github_class, tmp_path):
        """测试 3.7: 完整工作流程集成测试"""
        # 这个测试验证各个组件协同工作
        # 由于涉及真实文件系统操作，使用临时目录

        # 创建测试环境
        dll_dir = tmp_path / "DLL"
        dll_dir.mkdir()

        # 初始化 DLLManager（部分真实，部分 Mock）
        with patch('core.dll_manager.PathManager') as mock_path_manager:
            mock_path_manager.base_dir.return_value = tmp_path
            manager = DLLManager()

            # Mock GitHubReleases 的行为
            mock_github = Mock()
            mock_github.get_latest_release_info.return_value = {
                "version": "v1.2.3",
                "tag_name": "v1.2.3",
                "assets": [
                    {
                        "name": "OpenSteamTool-x64.zip",
                        "browser_download_url": "https://example.com/download.zip",
                    }
                ],
            }
            mock_github.get_asset_download_url.return_value = "https://example.com/download.zip"
            mock_github.download_asset.return_value = True

            # Mock extract_dll_from_zip 创建真实文件
            def mock_extract(zip_path, extract_dir):
                extract_dir.mkdir(parents=True, exist_ok=True)
                (extract_dir / "OpenSteamTool.dll").write_bytes(b"fake")
                (extract_dir / "dwmapi.dll").write_bytes(b"fake")
                (extract_dir / "xinput1_4.dll").write_bytes(b"fake")
                return ["OpenSteamTool.dll", "dwmapi.dll", "xinput1_4.dll"]

            mock_github.extract_dll_from_zip.side_effect = mock_extract
            manager._github = mock_github

            # 1. 检查更新
            update_available, msg, version_info = manager.check_for_updates()
            assert update_available is True
            assert version_info["version"] == "v1.2.3"

            # 2. 下载并安装
            success, install_msg = manager.download_and_install(version_info)
            assert success is True

            # 3. 验证安装
            assert manager.get_current_version() == "v1.2.3"
            version_dir = manager.get_version_dir("v1.2.3")
            assert (version_dir / "OpenSteamTool.dll").exists()

            manager.close()
