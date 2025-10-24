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
        # OSD 数据缓存
        self.osd_data = {
            'latitude': None, 'longitude': None, 'height': None, 'attitude_head': None,
            'horizontal_speed': None, 'speed_x': None, 'speed_y': None, 'speed_z': None,
            'down_distance': None, 'down_enable': None, 'down_work': None,
            'battery_percent': None
        }
        # 起飞点高度（第一次读取到的全局高度）
        self.takeoff_height = None

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

        # 订阅 DRC 上行主题（接收 OSD/HSI 数据）
        drc_up_topic = f"thing/product/{self.gateway_sn}/drc/up"
        self.client.subscribe(drc_up_topic, qos=0)
        console.print(f"[green]✓[/green] 已订阅: {drc_up_topic}")

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

    def get_latitude(self) -> Optional[float]:
        """获取最新纬度（无卫星信号时返回 None）"""
        with self.lock:
            return self.osd_data['latitude']

    def get_longitude(self) -> Optional[float]:
        """获取最新经度（无卫星信号时返回 None）"""
        with self.lock:
            return self.osd_data['longitude']

    def get_height(self) -> Optional[float]:
        """获取最新全局高度（GPS高度，无卫星信号时返回 None）"""
        with self.lock:
            return self.osd_data['height']

    def get_relative_height(self) -> Optional[float]:
        """获取距起飞点高度（当前高度 - 起飞点高度，无数据时返回 None）"""
        with self.lock:
            if self.osd_data['height'] is not None and self.takeoff_height is not None:
                return self.osd_data['height'] - self.takeoff_height
            return None

    def get_attitude_head(self) -> Optional[float]:
        """获取最新航向角（无数据时返回 None）"""
        with self.lock:
            return self.osd_data['attitude_head']

    def get_speed(self) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """获取速度数据 (水平速度, X轴速度, Y轴速度, Z轴速度)"""
        with self.lock:
            return (
                self.osd_data['horizontal_speed'],
                self.osd_data['speed_x'],
                self.osd_data['speed_y'],
                self.osd_data['speed_z']
            )

    def get_battery_percent(self) -> Optional[int]:
        """获取电池电量百分比（无数据时返回 None）"""
        with self.lock:
            return self.osd_data['battery_percent']

    def get_local_height(self) -> Optional[float]:
        """获取HSI高度/下视距离（无数据时返回 None）"""
        with self.lock:
            return self.osd_data['down_distance']

    def is_local_height_ok(self) -> bool:
        """判断 HSI 高度数据是否有效（down_enable 和 down_work 都为 True）"""
        with self.lock:
            return self.osd_data['down_enable'] is True and self.osd_data['down_work'] is True

    def get_position(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """获取最新位置 (纬度, 经度, 高度)，无卫星信号时返回 (None, None, None)"""
        with self.lock:
            return (self.osd_data['latitude'], self.osd_data['longitude'], self.osd_data['height'])

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

            # 处理 OSD 数据推送
            if payload.get('method') == 'osd_info_push':
                data = payload.get('data', {})
                with self.lock:
                    self.osd_data['latitude'] = data.get('latitude')
                    self.osd_data['longitude'] = data.get('longitude')
                    height = data.get('height')
                    self.osd_data['height'] = height
                    # 记录起飞点高度（第一次读取到有效高度时）
                    if height is not None and self.takeoff_height is None:
                        self.takeoff_height = height
                    self.osd_data['attitude_head'] = data.get('attitude_head')
                    self.osd_data['horizontal_speed'] = data.get('horizontal_speed')
                    self.osd_data['speed_x'] = data.get('speed_x')
                    self.osd_data['speed_y'] = data.get('speed_y')
                    self.osd_data['speed_z'] = data.get('speed_z')
                return

            # 处理 HSI 数据推送
            if payload.get('method') == 'hsi_info_push':
                data = payload.get('data', {})
                with self.lock:
                    self.osd_data['down_distance'] = data.get('down_distance')
                    self.osd_data['down_enable'] = data.get('down_enable')
                    self.osd_data['down_work'] = data.get('down_work')
                return

            # 处理电池信息推送
            if payload.get('method') == 'drc_batteries_info_push':
                data = payload.get('data', {})
                with self.lock:
                    self.osd_data['battery_percent'] = data.get('capacity_percent')
                return

            # 处理服务响应
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
