"""
MQTTClient 单元测试

测试内容：
- 连接管理
- 消息发布和订阅
- Future 响应处理
- 超时清理
- 线程安全
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call
import json
import threading
from concurrent.futures import Future
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from djisdk.core.mqtt_client import MQTTClient


class TestMQTTClient(unittest.TestCase):
    """测试 MQTTClient 核心功能"""

    def setUp(self):
        """测试前准备"""
        self.gateway_sn = "TEST_SN_123"
        self.mqtt_config = {
            'host': '127.0.0.1',
            'port': 1883,
            'username': 'test_user',
            'password': 'test_pass'
        }
        self.client = MQTTClient(self.gateway_sn, self.mqtt_config)

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.client.gateway_sn, self.gateway_sn)
        self.assertEqual(self.client.config, self.mqtt_config)
        self.assertIsNone(self.client.client)
        self.assertEqual(self.client.pending_requests, {})
        self.assertIsInstance(self.client.lock, type(threading.Lock()))

    @patch('djisdk.core.mqtt_client.mqtt.Client')
    def test_connect(self, mock_mqtt_client):
        """测试 MQTT 连接"""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        self.client.connect()

        # 验证连接参数
        mock_mqtt_client.assert_called_once_with(client_id=f"python-drc-{self.gateway_sn}")
        mock_client_instance.username_pw_set.assert_called_once_with('test_user', 'test_pass')
        mock_client_instance.connect.assert_called_once_with('127.0.0.1', 1883, 60)
        mock_client_instance.loop_start.assert_called_once()

        # 验证订阅
        expected_topic = f"thing/product/{self.gateway_sn}/services_reply"
        mock_client_instance.subscribe.assert_called_once_with(expected_topic, qos=1)

        # 验证回调设置
        self.assertEqual(mock_client_instance.on_message, self.client._on_message)

    @patch('djisdk.core.mqtt_client.mqtt.Client')
    def test_disconnect(self, mock_mqtt_client):
        """测试断开连接"""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        self.client.connect()
        self.client.disconnect()

        mock_client_instance.loop_stop.assert_called_once()
        mock_client_instance.disconnect.assert_called_once()

    @patch('djisdk.core.mqtt_client.mqtt.Client')
    @patch('time.time', return_value=1000000)
    def test_publish(self, mock_time, mock_mqtt_client):
        """测试消息发布"""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        self.client.connect()

        method = "test_method"
        data = {"key": "value"}
        tid = "test-tid-123"

        future = self.client.publish(method, data, tid)

        # 验证 Future 创建
        self.assertIsInstance(future, Future)
        self.assertIn(tid, self.client.pending_requests)
        self.assertEqual(self.client.pending_requests[tid], future)

        # 验证消息发布
        expected_topic = f"thing/product/{self.gateway_sn}/services"
        expected_payload = {
            "tid": tid,
            "bid": tid,
            "timestamp": 1000000000,
            "method": method,
            "data": data
        }

        mock_client_instance.publish.assert_called_once()
        call_args = mock_client_instance.publish.call_args
        self.assertEqual(call_args[0][0], expected_topic)
        self.assertEqual(json.loads(call_args[0][1]), expected_payload)
        self.assertEqual(call_args[1]['qos'], 1)

    def test_cleanup_request(self):
        """测试请求清理"""
        tid = "test-tid-123"
        future = Future()

        # 添加待处理请求
        with self.client.lock:
            self.client.pending_requests[tid] = future

        self.assertIn(tid, self.client.pending_requests)

        # 清理请求
        self.client.cleanup_request(tid)

        self.assertNotIn(tid, self.client.pending_requests)

    def test_cleanup_request_nonexistent(self):
        """测试清理不存在的请求"""
        # 不应该抛出异常
        self.client.cleanup_request("nonexistent-tid")

    @patch('djisdk.core.mqtt_client.mqtt.Client')
    def test_on_message_success(self, mock_mqtt_client):
        """测试成功接收消息"""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        self.client.connect()

        # 创建待处理请求
        tid = "test-tid-123"
        future = Future()
        with self.client.lock:
            self.client.pending_requests[tid] = future

        # 模拟收到响应
        msg = Mock()
        response_data = {"key": "value"}
        msg.payload.decode.return_value = json.dumps({
            "tid": tid,
            "info": {"code": 0},
            "data": response_data
        })

        self.client._on_message(None, None, msg)

        # 验证 Future 结果
        self.assertEqual(future.result(timeout=1), response_data)
        self.assertNotIn(tid, self.client.pending_requests)

    @patch('djisdk.core.mqtt_client.mqtt.Client')
    def test_on_message_error(self, mock_mqtt_client):
        """测试错误响应"""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        self.client.connect()

        # 创建待处理请求
        tid = "test-tid-123"
        future = Future()
        with self.client.lock:
            self.client.pending_requests[tid] = future

        # 模拟收到错误响应
        msg = Mock()
        msg.payload.decode.return_value = json.dumps({
            "tid": tid,
            "info": {"code": 1, "message": "Test error"}
        })

        self.client._on_message(None, None, msg)

        # 验证 Future 异常
        with self.assertRaises(Exception) as context:
            future.result(timeout=1)

        self.assertIn("Test error", str(context.exception))
        self.assertNotIn(tid, self.client.pending_requests)

    @patch('djisdk.core.mqtt_client.mqtt.Client')
    def test_on_message_no_tid(self, mock_mqtt_client):
        """测试没有 tid 的消息"""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        self.client.connect()

        msg = Mock()
        msg.payload.decode.return_value = json.dumps({"data": "test"})

        # 不应该抛出异常
        self.client._on_message(None, None, msg)

    def test_thread_safety(self):
        """测试线程安全"""
        tids = [f"tid-{i}" for i in range(100)]
        futures = []

        def add_request(tid):
            future = Future()
            with self.client.lock:
                self.client.pending_requests[tid] = future
            futures.append(future)

        # 多线程添加请求
        threads = [threading.Thread(target=add_request, args=(tid,)) for tid in tids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有请求都添加成功
        self.assertEqual(len(self.client.pending_requests), 100)

        # 多线程清理请求
        threads = [threading.Thread(target=self.client.cleanup_request, args=(tid,)) for tid in tids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有请求都清理成功
        self.assertEqual(len(self.client.pending_requests), 0)


if __name__ == '__main__':
    unittest.main()
