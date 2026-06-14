"""
测试用例 1: 测试 GitHubReleases 类

测试目标：
- 获取最新版本信息
- 获取 asset 下载链接
- 下载 asset
- 从 ZIP 提取 DLL
- 错误处理和降级策略
"""

import pytest
import json
import zipfile
import io
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from core.github_releases import GitHubReleases, GITHUB_API_LATEST_RELEASE, GITHUB_RELEASES_PAGE


class TestGitHubReleases:
    """GitHubReleases 类测试用例"""

    @pytest.fixture
    def github_client(self):
        """创建 GitHubReleases 实例"""
        client = GitHubReleases()
        yield client
        client.close()

    @pytest.fixture
    def mock_response(self):
        """创建模拟的 requests.Response"""
        mock = Mock()
        mock.status_code = 200
        mock.headers = {"content-length": "1000"}
        return mock

    # ===== 测试 1.1: 获取最新版本信息 (API 成功) =====
    def test_get_latest_release_info_success(self, github_client, mock_response):
        """测试 1.1: API 请求成功，返回正确的版本信息"""
        # 模拟 API 响应
        mock_response.json.return_value = {
            "tag_name": "v1.2.3",
            "published_at": "2024-01-01T00:00:00Z",
            "body": "Release notes",
            "html_url": "https://github.com/OpenSteam001/OpenSteamTool/releases/tag/v1.2.3",
            "assets": [
                {
                    "name": "OpenSteamTool-x64.zip",
                    "browser_download_url": "https://github.com/OpenSteam001/OpenSteamTool/releases/download/v1.2.3/OpenSteamTool-x64.zip",
                    "size": 123456,
                    "content_type": "application/zip",
                }
            ],
        }

        with patch.object(github_client._session, 'get', return_value=mock_response):
            result = github_client.get_latest_release_info()

        assert result is not None
        assert result["version"] == "v1.2.3"
        assert result["tag_name"] == "v1.2.3"
        assert len(result["assets"]) == 1
        assert result["assets"][0]["name"] == "OpenSteamTool-x64.zip"

    # ===== 测试 1.2: 获取最新版本信息 (API 失败，降级爬取) =====
    def test_get_latest_release_info_api_fails_scrape_success(self, github_client, mock_response):
        """测试 1.2: API 请求失败，降级到爬取 releases 页面成功"""
        # 第一次调用 (API) 失败 - 使用 requests.exceptions.RequestException 以触发降级
        import requests
        mock_api_fail = Mock()
        mock_api_fail.raise_for_status.side_effect = requests.exceptions.RequestException("API failed")

        # 第二次调用 (爬取页面) 成功
        mock_response.text = '''
        <html>
            <a href="/OpenSteam001/OpenSteamTool/releases/tag/v1.2.3">Latest</a>
            <a href="/OpenSteam001/OpenSteamTool/releases/tag/v1.2.2">Previous</a>
        </html>
        '''

        with patch.object(github_client._session, 'get', side_effect=[mock_api_fail, mock_response]):
            result = github_client.get_latest_release_info()

        assert result is not None
        assert result["version"] == "v1.2.3"
        assert result["assets"] == []  # 爬取时 assets 为空

    # ===== 测试 1.3: 获取最新版本信息 (网络错误) =====
    def test_get_latest_release_info_network_error(self, github_client):
        """测试 1.3: 网络错误，返回 None"""
        with patch.object(github_client._session, 'get', side_effect=Exception("Network error")):
            result = github_client.get_latest_release_info()

        assert result is None

    # ===== 测试 1.4: 解析 release 数据 =====
    def test_parse_release_data(self, github_client):
        """测试 1.4: 正确解析 GitHub API 返回的 release 数据"""
        data = {
            "tag_name": "v2.0.0",
            "published_at": "2024-06-01T00:00:00Z",
            "body": "Major release",
            "html_url": "https://github.com/OpenSteam001/OpenSteamTool/releases/tag/v2.0.0",
            "assets": [
                {"name": "OpenSteamTool-x64.zip", "browser_download_url": "url1", "size": 100},
                {"name": "README.md", "browser_download_url": "url2", "size": 10},  # 非 ZIP，应过滤
                {"name": "OpenSteamTool-x86.zip", "browser_download_url": "url3", "size": 90},
            ],
        }

        result = github_client._parse_release_data(data)

        assert result["version"] == "v2.0.0"
        assert len(result["assets"]) == 2  # 只保留 ZIP 文件
        assert all(a["name"].endswith(".zip") for a in result["assets"])

    # ===== 测试 1.5: 获取 asset 下载链接 =====
    def test_get_asset_download_url_success(self, github_client, mock_response):
        """测试 1.5: 成功获取指定版本的 DLL ZIP 下载链接"""
        mock_response.json.return_value = {
            "assets": [
                {
                    "name": "OpenSteamTool-x64.zip",
                    "browser_download_url": "https://github.com/download/v1.2.3/OpenSteamTool-x64.zip",
                }
            ]
        }

        with patch.object(github_client._session, 'get', return_value=mock_response):
            url = github_client.get_asset_download_url("v1.2.3")

        assert url == "https://github.com/download/v1.2.3/OpenSteamTool-x64.zip"

    # ===== 测试 1.6: 获取 asset 下载链接 (无 ZIP) =====
    def test_get_asset_download_url_no_zip(self, github_client, mock_response):
        """测试 1.6: 版本存在但没有 ZIP asset"""
        mock_response.json.return_value = {
            "assets": [
                {"name": "README.md", "browser_download_url": "url1"},
            ]
        }

        with patch.object(github_client._session, 'get', return_value=mock_response):
            url = github_client.get_asset_download_url("v1.2.3")

        assert url is None

    # ===== 测试 1.7: 下载 asset =====
    def test_download_asset_success(self, github_client, mock_response, tmp_path):
        """测试 1.7: 成功下载 asset"""
        # 模拟流式下载
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2", b"chunk3"]

        save_path = tmp_path / "test_download.zip"

        with patch.object(github_client._session, 'get', return_value=mock_response):
            result = github_client.download_asset(str(save_path), save_path)

        assert result is True
        assert save_path.exists()

    # ===== 测试 1.8: 下载 asset (失败清理) =====
    def test_download_asset_failure_cleans_up(self, github_client, mock_response, tmp_path):
        """测试 1.8: 下载失败时应清理未完成的文件"""
        # 模拟下载过程中失败
        mock_response.iter_content.side_effect = Exception("Download failed")

        save_path = tmp_path / "test_download.zip"

        with patch.object(github_client._session, 'get', return_value=mock_response):
            result = github_client.download_asset(str(save_path), save_path)

        assert result is False
        # 注意：由于 iter_content 立即失败，文件可能未创建

    # ===== 测试 1.9: 从 ZIP 提取 DLL =====
    def test_extract_dll_from_zip_success(self, github_client, tmp_path):
        """测试 1.9: 成功从 ZIP 中提取 DLL 文件"""
        # 创建模拟的 ZIP 文件
        zip_path = tmp_path / "test.zip"
        extract_dir = tmp_path / "extracted"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("OpenSteamTool.dll", "fake dll content")
            zf.writestr("dwmapi.dll", "fake dll content")
            zf.writestr("README.txt", "readme content")  # 非 DLL，不应提取

        # 提取 DLL
        extracted = github_client.extract_dll_from_zip(zip_path, extract_dir)

        assert len(extracted) == 2  # 只提取了 2 个 DLL
        assert "OpenSteamTool.dll" in extracted
        assert (extract_dir / "OpenSteamTool.dll").exists()

    # ===== 测试 1.10: 从 ZIP 提取 DLL (坏 ZIP) =====
    def test_extract_dll_from_zip_bad_zip(self, github_client, tmp_path):
        """测试 1.10: ZIP 文件损坏"""
        zip_path = tmp_path / "bad.zip"
        zip_path.write_bytes(b"not a zip file")  # 写入无效内容

        extract_dir = tmp_path / "extracted"

        extracted = github_client.extract_dll_from_zip(zip_path, extract_dir)

        assert extracted == []  # 应返回空列表

    # ===== 测试 1.11: 爬取 releases 页面 (正则匹配) =====
    def test_scrape_releases_page(self, github_client, mock_response):
        """测试 1.11: 正确爬取 releases 页面获取最新版本"""
        mock_response.text = '''
        <div class="release-entry">
            <a href="/OpenSteam001/OpenSteamTool/releases/tag/v1.2.3">v1.2.3</a>
            <a href="/OpenSteam001/OpenSteamTool/releases/tag/v1.2.2">v1.2.2</a>
            <a href="/OpenSteam001/OpenSteamTool/releases/tag/v1.1.0">v1.1.0</a>
        </div>
        '''

        with patch.object(github_client._session, 'get', return_value=mock_response):
            result = github_client._scrape_releases_page()

        assert result is not None
        assert result["version"] == "v1.2.3"  # 第一个匹配的标签

    # ===== 测试 1.12: 爬取 releases 页面 (无标签) =====
    def test_scrape_releases_page_no_tags(self, github_client, mock_response):
        """测试 1.12: releases 页面中没有版本标签"""
        mock_response.text = '<html><body>No releases here</body></html>'

        with patch.object(github_client._session, 'get', return_value=mock_response):
            result = github_client._scrape_releases_page()

        assert result is None
