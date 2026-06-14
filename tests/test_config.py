"""
测试 config.py — 应用配置常量
"""
import unittest

import config


class TestAppInfo(unittest.TestCase):
    """应用信息常量测试"""

    def test_app_name_is_string(self):
        self.assertIsInstance(config.APP_NAME, str)

    def test_app_version_is_string(self):
        self.assertIsInstance(config.APP_VERSION, str)

    def test_version_has_expected_format(self):
        parts = config.APP_VERSION.split(".")
        self.assertEqual(len(parts), 3)
        for p in parts:
            self.assertTrue(p.isdigit())


class TestConfigPaths(unittest.TestCase):
    """配置路径测试"""

    def test_config_dir_ends_with_subdir(self):
        self.assertTrue(config.CONFIG_DIR.endswith(".OpenSteamToolDesktop"))

    def test_config_file_is_json(self):
        self.assertTrue(config.CONFIG_FILE.endswith(".json"))


class TestGitHubConfig(unittest.TestCase):
    """GitHub 配置测试"""

    def test_owner_is_placeholder(self):
        # 提醒：此处应替换为真实用户名
        self.assertEqual(config.GITHUB_REPO_OWNER, "yourusername")

    def test_releases_url_format(self):
        self.assertIn(config.GITHUB_REPO_OWNER, config.GITHUB_RELEASES_URL)
        self.assertIn(config.GITHUB_REPO_NAME, config.GITHUB_RELEASES_URL)

    def test_api_url_format(self):
        self.assertTrue(config.GITHUB_API_LATEST_RELEASE.startswith("https://api.github.com"))


class TestThemeConfig(unittest.TestCase):
    """主题配置测试"""

    def test_default_theme_is_string(self):
        self.assertIsInstance(config.DEFAULT_THEME_MODE, str)

    def test_default_theme_color_is_hex(self):
        self.assertTrue(config.DEFAULT_THEME_COLOR.startswith("#"))


class TestLanguageConfig(unittest.TestCase):
    """语言配置测试"""

    def test_default_language(self):
        self.assertEqual(config.DEFAULT_LANGUAGE, "zh_CN")


class TestLogConfig(unittest.TestCase):
    """日志配置测试"""

    def test_log_level_is_valid(self):
        self.assertIn(config.LOG_LEVEL, ["DEBUG", "INFO", "WARNING", "ERROR"])

    def test_crash_log_enabled_is_bool(self):
        self.assertIsInstance(config.CRASH_LOG_ENABLED, bool)


class TestLuaConfig(unittest.TestCase):
    """Lua 配置测试"""

    def test_lua_dir_relative(self):
        self.assertEqual(config.LUA_DIR_RELATIVE, "config/lua")


class TestColorConstants(unittest.TestCase):
    """颜色常量测试"""

    def test_colors_are_hex(self):
        for c in [config.COLOR_SUCCESS, config.COLOR_ERROR, config.COLOR_WARNING]:
            self.assertTrue(c.startswith("#"), f"{c} should start with #")


if __name__ == "__main__":
    unittest.main()
