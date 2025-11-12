#!/usr/bin/env python3
"""
UWB to MQTT Publisher - 将 UWB 定位数据发布到 MQTT 服务器

实时读取 UWB 数据并以 JSON 格式发布到 MQTT broker

使用方法:
    python uwb2mqtt.py
"""

import json
import time
from uwb_client import UWBClient
import paho.mqtt.client as mqtt
from rich.console import Console

console = Console()

# ================== MQTT 配置 ===================
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# ================== UWB 配置 ===================
TARGET_NODE_ID = 0
PUBLISH_TOPIC = "uwb/position"
CLIENT_ID = f"uwb-pub-{int(time.time())}"
PUBLISH_RATE_HZ = 50  # 发布频率 (Hz)


# ================== MQTT 回调函数 ===================
def on_connect(client, userdata, flags, rc):
    """连接回调"""
    if rc == 0:
        console.print(f"[green]✓ Connected to MQTT broker: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}[/green]")
    else:
        console.print(f"[red]✗ Connection failed with code {rc}[/red]")


def on_disconnect(client, userdata, rc):
    """断开连接回调"""
    if rc != 0:
        console.print(f"[yellow]⚠ Unexpected disconnection (code {rc})[/yellow]")


# ================== 主函数 ===================
def main():
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]           UWB to MQTT Real-time Publisher                [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

    # 初始化 MQTT 客户端
    console.print(f"[cyan]Connecting to MQTT broker: {MQTT_CONFIG['host']}...[/cyan]")
    mqtt_client = mqtt.Client(client_id=CLIENT_ID)
    mqtt_client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect

    try:
        mqtt_client.connect(MQTT_CONFIG['host'], MQTT_CONFIG['port'], 60)
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to MQTT broker: {e}[/red]")
        return

    mqtt_client.loop_start()
    time.sleep(0.5)  # 等待连接建立

    # 初始化 UWB 客户端
    console.print(f"[cyan]Initializing UWB client (Node ID: {TARGET_NODE_ID})...[/cyan]")
    uwb_client = UWBClient(target_node_id=TARGET_NODE_ID, use_smoothing=True)

    console.print(f"\n[green]✓ Publish Topic:  {PUBLISH_TOPIC}[/green]")
    console.print(f"[green]✓ Publish Rate:   {PUBLISH_RATE_HZ} Hz[/green]")
    console.print(f"[green]✓ Client ID:      {CLIENT_ID}[/green]")
    console.print(f"\n[yellow]Press Ctrl+C to stop...[/yellow]\n")

    publish_interval = 1.0 / PUBLISH_RATE_HZ
    last_publish_time = time.time()
    msg_count = 0
    no_data_count = 0

    try:
        while True:
            current_time = time.time()

            if current_time - last_publish_time >= publish_interval:
                pos = uwb_client.get_position()

                if pos:
                    x, y, z = pos

                    # 构造 JSON 消息
                    message = {
                        'node_id': TARGET_NODE_ID,
                        'timestamp': round(current_time, 3),
                        'position': {
                            'x': round(x, 4),
                            'y': round(y, 4),
                            'z': round(z, 4)
                        }
                    }

                    # 发布到 MQTT
                    payload = json.dumps(message)
                    result = mqtt_client.publish(PUBLISH_TOPIC, payload, qos=0)

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        msg_count += 1
                        console.print(
                            f"[green]✓[/green] [[bold cyan]{msg_count:05d}[/bold cyan]] "
                            f"Published: x=[yellow]{x:7.4f}[/yellow], "
                            f"y=[yellow]{y:7.4f}[/yellow], "
                            f"z=[yellow]{z:7.4f}[/yellow]",
                            end='\r'
                        )
                        no_data_count = 0
                    else:
                        console.print(f"[red]✗ Publish failed (rc={result.rc})[/red]")

                    last_publish_time = current_time
                else:
                    no_data_count += 1
                    console.print(
                        f"[yellow]⚠ Waiting for UWB data... ({no_data_count})[/yellow]",
                        end='\r'
                    )

            time.sleep(0.001)  # 1ms 睡眠，避免 CPU 占用过高

    except KeyboardInterrupt:
        console.print(f"\n\n[bold yellow]✓ Stopped gracefully[/bold yellow]")
        console.print(f"[cyan]Total messages published: {msg_count}[/cyan]")
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
    finally:
        console.print(f"\n[cyan]Cleaning up...[/cyan]")
        uwb_client.stop()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        console.print("[green]✓ Disconnected from MQTT broker[/green]")
        console.print("[green]✓ UWB client stopped[/green]")


if __name__ == '__main__':
    main()
