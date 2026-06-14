"""
测试 core.app_state — 全局应用状态单例
"""
import unittest

from PyQt6.QtCore import QCoreApplication

# 确保 QApplication 存在（app_state 使用 QObject/Signal）
_app = QCoreApplication.instance()
if _app is None:
    _app = QCoreApplication([])

from core.app_state import (
    AppState,
    STEAM_INSTALLED,
    STEAM_RUNNING,
    STEAM_PATH,
    DLL_DEPLOYED,
    DLL_ACTIVE,
    GAME_COUNT,
    app_state,
)


class TestAppStateSingleton(unittest.TestCase):
    """AppState 单例测试"""

    def tearDown(self):
        # 重置状态
        app_state._state.clear()

    def test_instance_returns_same(self):
        a = AppState.instance()
        b = AppState.instance()
        self.assertIs(a, b)

    def test_constructor_raises(self):
        with self.assertRaises(RuntimeError):
            AppState()


class TestAppStateGetSet(unittest.TestCase):
    """AppState get/set 测试"""

    def tearDown(self):
        app_state._state.clear()

    def test_get_default(self):
        self.assertIsNone(app_state.get("nonexistent"))
        self.assertEqual(app_state.get("nonexistent", "fallback"), "fallback")

    def test_set_and_get(self):
        app_state.set("custom_key", "hello")
        self.assertEqual(app_state.get("custom_key"), "hello")

    def test_set_same_value_no_signal(self):
        called = []
        app_state.injection_changed.connect(lambda: called.append(True))
        app_state.set("custom_key", 42)
        self.assertEqual(len(called), 0)  # custom_key 不在 SIGNAL_KEYS 中

    def test_set_dll_active_triggers_signal(self):
        called = []
        app_state.injection_changed.connect(lambda: called.append(True))
        app_state.set(DLL_ACTIVE, True)
        self.assertEqual(len(called), 1)

    def test_set_same_value_no_duplicate_signal(self):
        app_state.set(STEAM_INSTALLED, True)
        called = []
        app_state.injection_changed.connect(lambda: called.append(True))
        app_state.set(STEAM_INSTALLED, True)  # 不变化
        self.assertEqual(len(called), 0)


class TestAppStateBulk(unittest.TestCase):
    """AppState set_bulk 测试"""

    def tearDown(self):
        app_state._state.clear()

    def test_set_bulk_updates_multiple(self):
        app_state.set_bulk({STEAM_INSTALLED: True, STEAM_RUNNING: True})
        self.assertTrue(app_state.get(STEAM_INSTALLED))
        self.assertTrue(app_state.get(STEAM_RUNNING))

    def test_set_bulk_triggers_signal_once(self):
        called = []
        app_state.injection_changed.connect(lambda: called.append(True))
        app_state.set_bulk({STEAM_INSTALLED: True, DLL_ACTIVE: True, GAME_COUNT: 5})
        self.assertEqual(len(called), 1)

    def test_set_bulk_no_change_no_signal(self):
        app_state.set(STEAM_PATH, "/steam")
        called = []
        app_state.injection_changed.connect(lambda: called.append(True))
        app_state.set_bulk({STEAM_PATH: "/steam"})  # 值没变
        self.assertEqual(len(called), 0)


class TestStateKeys(unittest.TestCase):
    """状态键常量测试"""

    def test_keys_are_strings(self):
        for key in [STEAM_INSTALLED, STEAM_RUNNING, STEAM_PATH,
                    DLL_DEPLOYED, DLL_ACTIVE, GAME_COUNT]:
            self.assertIsInstance(key, str)
            self.assertTrue(len(key) > 0)


if __name__ == "__main__":
    unittest.main()
