#!/usr/bin/env python3
"""
DRC 控制命令行工具

用法:
    python drc_control.py --sn <gateway_sn>

功能:
    1. 请求控制权
    2. 进入 DRC 模式
    3. 维持心跳
    4. 支持直播控制（镜头切换、清晰度设置等）
"""
import argparse
import time
from rich.console import Console
from rich.prompt import Prompt, Confirm

from ..core import MQTTClient, ServiceCaller
from ..services import (
    request_control_auth,
    release_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    change_live_lens,
    set_live_quality,
    start_live_push,
    stop_live_push,
    HeartbeatKeeper,
)

console = Console()


def main():
    # 解析参数
    parser = argparse.ArgumentParser(description='DJI DRC 控制工具')
    parser.add_argument('--sn', required=True, help='网关序列号')
    parser.add_argument('--host', default='mqtt.dji.com', help='MQTT 服务器地址')
    parser.add_argument('--port', type=int, default=1883, help='MQTT 端口')
    parser.add_argument('--username', required=True, help='MQTT 用户名')
    parser.add_argument('--password', required=True, help='MQTT 密码')
    args = parser.parse_args()

    # 初始化 MQTT 客户端
    mqtt_config = {
        'host': args.host,
        'port': args.port,
        'username': args.username,
        'password': args.password,
    }

    console.print("[bold cyan]═══ DJI DRC 控制工具 ═══[/bold cyan]\n")

    mqtt_client = MQTTClient(args.sn, mqtt_config)
    mqtt_client.connect()

    # 创建服务调用器
    caller = ServiceCaller(mqtt_client, timeout=10)

    # 创建心跳维持器
    heartbeat = HeartbeatKeeper(caller, interval=3)

    try:
        # Step 1: 请求控制权
        if not request_control_auth(caller):
            console.print("[red]无法获取控制权,退出[/red]")
            return

        # Step 2: 进入 DRC 模式
        if not enter_drc_mode(caller, osd_frequency=5, hsi_frequency=5):
            console.print("[red]无法进入 DRC 模式,退出[/red]")
            return

        # Step 3: 启动心跳
        heartbeat.start()

        # Step 4: 交互式控制
        console.print("\n[bold green]✓ DRC 模式已就绪[/bold green]")
        console.print("[dim]输入命令进行控制,输入 'help' 查看帮助[/dim]\n")

        interactive_control(caller)

    except KeyboardInterrupt:
        console.print("\n[yellow]接收到退出信号[/yellow]")

    finally:
        # 清理
        console.print("\n[cyan]清理资源...[/cyan]")
        heartbeat.stop()
        exit_drc_mode(caller)
        release_control_auth(caller)
        mqtt_client.disconnect()
        console.print("[green]✓ 已退出[/green]")


def interactive_control(caller: ServiceCaller):
    """交互式控制界面"""

    commands = {
        'help': '显示帮助',
        'lens': '切换直播镜头',
        'quality': '设置直播清晰度',
        'start': '开始直播推流',
        'stop': '停止直播推流',
        'quit': '退出程序',
    }

    while True:
        console.print()
        cmd = Prompt.ask("[bold cyan]命令[/bold cyan]", default="help").lower()

        if cmd == 'help':
            console.print("\n[bold]可用命令:[/bold]")
            for c, desc in commands.items():
                console.print(f"  [cyan]{c:10}[/cyan] - {desc}")

        elif cmd == 'lens':
            video_id = Prompt.ask("镜头 ID", default="52-0-0")
            video_type = Prompt.ask("镜头类型", default="normal")
            change_live_lens(caller, video_id, video_type)

        elif cmd == 'quality':
            console.print("\n清晰度选项:")
            console.print("  0 - 自适应")
            console.print("  1 - 流畅")
            console.print("  2 - 标清")
            console.print("  3 - 高清")
            console.print("  4 - 超清")
            quality = int(Prompt.ask("选择清晰度", default="0"))
            set_live_quality(caller, quality)

        elif cmd == 'start':
            url = Prompt.ask("推流 URL", default="rtmp://localhost/live/test")
            video_id = Prompt.ask("镜头 ID", default="52-0-0")
            start_live_push(caller, url, video_id)

        elif cmd == 'stop':
            video_id = Prompt.ask("镜头 ID", default="52-0-0")
            stop_live_push(caller, video_id)

        elif cmd == 'quit':
            if Confirm.ask("确认退出?"):
                break

        else:
            console.print(f"[red]未知命令: {cmd}[/red] (输入 'help' 查看帮助)")


if __name__ == '__main__':
    main()
