"""
Commands 服务层单元测试

测试内容：
- _call_service 通用包装
- 所有业务服务函数
- 错误处理
- 控制台输出
"""
import unittest
from unittest.mock import Mock, patch, call
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from djisdk.services.commands import (
    _call_service,
    request_control_auth,
    release_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    change_live_lens,
    set_live_quality,
    start_live_push,
    stop_live_push,
)


class TestCallService(unittest.TestCase):
    """测试 _call_service 通用包装函数"""

    def setUp(self):
        """测试前准备"""
        self.mock_caller = Mock()

    @patch('djisdk.services.commands.console')
    def test_call_service_success(self, mock_console):
        """测试成功调用"""
        self.mock_caller.call.return_value = {"result": 0, "data": {"key": "value"}}

        result = _call_service(
            self.mock_caller,
            "test_method",
            {"param": "value"},
            "操作成功"
        )

        # 验证调用参数
        self.mock_caller.call.assert_called_once_with("test_method", {"param": "value"})

        # 验证返回值
        self.assertEqual(result, {"key": "value"})

        # 验证控制台输出
        mock_console.print.assert_called_once_with("[green]✓ 操作成功[/green]")

    @patch('djisdk.services.commands.console')
    def test_call_service_success_no_message(self, mock_console):
        """测试成功调用（无成功消息）"""
        self.mock_caller.call.return_value = {"result": 0, "data": {"key": "value"}}

        result = _call_service(self.mock_caller, "test_method")

        self.assertEqual(result, {"key": "value"})
        mock_console.print.assert_not_called()

    @patch('djisdk.services.commands.console')
    def test_call_service_failure(self, mock_console):
        """测试调用失败"""
        self.mock_caller.call.return_value = {"result": 1, "message": "操作失败"}

        with self.assertRaises(Exception) as context:
            _call_service(self.mock_caller, "test_method")

        self.assertIn("test_method 失败: 操作失败", str(context.exception))
        mock_console.print.assert_called()

    @patch('djisdk.services.commands.console')
    def test_call_service_empty_data(self, mock_console):
        """测试空数据"""
        self.mock_caller.call.return_value = {"result": 0, "data": {"key": "value"}}

        result = _call_service(self.mock_caller, "test_method", None)

        # 验证传入空字典
        self.mock_caller.call.assert_called_once_with("test_method", {})
        self.assertEqual(result, {"key": "value"})

    @patch('djisdk.services.commands.console')
    def test_call_service_exception(self, mock_console):
        """测试异常处理"""
        self.mock_caller.call.side_effect = Exception("网络错误")

        with self.assertRaises(Exception) as context:
            _call_service(self.mock_caller, "test_method")

        self.assertIn("网络错误", str(context.exception))
        # 验证错误输出
        mock_console.print.assert_called()
        error_call = mock_console.print.call_args[0][0]
        self.assertIn("[red]", error_call)
        self.assertIn("test_method", error_call)


class TestControlAuthServices(unittest.TestCase):
    """测试控制权管理服务"""

    def setUp(self):
        self.mock_caller = Mock()

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_request_control_auth(self, mock_console, mock_call_service):
        """测试请求控制权"""
        mock_call_service.return_value = {"status": "success"}

        result = request_control_auth(
            self.mock_caller,
            user_id="test_user",
            user_callsign="测试呼号"
        )

        # 验证控制台输出
        mock_console.print.assert_called_once_with("[bold cyan]请求控制权...[/bold cyan]")

        # 验证调用参数
        mock_call_service.assert_called_once_with(
            self.mock_caller,
            "cloud_control_auth_request",
            {
                "user_id": "test_user",
                "user_callsign": "测试呼号",
                "control_keys": ["flight"]
            },
            "控制权请求成功"
        )

        self.assertEqual(result, {"status": "success"})

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_request_control_auth_default_params(self, mock_console, mock_call_service):
        """测试默认参数"""
        request_control_auth(self.mock_caller)

        call_args = mock_call_service.call_args[0]
        self.assertEqual(call_args[1], "cloud_control_auth_request")
        self.assertEqual(call_args[2]["user_id"], "default_user")
        self.assertEqual(call_args[2]["user_callsign"], "Cloud Pilot")

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_release_control_auth(self, mock_console, mock_call_service):
        """测试释放控制权"""
        release_control_auth(self.mock_caller)

        mock_console.print.assert_called_once_with("[cyan]释放控制权...[/cyan]")
        mock_call_service.assert_called_once_with(
            self.mock_caller,
            "cloud_control_auth_release",
            success_msg="控制权已释放"
        )


class TestDRCModeServices(unittest.TestCase):
    """测试 DRC 模式服务"""

    def setUp(self):
        self.mock_caller = Mock()
        self.mqtt_broker_config = {
            'address': '127.0.0.1:1883',
            'client_id': 'test-client',
            'username': 'admin',
            'password': 'password',
            'expire_time': 1700000000,
            'enable_tls': False
        }

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_enter_drc_mode(self, mock_console, mock_call_service):
        """测试进入 DRC 模式"""
        enter_drc_mode(
            self.mock_caller,
            mqtt_broker=self.mqtt_broker_config,
            osd_frequency=100,
            hsi_frequency=10
        )

        mock_console.print.assert_called_once_with("[bold cyan]进入 DRC 模式...[/bold cyan]")

        call_args = mock_call_service.call_args[0]
        self.assertEqual(call_args[1], "drc_mode_enter")
        self.assertEqual(call_args[2]["mqtt_broker"], self.mqtt_broker_config)
        self.assertEqual(call_args[2]["osd_frequency"], 100)
        self.assertEqual(call_args[2]["hsi_frequency"], 10)

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_enter_drc_mode_default_frequencies(self, mock_console, mock_call_service):
        """测试默认频率"""
        enter_drc_mode(self.mock_caller, mqtt_broker=self.mqtt_broker_config)

        call_args = mock_call_service.call_args[0]
        self.assertEqual(call_args[2]["osd_frequency"], 30)
        self.assertEqual(call_args[2]["hsi_frequency"], 10)

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_exit_drc_mode(self, mock_console, mock_call_service):
        """测试退出 DRC 模式"""
        exit_drc_mode(self.mock_caller)

        mock_console.print.assert_called_once_with("[cyan]退出 DRC 模式...[/cyan]")
        mock_call_service.assert_called_once_with(
            self.mock_caller,
            "drc_mode_exit",
            success_msg="已退出 DRC 模式"
        )


class TestLiveStreamServices(unittest.TestCase):
    """测试直播服务"""

    def setUp(self):
        self.mock_caller = Mock()

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_change_live_lens(self, mock_console, mock_call_service):
        """测试切换镜头"""
        change_live_lens(self.mock_caller, video_id="52-0-0", video_type="zoom")

        mock_console.print.assert_called_once()
        print_arg = mock_console.print.call_args[0][0]
        self.assertIn("52-0-0", print_arg)
        self.assertIn("zoom", print_arg)

        mock_call_service.assert_called_once()
        call_args = mock_call_service.call_args[0]
        self.assertEqual(call_args[1], "drc_live_lens_change")
        self.assertEqual(call_args[2]["video_id"], "52-0-0")
        self.assertEqual(call_args[2]["video_type"], "zoom")

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_set_live_quality(self, mock_console, mock_call_service):
        """测试设置清晰度"""
        set_live_quality(self.mock_caller, video_quality=3)

        print_arg = mock_console.print.call_args[0][0]
        self.assertIn("高清", print_arg)

        call_args = mock_call_service.call_args[0]
        self.assertEqual(call_args[1], "live_set_quality")
        self.assertEqual(call_args[2]["video_quality"], 3)

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_start_live_push(self, mock_console, mock_call_service):
        """测试开始推流"""
        start_live_push(
            self.mock_caller,
            url="rtmp://test.com/live",
            video_id="52-0-0",
            url_type=0,
            video_quality=2
        )

        # 验证控制台输出
        self.assertEqual(mock_console.print.call_count, 3)

        call_args = mock_call_service.call_args[0]
        self.assertEqual(call_args[1], "live_start_push")
        self.assertEqual(call_args[2]["url"], "rtmp://test.com/live")
        self.assertEqual(call_args[2]["video_id"], "52-0-0")
        self.assertEqual(call_args[2]["url_type"], 0)
        self.assertEqual(call_args[2]["video_quality"], 2)

    @patch('djisdk.services.commands._call_service')
    @patch('djisdk.services.commands.console')
    def test_stop_live_push(self, mock_console, mock_call_service):
        """测试停止推流"""
        stop_live_push(self.mock_caller, video_id="52-0-0")

        print_arg = mock_console.print.call_args[0][0]
        self.assertIn("52-0-0", print_arg)

        call_args = mock_call_service.call_args[0]
        self.assertEqual(call_args[1], "live_stop_push")
        self.assertEqual(call_args[2]["video_id"], "52-0-0")


if __name__ == '__main__':
    unittest.main()
