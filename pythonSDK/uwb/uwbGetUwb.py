#!/usr/bin/env python3
"""
UWB MQTT Subscriber - 订阅并显示 UWB 定位数据

从 MQTT broker 接收 UWB 数据并打印 JSON 原始内容（用于调试）

使用方法:
    python uwbGetUwb.py
"""

import json
import time
import paho.mqtt.client as mqtt
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from datetime import datetime

console = Console()

# ================== MQTT 配置 ===================
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

SUBSCRIBE_TOPIC = "uwb/position"
CLIENT_ID = f"uwb-sub-{int(time.time())}"

msg_count = 0
start_time = time.time()


# ================== MQTT 回调函数 ===================
def on_connect(client, userdata, flags, rc):
    """连接回调"""
    if rc == 0:
        console.print(f"\n[green]✓ Connected to MQTT broker: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}[/green]")
        client.subscribe(SUBSCRIBE_TOPIC, qos=0)
        console.print(f"[green]✓ Subscribed to topic: [bold]{SUBSCRIBE_TOPIC}[/bold][/green]\n")
        console.print("[yellow]Waiting for messages...[/yellow]\n")
    else:
        console.print(f"[red]✗ Connection failed with code {rc}[/red]")


def on_message(client, userdata, msg):
    """消息接收回调"""
    global msg_count
    msg_count += 1

    try:
        # 解析 JSON 数据
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)

        # 计算接收时间
        receive_time = time.time()
        elapsed = receive_time - start_time
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # 打印消息头
        console.print(f"[cyan]{'─' * 70}[/cyan]")
        console.print(
            f"[bold yellow]Message #{msg_count:05d}[/bold yellow] | "
            f"[cyan]Time: {timestamp}[/cyan] | "
            f"[cyan]Elapsed: {elapsed:.2f}s[/cyan]"
        )
        console.print(f"[cyan]Topic: {msg.topic}[/cyan]")
        console.print(f"[cyan]{'─' * 70}[/cyan]")

        # 打印原始 JSON（使用 rich.json 格式化）
        console.print("[bold magenta]Raw JSON:[/bold magenta]")
        json_obj = JSON(payload)
        console.print(json_obj)

        # 打印解析后的关键信息
        if 'position' in data:
            pos = data['position']
            node_id = data.get('node_id', 'N/A')
            msg_timestamp = data.get('timestamp', 'N/A')

            # 计算延迟（如果有时间戳）
            latency_str = ""
            if isinstance(msg_timestamp, (int, float)):
                latency = (receive_time - msg_timestamp) * 1000  # ms
                latency_str = f" | [yellow]Latency: {latency:.1f}ms[/yellow]"

            console.print(
                f"\n[bold green]Position Summary:[/bold green] "
                f"Node ID=[cyan]{node_id}[/cyan]{latency_str}"
            )
            console.print(
                f"  x = [yellow]{pos['x']:8.4f}[/yellow] m\n"
                f"  y = [yellow]{pos['y']:8.4f}[/yellow] m\n"
                f"  z = [yellow]{pos['z']:8.4f}[/yellow] m"
            )

        console.print()  # 空行分隔

    except json.JSONDecodeError as e:
        console.print(f"[red]✗ JSON decode error: {e}[/red]")
        console.print(f"[yellow]Raw payload:[/yellow] {msg.payload}")
    except Exception as e:
        console.print(f"[red]✗ Error processing message: {e}[/red]")


def on_disconnect(client, userdata, rc):
    """断开连接回调"""
    if rc != 0:
        console.print(f"[yellow]⚠ Unexpected disconnection (code {rc})[/yellow]")


# ================== 主函数 ===================
def main():
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]           UWB MQTT Subscriber (Debug Mode)                [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

    # 显示配置信息
    config_panel = Panel(
        f"[cyan]Host:[/cyan]     {MQTT_CONFIG['host']}\n"
        f"[cyan]Port:[/cyan]     {MQTT_CONFIG['port']}\n"
        f"[cyan]Topic:[/cyan]    {SUBSCRIBE_TOPIC}\n"
        f"[cyan]Client ID:[/cyan] {CLIENT_ID}",
        title="[bold yellow]Configuration[/bold yellow]",
        border_style="cyan"
    )
    console.print(config_panel)

    # 初始化 MQTT 客户端
    console.print(f"\n[cyan]Connecting to MQTT broker...[/cyan]")
    client = mqtt.Client(client_id=CLIENT_ID)
    client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(MQTT_CONFIG['host'], MQTT_CONFIG['port'], 60)
    except Exception as e:
        console.print(f"[red]✗ Failed to connect: {e}[/red]")
        return

    console.print(f"[yellow]Press Ctrl+C to stop...[/yellow]")

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        console.print(f"\n\n[bold yellow]✓ Stopped gracefully[/bold yellow]")
        console.print(f"[cyan]Total messages received: {msg_count}[/cyan]")
        console.print(f"[cyan]Total duration: {time.time() - start_time:.2f}s[/cyan]")
        if msg_count > 0:
            avg_rate = msg_count / (time.time() - start_time)
            console.print(f"[cyan]Average rate: {avg_rate:.2f} msg/s[/cyan]")
    finally:
        client.disconnect()
        console.print("[green]✓ Disconnected from MQTT broker[/green]")


if __name__ == '__main__':
    main()
