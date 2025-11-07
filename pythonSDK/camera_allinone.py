#!/usr/bin/env python3
"""
多无人机相机同步控制工具

功能：一个按键同时控制所有无人机的云台和变焦

键盘映射（所有无人机同步）：
  ↑ (Up Arrow)    - 云台回中（reset_mode=0）
  ↓ (Down Arrow)  - 云台向下（reset_mode=1）
  P               - Look At 地面（使用各自当前位置，高度-100m）
  Z               - 放大（Zoom In +2x）
  X               - 缩小（Zoom Out -2x）
  Q               - 退出程序
"""
import sys
import time
import threading
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live

from djisdk import (
    setup_multiple_drc_connections,
    stop_heartbeat,
    reset_gimbal,
    camera_look_at,
    set_camera_zoom,
)

# 尝试导入 pynput（用于键盘监听）
try:
    from pynput import keyboard
    from pynput.keyboard import Key
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("警告: pynput 未安装，将使用基础键盘输入模式")
    print("安装方法: pip install pynput")

console = Console()

# ========== 配置区域 ==========

# MQTT 配置
MQTT_CONFIG = {
    'host': 'grve.me',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# 无人机配置
UAV_CONFIGS = [
    {
        'name': 'Drone001',
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot_1',
        'callsign': 'Alpha',
        'zoom': {
            'current': 7,      # 当前变焦倍数
            'step': 2,         # 每次变焦步进
            'min': 2,          # 最小变焦
            'max': 200,        # 最大变焦
        }
    },
    {
        'name': 'Drone002',
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot_2',
        'callsign': 'Bravo',
        'zoom': {
            'current': 5,
            'step': 2,
            'min': 2,
            'max': 200,
        }
    },
    {
        'name': 'Drone003',
        'sn': '9N9CN180011TJN',
        'user_id': 'pilot_3',
        'callsign': 'Charlie',
        'zoom': {
            'current': 10,
            'step': 2,
            'min': 2,
            'max': 200,
        }
    },
]

# DRC 配置
OSD_FREQUENCY = 1  # Hz（降低频率减少流量）
HSI_FREQUENCY = 1  # Hz
SKIP_DRC_SETUP = True  # 跳过 DRC 模式设置（仅连接 MQTT）

# ========== 全局状态 ==========

uav_states = {}  # {callsign: {'mqtt': ..., 'caller': ..., 'config': ..., 'last_action': ...}}
stop_event = threading.Event()
last_command = "无"  # 最后执行的命令


# ========== 同步控制函数 ==========

def sync_gimbal_reset_center():
    """同步所有无人机：云台回中"""
    global last_command
    last_command = "云台回中"
    console.print(f"\n[bold bright_cyan]>>> 所有无人机：云台回中 <<<[/bold bright_cyan]")

    for callsign, uav_state in uav_states.items():
        try:
            mqtt = uav_state['mqtt']
            payload_index = mqtt.get_payload_index() or "88-0-0"

            # 云台回中（reset_mode=0: yaw回中、pitch回中）
            reset_gimbal(mqtt, payload_index=payload_index, reset_mode=0)

            log_msg = "云台回中"
            console.print(f"  [bright_green]✓ [{callsign}] {log_msg}[/bright_green]")
            uav_state['last_action'] = log_msg
        except Exception as e:
            log_msg = f"云台重置失败: {e}"
            console.print(f"  [bright_red]✗ [{callsign}] {log_msg}[/bright_red]")
            uav_state['last_action'] = log_msg


def sync_gimbal_reset_down():
    """同步所有无人机：云台向下"""
    global last_command
    last_command = "云台向下"
    console.print(f"\n[bold bright_cyan]>>> 所有无人机：云台向下 <<<[/bold bright_cyan]")

    for callsign, uav_state in uav_states.items():
        try:
            mqtt = uav_state['mqtt']
            payload_index = mqtt.get_payload_index() or "88-0-0"

            # 云台向下（reset_mode=1: yaw回中、pitch向下）
            reset_gimbal(mqtt, payload_index=payload_index, reset_mode=1)

            log_msg = "云台向下"
            console.print(f"  [bright_green]✓ [{callsign}] {log_msg}[/bright_green]")
            uav_state['last_action'] = log_msg
        except Exception as e:
            log_msg = f"云台向下失败: {e}"
            console.print(f"  [bright_red]✗ [{callsign}] {log_msg}[/bright_red]")
            uav_state['last_action'] = log_msg


def sync_lookat_ground():
    """同步所有无人机：Look At 地面"""
    global last_command
    last_command = "Look At 地面"
    console.print(f"\n[bold bright_cyan]>>> 所有无人机：Look At 地面 <<<[/bold bright_cyan]")

    for callsign, uav_state in uav_states.items():
        try:
            mqtt = uav_state['mqtt']
            payload_index = mqtt.get_payload_index() or "88-0-0"

            # 获取当前位置
            lat, lon, current_height = mqtt.get_position()
            if lat is None or lon is None:
                log_msg = "无 GPS 信号"
                console.print(f"  [bright_yellow]⚠ [{callsign}] {log_msg}[/bright_yellow]")
                uav_state['last_action'] = log_msg
                continue

            # Look At 地面（高度为当前高度 - 100 米）
            target_height = (current_height or 0) - 100

            camera_look_at(
                mqtt,
                payload_index=payload_index,
                latitude=lat,
                longitude=lon,
                height=target_height,
                locked=False  # 仅云台转，机身不转
            )

            log_msg = f"Look At 地面 (h={target_height:.1f}m)"
            console.print(f"  [bright_green]✓ [{callsign}] {log_msg}[/bright_green]")
            uav_state['last_action'] = log_msg
        except Exception as e:
            log_msg = f"Look At 失败: {e}"
            console.print(f"  [bright_red]✗ [{callsign}] {log_msg}[/bright_red]")
            uav_state['last_action'] = log_msg


def sync_zoom_in():
    """同步所有无人机：放大"""
    global last_command
    last_command = "放大 (Zoom In)"
    console.print(f"\n[bold bright_cyan]>>> 所有无人机：放大 <<<[/bold bright_cyan]")

    for callsign, uav_state in uav_states.items():
        try:
            mqtt = uav_state['mqtt']
            payload_index = mqtt.get_payload_index() or "88-0-0"
            config = uav_state['config']

            # 增加变焦倍数
            zoom_config = config['zoom']
            new_zoom = min(zoom_config['current'] + zoom_config['step'], zoom_config['max'])
            zoom_config['current'] = new_zoom

            set_camera_zoom(mqtt, payload_index=payload_index, zoom_factor=new_zoom, camera_type="zoom")

            log_msg = f"放大 → {new_zoom}x"
            console.print(f"  [bright_cyan]✓ [{callsign}] {log_msg}[/bright_cyan]")
            uav_state['last_action'] = log_msg
        except Exception as e:
            log_msg = f"变焦失败: {e}"
            console.print(f"  [bright_red]✗ [{callsign}] {log_msg}[/bright_red]")
            uav_state['last_action'] = log_msg


def sync_zoom_out():
    """同步所有无人机：缩小"""
    global last_command
    last_command = "缩小 (Zoom Out)"
    console.print(f"\n[bold bright_cyan]>>> 所有无人机：缩小 <<<[/bold bright_cyan]")

    for callsign, uav_state in uav_states.items():
        try:
            mqtt = uav_state['mqtt']
            payload_index = mqtt.get_payload_index() or "88-0-0"
            config = uav_state['config']

            # 减少变焦倍数
            zoom_config = config['zoom']
            new_zoom = max(zoom_config['current'] - zoom_config['step'], zoom_config['min'])
            zoom_config['current'] = new_zoom

            set_camera_zoom(mqtt, payload_index=payload_index, zoom_factor=new_zoom, camera_type="zoom")

            log_msg = f"缩小 → {new_zoom}x"
            console.print(f"  [bright_cyan]✓ [{callsign}] {log_msg}[/bright_cyan]")
            uav_state['last_action'] = log_msg
        except Exception as e:
            log_msg = f"变焦失败: {e}"
            console.print(f"  [bright_red]✗ [{callsign}] {log_msg}[/bright_red]")
            uav_state['last_action'] = log_msg


# ========== 键盘监听 ==========

def on_key_press(key):
    """键盘按下回调（pynput 模式）"""
    try:
        # 处理特殊键（方向键）
        if key == Key.up:
            sync_gimbal_reset_center()
        elif key == Key.down:
            sync_gimbal_reset_down()
        # 处理字符键
        elif hasattr(key, 'char') and key.char:
            key_char = key.char.lower()

            if key_char == 'q':
                console.print("\n[bright_yellow]收到退出信号 (Q)[/bright_yellow]")
                stop_event.set()
                return False  # 停止监听
            elif key_char == 'p':
                sync_lookat_ground()
            elif key_char == 'z':
                sync_zoom_in()
            elif key_char == 'x':
                sync_zoom_out()

    except Exception as e:
        console.print(f"[bright_red]按键处理异常: {e}[/bright_red]")


def keyboard_listener_pynput():
    """键盘监听线程（pynput 模式）"""
    with keyboard.Listener(on_press=on_key_press) as listener:
        listener.join()


def keyboard_listener_basic():
    """键盘监听线程（基础模式，使用 input()）"""
    console.print("\n[bright_yellow]基础键盘模式：输入命令后按 Enter[/bright_yellow]")
    console.print("[dim]命令: up(云台回中), down(云台向下), p(看地面), z(放大), x(缩小), q(退出)[/dim]\n")

    while not stop_event.is_set():
        try:
            cmd = input("命令> ").strip().lower()

            if cmd == 'q':
                console.print("[bright_yellow]收到退出信号 (Q)[/bright_yellow]")
                stop_event.set()
                break
            elif cmd == 'up':
                sync_gimbal_reset_center()
            elif cmd == 'down':
                sync_gimbal_reset_down()
            elif cmd == 'p':
                sync_lookat_ground()
            elif cmd == 'z':
                sync_zoom_in()
            elif cmd == 'x':
                sync_zoom_out()
            else:
                console.print(f"[bright_red]未知命令: {cmd}[/bright_red]")
                console.print("[dim]可用命令: up, down, p, z, x, q[/dim]")

        except (EOFError, KeyboardInterrupt):
            console.print("\n[bright_yellow]收到中断信号[/bright_yellow]")
            stop_event.set()
            break
        except Exception as e:
            console.print(f"[bright_red]命令处理异常: {e}[/bright_red]")


# ========== UI 显示 ==========

def create_ui_layout():
    """创建 UI 布局"""
    # 键盘映射表
    keyboard_table = Table(title="[bold bright_cyan]键盘控制（同步所有无人机）[/bold bright_cyan]",
                           show_header=True, header_style="bold magenta")
    keyboard_table.add_column("按键", style="cyan", justify="center", width=20)
    keyboard_table.add_column("功能", style="green", justify="left")

    keyboard_table.add_row("↑ (Up Arrow)", "云台回中（reset_mode=0）")
    keyboard_table.add_row("↓ (Down Arrow)", "云台向下（reset_mode=1）")
    keyboard_table.add_row("P", "Look At 地面（使用各自位置，高度-100m）")
    keyboard_table.add_row("Z", "放大（Zoom In +2x）")
    keyboard_table.add_row("X", "缩小（Zoom Out -2x）")
    keyboard_table.add_row("[bold red]Q[/bold red]", "[bold red]退出程序[/bold red]")

    # 无人机状态表
    status_table = Table(title=f"[bold bright_green]无人机状态 | 最后命令: {last_command}[/bold bright_green]",
                         show_header=True, header_style="bold magenta")
    status_table.add_column("无人机", style="cyan", justify="center", width=12)
    status_table.add_column("连接", style="green", justify="center", width=10)
    status_table.add_column("GPS", style="yellow", justify="center", width=10)
    status_table.add_column("变焦", style="blue", justify="center", width=8)
    status_table.add_column("最近操作", style="white")

    for callsign, uav_state in uav_states.items():
        config = uav_state['config']
        mqtt = uav_state['mqtt']

        # 连接状态
        is_online = mqtt.is_online(timeout=5.0)
        status = "[bright_green]✓[/bright_green]" if is_online else "[bright_red]✗[/bright_red]"

        # GPS 状态
        lat, lon, height = mqtt.get_position()
        gps_status = "[bright_green]✓[/bright_green]" if lat and lon else "[bright_red]✗[/bright_red]"

        # 变焦倍数
        zoom = f"{config['zoom']['current']}x"

        # 最近操作
        recent_action = uav_state.get('last_action', "无操作")

        status_table.add_row(callsign, status, gps_status, zoom, recent_action)

    # 组合布局
    layout = Layout()
    layout.split_column(
        Layout(Panel(keyboard_table, border_style="bright_cyan"), size=11),
        Layout(Panel(status_table, border_style="bright_green"))
    )

    return layout


# ========== 主程序 ==========

def main():
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]多无人机相机同步控制工具[/bold cyan]")
    console.print("=" * 70 + "\n")

    # 检查 pynput
    if not PYNPUT_AVAILABLE:
        console.print("[bright_yellow]⚠ pynput 未安装，将使用基础键盘模式[/bright_yellow]")
        console.print("[dim]安装方法: pip install pynput[/dim]\n")

    # 步骤 1: 建立 DRC 连接
    console.print("[bold cyan]========== 建立 DRC 连接 ==========[/bold cyan]\n")

    connections = setup_multiple_drc_connections(
        uav_configs=UAV_CONFIGS,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=OSD_FREQUENCY,
        hsi_frequency=HSI_FREQUENCY,
        skip_drc_setup=SKIP_DRC_SETUP
    )

    console.print(f"\n[green]✓ 已连接 {len(connections)} 架无人机[/green]\n")

    # 初始化全局状态
    for (mqtt, caller, heartbeat), config in zip(connections, UAV_CONFIGS):
        callsign = config['callsign']
        uav_states[callsign] = {
            'mqtt': mqtt,
            'caller': caller,
            'heartbeat': heartbeat,
            'config': config,
            'last_action': '待命'
        }

    try:
        # 步骤 2: 启动键盘监听
        console.print("[bold cyan]========== 启动键盘控制 ==========[/bold cyan]\n")

        if PYNPUT_AVAILABLE:
            console.print("[bright_green]✓ 使用 pynput 键盘监听模式[/bright_green]")
            console.print("[dim]直接按键即可控制所有无人机，无需按 Enter[/dim]\n")
            keyboard_thread = threading.Thread(target=keyboard_listener_pynput, daemon=True)
        else:
            keyboard_thread = threading.Thread(target=keyboard_listener_basic, daemon=True)

        keyboard_thread.start()

        # 步骤 3: 实时显示 UI
        console.print("[bold cyan]========== 实时监控 ==========[/bold cyan]\n")

        if PYNPUT_AVAILABLE:
            # pynput 模式：实时更新 UI
            with Live(console=console, refresh_per_second=2, screen=True) as live:
                while not stop_event.is_set():
                    layout = create_ui_layout()
                    live.update(layout)
                    time.sleep(0.5)
        else:
            # 基础模式：键盘监听线程会处理所有输入
            keyboard_thread.join()

    except KeyboardInterrupt:
        console.print("\n\n[bright_yellow]收到中断信号[/bright_yellow]\n")

    finally:
        # 清理资源
        console.print("[bold cyan]========== 断开连接 ==========[/bold cyan]\n")

        for callsign, uav_state in uav_states.items():
            try:
                stop_heartbeat(uav_state['heartbeat'])
                uav_state['mqtt'].disconnect()
                console.print(f"[green]✓ [{callsign}] 已断开[/green]")
            except Exception as e:
                console.print(f"[yellow]⚠ [{callsign}] 断开失败: {e}[/yellow]")

        console.print(f"\n[bold green]✓ 清理完成[/bold green]\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        console.print(f"\n[bold red]程序异常: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
