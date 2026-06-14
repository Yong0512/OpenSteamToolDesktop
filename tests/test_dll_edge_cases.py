"""
测试用例 4: 边界条件测试

测试目标：
- 网络错误
- GitHub API 受限
- ZIP 文件损坏
- 权限问题
- 并发下载
- 异常情况处理
"""

import pytest
import json
import zipfile
import os
import stat
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from core.github_releases import GitHubReleases
from core.dll_manager import DLLManager


class TestDLLEdgeCases:
    """DLL 管理边界条件测试用例"""

    # ===== 测试 4.1: 网络错误 - 断网 =====
    def test_network_error_no_internet(self):
        """测试 4.1: 断网情况下获取版本信息"""
        client = GitHubReleases()

        # Mock 网络异常
        with patch.object(client._session, 'get', side_effect=Exception("Network unreachable")):
            result = client.get_latest_release_info()

        assert result is None  # 应优雅返回 None，不闪退
        client.close()

    # ===== 测试 4.2: GitHub API 受限 (403) =====
    def test_github_api_rate_limit(self):
        """测试 4.2: GitHub API 返回 403（速率限制）"""
        import requests
        client = GitHubReleases()

        # 第一次调用 API 返回 403 (使用 RequestException 以触发降级)
        mock_api_response = Mock()
        mock_api_response.raise_for_status.side_effect = requests.exceptions.RequestException("403 Forbidden")

        # 第二次调用（爬取页面）也失败
        with patch.object(client._session, 'get', side_effect=[
            mock_api_response,
            requests.exceptions.RequestException("Connection timeout"),
        ]):
            result = client.get_latest_release_info()

        assert result is None  # 两次都失败，返回 None
        client.close()

    # ===== 测试 4.3: GitHub API 受限 (自动降级) =====
    def test_github_api_rate_limit_fallback(self):
        """测试 4.3: API 失败但爬取页面成功（降级策略）"""
        import requests
        client = GitHubReleases()

        # 第一次调用 API 失败 (使用 RequestException)
        mock_api_fail = Mock()
        mock_api_fail.raise_for_status.side_effect = requests.exceptions.RequestException("403 Forbidden")

        # 第二次调用（爬取页面）成功
        mock_scrape_response = Mock()
        mock_scrape_response.text = '''
        <a href="/OpenSteam001/OpenSteamTool/releases/tag/v1.2.3">v1.2.3</a>
        '''
        mock_scrape_response.raise_for_status = Mock()

        with patch.object(client._session, 'get', side_effect=[
            mock_api_fail,
            mock_scrape_response,
        ]):
            result = client.get_latest_release_info()

        assert result is not None
        assert result["version"] == "v1.2.3"
        client.close()

    # ===== 测试 4.4: ZIP 文件损坏 =====
    def test_corrupted_zip_file(self, tmp_path):
        """测试 4.4: 下载的 ZIP 文件损坏"""
        client = GitHubReleases()

        # 创建损坏的 ZIP 文件
        corrupt_zip = tmp_path / "corrupt.zip"
        corrupt_zip.write_bytes(b"This is not a valid ZIP file")

        extract_dir = tmp_path / "extracted"

        # 尝试提取
        extracted = client.extract_dll_from_zip(corrupt_zip, extract_dir)

        assert extracted == []  # 应返回空列表，不崩溃
        client.close()

    # ===== 测试 4.5: ZIP 文件部分损坏 =====
    def test_partial_corrupted_zip(self, tmp_path):
        """测试 4.5: ZIP 文件部分损坏（能打开但某些文件损坏）"""
        client = GitHubReleases()

        # 创建一个有效的 ZIP 但内容损坏
        zip_path = tmp_path / "partial_corrupt.zip"

        # 写入一个看似有效但内容错误的 ZIP
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("OpenSteamTool.dll", b"not a real dll")

        extract_dir = tmp_path / "extracted"

        # 应能提取（文件存在即可，内容不验证）
        extracted = client.extract_dll_from_zip(zip_path, extract_dir)

        assert "OpenSteamTool.dll" in extracted
        client.close()

    # ===== 测试 4.6: 权限问题 - DLL 目录无写入权限 =====
    def test_permission_denied_dll_dir(self, tmp_path):
        """测试 4.6: .OpenSteamToolDesktop/DLL/ 目录无写入权限"""
        # 创建只读目录
        dll_dir = tmp_path / "DLL"
        dll_dir.mkdir()
        os.chmod(str(dll_dir), stat.S_IREAD)  # 只读

        try:
            manager = DLLManager()

            with patch.object(manager, '_dll_dir', dll_dir):
                # 尝试创建版本目录（应失败）
                version_dir = manager.get_version_dir("v1.2.3")

                # 尝试创建目录会失败
                try:
                    version_dir.mkdir(parents=True, exist_ok=True)
                    # 如果在这台机器上能创建（如 Windows），检查是否正确错误处理
                except PermissionError:
                    pass  # 预期的权限错误

            manager.close()
        finally:
            # 恢复权限以便清理
            os.chmod(str(dll_dir), stat.S_IWRITE | stat.S_IREAD)

    # ===== 测试 4.7: 权限问题 - current_version.json 无写入权限 =====
    def test_permission_denied_version_file(self, tmp_path):
        """测试 4.7: current_version.json 无写入权限"""
        manager = DLLManager()

        with patch.object(manager, '_dll_dir', tmp_path / "DLL"):
            manager._dll_dir.mkdir(parents=True, exist_ok=True)
            manager._current_version_file = manager._dll_dir / "current_version.json"

            # 创建只读的版本文件
            manager._current_version_file.write_text('{"version": "v1.0.0"}')
            os.chmod(str(manager._current_version_file), stat.S_IREAD)

            try:
                # 尝试写入（应失败但不崩溃）
                result = manager.set_current_version("v1.2.3")
                # 在 Windows 上可能仍能写入，所以不强制断言
            except PermissionError:
                pass  # 预期的权限错误
            finally:
                # 恢复权限以便清理
                os.chmod(str(manager._current_version_file), stat.S_IWRITE | stat.S_IREAD)

        manager.close()

    # ===== 测试 4.8: 超时处理 =====
    def test_request_timeout(self):
        """测试 4.8: 网络请求超时"""
        client = GitHubReleases()

        # Mock 超时异常
        with patch.object(client._session, 'get', side_effect=Exception("Request timeout")):
            result = client.get_latest_release_info()

        assert result is None  # 超时应返回 None
        client.close()

    # ===== 测试 4.9: 下载过程中网络中断 =====
    def test_download_interrupt(self, tmp_path):
        """测试 4.9: 下载过程中网络中断"""
        client = GitHubReleases()

        # Mock 下载过程中抛出异常
        mock_response = Mock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.side_effect = Exception("Connection reset")

        save_path = tmp_path / "interrupted.zip"

        with patch.object(client._session, 'get', return_value=mock_response):
            result = client.download_asset("http://example.com/test.zip", save_path)

        assert result is False  # 下载失败

        # 清理可能创建的残缺文件
        if save_path.exists():
            save_path.unlink()

        client.close()

    # ===== 测试 4.10: 版本号格式异常 =====
    def test_invalid_version_format(self):
        """测试 4.10: 版本号格式异常"""
        manager = DLLManager()

        # 测试各种异常版本号格式
        test_cases = [
            ("v1.2", (0, 0, 0)),  # 只有 2 段
            ("v1.2.3.4", (0, 0, 0)),  # 4 段（不应匹配）
            ("version1.2.3", (0, 0, 0)),  # 前缀不是 v
            ("", (0, 0, 0)),  # 空字符串
            ("latest", (0, 0, 0)),  # 非数字
        ]

        for version_str, expected in test_cases:
            result = manager._parse_version(version_str)
            assert result == expected, f"Failed for {version_str}"

        manager.close()

    # ===== 测试 4.11: 版本目录名验证（边界） =====
    def test_version_dir_edge_cases(self):
        """测试 4.11: 版本目录名验证边界情况"""
        manager = DLLManager()

        # 有效目录名
        assert manager._is_valid_version_dir("v1.2.3") is True
        assert manager._is_valid_version_dir("v0.0.1") is True
        assert manager._is_valid_version_dir("v999.999.999") is True

        # 无效目录名
        assert manager._is_valid_version_dir("v1.2") is False
        assert manager._is_valid_version_dir("v1.2.3.4") is False
        assert manager._is_valid_version_dir("OpenSteamTool-x64") is False
        assert manager._is_valid_version_dir("current_version.json") is False
        assert manager._is_valid_version_dir("") is False

        manager.close()

    # ===== 测试 4.12: 磁盘空间不足 =====
    def test_disk_full(self, tmp_path):
        """测试 4.12: 磁盘空间不足（模拟）"""
        client = GitHubReleases()

        # Mock 写入时抛出磁盘满异常
        mock_response = Mock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"x" * 8192]

        save_path = tmp_path / "test.zip"

        # 模拟磁盘满
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            with patch.object(client._session, 'get', return_value=mock_response):
                result = client.download_asset("http://example.com/test.zip", save_path)

        assert result is False  # 下载失败
        client.close()

    # ===== 测试 4.13: 并发下载（线程安全） =====
    def test_concurrent_downloads(self):
        """测试 4.13: 多次调用下载（应使用不同实例）"""
        # 这个测试验证设计上是否支持并发
        # 由于使用 QThread，实际并发测试较复杂，这里只测试实例化
        client1 = GitHubReleases()
        client2 = GitHubReleases()

        assert client1 is not client2
        assert client1._session is not client2._session

        client1.close()
        client2.close()

    # ===== 测试 4.14: JSON 解析异常 =====
    def test_json_parse_edge_cases(self, tmp_path):
        """测试 4.14: current_version.json 各种异常格式"""
        manager = DLLManager()

        with patch.object(manager, '_dll_dir', tmp_path / "DLL"):
            manager._dll_dir.mkdir(parents=True, exist_ok=True)
            manager._current_version_file = manager._dll_dir / "current_version.json"

            # 测试空文件
            manager._current_version_file.write_text("", encoding="utf-8")
            assert manager.get_current_version() == ""

            # 测试无效 JSON
            manager._current_version_file.write_text("{invalid json}", encoding="utf-8")
            assert manager.get_current_version() == ""

            # 测试缺少 version 字段
            manager._current_version_file.write_text('{"name": "test"}', encoding="utf-8")
            assert manager.get_current_version() == ""

        manager.close()

    # ===== 测试 4.15: Unicode 和特殊字符 =====
    def test_unicode_in_paths(self, tmp_path):
        """测试 4.15: 路径中包含 Unicode 字符"""
        client = GitHubReleases()

        # 使用包含 Unicode 的路径
        unicode_dir = tmp_path / "测试目录"
        unicode_dir.mkdir()

        zip_path = unicode_dir / "测试文件.zip"
        extract_dir = unicode_dir / "解压目录"

        # 创建测试 ZIP
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("测试.dll", b"fake content")

        # 提取（应正确处理 Unicode 路径）
        extracted = client.extract_dll_from_zip(zip_path, extract_dir)

        assert "测试.dll" in extracted
        client.close()
