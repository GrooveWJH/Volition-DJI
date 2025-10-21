#!/usr/bin/env python3
"""
一键发送控制权请求并进入 DRC 模式（使用 DRC 库）+ 监控所有 UP 消息

执行流程：
1. 向遥控器请求云端飞行控制权
2. 提示用户在遥控器上确认授权
3. 进入 DRC 模式
4. 启动心跳维持 DRC 连接
5. 实时监控所有 UP 消息并显示统计
6. Ctrl+C 退出时保存所有消息数据到 JSON 文件

运行：python request_and_enter_drc.py
"""
import sys
import time
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from drc import MQTTClient, ServiceCaller, request_control_auth, enter_drc_mode, HeartbeatKeeper

# ======== 配置 ========
MQTT_CONFIG = {'host': '172.20.10.2', 'port': 1883, 'username': 'admin', 'password': '302811055wjhhz'}
GATEWAY_SN = "9N9CN180011TJN"  # 9N9CN2J0012CXY (001) | 9N9CN180011TJN (003)
USER_ID, USER_CALLSIGN = "groove", "吴建豪"

# DRC 模式参数
MQTT_BROKER_CONFIG = {
    'address': f"{MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}",
    'client_id': f"drc-{GATEWAY_SN}",
    'username': 'admin',
    'password': '302811055wjhhz',
    'expire_time': 1_700_000_000,
    'enable_tls': False,
}
OSD_FREQUENCY, HSI_FREQUENCY, HEARTBEAT_INTERVAL = 100, 2, 0.2  # Hz, Hz, 秒
OUTPUT_JSON = f"drc_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"  # 输出文件名
# ======== 配置结束 ========


class DRCMessageMonitor:
    """DRC UP 消息监控器"""

    def __init__(self, mqtt_client: MQTTClient, heartbeat: 'HeartbeatKeeper' = None):
        self.mqtt = mqtt_client
        self.heartbeat = heartbeat
        self.drc_up_topic = f"thing/product/{mqtt_client.gateway_sn}/drc/up"

        # 统计信息
        self.message_counts: Dict[str, int] = defaultdict(int)  # method -> count
        self.latest_messages: Dict[str, Any] = {}  # method -> 最新消息数据
        self.first_time: Dict[str, float] = {}  # method -> 第一次收到的时间
        self.last_time: Dict[str, float] = {}  # method -> 最后一次收到的时间
        self.start_time = time.time()

        # 注册消息处理器
        self._original_on_message = mqtt_client.client.on_message
        mqtt_client.client.on_message = self._on_message_wrapper

        # 订阅 DRC UP 主题
        mqtt_client.client.subscribe(self.drc_up_topic, qos=0)

    def _on_message_wrapper(self, client, userdata, msg):
        """消息处理包装器"""
        # 先让原始处理器处理
        if self._original_on_message:
            self._original_on_message(client, userdata, msg)

        # 处理 DRC UP 消息
        if msg.topic == self.drc_up_topic:
            try:
                payload = json.loads(msg.payload.decode())
                method = payload.get('method')
                if method:
                    now = time.time()
                    self.message_counts[method] += 1
                    self.latest_messages[method] = payload
                    self.last_time[method] = now
                    if method not in self.first_time:
                        self.first_time[method] = now
            except Exception:
                pass

    def get_frequency(self, method: str) -> float:
        """计算消息频率（Hz）"""
        if method not in self.first_time or method not in self.last_time:
            return 0.0
        count = self.message_counts[method]
        if count <= 1:
            return 0.0
        time_span = self.last_time[method] - self.first_time[method]
        if time_span <= 0:
            return 0.0
        return (count - 1) / time_span

    def render_status(self) -> Panel:
        """渲染监控面板（包含心跳信息）"""
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("消息类型 (Method)", style="cyan", width=30)
        table.add_column("次数", justify="right", style="yellow", width=10)
        table.add_column("频率 (Hz)", justify="right", style="green", width=15)
        table.add_column("最后更新", justify="right", style="dim", width=15)

        # 按消息类型排序
        sorted_methods = sorted(self.message_counts.keys())

        for method in sorted_methods:
            count = self.message_counts[method]
            freq = self.get_frequency(method)
            last_time_ago = time.time() - self.last_time.get(method, 0)

            # 格式化频率显示
            if freq > 0:
                freq_str = f"{freq:.2f} Hz"
            else:
                freq_str = "-"

            # 格式化最后更新时间
            if last_time_ago < 1:
                time_str = "刚刚"
            elif last_time_ago < 60:
                time_str = f"{last_time_ago:.0f}秒前"
            else:
                time_str = f"{last_time_ago/60:.0f}分钟前"

            table.add_row(method, str(count), freq_str, time_str)

        # 总运行时间和心跳状态
        runtime = time.time() - self.start_time
        summary_parts = [
            f"[bold]运行时间[/bold]: {runtime:.1f}秒",
            f"[bold]消息类型[/bold]: {len(self.message_counts)}"
        ]

        # 添加心跳状态
        if self.heartbeat:
            hb_freq = 1.0 / self.heartbeat.interval if self.heartbeat.interval > 0 else 0
            summary_parts.append(
                f"[bold green]心跳[/bold green]: 发{self.heartbeat.sent_count}/收{self.heartbeat.recv_count} ({hb_freq:.1f}Hz)"
            )

        summary = " | ".join(summary_parts)

        return Panel(
            table,
            title="[bold cyan]DRC UP 消息监控[/bold cyan]",
            subtitle=summary,
            border_style="cyan"
        )

    def save_to_json(self, filename: str):
        """保存所有消息数据到 JSON 文件"""
        output = {
            "metadata": {
                "gateway_sn": self.mqtt.gateway_sn,
                "capture_time": datetime.now().isoformat(),
                "runtime_seconds": time.time() - self.start_time,
                "total_message_types": len(self.message_counts),
                "total_messages": sum(self.message_counts.values())
            },
            "statistics": {
                method: {
                    "count": self.message_counts[method],
                    "frequency_hz": self.get_frequency(method),
                    "first_time": datetime.fromtimestamp(self.first_time[method]).isoformat() if method in self.first_time else None,
                    "last_time": datetime.fromtimestamp(self.last_time[method]).isoformat() if method in self.last_time else None
                }
                for method in sorted(self.message_counts.keys())
            },
            "latest_messages": self.latest_messages
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)


def main() -> int:
    console = Console()

    # 1. 连接 MQTT
    console.rule("[bold cyan]连接 MQTT[/bold cyan]")
    mqtt = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
    mqtt.connect()
    caller = ServiceCaller(mqtt, timeout=10)

    # 2. 请求控制权
    console.rule("[bold cyan]请求控制权[/bold cyan]")
    try:
        request_control_auth(caller, user_id=USER_ID, user_callsign=USER_CALLSIGN)
    except Exception as e:
        console.print(f"[red]✗ 控制权请求失败: {e}[/red]")
        mqtt.disconnect()
        return 1

    # 3. 等待用户在遥控器上确认
    console.print("\n[bold green]控制权请求已发送，请在遥控器上点击确认授权。完成后在此处按回车继续...[/bold green]")
    try:
        input()
    except KeyboardInterrupt:
        console.print("[yellow]检测到中断，退出。[/yellow]")
        mqtt.disconnect()
        return 1

    # 4. 进入 DRC 模式
    console.rule("[bold cyan]进入 DRC 模式[/bold cyan]")
    try:
        enter_drc_mode(caller, mqtt_broker=MQTT_BROKER_CONFIG, osd_frequency=OSD_FREQUENCY, hsi_frequency=HSI_FREQUENCY)
    except Exception as e:
        console.print(f"[red]✗ 进入 DRC 模式失败: {e}[/red]")
        mqtt.disconnect()
        return 1

    # 5. 启动消息监控和心跳
    console.rule("[bold cyan]DRC 心跳 + 消息监控[/bold cyan]")
    console.print(
        "[bold green]已进入 DRC 模式，开始发送心跳以维持链路。[/bold green]\n"
        "[bold yellow]按 Ctrl+C 停止心跳、保存数据并退出。[/bold yellow]\n"
    )

    # 先启动心跳（不显示 Live 面板）
    heartbeat = HeartbeatKeeper(mqtt, interval=HEARTBEAT_INTERVAL)
    heartbeat.start()

    # 启动监控（传入 heartbeat 引用，整合显示）
    console.print("[dim]正在启动 DRC 消息监控...[/dim]")
    monitor = DRCMessageMonitor(mqtt, heartbeat=heartbeat)

    # 实时显示统一的监控面板
    try:
        with Live(monitor.render_status(), refresh_per_second=2, console=console) as live:
            while True:
                time.sleep(0.5)
                live.update(monitor.render_status())
    except KeyboardInterrupt:
        console.print("\n[yellow]检测到中断，正在停止...[/yellow]")
    finally:
        heartbeat.stop()

        # 保存数据
        console.print(f"[cyan]正在保存消息数据到 {OUTPUT_JSON}...[/cyan]")
        monitor.save_to_json(OUTPUT_JSON)
        console.print(f"[green]✓ 数据已保存到 {OUTPUT_JSON}[/green]")

        mqtt.disconnect()

    console.print("[green]✓ 已退出 DRC 模式[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
