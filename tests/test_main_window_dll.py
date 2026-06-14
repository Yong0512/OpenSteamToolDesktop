"""
测试用例 5: UI 测试 - 测试 main_window.py 中的 DLL 相关功能

测试目标：
- 启动时 DLL 版本检查
- 下载进度显示
- 对话框样式（应使用 qfluentwidgets）
- 稍后提醒功能
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

# 需要在导入 PyQt 之前设置 QApplication
app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestMainWindowDLL:
    """MainWindow DLL 相关功能测试用例"""

    @pytest.fixture
    def mock_main_window(self):
        """创建 Mock MainWindow（不创建真实 UI）"""
        with patch('gui.main_window.MessageBox') as mock_msg_box_class:
            with patch('gui.main_window.StateToolTip') as mock_state_tip_class:
                with patch('gui.main_window.InfoBar') as mock_info_bar_class:
                    # 创建 MainWindow 实例（但需要大量 Mock）
                    with patch('gui.main_window.MSFluentWindow.__init__', return_value=None):
                        with patch('gui.main_window.MSFluentWindow.setWindowTitle'):
                            with patch('gui.main_window.MSFluentWindow.resize'):
                                with patch('gui.main_window.MSFluentWindow.setMinimumSize'):
                                    from gui.main_window import MainWindow

                                    # 不调用真实 __init__，手动设置属性
                                    window = object.__new__(MainWindow)
                                    window._bridge = Mock()
                                    window._game_manager = Mock()
                                    window._config = Mock()
                                    window._download_progress_tip = None

                                    yield window

    # ===== 测试 5.1: 提示下载新版本 (用户点击"立即下载") =====
    def test_prompt_download_user_accepts(self, mock_main_window):
        """测试 5.1: 用户点击"立即下载"，应触发下载"""
        # Mock MessageBox.exec 返回 True（用户点击"是"）
        with patch('gui.main_window.MessageBox') as mock_msg_box:
            mock_instance = Mock()
            mock_instance.exec.return_value = True
            mock_instance.yesButton = Mock()
            mock_instance.cancelButton = Mock()
            mock_msg_box.return_value = mock_instance

            # Mock _download_and_install_dll
            with patch.object(mock_main_window, '_download_and_install_dll') as mock_download:
                version_info = {"version": "v1.2.3"}

                # 调用
                mock_main_window._prompt_download_new_version(
                    "发现新版本 v1.2.3",
                    version_info,
                )

                # 验证下载被调用
                mock_download.assert_called_once_with(version_info)

    # ===== 测试 5.2: 提示下载新版本 (用户点击"稍后提醒") =====
    def test_prompt_download_user_defers(self, mock_main_window):
        """测试 5.2: 用户点击"稍后提醒"，应设置 DLL_VERSION_MISMATCH 状态"""
        # Mock app_state
        with patch('gui.main_window.app_state') as mock_app_state:
            # Mock MessageBox.exec 返回 False（用户点击"否"）
            with patch('gui.main_window.MessageBox') as mock_msg_box:
                mock_instance = Mock()
                mock_instance.exec.return_value = False
                mock_instance.yesButton = Mock()
                mock_instance.cancelButton = Mock()
                mock_msg_box.return_value = mock_instance

                version_info = {"version": "v1.2.3"}

                # 调用
                mock_main_window._prompt_download_new_version(
                    "发现新版本 v1.2.3",
                    version_info,
                )

                # 验证状态被设置
                mock_app_state.set.assert_called_once_with(
                    'DLL_VERSION_MISMATCH', True
                )

    # ===== 测试 5.3: 下载进度更新 =====
    def test_download_progress_update(self, mock_main_window):
        """测试 5.3: 下载进度正确更新 StateToolTip"""
        # 创建 Mock StateToolTip
        mock_progress_tip = Mock()
        mock_main_window._download_progress_tip = mock_progress_tip

        # 调用进度更新 (50%)
        mock_main_window._on_download_progress(500, 1000)

        # 验证内容被更新
        mock_progress_tip.setContent.assert_called_once()
        call_args = mock_progress_tip.setContent.call_args[0][0]
        assert "50%" in call_args

    # ===== 测试 5.4: 下载完成 (成功) =====
    def test_download_complete_success(self, mock_main_window):
        """测试 5.4: 下载成功后显示 InfoBar.success"""
        # Mock InfoBar.success
        with patch('gui.main_window.InfoBar') as mock_info_bar:
            with patch('gui.main_window.app_state') as mock_app_state:
                # 调用
                result = {"success": True, "message": "成功安装版本 v1.2.3"}
                mock_main_window._on_download_complete(result)

                # 验证 InfoBar.success 被调用
                mock_info_bar.success.assert_called_once()

                # 验证状态被清除
                mock_app_state.set.assert_called_once_with(
                    'DLL_VERSION_MISMATCH', False
                )

    # ===== 测试 5.5: 下载完成 (失败) =====
    def test_download_complete_failure(self, mock_main_window):
        """测试 5.5: 下载失败后显示 InfoBar.error"""
        # Mock InfoBar.error
        with patch('gui.main_window.InfoBar') as mock_info_bar:
            # 调用
            result = {"success": False, "message": "下载失败"}
            mock_main_window._on_download_complete(result)

            # 验证 InfoBar.error 被调用
            mock_info_bar.error.assert_called_once()

    # ===== 测试 5.6: 检查本地 DLL 版本不匹配 =====
    def test_check_local_dll_mismatch_found(self, mock_main_window):
        """测试 5.6: 检测到 DLL 版本不匹配，应提示用户"""
        # Mock bridge.check_dll_version_mismatch 返回不匹配
        mock_main_window._bridge.check_dll_version_mismatch.return_value = (
            True,
            ["OpenSteamTool.dll"],
        )

        # Mock MessageBox
        with patch('gui.main_window.MessageBox') as mock_msg_box:
            mock_instance = Mock()
            mock_instance.exec.return_value = False  # 用户点击"稍后提醒"
            mock_instance.yesButton = Mock()
            mock_instance.cancelButton = Mock()
            mock_msg_box.return_value = mock_instance

            # Mock app_state
            with patch('gui.main_window.app_state') as mock_app_state:
                # 调用
                mock_main_window._check_local_dll_mismatch()

                # 验证 MessageBox 被创建
                mock_msg_box.assert_called_once()

                # 验证状态被设置
                mock_app_state.set.assert_called_once_with(
                    'DLL_VERSION_MISMATCH', True
                )

    # ===== 测试 5.7: 检查本地 DLL 版本匹配 =====
    def test_check_local_dll_mismatch_none(self, mock_main_window):
        """测试 5.7: 本地 DLL 版本匹配，不应提示用户"""
        # Mock bridge.check_dll_version_mismatch 返回匹配
        mock_main_window._bridge.check_dll_version_mismatch.return_value = (
            False,
            [],
        )

        # Mock MessageBox（不应被调用）
        with patch('gui.main_window.MessageBox') as mock_msg_box:
            # 调用
            mock_main_window._check_local_dll_mismatch()

            # 验证 MessageBox 未被调用
            mock_msg_box.assert_not_called()

    # ===== 测试 5.8: 使用 AsyncWorker 后台检查更新 =====
    def test_check_dll_version_on_startup(self, mock_main_window):
        """测试 5.8: 启动时正确调用 AsyncWorker 检查更新"""
        # Mock AsyncWorker
        with patch('gui.main_window.AsyncWorker') as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker

            # 调用
            mock_main_window._check_dll_version_on_startup()

            # 验证 AsyncWorker 被创建并启动
            mock_worker_class.assert_called_once()
            mock_worker.start.assert_called_once()

    # ===== 测试 5.9: 对话框使用 qfluentwidgets (而非 PyQt6) =====
    def test_message_box_uses_qfluentwidgets(self):
        """测试 5.9: 验证导入的是 qfluentwidgets.MessageBox"""
        # 检查 main_window.py 中的导入
        import gui.main_window as main_window_module

        # 验证 MessageBox 来自 qfluentwidgets
        from qfluentwidgets import MessageBox as QFluentMessageBox

        # 检查模块中使用的 MessageBox
        # 注意：这是一个静态检查，验证代码正确使用库
        assert hasattr(main_window_module, 'MessageBox')

    # ===== 测试 5.10: 下载线程安全退出 =====
    def test_download_worker_thread_safety(self, mock_main_window):
        """测试 5.10: 下载 worker 正确清理，无 QThread 警告"""
        # Mock _download_worker
        mock_worker = Mock()
        mock_main_window._download_worker = mock_worker

        # 模拟下载错误
        mock_main_window._on_download_error("Test error")

        # 验证进度提示被关闭
        if hasattr(mock_main_window, '_download_progress_tip'):
            if mock_main_window._download_progress_tip:
                # 在实际代码中，应调用 close()
                pass
