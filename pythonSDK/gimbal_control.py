#!/usr/bin/env python3
"""
云台控制 - 键盘控制云台重置

功能：
- 连接无人机 DRC 模式
- 自动获取云台 payload_index
- 使用上下箭头键控制云台重置
  - ↑ 键: 云台回中（reset_mode=0）
  - ↓ 键: 云台向下（reset_mode=1）
- Ctrl+C 退出

使用方法:
    python gimbal_control.py
"""
import sys
import termios
import tty
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from djisdk import (
    setup_drc_connection,
    stop_heartbeat,
    reset_gimbal,
    send_stick_control,
)
from djisdk.utils import wait_for_camera_data

console = Console()

# ========== 配置 ==========
CONFIG = {
    'gateway_sn': '9N9CN2J0012CXY',
    'mqtt_config': {
        'host': 'grve.me',
        'port': 1883,
        'username': 'dji',
        'password': 'lab605605'
    },
    'osd_frequency': 50,
    'hsi_frequency': 10,
    'heartbeat_interval': 0.2,
}


def get_key():
    """
    获取单个按键输入（非阻塞）

    Returns:
        str: 按键字符，特殊键返回转义序列
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)

        # 检测箭头键（ESC序列）
        if ch == '\x1b':  # ESC
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                return f'\x1b[{ch3}'  # 返回完整的箭头键序列
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def print_help():
    """显示帮助信息"""
    table = Table(title="[bold bright_cyan]🎮 云台控制键位[/bold bright_cyan]", show_header=True)
    table.add_column("按键", style="bright_yellow", width=10)
    table.add_column("功能", style="bright_white", width=30)
    table.add_column("说明", style="dim", width=40)

    table.add_row("↑", "云台回中", "yaw回中 + pitch回中 (reset_mode=0)")
    table.add_row("↓", "云台向下", "yaw回中 + pitch向下 (reset_mode=1)")
    table.add_row("Ctrl+C", "退出程序", "断开连接并退出")

    console.print("\n")
    console.print(table)
    console.print("\n")


def main():
    """主函数"""
    console.print(Panel.fit(
        "[bold bright_cyan]🎮 云台控制程序[/bold bright_cyan]\n"
        f"[dim]无人机SN: {CONFIG['gateway_sn']}[/dim]\n"
        f"[dim]MQTT: {CONFIG['mqtt_config']['host']}:{CONFIG['mqtt_config']['port']}[/dim]",
        border_style="bright_cyan"
    ))

    # 显示键位说明
    print_help()

    # 步骤1: 建立 DRC 连接
    console.print("[bold bright_cyan]━━━ 步骤 1/3: 连接无人机 ━━━[/bold bright_cyan]")
    try:
        mqtt, caller, heartbeat = setup_drc_connection(
            gateway_sn=CONFIG['gateway_sn'],
            mqtt_config=CONFIG['mqtt_config'],
            user_id='gimbal_controller',
            user_callsign='Gimbal Pilot',
            osd_frequency=CONFIG['osd_frequency'],
            hsi_frequency=CONFIG['hsi_frequency'],
            heartbeat_interval=CONFIG['heartbeat_interval'],
            wait_for_user=True
        )
    except Exception as e:
        console.print(f"[bright_red]✗ 连接失败: {e}[/bright_red]")
        return 1

    # 步骤2: 自动获取云台 payload_index
    console.print("\n[bold bright_cyan]━━━ 步骤 2/3: 获取云台信息 ━━━[/bold bright_cyan]")
    aircraft_sn, payload_index = wait_for_camera_data(mqtt, max_wait=10)

    if not payload_index:
        console.print("[bright_yellow]⚠ 未获取到云台数据，使用默认值: 88-0-0[/bright_yellow]")
        payload_index = "88-0-0"
    else:
        console.print(f"[bright_green]✓ 云台索引: {payload_index}[/bright_green]")

    # 步骤3: 进入云台控制循环
    console.print("\n[bold bright_cyan]━━━ 步骤 3/3: 云台控制模式 ━━━[/bold bright_cyan]")
    console.print("[bright_yellow]使用 ↑↓ 键控制云台，按 Ctrl+C 退出[/bright_yellow]\n")

    try:
        last_key_time = 0
        key_cooldown = 0.5  # 按键冷却时间（秒），防止连续触发

        while True:
            # 维持悬停（发送心跳杆量）
            send_stick_control(mqtt)

            # 非阻塞获取按键
            try:
                key = get_key()
                current_time = time.time()

                # 冷却检查
                if current_time - last_key_time < key_cooldown:
                    continue

                # 处理箭头键
                if key == '\x1b[A':  # 上箭头
                    console.print(
                        f"[bright_cyan]{time.strftime('%H:%M:%S')}[/bright_cyan] | "
                        f"[bright_green]↑ 云台回中[/bright_green]"
                    )
                    reset_gimbal(mqtt, payload_index=payload_index, reset_mode=0)
                    last_key_time = current_time

                elif key == '\x1b[B':  # 下箭头
                    console.print(
                        f"[bright_cyan]{time.strftime('%H:%M:%S')}[/bright_cyan] | "
                        f"[bright_yellow]↓ 云台向下[/bright_yellow]"
                    )
                    reset_gimbal(mqtt, payload_index=payload_index, reset_mode=1)
                    last_key_time = current_time

                elif key == 'q' or key == '\x03':  # q 或 Ctrl+C
                    break

            except Exception as e:
                # 忽略读取错误，继续循环
                pass

            time.sleep(0.05)  # 50ms 循环

    except KeyboardInterrupt:
        console.print("\n\n[bright_yellow]⚠ 收到中断信号 (Ctrl+C)[/bright_yellow]")

    finally:
        # 清理资源
        console.print("\n[bold bright_cyan]━━━ 断开连接 ━━━[/bold bright_cyan]")
        try:
            stop_heartbeat(heartbeat)
            mqtt.disconnect()
            console.print("[bright_green]✓ 已断开连接[/bright_green]\n")
        except Exception as e:
            console.print(f"[bright_yellow]⚠ 清理警告: {e}[/bright_yellow]\n")

    return 0


if __name__ == '__main__':
    exit(main())
