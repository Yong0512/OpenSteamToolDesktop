"""
测试 utils.http_client — HTTP 客户端与 404 缓存
"""
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

import httpx

from utils.http_client import (
    get,
    get_json,
    get_bytes,
    get_text,
    is_404_cached,
    add_404_cache,
    save_404_cache_now,
)


class TestHttpClientCache(unittest.TestCase):
    """404 缓存测试"""

    def setUp(self):
        # 清空模块级缓存
        import utils.http_client as client_module
        client_module._404_cache.clear()

    def tearDown(self):
        import utils.http_client as client_module
        client_module._404_cache.clear()

    def test_add_and_check_cache(self):
        url = "https://example.com/image.jpg"
        self.assertFalse(is_404_cached(url))
        add_404_cache(url)
        self.assertTrue(is_404_cached(url))

    def test_is_404_cached_unknown(self):
        self.assertFalse(is_404_cached("https://unknown.url/img.jpg"))

    def test_multiple_urls(self):
        urls = [f"https://example.com/{i}.jpg" for i in range(5)]
        for u in urls:
            add_404_cache(u)
        for u in urls:
            self.assertTrue(is_404_cached(u))
        self.assertFalse(is_404_cached("https://other.com/img.jpg"))


class TestHttpGet(unittest.TestCase):
    """get() 函数测试"""

    def setUp(self):
        import utils.http_client as client_module
        client_module._404_cache.clear()

    def tearDown(self):
        import utils.http_client as client_module
        client_module._404_cache.clear()

    @patch("utils.http_client.httpx.Client")
    def test_successful_get(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        resp = get("https://example.com/api")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 200)

    @patch("utils.http_client.httpx.Client")
    def test_404_short_circuit(self, mock_client_cls):
        add_404_cache("https://example.com/nonexistent.jpg")
        resp = get("https://example.com/nonexistent.jpg")
        self.assertIsNone(resp)
        mock_client_cls.return_value.__enter__.return_value.get.assert_not_called()

    @patch("utils.http_client.httpx.Client")
    def test_404_cached_on_failure(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        error = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_resp)
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = error

        resp = get("https://example.com/missing.jpg")
        self.assertIsNone(resp)
        self.assertTrue(is_404_cached("https://example.com/missing.jpg"))

    @patch("utils.http_client.httpx.Client")
    def test_retry_on_timeout(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.TimeoutException("timeout")
        )
        resp = get("https://example.com/slow")
        self.assertIsNone(resp)
        # 默认重试 2 次 = 总共 3 次请求
        self.assertEqual(
            mock_client_cls.return_value.__enter__.return_value.get.call_count,
            3,
        )

    @patch("utils.http_client.httpx.Client")
    def test_headers_included(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        get("https://example.com", headers={"X-Custom": "val"})
        call_args = mock_client_cls.call_args
        # 检查 Client 创建时的 headers 参数
        self.assertIn("headers", call_args[1])


class TestHttpGetJson(unittest.TestCase):
    """get_json() 测试"""

    @patch("utils.http_client.get")
    def test_valid_json(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"key": "value"}
        mock_get.return_value = mock_resp

        result = get_json("https://example.com/api")
        self.assertEqual(result, {"key": "value"})

    @patch("utils.http_client.get")
    def test_invalid_json(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("Bad JSON")
        mock_get.return_value = mock_resp

        result = get_json("https://example.com/api")
        self.assertIsNone(result)

    @patch("utils.http_client.get")
    def test_none_response(self, mock_get):
        mock_get.return_value = None
        result = get_json("https://example.com/api")
        self.assertIsNone(result)


class TestHttpGetBytes(unittest.TestCase):
    """get_bytes() 测试"""

    @patch("utils.http_client.get")
    def test_binary_data(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.content = b"\x89PNG\r\n"
        mock_get.return_value = mock_resp

        result = get_bytes("https://example.com/image.png")
        self.assertEqual(result, b"\x89PNG\r\n")

    @patch("utils.http_client.get")
    def test_none_response(self, mock_get):
        mock_get.return_value = None
        result = get_bytes("https://example.com/image.png")
        self.assertIsNone(result)


class TestHttpGetText(unittest.TestCase):
    """get_text() 测试"""

    @patch("utils.http_client.get")
    def test_text_data(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html>Hello</html>"
        mock_get.return_value = mock_resp

        result = get_text("https://example.com/page")
        self.assertEqual(result, "<html>Hello</html>")

    @patch("utils.http_client.get")
    def test_none_response(self, mock_get):
        mock_get.return_value = None
        result = get_text("https://example.com/page")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
