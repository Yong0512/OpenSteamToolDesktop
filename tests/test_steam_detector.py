import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.steam_detector import SteamDetector, SteamStatus, SteamDetectionResult


class TestSteamDetector(unittest.TestCase):
    """SteamDetector 单元测试套件
    
    覆盖场景：
    - Steam 未安装
    - 通过注册表检测到默认路径安装
    - 通过注册表检测到自定义路径安装
    - 通过默认目录检测到安装
    - 通过自定义目录检测到安装
    - 注册表路径存在但 Steam.exe 缺失
    - 注册表访问权限错误
    - 路径验证功能
    """

    def setUp(self):
        """每个测试用例前初始化检测器"""
        self.detector = SteamDetector()

    def test_steam_status_enum(self):
        """测试 SteamStatus 枚举值"""
        self.assertEqual(SteamStatus.NOT_INSTALLED.name, "NOT_INSTALLED")
        self.assertEqual(SteamStatus.INSTALLED.name, "INSTALLED")
        self.assertEqual(SteamStatus.PATH_INVALID.name, "PATH_INVALID")
        self.assertEqual(SteamStatus.REGISTRY_ERROR.name, "REGISTRY_ERROR")
        self.assertEqual(SteamStatus.UNKNOWN_ERROR.name, "UNKNOWN_ERROR")

    def test_detection_result_dataclass(self):
        """测试 SteamDetectionResult 数据类"""
        result = SteamDetectionResult(
            status=SteamStatus.INSTALLED,
            path=r"C:\Program Files (x86)\Steam",
            message="检测成功"
        )
        self.assertEqual(result.status, SteamStatus.INSTALLED)
        self.assertEqual(result.path, r"C:\Program Files (x86)\Steam")
        self.assertEqual(result.message, "检测成功")

    def test_verify_steam_path_with_valid_path(self):
        """测试验证有效的 Steam 路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建模拟的 Steam.exe
            steam_exe = os.path.join(tmpdir, "Steam.exe")
            with open(steam_exe, "w") as f:
                f.write("")
            
            result = self.detector._verify_steam_path(tmpdir)
            self.assertTrue(result)

    def test_verify_steam_path_without_exe(self):
        """测试路径存在但缺少 Steam.exe"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.detector._verify_steam_path(tmpdir)
            self.assertFalse(result)

    def test_verify_steam_path_nonexistent(self):
        """测试不存在的路径"""
        result = self.detector._verify_steam_path(r"C:\NonExistent\Steam\Path")
        self.assertFalse(result)

    def test_verify_steam_path_empty(self):
        """测试空路径"""
        result = self.detector._verify_steam_path("")
        self.assertFalse(result)
        result = self.detector._verify_steam_path(None)
        self.assertFalse(result)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_steam_not_installed(self, mock_custom, mock_default, mock_registry):
        """测试 Steam 未安装场景"""
        mock_registry.return_value = None
        mock_default.return_value = None
        mock_custom.return_value = None

        result = self.detector.detect()

        self.assertEqual(result.status, SteamStatus.NOT_INSTALLED)
        self.assertIsNone(result.path)
        self.assertIn("未检测到", result.message)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_from_registry_default_path(self, mock_custom, mock_default, mock_registry):
        """测试通过注册表检测到默认路径安装的 Steam"""
        expected_path = r"C:\Program Files (x86)\Steam"
        mock_registry.return_value = expected_path
        mock_default.return_value = None
        mock_custom.return_value = None

        result = self.detector.detect()

        self.assertEqual(result.status, SteamStatus.INSTALLED)
        self.assertEqual(result.path, expected_path)
        self.assertIn("注册表", result.message)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_from_registry_custom_path(self, mock_custom, mock_default, mock_registry):
        """测试通过注册表检测到自定义路径安装的 Steam"""
        expected_path = r"D:\Games\Steam"
        mock_registry.return_value = expected_path
        mock_default.return_value = None
        mock_custom.return_value = None

        result = self.detector.detect()

        self.assertEqual(result.status, SteamStatus.INSTALLED)
        self.assertEqual(result.path, expected_path)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_from_default_path(self, mock_custom, mock_default, mock_registry):
        """测试通过默认目录检测到 Steam（注册表未找到）"""
        expected_path = r"C:\Program Files (x86)\Steam"
        mock_registry.return_value = None
        mock_default.return_value = expected_path
        mock_custom.return_value = None

        result = self.detector.detect()

        self.assertEqual(result.status, SteamStatus.INSTALLED)
        self.assertEqual(result.path, expected_path)
        self.assertIn("默认目录", result.message)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_from_custom_path(self, mock_custom, mock_default, mock_registry):
        """测试通过自定义路径检测到 Steam"""
        expected_path = r"E:\Steam"
        mock_registry.return_value = None
        mock_default.return_value = None
        mock_custom.return_value = expected_path

        result = self.detector.detect()

        self.assertEqual(result.status, SteamStatus.INSTALLED)
        self.assertEqual(result.path, expected_path)
        self.assertIn("自定义路径", result.message)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_registry_priority(self, mock_custom, mock_default, mock_registry):
        """测试注册表检测优先级高于目录检测"""
        registry_path = r"C:\Program Files (x86)\Steam"
        default_path = r"D:\Steam"
        custom_path = r"E:\Steam"
        
        mock_registry.return_value = registry_path
        mock_default.return_value = default_path
        mock_custom.return_value = custom_path

        result = self.detector.detect()

        # 应该优先返回注册表检测到的路径
        self.assertEqual(result.path, registry_path)
        self.assertIn("注册表", result.message)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_permission_error(self, mock_custom, mock_default, mock_registry):
        """测试注册表访问权限错误场景"""
        mock_registry.side_effect = PermissionError("Access denied")
        mock_default.return_value = None
        mock_custom.return_value = None

        result = self.detector.detect()

        self.assertEqual(result.status, SteamStatus.REGISTRY_ERROR)
        self.assertIn("权限", result.message)

    @patch.object(SteamDetector, '_detect_from_registry')
    @patch.object(SteamDetector, '_detect_from_default_paths')
    @patch.object(SteamDetector, '_detect_from_custom_paths')
    def test_detect_os_error(self, mock_custom, mock_default, mock_registry):
        """测试系统错误场景"""
        mock_registry.side_effect = OSError("System error")
        mock_default.return_value = None
        mock_custom.return_value = None

        result = self.detector.detect()

        self.assertEqual(result.status, SteamStatus.UNKNOWN_ERROR)
        self.assertIn("系统错误", result.message)

    def test_detect_from_registry_with_mock(self):
        """测试注册表检测的内部逻辑（使用模拟）"""
        with patch.object(self.detector, '_check_registry') as mock_check:
            mock_check.return_value = r"C:\Program Files (x86)\Steam"
            
            with patch.object(self.detector, '_verify_steam_path') as mock_verify:
                mock_verify.return_value = True
                
                result = self.detector._detect_from_registry()
                self.assertEqual(result, r"C:\Program Files (x86)\Steam")

    def test_detect_from_registry_not_found(self):
        """测试注册表中未找到 Steam"""
        with patch.object(self.detector, '_check_registry') as mock_check:
            mock_check.return_value = None
            
            result = self.detector._detect_from_registry()
            self.assertIsNone(result)

    def test_detect_from_registry_invalid_path(self):
        """测试注册表路径存在但 Steam.exe 缺失"""
        with patch.object(self.detector, '_check_registry') as mock_check:
            mock_check.return_value = r"C:\Invalid\Steam\Path"
            
            with patch.object(self.detector, '_verify_steam_path') as mock_verify:
                mock_verify.return_value = False
                
                result = self.detector._detect_from_registry()
                self.assertIsNone(result)

    def test_is_steam_running(self):
        """测试 Steam 进程检测（基本功能测试）"""
        # 由于进程检测依赖于实际系统状态，这里只验证方法可调用
        result = self.detector.is_steam_running()
        self.assertIsInstance(result, bool)

    def test_constants(self):
        """测试类常量定义"""
        self.assertEqual(self.detector.STEAM_EXE, "Steam.exe")
        self.assertEqual(self.detector.REG_VALUE_NAME, "InstallPath")
        self.assertIn(r"C:\Program Files (x86)\Steam", self.detector.DEFAULT_PATHS)
        self.assertIn(r"D:\Steam", self.detector.COMMON_CUSTOM_PATHS)


class TestSteamDetectorIntegration(unittest.TestCase):
    """SteamDetector 集成测试
    
    这些测试在实际系统上运行，不依赖模拟
    """

    def setUp(self):
        self.detector = SteamDetector()

    def test_real_detect(self):
        """在实际系统上执行真实检测"""
        result = self.detector.detect()
        
        # 验证返回结果类型正确
        self.assertIsInstance(result, SteamDetectionResult)
        self.assertIsInstance(result.status, SteamStatus)
        self.assertIsInstance(result.message, str)
        
        # 如果检测到安装，路径应该不为空
        if result.status == SteamStatus.INSTALLED:
            self.assertIsNotNone(result.path)
            self.assertTrue(os.path.isdir(result.path))
            self.assertTrue(os.path.isfile(os.path.join(result.path, "Steam.exe")))
            print(f"\n[集成测试] 检测到 Steam: {result.path}")
        else:
            print(f"\n[集成测试] {result.message}")

    def test_real_is_steam_running(self):
        """测试实际进程检测"""
        result = self.detector.is_steam_running()
        self.assertIsInstance(result, bool)
        print(f"\n[集成测试] Steam 运行状态: {'运行中' if result else '未运行'}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
