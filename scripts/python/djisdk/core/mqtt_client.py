"""
MQTT 客户端 - 负责连接管理和消息收发
"""
import json
import threading
from typing import Dict, Any, Optional
from concurrent.futures import Future
import paho.mqtt.client as mqtt
from rich.console import Console

console = Console()


class MQTTClient:
    """简单的 MQTT 客户端封装"""

    def __init__(self, gateway_sn: str, mqtt_config: Dict[str, Any]):
        self.gateway_sn = gateway_sn
        self.config = mqtt_config
        self.client: Optional[mqtt.Client] = None
        self.pending_requests: Dict[str, Future] = {}
        self.lock = threading.Lock()

    def connect(self):
        """建立 MQTT 连接"""
        self.client = mqtt.Client(client_id=f"python-drc-{self.gateway_sn}")
        self.client.username_pw_set(self.config['username'], self.config['password'])
        self.client.on_message = self._on_message

        console.print(f"[cyan]连接 MQTT: {self.config['host']}:{self.config['port']}[/cyan]")
        self.client.connect(self.config['host'], self.config['port'], 60)
        self.client.loop_start()

        # 订阅响应主题
        reply_topic = f"thing/product/{self.gateway_sn}/services_reply"
        self.client.subscribe(reply_topic, qos=1)
        console.print(f"[green]✓[/green] 已订阅: {reply_topic}")

    def disconnect(self):
        """断开连接"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            console.print("[yellow]MQTT 连接已断开[/yellow]")

    def cleanup_request(self, tid: str):
        """清理挂起的请求（用于超时处理）"""
        with self.lock:
            self.pending_requests.pop(tid, None)

    def publish(self, method: str, data: Dict[str, Any], tid: str) -> Future:
        """
        发布消息并返回 Future 等待响应

        Args:
            method: 服务方法名
            data: 请求数据
            tid: 事务 ID

        Returns:
            Future 对象，可通过 result() 获取响应
        """
        topic = f"thing/product/{self.gateway_sn}/services"
        payload = {
            "tid": tid,
            # bid (business id) 和 tid (transaction id):
            # DJI 协议要求两个字段，实测中两者可以相同
            "bid": tid,
            "timestamp": int(__import__('time').time() * 1000),
            "method": method,
            "data": data
        }

        # 创建 Future 等待响应
        future = Future()
        with self.lock:
            self.pending_requests[tid] = future

        # 发布消息
        msg_json = json.dumps(payload)
        self.client.publish(topic, msg_json, qos=1)
        console.print(f"[blue]→[/blue] 发送 {method} (tid: {tid[:8]}...)")

        return future

    def _on_message(self, client, userdata, msg):
        """处理收到的消息"""
        try:
            payload = json.loads(msg.payload.decode())
            tid = payload.get('tid')

            if not tid:
                return

            with self.lock:
                future = self.pending_requests.pop(tid, None)

            if future:
                # 检查是否有错误 - DJI 协议中 info.code != 0 表示错误
                info = payload.get('info', {})
                if info and info.get('code') != 0:
                    error_msg = info.get('message', 'Unknown error')
                    console.print(f"[red]✗[/red] 错误: {error_msg}")
                    future.set_exception(Exception(error_msg))
                else:
                    console.print(f"[green]←[/green] 收到响应 (tid: {tid[:8]}...)")
                    future.set_result(payload.get('data', {}))

        except Exception as e:
            console.print(f"[red]消息处理异常: {e}[/red]")
