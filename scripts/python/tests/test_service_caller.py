"""
ServiceCaller 单元测试

测试内容：
- 服务调用
- 超时处理
- 错误处理
- 集成 MQTTClient
"""
import unittest
from unittest.mock import Mock, patch
from concurrent.futures import Future, TimeoutError
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from djisdk.core.service_caller import ServiceCaller
from djisdk.core.mqtt_client import MQTTClient


class TestServiceCaller(unittest.TestCase):
    """测试 ServiceCaller 核心功能"""

    def setUp(self):
        """测试前准备"""
        self.mock_mqtt = Mock(spec=MQTTClient)
        self.caller = ServiceCaller(self.mock_mqtt, timeout=5)

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.caller.mqtt, self.mock_mqtt)
        self.assertEqual(self.caller.timeout, 5)

    def test_init_default_timeout(self):
        """测试默认超时时间"""
        caller = ServiceCaller(self.mock_mqtt)
        self.assertEqual(caller.timeout, 10)

    @patch('uuid.uuid4', return_value='mock-uuid-123')
    def test_call_success(self, mock_uuid):
        """测试成功调用服务"""
        # 模拟成功响应
        future = Future()
        future.set_result({"result": 0, "data": {"key": "value"}})
        self.mock_mqtt.publish.return_value = future

        method = "test_method"
        data = {"param": "value"}

        result = self.caller.call(method, data)

        # 验证调用参数
        self.mock_mqtt.publish.assert_called_once_with(method, data, 'mock-uuid-123')
        self.assertEqual(result, {"result": 0, "data": {"key": "value"}})

    @patch('uuid.uuid4', return_value='mock-uuid-123')
    def test_call_with_empty_data(self, mock_uuid):
        """测试不带数据的调用"""
        future = Future()
        future.set_result({"result": 0})
        self.mock_mqtt.publish.return_value = future

        result = self.caller.call("test_method")

        self.mock_mqtt.publish.assert_called_once_with("test_method", {}, 'mock-uuid-123')
        self.assertEqual(result, {"result": 0})

    @patch('uuid.uuid4', return_value='mock-uuid-123')
    def test_call_timeout(self, mock_uuid):
        """测试超时处理"""
        # 模拟超时
        future = Future()

        def timeout_result(timeout):
            raise TimeoutError("Service call timeout")

        future.result = timeout_result
        self.mock_mqtt.publish.return_value = future

        with self.assertRaises(TimeoutError) as context:
            self.caller.call("test_method", {"data": "test"})

        # 验证清理函数被调用
        self.mock_mqtt.cleanup_request.assert_called_once_with('mock-uuid-123')
        self.assertIn("服务调用超时: test_method", str(context.exception))

    @patch('uuid.uuid4', return_value='mock-uuid-123')
    def test_call_exception(self, mock_uuid):
        """测试服务调用异常"""
        future = Future()
        future.set_exception(Exception("Network error"))
        self.mock_mqtt.publish.return_value = future

        with self.assertRaises(Exception) as context:
            self.caller.call("test_method")

        self.assertIn("Network error", str(context.exception))

    @patch('uuid.uuid4')
    def test_call_generates_unique_tid(self, mock_uuid):
        """测试每次调用生成唯一的 tid"""
        mock_uuid.side_effect = ['tid-1', 'tid-2', 'tid-3']

        future = Future()
        future.set_result({})
        self.mock_mqtt.publish.return_value = future

        for i in range(3):
            self.caller.call("test_method")

        # 验证生成了 3 个不同的 tid
        calls = self.mock_mqtt.publish.call_args_list
        self.assertEqual(calls[0][0][2], 'tid-1')
        self.assertEqual(calls[1][0][2], 'tid-2')
        self.assertEqual(calls[2][0][2], 'tid-3')


class TestServiceCallerIntegration(unittest.TestCase):
    """测试 ServiceCaller 与 MQTTClient 集成"""

    @patch('djisdk.core.mqtt_client.mqtt.Client')
    @patch('uuid.uuid4', return_value='integration-tid-123')
    def test_full_integration(self, mock_uuid, mock_mqtt_client):
        """测试完整的集成流程"""
        # 创建真实的 MQTTClient
        mqtt_config = {'host': '127.0.0.1', 'port': 1883, 'username': 'test', 'password': 'test'}
        mqtt = MQTTClient("TEST_SN", mqtt_config)

        # Mock MQTT 客户端
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        mqtt.connect()

        # 创建 ServiceCaller
        caller = ServiceCaller(mqtt, timeout=5)

        # 启动调用（在后台线程中）
        import threading

        result_container = {}

        def call_service():
            try:
                result_container['result'] = caller.call("test_method", {"test": "data"})
            except Exception as e:
                result_container['error'] = e

        thread = threading.Thread(target=call_service)
        thread.start()

        # 等待一小段时间确保请求发送
        import time
        time.sleep(0.1)

        # 模拟收到响应
        msg = Mock()
        import json
        msg.payload.decode.return_value = json.dumps({
            "tid": "integration-tid-123",
            "info": {"code": 0},
            "data": {"response": "success"}
        })

        mqtt._on_message(None, None, msg)

        # 等待线程完成
        thread.join(timeout=2)

        # 验证结果
        self.assertIn('result', result_container)
        self.assertEqual(result_container['result'], {"response": "success"})


if __name__ == '__main__':
    unittest.main()
