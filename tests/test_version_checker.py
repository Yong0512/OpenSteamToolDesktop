"""
测试 core.version_checker — GitHub 版本检查
"""
import re
import unittest
from unittest.mock import Mock, patch

from core.version_checker import (
    ReleaseInfo,
    _parse_semver,
    _is_newer,
    check_for_updates,
)


class TestReleaseInfo(unittest.TestCase):
    """ReleaseInfo 数据类测试"""

    def test_create(self):
        info = ReleaseInfo(
            version="2.0.0",
            tag_name="v2.0.0",
            title="Release 2.0",
            body="Changelog",
            html_url="https://github.com/x/releases/v2.0.0",
            published_at="2026-01-01",
            is_newer=True,
        )
        self.assertEqual(info.version, "2.0.0")
        self.assertTrue(info.is_newer)

    def test_default_is_newer_false(self):
        info = ReleaseInfo(
            version="1.0.0",
            tag_name="v1.0.0",
            title="",
            body="",
            html_url="",
            published_at="",
            is_newer=False,
        )
        self.assertFalse(info.is_newer)


class TestParseSemver(unittest.TestCase):
    """语义化版本解析测试"""

    def test_simple(self):
        self.assertEqual(_parse_semver("1.2.3"), (1, 2, 3))

    def test_with_v_prefix(self):
        self.assertEqual(_parse_semver("v2.0.0"), (2, 0, 0))

    def test_two_digit(self):
        self.assertEqual(_parse_semver("1.2"), (1, 2, 0))

    def test_single_digit(self):
        self.assertEqual(_parse_semver("1"), (1, 0, 0))

    def test_non_numeric(self):
        self.assertEqual(_parse_semver("abc"), (0, 0, 0))

    def test_empty_string(self):
        self.assertEqual(_parse_semver(""), (0, 0, 0))

    def test_large_version(self):
        self.assertEqual(_parse_semver("v99.88.77"), (99, 88, 77))


class TestIsNewer(unittest.TestCase):
    """版本比较测试"""

    def test_newer_major(self):
        self.assertTrue(_is_newer("2.0.0", "1.0.0"))

    def test_newer_minor(self):
        self.assertTrue(_is_newer("1.2.0", "1.1.0"))

    def test_newer_patch(self):
        self.assertTrue(_is_newer("1.0.1", "1.0.0"))

    def test_same(self):
        self.assertFalse(_is_newer("1.0.0", "1.0.0"))

    def test_older(self):
        self.assertFalse(_is_newer("0.9.0", "1.0.0"))

    def test_current_is_newer(self):
        self.assertFalse(_is_newer("1.0.0", "2.0.0"))

    def test_with_v_prefix_current(self):
        self.assertTrue(_is_newer("v2.0.0", "1.0.0"))

    def test_with_v_prefix_latest(self):
        self.assertTrue(_is_newer("2.0.0", "v1.0.0"))

    def test_both_v_prefix(self):
        self.assertFalse(_is_newer("v1.0.0", "v1.0.0"))


def _make_html_with_tag(owner: str, repo: str, tag: str) -> str:
    """构造包含指定 tag 的 GitHub Releases 页面 HTML"""
    return f'''
    <html>
    <body>
        <a href="/{owner}/{repo}/releases/tag/{tag}">Latest</a>
    </body>
    </html>
    '''


class TestFetchLatestRelease(unittest.TestCase):
    """_fetch_latest_release 测试"""

    @patch("core.version_checker.GITHUB_REPO_OWNER", "yong0512")
    @patch("core.version_checker.GITHUB_REPO_NAME", "OpenSteamToolDesktop")
    @patch("core.version_checker.httpx.Client")
    def test_fetch_success(self, mock_client_cls):
        html = _make_html_with_tag("yong0512", "OpenSteamToolDesktop", "v1.2.3")
        mock_resp = Mock()
        mock_resp.text = html
        mock_resp.url = "https://github.com/yong0512/OpenSteamToolDesktop/releases/tag/v1.2.3"
        mock_resp.raise_for_status = Mock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        from core.version_checker import _fetch_latest_release
        data, error = _fetch_latest_release()
        self.assertIsNotNone(data)
        self.assertIsNone(error)
        self.assertEqual(data["tag_name"], "v1.2.3")
        self.assertEqual(data["version"], "1.2.3")

    @patch("core.version_checker.GITHUB_REPO_OWNER", "yong0512")
    @patch("core.version_checker.GITHUB_REPO_NAME", "OpenSteamToolDesktop")
    @patch("core.version_checker.httpx.Client")
    def test_fetch_via_redirect_url(self, mock_client_cls):
        # HTML 中没有匹配项，但 URL 中有（通过 redirect）
        mock_resp = Mock()
        mock_resp.text = "<html>no tag here</html>"
        mock_resp.url = "https://github.com/yong0512/OpenSteamToolDesktop/releases/tag/v2.0.0"
        mock_resp.raise_for_status = Mock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        from core.version_checker import _fetch_latest_release
        data, error = _fetch_latest_release()
        self.assertIsNotNone(data)
        self.assertIsNone(error)
        self.assertEqual(data["tag_name"], "v2.0.0")

    @patch("core.version_checker.httpx.Client")
    def test_fetch_no_tag_found(self, mock_client_cls):
        mock_resp = Mock()
        mock_resp.text = "<html>no releases here</html>"
        mock_resp.url = "https://github.com/x/y/releases"
        mock_resp.raise_for_status = Mock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        from core.version_checker import _fetch_latest_release
        data, error = _fetch_latest_release()
        self.assertIsNone(data)
        self.assertIsNone(error)

    @patch("core.version_checker.httpx.Client")
    def test_fetch_timeout(self, mock_client_cls):
        import httpx
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.TimeoutException("timeout")
        )

        from core.version_checker import _fetch_latest_release
        data, error = _fetch_latest_release()
        self.assertIsNone(data)
        self.assertIsNotNone(error)
        self.assertIn("超时", error)

    @patch("core.version_checker.httpx.Client")
    def test_fetch_http_error(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            OSError("Connection refused")
        )

        from core.version_checker import _fetch_latest_release
        data, error = _fetch_latest_release()
        self.assertIsNone(data)
        self.assertIsNotNone(error)


class TestCheckForUpdates(unittest.TestCase):
    """check_for_updates 集成测试"""

    @patch("core.version_checker.GITHUB_REPO_OWNER", "yong0512")
    @patch("core.version_checker.GITHUB_REPO_NAME", "OpenSteamToolDesktop")
    @patch("core.version_checker.httpx.Client")
    def test_no_new_version_same(self, mock_client_cls):
        html = _make_html_with_tag("yong0512", "OpenSteamToolDesktop", "v1.0.0")
        mock_resp = Mock()
        mock_resp.text = html
        mock_resp.url = "https://github.com/yong0512/OpenSteamToolDesktop/releases/tag/v1.0.0"
        mock_resp.raise_for_status = Mock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with patch("core.version_checker.APP_VERSION", "1.0.0"):
            result, error = check_for_updates()
            self.assertIsNone(result)
            self.assertIsNone(error)

    @patch("core.version_checker.GITHUB_REPO_OWNER", "yong0512")
    @patch("core.version_checker.GITHUB_REPO_NAME", "OpenSteamToolDesktop")
    @patch("core.version_checker.httpx.Client")
    def test_new_version_available(self, mock_client_cls):
        html = _make_html_with_tag("yong0512", "OpenSteamToolDesktop", "v2.0.0")
        mock_resp = Mock()
        mock_resp.text = html
        mock_resp.url = "https://github.com/yong0512/OpenSteamToolDesktop/releases/tag/v2.0.0"
        mock_resp.raise_for_status = Mock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with patch("core.version_checker.APP_VERSION", "1.0.0"):
            result, error = check_for_updates()
            self.assertIsNotNone(result)
            self.assertIsNone(error)
            self.assertEqual(result.version, "2.0.0")
            self.assertTrue(result.is_newer)

    @patch("core.version_checker.httpx.Client")
    def test_network_error_returns_error_msg(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            OSError("Connection refused")
        )
        with patch("core.version_checker.APP_VERSION", "1.0.0"):
            result, error = check_for_updates()
            self.assertIsNone(result)
            self.assertIsNotNone(error)

    @patch("core.version_checker.httpx.Client")
    def test_timeout_returns_error_msg(self, mock_client_cls):
        import httpx
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.TimeoutException("timeout")
        )
        with patch("core.version_checker.APP_VERSION", "1.0.0"):
            result, error = check_for_updates()
            self.assertIsNone(result)
            self.assertIsNotNone(error)

    @patch("core.version_checker.httpx.Client")
    def test_no_tag_name(self, mock_client_cls):
        mock_resp = Mock()
        mock_resp.text = "<html>no tag</html>"
        mock_resp.url = "https://github.com/x/y/releases"
        mock_resp.raise_for_status = Mock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with patch("core.version_checker.APP_VERSION", "1.0.0"):
            result, error = check_for_updates()
            self.assertIsNone(result)
            self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
