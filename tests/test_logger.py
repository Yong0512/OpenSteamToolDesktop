"""
测试 utils.logger — 日志模块
"""
import logging
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from utils.logger import setup_logger, set_log_level, LOG_LEVEL_MAP, LOG_DIR


class TestSetupLogger(unittest.TestCase):
    """setup_logger 测试"""

    def test_returns_logger(self):
        logger = setup_logger("TestModule")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "TestModule")

    def test_same_name_returns_same_logger(self):
        a = setup_logger("TestSame")
        b = setup_logger("TestSame")
        self.assertIs(a, b)

    def test_different_names_different_loggers(self):
        a = setup_logger("TestA")
        b = setup_logger("TestB")
        self.assertIsNot(a, b)

    def test_logger_is_enabled(self):
        logger = setup_logger("TestEnabled")
        logger.debug("debug test message")  # 不应抛异常

    def test_handlers_added_only_once(self):
        logger = setup_logger("TestOnce")
        initial_count = len(logger.handlers)
        setup_logger("TestOnce")
        self.assertEqual(len(logger.handlers), initial_count)

    @patch("utils.logger.LOG_FILE", new_callable=lambda: os.path.join(tempfile.mkdtemp(), "test.log"))
    def test_file_handler_created(self, _mock_file):
        logger = setup_logger("TestFileHandler")
        has_file_handler = any(
            isinstance(h, logging.FileHandler) for h in logger.handlers
        )
        self.assertTrue(has_file_handler)

    def test_has_stream_handler(self):
        logger = setup_logger("TestStream")
        has_stream = any(
            isinstance(h, logging.StreamHandler) for h in logger.handlers
        )
        self.assertTrue(has_stream)


class TestSetLogLevel(unittest.TestCase):
    """set_log_level 测试（level 参数为 int）"""

    def test_set_debug_level(self):
        logger = setup_logger("TestLevelDebug")
        set_log_level(logger, logging.DEBUG)
        self.assertEqual(logger.level, logging.DEBUG)

    def test_set_info_level(self):
        logger = setup_logger("TestLevelInfo")
        set_log_level(logger, logging.INFO)
        self.assertEqual(logger.level, logging.INFO)

    def test_set_warning_level(self):
        logger = setup_logger("TestLevelWarning")
        set_log_level(logger, logging.WARNING)
        self.assertEqual(logger.level, logging.WARNING)

    def test_set_error_level(self):
        logger = setup_logger("TestLevelError")
        set_log_level(logger, logging.ERROR)
        self.assertEqual(logger.level, logging.ERROR)


class TestLogLevelMap(unittest.TestCase):
    """LOG_LEVEL_MAP 测试"""

    def test_has_debug_info_warning_error(self):
        self.assertIn("DEBUG", LOG_LEVEL_MAP)
        self.assertIn("INFO", LOG_LEVEL_MAP)
        self.assertIn("WARNING", LOG_LEVEL_MAP)
        self.assertIn("ERROR", LOG_LEVEL_MAP)

    def test_no_critical_key(self):
        # logger.py 的 LOG_LEVEL_MAP 只有 4 种级别
        self.assertNotIn("CRITICAL", LOG_LEVEL_MAP)

    def test_maps_to_correct_levels(self):
        self.assertEqual(LOG_LEVEL_MAP["DEBUG"], logging.DEBUG)
        self.assertEqual(LOG_LEVEL_MAP["INFO"], logging.INFO)
        self.assertEqual(LOG_LEVEL_MAP["WARNING"], logging.WARNING)
        self.assertEqual(LOG_LEVEL_MAP["ERROR"], logging.ERROR)


class TestLogDir(unittest.TestCase):
    """LOG_DIR 测试"""

    def test_log_dir_is_string(self):
        # logger.py 中 LOG_DIR 是 str，不是 Path
        self.assertIsInstance(LOG_DIR, str)

    def test_log_dir_ends_with_logs(self):
        self.assertTrue(LOG_DIR.endswith("logs"))


if __name__ == "__main__":
    unittest.main()
