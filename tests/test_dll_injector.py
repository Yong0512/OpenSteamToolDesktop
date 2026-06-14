"""
测试 core.dll_injector — DLL 部署/验证/卸载/清理
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dll_injector import DLLInjector, InjectStatus, InjectResult


class TestInjectStatus(unittest.TestCase):
    """InjectStatus 枚举值测试"""

    def test_expected_statuses(self):
        self.assertIn("SUCCESS", InjectStatus.__members__)
        self.assertIn("STEAM_NOT_FOUND", InjectStatus.__members__)
        self.assertIn("DLL_SOURCE_NOT_FOUND", InjectStatus.__members__)
        self.assertIn("DLL_ALREADY_DEPLOYED", InjectStatus.__members__)
        self.assertIn("DEPLOY_FAILED", InjectStatus.__members__)
        self.assertIn("VERIFICATION_FAILED", InjectStatus.__members__)
        self.assertIn("UNINSTALL_FAILED", InjectStatus.__members__)
        self.assertIn("UNKNOWN_ERROR", InjectStatus.__members__)

    def test_status_count(self):
        self.assertEqual(len(InjectStatus.__members__), 8)


class TestInjectResult(unittest.TestCase):
    """InjectResult 数据类测试"""

    def test_create_minimal(self):
        result = InjectResult(status=InjectStatus.SUCCESS)
        self.assertEqual(result.status, InjectStatus.SUCCESS)
        self.assertEqual(result.message, "")
        self.assertIsNone(result.details)

    def test_create_with_message(self):
        result = InjectResult(
            status=InjectStatus.DEPLOY_FAILED,
            message="复制失败",
        )
        self.assertEqual(result.status, InjectStatus.DEPLOY_FAILED)
        self.assertEqual(result.message, "复制失败")

    def test_create_with_details(self):
        result = InjectResult(
            status=InjectStatus.SUCCESS,
            message="成功",
            details=["dwmapi.dll", "xinput1_4.dll"],
        )
        self.assertEqual(result.details, ["dwmapi.dll", "xinput1_4.dll"])


class TestDLLInjectorInit(unittest.TestCase):
    """DLLInjector 初始化测试"""

    def test_default_init(self):
        injector = DLLInjector()
        self.assertEqual(injector._steam_path, "")
        self.assertEqual(injector._dll_source_dir, "")

    def test_init_with_paths(self):
        injector = DLLInjector(steam_path="C:\\Steam", dll_source_dir="C:\\dll")
        self.assertEqual(injector._steam_path, "C:\\Steam")
        self.assertEqual(injector._dll_source_dir, "C:\\dll")

    def test_set_steam_path(self):
        injector = DLLInjector()
        injector.set_steam_path("D:\\SteamLibrary")
        self.assertEqual(injector._steam_path, "D:\\SteamLibrary")
        self.assertEqual(injector.get_steam_path(), "D:\\SteamLibrary")

    def test_set_dll_source_dir(self):
        injector = DLLInjector()
        injector.set_dll_source_dir("E:\\OpenSteamTool\\dlls")
        self.assertEqual(injector._dll_source_dir, "E:\\OpenSteamTool\\dlls")


class TestCheckDllsDeployed(unittest.TestCase):
    """check_dlls_deployed 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_empty_path_returns_false(self):
        ok, missing = self.injector.check_dlls_deployed()
        self.assertFalse(ok)
        self.assertEqual(len(missing), 3)

    def test_nonexistent_directory(self):
        self.injector.set_steam_path(r"C:\NonExistentSteam")
        ok, missing = self.injector.check_dlls_deployed()
        self.assertFalse(ok)

    def test_all_dlls_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for dll in DLLInjector.ALL_DLLS:
                with open(os.path.join(tmpdir, dll), "w") as f:
                    f.write("")
            self.injector.set_steam_path(tmpdir)
            ok, missing = self.injector.check_dlls_deployed()
            self.assertTrue(ok)
            self.assertEqual(len(missing), 0)

    def test_partial_dlls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 只创建一个 DLL
            with open(os.path.join(tmpdir, "dwmapi.dll"), "w") as f:
                f.write("")
            self.injector.set_steam_path(tmpdir)
            ok, missing = self.injector.check_dlls_deployed()
            self.assertFalse(ok)
            self.assertEqual(len(missing), 2)


class TestCheckLuaDir(unittest.TestCase):
    """check_lua_dir 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_empty_path(self):
        self.assertFalse(self.injector.check_lua_dir())

    def test_lua_dir_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lua_dir = os.path.join(tmpdir, "config", "lua")
            os.makedirs(lua_dir)
            self.injector.set_steam_path(tmpdir)
            self.assertTrue(self.injector.check_lua_dir())

    def test_lua_dir_not_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.injector.set_steam_path(tmpdir)
            self.assertFalse(self.injector.check_lua_dir())


class TestDeployDlls(unittest.TestCase):
    """deploy_dlls 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_steam_not_found(self):
        result = self.injector.deploy_dlls()
        self.assertEqual(result.status, InjectStatus.STEAM_NOT_FOUND)

    def test_no_source_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.injector.set_steam_path(tmpdir)
            result = self.injector.deploy_dlls()
            self.assertEqual(result.status, InjectStatus.DLL_SOURCE_NOT_FOUND)

    def test_deploy_success(self):
        with tempfile.TemporaryDirectory() as steam_dir, \
             tempfile.TemporaryDirectory() as dll_dir:
            for dll in DLLInjector.ALL_DLLS:
                with open(os.path.join(dll_dir, dll), "w") as f:
                    f.write("fake dll content")

            self.injector.set_steam_path(steam_dir)
            self.injector.set_dll_source_dir(dll_dir)
            result = self.injector.deploy_dlls()
            self.assertEqual(result.status, InjectStatus.SUCCESS)
            # 验证文件确实被复制
            for dll in DLLInjector.ALL_DLLS:
                self.assertTrue(
                    os.path.isfile(os.path.join(steam_dir, dll)),
                    f"{dll} should exist in steam dir",
                )

    def test_source_missing_one_dll(self):
        with tempfile.TemporaryDirectory() as steam_dir, \
             tempfile.TemporaryDirectory() as dll_dir:
            # 只放 1 个 DLL，缺 2 个
            with open(os.path.join(dll_dir, "dwmapi.dll"), "w") as f:
                f.write("fake")

            self.injector.set_steam_path(steam_dir)
            self.injector.set_dll_source_dir(dll_dir)
            result = self.injector.deploy_dlls()
            self.assertEqual(result.status, InjectStatus.DEPLOY_FAILED)


class TestCreateLuaDir(unittest.TestCase):
    """create_lua_dir 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_steam_not_found(self):
        result = self.injector.create_lua_dir()
        self.assertEqual(result.status, InjectStatus.STEAM_NOT_FOUND)

    def test_create_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.injector.set_steam_path(tmpdir)
            result = self.injector.create_lua_dir()
            self.assertEqual(result.status, InjectStatus.SUCCESS)
            lua_dir = os.path.join(tmpdir, "config", "lua")
            self.assertTrue(os.path.isdir(lua_dir))

    def test_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lua_dir = os.path.join(tmpdir, "config", "lua")
            os.makedirs(lua_dir)
            self.injector.set_steam_path(tmpdir)
            result = self.injector.create_lua_dir()
            self.assertEqual(result.status, InjectStatus.SUCCESS)


class TestVerifyInjection(unittest.TestCase):
    """verify_injection 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_steam_not_found(self):
        result = self.injector.verify_injection()
        self.assertEqual(result.status, InjectStatus.STEAM_NOT_FOUND)

    @patch.object(DLLInjector, '_is_module_loaded_in_steam')
    def test_module_loaded(self, mock_loaded):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loaded.return_value = True
            self.injector.set_steam_path(tmpdir)
            result = self.injector.verify_injection()
            self.assertEqual(result.status, InjectStatus.SUCCESS)

    @patch.object(DLLInjector, '_is_module_loaded_in_steam')
    def test_log_exists(self, mock_loaded):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loaded.return_value = False
            log_dir = os.path.join(tmpdir, "opensteamtool")
            os.makedirs(log_dir)
            with open(os.path.join(log_dir, "main.log"), "w") as f:
                f.write("log")
            self.injector.set_steam_path(tmpdir)
            result = self.injector.verify_injection()
            self.assertEqual(result.status, InjectStatus.SUCCESS)

    @patch.object(DLLInjector, '_is_module_loaded_in_steam')
    def test_deployed_but_not_active(self, mock_loaded):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loaded.return_value = False
            for dll in DLLInjector.ALL_DLLS:
                with open(os.path.join(tmpdir, dll), "w") as f:
                    f.write("")
            self.injector.set_steam_path(tmpdir)
            result = self.injector.verify_injection()
            self.assertEqual(result.status, InjectStatus.VERIFICATION_FAILED)
            self.assertIn("重启", result.message)

    @patch.object(DLLInjector, '_is_module_loaded_in_steam')
    def test_nothing_detected(self, mock_loaded):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_loaded.return_value = False
            self.injector.set_steam_path(tmpdir)
            result = self.injector.verify_injection()
            self.assertEqual(result.status, InjectStatus.VERIFICATION_FAILED)


class TestUninstallDlls(unittest.TestCase):
    """uninstall_dlls 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_steam_not_found(self):
        result = self.injector.uninstall_dlls()
        self.assertEqual(result.status, InjectStatus.STEAM_NOT_FOUND)

    def test_already_removed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.injector.set_steam_path(tmpdir)
            result = self.injector.uninstall_dlls()
            self.assertEqual(result.status, InjectStatus.DLL_ALREADY_DEPLOYED)

    def test_remove_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for dll in DLLInjector.ALL_DLLS:
                with open(os.path.join(tmpdir, dll), "w") as f:
                    f.write("fake")
            self.injector.set_steam_path(tmpdir)
            result = self.injector.uninstall_dlls()
            self.assertEqual(result.status, InjectStatus.SUCCESS)
            for dll in DLLInjector.ALL_DLLS:
                self.assertFalse(os.path.isfile(os.path.join(tmpdir, dll)))


class TestCleanLogs(unittest.TestCase):
    """clean_logs 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_steam_not_found(self):
        result = self.injector.clean_logs()
        self.assertEqual(result.status, InjectStatus.STEAM_NOT_FOUND)

    def test_no_log_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.injector.set_steam_path(tmpdir)
            result = self.injector.clean_logs()
            self.assertEqual(result.status, InjectStatus.SUCCESS)

    def test_clean_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "opensteamtool")
            os.makedirs(log_dir)
            with open(os.path.join(log_dir, "main.log"), "w") as f:
                f.write("test")
            self.injector.set_steam_path(tmpdir)
            result = self.injector.clean_logs()
            self.assertEqual(result.status, InjectStatus.SUCCESS)


class TestCleanLuaConfigs(unittest.TestCase):
    """clean_lua_configs 测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_steam_not_found(self):
        result = self.injector.clean_lua_configs()
        self.assertEqual(result.status, InjectStatus.STEAM_NOT_FOUND)

    def test_no_lua_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.injector.set_steam_path(tmpdir)
            result = self.injector.clean_lua_configs()
            self.assertEqual(result.status, InjectStatus.SUCCESS)

    def test_clean_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lua_dir = os.path.join(tmpdir, "config", "lua")
            os.makedirs(lua_dir)
            with open(os.path.join(lua_dir, "730.lua"), "w") as f:
                f.write("addappid(730)")
            self.injector.set_steam_path(tmpdir)
            result = self.injector.clean_lua_configs()
            self.assertEqual(result.status, InjectStatus.SUCCESS)
            self.assertFalse(os.path.isfile(os.path.join(lua_dir, "730.lua")))


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        self.injector = DLLInjector()

    def test_verify_injection_real(self):
        result = self.injector.verify_injection()
        self.assertIsInstance(result, InjectResult)
        self.assertIsInstance(result.status, InjectStatus)
        print(f"\n[集成] verify_injection: {result.status.name} - {result.message}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
