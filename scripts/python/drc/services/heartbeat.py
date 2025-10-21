"""
DRC 心跳维持服务
"""
import json
import time
import threading
from typing import Optional
from ..core import MQTTClient
from rich.console import Console
from rich.panel import Panel
from rich.live import Live

console = Console()


class HeartbeatKeeper:
    """DRC 心跳维持器 - 直接通过 MQTT 发送心跳"""

    def __init__(self, mqtt_client: MQTTClient, interval: float = 0.2):
        """
        Args:
            mqtt_client: MQTT 客户端
            interval: 心跳间隔（秒）
        """
        self.mqtt = mqtt_client
        self.interval = interval
        self.running = False
        self.thread = None

        # 统计信息
        self.sent_count = 0
        self.recv_count = 0
        self.failed_count = 0
        self.last_seq = int(time.time() * 1000)
        self.last_sent_ts: Optional[int] = None
        self.last_send_seq: Optional[int] = None
        self.last_recv_ts: Optional[int] = None
        self.last_recv_seq: Optional[int] = None

        # Rich Live display
        self.live: Optional[Live] = None

        # 订阅心跳响应
        self.drc_up_topic = f"thing/product/{mqtt_client.gateway_sn}/drc/up"
        self.drc_down_topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"

        # 注册心跳消息处理器
        self._original_on_message = mqtt_client.client.on_message
        mqtt_client.client.on_message = self._on_message_wrapper

    def _on_message_wrapper(self, client, userdata, msg):
        """消息处理包装器 - 同时处理心跳和其他消息"""
        # 先让原始处理器处理
        if self._original_on_message:
            self._original_on_message(client, userdata, msg)

        # 处理心跳响应
        if msg.topic == self.drc_up_topic:
            try:
                payload = json.loads(msg.payload.decode())
                if payload.get('method') == 'heart_beat':
                    self.recv_count += 1
                    self.last_recv_seq = payload.get('seq')
                    self.last_recv_ts = (payload.get('data') or {}).get('timestamp')
                    if self.live:
                        self.live.update(self._render_status(), refresh=True)
            except Exception:
                pass

    def _next_seq(self) -> int:
        """生成下一个序列号"""
        candidate = int(time.time() * 1000)
        if candidate <= self.last_seq:
            candidate = self.last_seq + 1
        self.last_seq = candidate
        return candidate

    def _render_status(self) -> Panel:
        """渲染心跳状态面板"""
        summary = (
            f"[bold green]发出[/]: {self.sent_count} (失败 {self.failed_count})\n"
            f"[bold cyan]收到[/]: {self.recv_count}\n"
            f"[bold green]最近发送[/]: seq={self.last_send_seq or '-'}, ts={self.last_sent_ts or '-'}\n"
            f"[bold cyan]最近收到[/]: seq={self.last_recv_seq or '-'}, ts={self.last_recv_ts or '-'}\n"
            f"[bold yellow]频率[/]: {1.0/self.interval:.2f}Hz"
        )
        return Panel(summary, title="DRC Heart Beat", padding=(1, 2))

    def start(self):
        """启动心跳"""
        # 检查是否已有线程在运行
        if self.thread and self.thread.is_alive():
            console.print("[yellow]⚠ 心跳已在运行中，跳过启动[/yellow]")
            return

        # 订阅心跳响应主题
        self.mqtt.client.subscribe(self.drc_up_topic, qos=0)
        console.print(f"[dim]已订阅心跳响应: {self.drc_up_topic}[/dim]")

        self.running = True
        self.sent_count = 0
        self.recv_count = 0
        self.failed_count = 0

        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
        console.print(f"[green]✓ 心跳已启动 (间隔: {self.interval}s, 频率: {1.0/self.interval:.1f}Hz)[/green]")

    def stop(self):
        """停止心跳"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            # 检查线程是否正常退出
            if self.thread.is_alive():
                console.print("[red]⚠ 心跳线程未能正常退出[/red]")
            else:
                console.print("[yellow]心跳已停止[/yellow]")

    def _heartbeat_loop(self):
        """心跳循环 - 使用精确定时（无 Live 显示）"""
        next_tick = time.perf_counter()

        try:
            while self.running:
                now = time.perf_counter()
                if now < next_tick:
                    time.sleep(min(self.interval, next_tick - now))
                    continue

                # 构建心跳消息
                seq = self._next_seq()
                timestamp = int(time.time() * 1000)
                payload = {
                    "seq": seq,
                    "method": "heart_beat",
                    "data": {
                        "timestamp": timestamp,
                    },
                }

                # 发送心跳（QoS 0，不等待响应）
                try:
                    info = self.mqtt.client.publish(
                        self.drc_down_topic,
                        json.dumps(payload),
                        qos=0
                    )

                    if info.rc == 0:
                        self.sent_count += 1
                        self.last_send_seq = seq
                        self.last_sent_ts = timestamp
                    else:
                        self.failed_count += 1
                except Exception as e:
                    self.failed_count += 1
                    console.print(f"[red]心跳发送异常: {e}[/red]")

                # 计算下一次发送时间
                next_tick += self.interval
                if next_tick < now:
                    next_tick = now + self.interval

        except KeyboardInterrupt:
            pass
        finally:
            self.live = None
