"""
测试 utils.download_cover — 封面缓存与下载
"""
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from utils.download_cover import CoverCache, download_cover


class TestCoverCacheSingleton(unittest.TestCase):
    """CoverCache 单例测试"""

    def tearDown(self):
        CoverCache._instance = None

    def test_singleton_returns_same_instance(self):
        a = CoverCache.instance()
        b = CoverCache.instance()
        self.assertIs(a, b)

    def test_constructor_raises(self):
        CoverCache.instance()  # 先创建
        with self.assertRaises(RuntimeError):
            CoverCache()


class TestCoverCacheBasic(unittest.TestCase):
    """CoverCache 基本操作测试"""

    def setUp(self):
        CoverCache._instance = None
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmp.name) / "covers"
        self.cache_dir.mkdir(exist_ok=True)
        self._patcher = patch(
            "utils.download_cover.PathManager.covers_dir",
            return_value=self.cache_dir,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        CoverCache._instance = None
        self.tmp.cleanup()

    def test_has_returns_false_for_unknown(self):
        cache = CoverCache.instance()
        self.assertFalse(cache.has("99999"))

    def test_set_and_has(self):
        cache = CoverCache.instance()
        cache.set("12345", None)
        self.assertTrue(cache.has("12345"))

    def test_is_known_missing(self):
        cache = CoverCache.instance()
        cache.set("67890", None)
        self.assertTrue(cache.is_known_missing("67890"))
        self.assertTrue(cache.has("67890"))

    def test_get_raises_keyerror(self):
        cache = CoverCache.instance()
        with self.assertRaises(KeyError):
            cache.get("unknown_id")

    def test_get_returns_none_for_missing(self):
        cache = CoverCache.instance()
        cache.set("11111", None)
        self.assertIsNone(cache.get("11111"))


class TestCoverCacheDiskSave(unittest.TestCase):
    """CoverCache 磁盘保存测试"""

    def setUp(self):
        CoverCache._instance = None
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmp.name) / "covers"
        self.cache_dir.mkdir(exist_ok=True)
        self._patcher = patch(
            "utils.download_cover.PathManager.covers_dir",
            return_value=self.cache_dir,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        CoverCache._instance = None
        self.tmp.cleanup()

    def test_save_to_disk_creates_file(self):
        cache = CoverCache.instance()
        data = b"\x89PNG fake image data"
        cache.save_to_disk("730", data)
        filepath = self.cache_dir / "730.jpg"
        self.assertTrue(filepath.exists())
        with open(filepath, "rb") as f:
            self.assertEqual(f.read(), data)

    def test_save_to_disk_overwrites(self):
        cache = CoverCache.instance()
        cache.save_to_disk("570", b"old data")
        cache.save_to_disk("570", b"new data")
        filepath = self.cache_dir / "570.jpg"
        with open(filepath, "rb") as f:
            self.assertEqual(f.read(), b"new data")


class TestDownloadCover(unittest.TestCase):
    """download_cover() 函数测试 — get_bytes 在函数内部导入"""

    @patch("utils.http_client.get_bytes")
    def test_download_success(self, mock_get_bytes):
        mock_get_bytes.return_value = b"\xff\xd8\xff\xe0"
        data = download_cover("730")
        self.assertEqual(data, b"\xff\xd8\xff\xe0")
        mock_get_bytes.assert_called_once()

    @patch("utils.http_client.get_bytes")
    def test_download_failure(self, mock_get_bytes):
        mock_get_bytes.return_value = None
        data = download_cover("invalid_id")
        self.assertIsNone(data)


if __name__ == "__main__":
    unittest.main()
