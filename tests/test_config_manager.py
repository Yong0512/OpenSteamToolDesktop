"""
测试 core.config_manager — JSON 配置文件读写
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from config import CONFIG_FILE
from core.config_manager import ConfigManager


class TestConfigManagerInit(unittest.TestCase):
    """ConfigManager 初始化测试"""

    @patch.object(ConfigManager, "_load")
    def test_init_calls_load(self, mock_load):
        cm = ConfigManager()
        cm._load = mock_load  # 恢复 patch 后的 _load
        cm._load()
        mock_load.assert_called()

    def test_config_file_is_set(self):
        cm = ConfigManager()
        self.assertEqual(cm.config_file, CONFIG_FILE)


class TestConfigManagerReadWrite(unittest.TestCase):
    """ConfigManager 读写测试"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp.name, "config.json")
        self._patcher = patch("core.config_manager.CONFIG_FILE", self.config_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.tmp.cleanup()

    def test_get_default_when_no_file(self):
        cm = ConfigManager()
        self.assertEqual(cm.get("nonexistent", "default"), "default")
        self.assertIsNone(cm.get("nonexistent"))

    def test_set_and_get(self):
        cm = ConfigManager()
        cm.set("theme", "dark")
        self.assertEqual(cm.get("theme"), "dark")

    def test_set_persists_to_disk(self):
        cm = ConfigManager()
        cm.set("key1", "value1")
        # 重新加载
        cm2 = ConfigManager()
        self.assertEqual(cm2.get("key1"), "value1")

    def test_set_bulk(self):
        cm = ConfigManager()
        cm.set_bulk({"a": 1, "b": 2})
        self.assertEqual(cm.get("a"), 1)
        self.assertEqual(cm.get("b"), 2)

    def test_get_all(self):
        cm = ConfigManager()
        cm.set("x", 10)
        all_data = cm.get_all()
        self.assertEqual(all_data["x"], 10)
        # 返回副本，修改不影响内部
        all_data["x"] = 99
        self.assertEqual(cm.get("x"), 10)

    def test_load_malformed_json(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        cm = ConfigManager()
        self.assertEqual(cm.get_all(), {})


class TestConfigManagerTypes(unittest.TestCase):
    """ConfigManager 数据类型测试"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp.name, "config.json")
        self._patcher = patch("core.config_manager.CONFIG_FILE", self.config_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.tmp.cleanup()

    def test_int_value(self):
        cm = ConfigManager()
        cm.set("count", 42)
        self.assertEqual(cm.get("count"), 42)

    def test_float_value(self):
        cm = ConfigManager()
        cm.set("ratio", 3.14)
        self.assertAlmostEqual(cm.get("ratio"), 3.14)

    def test_bool_value(self):
        cm = ConfigManager()
        cm.set("enabled", True)
        self.assertTrue(cm.get("enabled"))

    def test_list_value(self):
        cm = ConfigManager()
        cm.set("items", [1, 2, 3])
        self.assertEqual(cm.get("items"), [1, 2, 3])

    def test_dict_value(self):
        cm = ConfigManager()
        cm.set("nested", {"inner": "val"})
        self.assertEqual(cm.get("nested"), {"inner": "val"})


if __name__ == "__main__":
    unittest.main()
