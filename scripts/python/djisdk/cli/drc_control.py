#!/usr/bin/env python3
"""
DJI DRC 控制命令行工具

基于 djisdk 重构后的架构 - 使用纯函数服务接口。

用法:
    python -m djisdk.cli.drc_control --sn <gateway_sn> --username <user> --password <pass>

功能:
    1. 请求控制权
    2. 进入 DRC 模式
    3. 维持心跳
    4. 支持直播控制（镜头切换、清晰度设置等）
    5. 交互式命令界面
"""
import argparse
import sys
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

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
    start_heartbeat,
    stop_heartbeat,
)

console = Console()


def main():
    """主函数 - DRC 控制工具入口"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='DJI DRC 控制工具 - 基于 djisdk 重构架构',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m djisdk.cli.drc_control --sn 9N9CN180011TJN --username admin --password mypass
  python -m djisdk.cli.drc_control --sn 9N9CN180011TJN --host 172.20.10.2 --username admin --password mypass
        """
    )
    parser.add_argument('--sn', required=True, help='网关序列号 (必需)')
    parser.add_argument('--host', default='172.20.10.2', help='MQTT 服务器地址 (默认: 172.20.10.2)')
    parser.add_argument('--port', type=int, default=1883, help='MQTT 端口 (默认: 1883)')
    parser.add_argument('--username', required=True, help='MQTT 用户名 (必需)')
    parser.add_argument('--password', required=True, help='MQTT 密码 (必需)')
    parser.add_argument('--user-id', default='cli_user', help='用户 ID (默认: cli_user)')
    parser.add_argument('--user-callsign', default='CLI Pilot', help='用户呼号 (默认: CLI Pilot)')
    parser.add_argument('--osd-freq', type=int, default=30, help='OSD 频率 Hz (默认: 30)')
    parser.add_argument('--hsi-freq', type=int, default=10, help='HSI 频率 Hz (默认: 10)')
    parser.add_argument('--heartbeat-interval', type=float, default=0.2, help='心跳间隔秒 (默认: 0.2)')

    args = parser.parse_args()

    # 构建配置
    mqtt_config = {
        'host': args.host,
        'port': args.port,
        'username': args.username,
        'password': args.password,
    }

    mqtt_broker_config = {
        'address': f"{args.host}:{args.port}",
        'client_id': f"drc-cli-{args.sn}",
        'username': args.username,
        'password': args.password,
        'expire_time': 1_700_000_000,
        'enable_tls': False,
    }

    # 打印欢迎界面
    print_welcome(args.sn, args.host)

    # 初始化连接
    mqtt_client = MQTTClient(args.sn, mqtt_config)
    mqtt_client.connect()
    caller = ServiceCaller(mqtt_client, timeout=10)

    heartbeat_thread = None

    try:
        # ========== Step 1: 请求控制权 ==========
        console.rule("[bold cyan]Step 1: 请求控制权[/bold cyan]")
        try:
            request_control_auth(caller, user_id=args.user_id, user_callsign=args.user_callsign)
        except Exception as e:
            console.print(f"[red]✗ 控制权请求失败: {e}[/red]")
            console.print("[yellow]请检查：1) 无人机是否开机 2) MQTT 配置是否正确[/yellow]")
            return 1

        console.print("\n[yellow]⚠ 请在遥控器上确认授权，完成后按回车继续...[/yellow]")
        input()

        # ========== Step 2: 进入 DRC 模式 ==========
        console.rule("[bold cyan]Step 2: 进入 DRC 模式[/bold cyan]")
        try:
            enter_drc_mode(
                caller,
                mqtt_broker=mqtt_broker_config,
                osd_frequency=args.osd_freq,
                hsi_frequency=args.hsi_freq
            )
        except Exception as e:
            console.print(f"[red]✗ 进入 DRC 模式失败: {e}[/red]")
            return 1

        # ========== Step 3: 启动心跳 ==========
        console.rule("[bold cyan]Step 3: 启动心跳[/bold cyan]")
        heartbeat_thread = start_heartbeat(mqtt_client, interval=args.heartbeat_interval)

        # ========== Step 4: 交互式控制 ==========
        console.rule("[bold green]✓ DRC 模式就绪[/bold green]")
        console.print("[dim]输入命令进行控制，输入 'help' 查看帮助，输入 'quit' 退出[/dim]\n")

        interactive_control(caller)

    except KeyboardInterrupt:
        console.print("\n[yellow]检测到 Ctrl+C 中断信号[/yellow]")

    except Exception as e:
        console.print(f"\n[red]✗ 发生错误: {e}[/red]")
        return 1

    finally:
        # ========== 清理资源 ==========
        console.print("\n")
        console.rule("[bold cyan]清理资源[/bold cyan]")

        if heartbeat_thread:
            stop_heartbeat(heartbeat_thread)

        try:
            exit_drc_mode(caller)
        except Exception as e:
            console.print(f"[yellow]退出 DRC 模式失败: {e}[/yellow]")

        try:
            release_control_auth(caller)
        except Exception as e:
            console.print(f"[yellow]释放控制权失败: {e}[/yellow]")

        mqtt_client.disconnect()
        console.print("[green]✓ 已安全退出[/green]")

    return 0


def print_welcome(sn: str, host: str):
    """打印欢迎界面"""
    welcome_text = f"""
[bold cyan]DJI DRC 控制工具[/bold cyan]

[bold]连接信息:[/bold]
  • 网关 SN: [yellow]{sn}[/yellow]
  • MQTT 地址: [yellow]{host}[/yellow]

[bold]架构:[/bold]
  • 基于 djisdk 重构后的极简架构
  • 2 个核心类 (MQTTClient + ServiceCaller)
  • 纯函数业务层 (无状态服务)
"""
    console.print(Panel(welcome_text, border_style="cyan"))


def interactive_control(caller: ServiceCaller):
    """
    交互式控制界面

    命令:
        help    - 显示帮助
        lens    - 切换直播镜头
        quality - 设置直播清晰度
        start   - 开始直播推流
        stop    - 停止直播推流
        status  - 显示当前状态（预留）
        quit    - 退出程序
    """
    commands = {
        'help': '显示帮助信息',
        'lens': '切换直播镜头',
        'quality': '设置直播清晰度',
        'start': '开始直播推流',
        'stop': '停止直播推流',
        'status': '显示当前状态 (预留功能)',
        'quit': '退出程序',
    }

    while True:
        console.print()
        cmd = Prompt.ask("[bold cyan]›[/bold cyan]", default="help").strip().lower()

        if cmd == 'help':
            show_help(commands)

        elif cmd == 'lens':
            handle_lens_change(caller)

        elif cmd == 'quality':
            handle_quality_change(caller)

        elif cmd == 'start':
            handle_start_push(caller)

        elif cmd == 'stop':
            handle_stop_push(caller)

        elif cmd == 'status':
            console.print("[yellow]⚠ 状态显示功能待实现 - 需要订阅 OSD/HSI 数据[/yellow]")

        elif cmd == 'quit':
            if Confirm.ask("[yellow]确认退出?[/yellow]", default=True):
                break

        elif cmd == '':
            continue

        else:
            console.print(f"[red]✗ 未知命令: '{cmd}'[/red] (输入 'help' 查看帮助)")


def show_help(commands: dict):
    """显示帮助信息"""
    table = Table(title="可用命令", show_header=True, header_style="bold cyan")
    table.add_column("命令", style="cyan", width=12)
    table.add_column("说明", style="white")

    for cmd, desc in commands.items():
        table.add_row(cmd, desc)

    console.print(table)


def handle_lens_change(caller: ServiceCaller):
    """处理镜头切换"""
    console.print("\n[bold]切换直播镜头[/bold]")
    video_id = Prompt.ask("  镜头 ID", default="52-0-0")
    console.print("\n  镜头类型:")
    console.print("    • thermal - 红外镜头")
    console.print("    • wide    - 广角镜头")
    console.print("    • zoom    - 变焦镜头")
    console.print("    • normal  - 普通镜头")
    video_type = Prompt.ask("  镜头类型", default="normal")

    try:
        change_live_lens(caller, video_id, video_type)
    except Exception as e:
        console.print(f"[red]✗ 镜头切换失败: {e}[/red]")


def handle_quality_change(caller: ServiceCaller):
    """处理清晰度设置"""
    console.print("\n[bold]设置直播清晰度[/bold]")
    console.print("  0 - 自适应")
    console.print("  1 - 流畅")
    console.print("  2 - 标清")
    console.print("  3 - 高清")
    console.print("  4 - 超清")

    try:
        quality = int(Prompt.ask("  选择清晰度", default="0"))
        if quality < 0 or quality > 4:
            console.print("[red]✗ 清晰度必须在 0-4 之间[/red]")
            return
        set_live_quality(caller, quality)
    except ValueError:
        console.print("[red]✗ 请输入有效的数字[/red]")
    except Exception as e:
        console.print(f"[red]✗ 设置清晰度失败: {e}[/red]")


def handle_start_push(caller: ServiceCaller):
    """处理开始推流"""
    console.print("\n[bold]开始直播推流[/bold]")
    url = Prompt.ask("  推流 URL", default="rtmp://localhost/live/test")
    video_id = Prompt.ask("  镜头 ID", default="52-0-0")

    console.print("\n  URL 类型:")
    console.print("    0 - RTMP")
    console.print("    1 - RTSP")
    console.print("    2 - GB28181")

    try:
        url_type = int(Prompt.ask("  URL 类型", default="0"))
        video_quality = int(Prompt.ask("  清晰度 (0-4)", default="0"))

        start_live_push(caller, url, video_id, url_type, video_quality)
    except ValueError:
        console.print("[red]✗ 请输入有效的数字[/red]")
    except Exception as e:
        console.print(f"[red]✗ 开始推流失败: {e}[/red]")


def handle_stop_push(caller: ServiceCaller):
    """处理停止推流"""
    console.print("\n[bold]停止直播推流[/bold]")
    video_id = Prompt.ask("  镜头 ID", default="52-0-0")

    try:
        stop_live_push(caller, video_id)
    except Exception as e:
        console.print(f"[red]✗ 停止推流失败: {e}[/red]")


if __name__ == '__main__':
    sys.exit(main())
