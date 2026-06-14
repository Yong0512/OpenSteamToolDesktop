"""
测试 config.py — 全局常量模块
"""
import unittest

import config


class TestSteamUrls(unittest.TestCase):
    """Steam CDN/API URL 常量测试"""

    def test_store_api_url(self):
        self.assertTrue(config.STEAM_STORE_API.startswith("https://"))

    def test_store_search_api_url(self):
        self.assertTrue(config.STEAM_STORE_SEARCH_API.startswith("https://"))

    def test_cdn_base_url(self):
        self.assertIn("steamstatic.com", config.STEAM_CDN_BASE)

    def test_cdn_api_url(self):
        self.assertIn("IContentServerDirectoryService", config.STEAM_CDN_API)

    def test_sudama_api_url(self):
        self.assertIn("sudama.app", config.SUDAMA_API_DEPOT_KEYS)


class TestGitHubUrls(unittest.TestCase):
    """GitHub 常量测试"""

    def test_owner_is_set(self):
        self.assertIsInstance(config.GITHUB_REPO_OWNER, str)
        self.assertTrue(len(config.GITHUB_REPO_OWNER) > 0)

    def test_repo_name(self):
        self.assertEqual(config.GITHUB_REPO_NAME, "OpenSteamToolDesktop")

    def test_releases_url_contains_owner(self):
        self.assertIn(config.GITHUB_REPO_OWNER, config.GITHUB_RELEASES_URL)

    def test_api_url_is_https(self):
        self.assertTrue(config.GITHUB_API_LATEST.startswith("https://api.github.com"))

    def test_issues_url_format(self):
        self.assertTrue(config.GITHUB_ISSUES_URL.endswith("/issues/new"))


class TestColors(unittest.TestCase):
    """颜色常量测试"""

    def test_primary_is_hex(self):
        self.assertTrue(config.COLOR_PRIMARY.startswith("#"))

    def test_success_is_hex(self):
        self.assertTrue(config.COLOR_SUCCESS.startswith("#"))

    def test_error_is_hex(self):
        self.assertTrue(config.COLOR_ERROR.startswith("#"))

    def test_warning_is_hex(self):
        self.assertTrue(config.COLOR_WARNING.startswith("#"))


class TestHttpConfig(unittest.TestCase):
    """HTTP 配置测试"""

    def test_default_timeout(self):
        self.assertEqual(config.HTTP_DEFAULT_TIMEOUT, 15.0)

    def test_cover_timeout(self):
        self.assertEqual(config.HTTP_COVER_TIMEOUT, 8.0)

    def test_max_retries(self):
        self.assertEqual(config.HTTP_MAX_RETRIES, 2)

    def test_user_agent_contains_chrome(self):
        self.assertIn("Chrome", config.STEAM_USER_AGENT)


class TestPaths(unittest.TestCase):
    """路径常量测试"""

    def test_lua_dir_relative(self):
        self.assertEqual(config.LUA_DIR_RELATIVE, "config/lua")


class TestCdnFallback(unittest.TestCase):
    """CDN 备用列表测试"""

    def test_fallback_has_entries(self):
        self.assertTrue(len(config.FALLBACK_CDN_HOSTS) >= 10)

    def test_fallback_all_steamcontent(self):
        for host in config.FALLBACK_CDN_HOSTS:
            self.assertIn("steamcontent.com", host)


if __name__ == "__main__":
    unittest.main()
