"""
Heartbeat 服务单元测试

测试内容：
- 心跳线程启动
- 心跳线程停止
- 心跳消息发送
- 精确定时
"""
import unittest
from unittest.mock import Mock, patch, call
import threading
import time
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from djisdk.services.heartbeat import start_heartbeat, stop_heartbeat


class TestHeartbeat(unittest.TestCase):
    """测试心跳服务"""

    @patch('djisdk.services.heartbeat.console')
    def test_start_heartbeat(self, mock_console):
        """测试启动心跳"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        thread = start_heartbeat(mock_mqtt, interval=0.1)

        # 验证返回值
        self.assertIsInstance(thread, threading.Thread)
        self.assertTrue(thread.is_alive())
        self.assertTrue(thread.daemon)
        self.assertTrue(hasattr(thread, 'stop_flag'))

        # 等待一些心跳发送
        time.sleep(0.35)

        # 停止心跳
        stop_heartbeat(thread)

        # 验证线程已停止
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())

        # 验证至少发送了 2 次心跳（0.35s / 0.1s = 3.5，考虑启动延迟）
        self.assertGreaterEqual(mock_mqtt.client.publish.call_count, 2)

    @patch('djisdk.services.heartbeat.console')
    def test_heartbeat_message_format(self, mock_console):
        """测试心跳消息格式"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        thread = start_heartbeat(mock_mqtt, interval=0.1)
        time.sleep(0.15)  # 等待至少一次心跳
        stop_heartbeat(thread)
        thread.join(timeout=1)

        # 验证发送的消息
        self.assertGreater(mock_mqtt.client.publish.call_count, 0)

        # 检查第一次调用
        first_call = mock_mqtt.client.publish.call_args_list[0]
        topic, payload, qos = first_call[0][0], first_call[0][1], first_call[1]['qos']

        # 验证 topic
        self.assertEqual(topic, "thing/product/TEST_SN/drc/down")

        # 验证 QoS
        self.assertEqual(qos, 0)

        # 验证 payload
        payload_dict = json.loads(payload)
        self.assertIn('seq', payload_dict)
        self.assertIn('method', payload_dict)
        self.assertIn('data', payload_dict)
        self.assertEqual(payload_dict['method'], 'heart_beat')
        self.assertIn('timestamp', payload_dict['data'])

    @patch('djisdk.services.heartbeat.console')
    def test_heartbeat_sequence_increment(self, mock_console):
        """测试序列号递增"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        thread = start_heartbeat(mock_mqtt, interval=0.05)
        time.sleep(0.25)  # 发送多次心跳
        stop_heartbeat(thread)
        thread.join(timeout=1)

        # 获取所有调用的序列号
        calls = mock_mqtt.client.publish.call_args_list
        self.assertGreater(len(calls), 2)

        seqs = []
        for call_item in calls:
            payload = json.loads(call_item[0][1])
            seqs.append(payload['seq'])

        # 验证序列号递增
        for i in range(1, len(seqs)):
            self.assertEqual(seqs[i], seqs[i - 1] + 1)

    @patch('djisdk.services.heartbeat.console')
    def test_stop_heartbeat(self, mock_console):
        """测试停止心跳"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        thread = start_heartbeat(mock_mqtt, interval=0.1)
        self.assertTrue(thread.is_alive())

        stop_heartbeat(thread)
        thread.join(timeout=1)

        self.assertFalse(thread.is_alive())

    @patch('djisdk.services.heartbeat.console')
    def test_heartbeat_timing_accuracy(self, mock_console):
        """测试心跳定时精确性"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        interval = 0.1
        thread = start_heartbeat(mock_mqtt, interval=interval)

        start_time = time.perf_counter()
        time.sleep(0.5)
        stop_heartbeat(thread)
        thread.join(timeout=1)
        elapsed = time.perf_counter() - start_time

        # 获取调用次数
        call_count = mock_mqtt.client.publish.call_count

        # 验证频率（容忍 20% 误差）
        expected_count = elapsed / interval
        self.assertAlmostEqual(call_count, expected_count, delta=expected_count * 0.2)

    @patch('djisdk.services.heartbeat.console')
    def test_multiple_heartbeat_threads(self, mock_console):
        """测试多个心跳线程不干扰"""
        mock_mqtt1 = Mock()
        mock_mqtt1.gateway_sn = "SN1"
        mock_mqtt1.client = Mock()

        mock_mqtt2 = Mock()
        mock_mqtt2.gateway_sn = "SN2"
        mock_mqtt2.client = Mock()

        thread1 = start_heartbeat(mock_mqtt1, interval=0.1)
        thread2 = start_heartbeat(mock_mqtt2, interval=0.1)

        time.sleep(0.25)

        stop_heartbeat(thread1)
        stop_heartbeat(thread2)

        thread1.join(timeout=1)
        thread2.join(timeout=1)

        # 验证两个线程都发送了消息
        self.assertGreater(mock_mqtt1.client.publish.call_count, 0)
        self.assertGreater(mock_mqtt2.client.publish.call_count, 0)

        # 验证发送到不同的 topic
        topic1 = mock_mqtt1.client.publish.call_args_list[0][0][0]
        topic2 = mock_mqtt2.client.publish.call_args_list[0][0][0]

        self.assertEqual(topic1, "thing/product/SN1/drc/down")
        self.assertEqual(topic2, "thing/product/SN2/drc/down")

    @patch('djisdk.services.heartbeat.console')
    def test_multiple_heartbeat_instances(self, mock_console):
        """测试多个心跳实例可以同时运行"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        # 启动第一个线程
        thread1 = start_heartbeat(mock_mqtt, interval=0.1)
        time.sleep(0.05)

        # 启动第二个线程（模拟多实例场景）
        thread2 = start_heartbeat(mock_mqtt, interval=0.1)

        # 验证两个线程都在运行
        self.assertTrue(thread1.is_alive())
        self.assertTrue(thread2.is_alive())

        # 清理
        stop_heartbeat(thread1)
        stop_heartbeat(thread2)
        thread1.join(timeout=1)
        thread2.join(timeout=1)


class TestHeartbeatEdgeCases(unittest.TestCase):
    """测试心跳边界情况"""

    @patch('djisdk.services.heartbeat.console')
    def test_very_fast_interval(self, mock_console):
        """测试非常快的心跳间隔"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        # 0.01s = 100Hz
        thread = start_heartbeat(mock_mqtt, interval=0.01)
        time.sleep(0.1)
        stop_heartbeat(thread)
        thread.join(timeout=1)

        # 应该发送了约 10 次
        self.assertGreater(mock_mqtt.client.publish.call_count, 5)

    @patch('djisdk.services.heartbeat.console')
    def test_stop_already_stopped_thread(self, mock_console):
        """测试停止已停止的线程"""
        mock_mqtt = Mock()
        mock_mqtt.gateway_sn = "TEST_SN"
        mock_mqtt.client = Mock()

        thread = start_heartbeat(mock_mqtt, interval=0.1)
        stop_heartbeat(thread)
        thread.join(timeout=1)

        # 再次停止不应该抛出异常
        stop_heartbeat(thread)


if __name__ == '__main__':
    unittest.main()
