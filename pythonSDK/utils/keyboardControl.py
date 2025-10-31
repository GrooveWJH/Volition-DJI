#!/usr/bin/env python3
"""
DJI 无人机键盘控制（复用 keyboard.py 的输入逻辑）

配置参数请直接修改下方的 CONFIG 字典
"""
import sys
import os
import time

# 动态路径处理
if __name__ == '__main__' and __package__ is None:
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..')))

# 导入 DJI SDK
try:
    from ..djisdk import (
        MQTTClient, ServiceCaller, request_control_auth, enter_drc_mode,
        start_heartbeat, stop_heartbeat, send_stick_control
    )
except ImportError:
    from djisdk import (
        MQTTClient, ServiceCaller, request_control_auth, enter_drc_mode,
        start_heartbeat, stop_heartbeat, send_stick_control
    )

# 导入键盘控制 App（复用所有输入逻辑）
try:
    from .keyboard import JoystickApp
except ImportError:
    from keyboard import JoystickApp

# ========== 配置参数 ==========
CONFIG = {
    'gateway_sn': '9N9CN2J0012CXY',
    # 'mqtt_host': 'grve.me',
    'mqtt_host': '192.168.31.73',
    'mqtt_port': 1883,
    'mqtt_username': 'dji',
    'mqtt_password': 'lab605605',
    'frequency': 30.0,
    'user_id': 'keyboard_pilot',
    'user_callsign': 'Keyboard Pilot',
    'in_drc_mode': True,
    'auto_confirm_auth': True,
    'osd_frequency': 100,
    'hsi_frequency': 10,
    'ui_scale': 1.0,
}


def main():
    from rich.console import Console
    from rich.panel import Panel
    import platform

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]🚁 DJI 无人机键盘控制[/bold cyan]\n"
        f"[dim]SN: {CONFIG['gateway_sn']}[/dim]\n"
        f"[dim]MQTT: {CONFIG['mqtt_host']}:{CONFIG['mqtt_port']}[/dim]",
        border_style="cyan"
    ))

    # macOS 长按键盘提示
    if platform.system() == 'Darwin':
        console.print("\n[bold yellow]⚠️  macOS 用户重要提示[/bold yellow]")
        console.print("[yellow]长按键盘可能会弹出字符选择器,影响无人机控制。[/yellow]")
        console.print("[yellow]解决方案（二选一）：[/yellow]")
        console.print(
            "[cyan]1. 临时禁用（推荐）: defaults write -g ApplePressAndHoldEnabled -bool false[/cyan]")
        console.print("[cyan]2. 使用 Shift+P 暂停后切换窗口操作[/cyan]")
        console.print("[dim]提示：禁用后需要重启终端或重新登录生效[/dim]")
        console.print(
            "[dim]退出后可恢复: defaults write -g ApplePressAndHoldEnabled -bool true[/dim]\n")

    # 1. 连接 MQTT
    console.print("[bold cyan]━━━ 步骤 1/4: 连接 MQTT ━━━[/bold cyan]")
    mqtt_client = MQTTClient(CONFIG['gateway_sn'], {
        'host': CONFIG['mqtt_host'], 'port': CONFIG['mqtt_port'],
        'username': CONFIG['mqtt_username'], 'password': CONFIG['mqtt_password']
    })
    try:
        mqtt_client.connect()
    except Exception as e:
        console.print(f"[red]✗ MQTT 连接失败: {e}[/red]")
        return 1

    caller = ServiceCaller(mqtt_client)
    in_drc_mode = CONFIG['in_drc_mode']

    # 2-3. 请求控制权并进入 DRC 模式（如果需要）
    if not in_drc_mode:
        console.print("\n[bold cyan]━━━ 步骤 2/4: 请求控制权 ━━━[/bold cyan]")
        try:
            request_control_auth(
                caller, user_id=CONFIG['user_id'], user_callsign=CONFIG['user_callsign'])
        except Exception as e:
            console.print(f"[red]✗ 控制权请求失败: {e}[/red]")
            mqtt_client.disconnect()
            return 1

        console.print("\n[bold green]控制权请求已发送，请在遥控器上点击确认授权。[/bold green]")
        if CONFIG['auto_confirm_auth']:
            console.print("[bold cyan]自动等待 3 秒后继续...[/bold cyan]")
            time.sleep(3)
        else:
            console.print("[bold yellow]完成后按回车继续...[/bold yellow]")
            try:
                input()
            except KeyboardInterrupt:
                console.print("\n[yellow]检测到中断，退出。[/yellow]")
                mqtt_client.disconnect()
                return 1

        console.print("\n[bold cyan]━━━ 步骤 3/4: 进入 DRC 模式 ━━━[/bold cyan]")
        enter_drc_mode(caller, mqtt_broker={
            'address': f"{CONFIG['mqtt_host']}:{CONFIG['mqtt_port']}",
            'client_id': 'drc-keyboard-control',
            'username': CONFIG['mqtt_username'],
            'password': CONFIG['mqtt_password'],
            'expire_time': int(time.time()) + 3600,
            'enable_tls': False
        }, osd_frequency=CONFIG['osd_frequency'], hsi_frequency=CONFIG['hsi_frequency'])
    else:
        console.print("[bold green]✓ 已跳过控制权请求和进入 DRC 模式。[/bold green]")

    # 4. 启动心跳
    console.print("\n[bold cyan]━━━ 步骤 4/4: 启动心跳 ━━━[/bold cyan]")
    heartbeat_thread = start_heartbeat(mqtt_client, interval=0.2)

    console.print("\n[bold green]✓ 初始化完成！启动 TUI...[/bold green]")
    console.print("[green]✓ 自动焦点检测已启用（失去焦点时自动不响应）[/green]")
    console.print("[bold cyan]💡 按 Shift+P 可暂停（暂停时可切换到其他窗口打字）[/bold cyan]\n")

    try:
        # 定义 MQTT 发送回调（核心：唯一的新功能）
        def send_to_drone(stick_state):
            send_stick_control(
                mqtt_client,
                roll=stick_state['roll'],
                pitch=stick_state['pitch'],
                throttle=stick_state['throttle'],
                yaw=stick_state['yaw']
            )

        # 运行 App（复用 keyboard.py 的所有输入逻辑）
        app = JoystickApp(
            scale=CONFIG['ui_scale'],
            on_stick_update=send_to_drone,
            update_interval=1.0 / CONFIG['frequency']
        )
        app.title = f"🚁 DJI 无人机键盘控制 - SN: {CONFIG['gateway_sn']}"
        app.run()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ 收到中断信号[/yellow]")

    finally:
        # 清理资源
        console.print("\n[cyan]━━━ 清理资源 ━━━[/cyan]")
        console.print("[yellow]发送悬停指令...[/yellow]")
        for _ in range(5):
            send_stick_control(mqtt_client)
            time.sleep(0.1)
        stop_heartbeat(heartbeat_thread)
        mqtt_client.disconnect()
        console.print("[bold green]✓ 已安全退出[/bold green]")

    return 0


if __name__ == '__main__':
    exit(main())
