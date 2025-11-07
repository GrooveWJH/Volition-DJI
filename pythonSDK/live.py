#!/usr/bin/env python3
"""
DJI 无人机 RTMP 直播工具 - 多机版本

功能：
1. 支持多架无人机同时直播
2. 每架无人机独立的 RTMP 推流地址
3. 并行控制多个相机变焦
4. 统一启动/停止直播
"""

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from djisdk import (
    setup_multiple_drc_connections,
    stop_heartbeat,
    wait_for_camera_data,
    start_live,
    stop_live,
)
from djisdk.services.drc_commands import set_camera_zoom
import time
import threading
import sys

console = Console()

# ========== 配置区域 ==========

# MQTT 配置
MQTT_CONFIG = {
    'host': '81.70.222.38',
    # 'host': '192.168.31.73',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

# 无人机配置列表（每架无人机有独立的直播地址）
UAV_CONFIGS = [
    # {
    #     'name': 'Drone001',
    #     'sn': '9N9CN2J0012CXY',
    #     'user_id': 'pilot_1',
    #     'callsign': 'Alpha',
    #     'rtmp_stream_key': 'Drone001',  # RTMP 流名称（拼接到 base_url 后）
    #     'video_index': 'normal-0',
    #     'video_quality': 0,  # 0=自适应, 1=流畅, 2=标清, 3=高清, 4=超清
    #     'zoom': {
    #         'enabled': True,  # 是否启用变焦控制
    #         'initial': 7,  # 初始变焦倍数
    #         'step': 2,  # 变焦步进
    #     }
    # },
    {
        'name': 'Drone002',
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot_2',
        'callsign': 'Bravo',
        'rtmp_stream_key': 'Drone002',
        'video_index': 'normal-0',
        'video_quality': 0,
        'zoom': {
            'enabled': True,
            'initial': 5,
            'step': 2,
        }
    },
    # {
    #     'name': 'Drone003',
    #     'sn': '9N9CN180011TJN',
    #     'user_id': 'pilot_3',
    #     'callsign': 'Charlie',
    #     'rtmp_stream_key': 'drone003',
    #     'video_index': 'normal-0',
    #     'video_quality': 0,
    #     'zoom': {
    #         'enabled': True,
    #         'initial': 10,
    #         'step': 2,
    #     }
    # },
]

# RTMP 服务器配置
RTMP_BASE_URL = 'rtmp://81.70.222.38:1935/live/'  # 基础 URL

# DRC 配置
OSD_FREQUENCY = 1  # Hz
HSI_FREQUENCY = 1  # Hz

# 控制程序结束时是否自动停止直播
STOP_LIVE_ON_EXIT = True

# ========== 全局状态 ==========

# 存储每架无人机的状态
uav_states = {}  # {sn: {'mqtt': ..., 'caller': ..., 'video_id': ..., 'zoom_level': ...}}
stop_event = threading.Event()  # 用于停止所有控制线程


# ========== 工具函数 ==========


def display_uav_list():
    """显示无人机列表"""
    table = Table(title="[bold cyan]可用无人机列表[/bold cyan]",
                  show_header=True, header_style="bold magenta")
    table.add_column("编号", style="cyan", justify="center")
    table.add_column("名称", style="green")
    table.add_column("序列号", style="yellow")
    table.add_column("直播流", style="blue")

    for i, uav in enumerate(UAV_CONFIGS, 1):
        stream_url = f"{RTMP_BASE_URL}{uav['rtmp_stream_key']}"
        table.add_row(str(i), uav['name'], uav['sn'], stream_url)

    console.print(table)


def select_uavs():
    """让用户选择要启动的无人机"""
    display_uav_list()

    console.print("\n[bold cyan]选择启动模式:[/bold cyan]")
    console.print("  [1] 启动所有无人机")
    console.print("  [2] 选择特定无人机")

    choice = Prompt.ask("请选择", choices=["1", "2"], default="1")

    if choice == "1":
        return UAV_CONFIGS
    else:
        # 让用户选择特定无人机
        indices = Prompt.ask(
            "\n输入要启动的无人机编号（多个用逗号分隔，如 1,3）",
            default="1"
        )
        selected_indices = [int(i.strip()) - 1 for i in indices.split(',')]
        selected = [UAV_CONFIGS[i] for i in selected_indices if 0 <= i < len(UAV_CONFIGS)]

        console.print(f"\n[green]✓ 已选择 {len(selected)} 架无人机[/green]")
        return selected


def start_live_for_uav(mqtt, caller, config):
    """
    为单架无人机启动直播

    Args:
        mqtt: MQTTClient
        caller: ServiceCaller
        config: 无人机配置

    Returns:
        video_id or None
    """
    sn = config['sn']
    callsign = config['callsign']

    try:
        # 1. 等待相机数据
        console.print(f"[{callsign}] 等待相机数据...")
        wait_for_camera_data(mqtt, max_wait=10)

        # 2. 构建 RTMP URL
        rtmp_url = f"{RTMP_BASE_URL}{config['rtmp_stream_key']}"
        console.print(f"[{callsign}] 推流地址: {rtmp_url}")

        # 3. 启动直播
        video_id = start_live(
            caller,
            mqtt,
            rtmp_url,
            config['video_index'],
            config['video_quality']
        )

        if video_id:
            # 4. 设置初始变焦
            zoom_config = config.get('zoom', {})
            if zoom_config.get('enabled', False):
                initial_zoom = zoom_config.get('initial', 7)
                payload_index = mqtt.get_payload_index() or "88-0-0"
                console.print(f"[{callsign}] 设置初始变焦 {initial_zoom}x")
                set_camera_zoom(mqtt, payload_index, initial_zoom, camera_type="zoom")

            console.print(f"[green]✓ [{callsign}] 直播已启动 (video_id: {video_id})[/green]")
            return video_id
        else:
            console.print(f"[red]✗ [{callsign}] 直播启动失败[/red]")
            return None

    except Exception as e:
        console.print(f"[red]✗ [{callsign}] 直播启动异常: {e}[/red]")
        return None


def zoom_control_thread(mqtt, config):
    """
    单架无人机的变焦控制线程

    监听键盘输入，控制变焦。
    由于多机场景下不好区分输入，这里暂时禁用键盘控制，
    改为在启动时设置初始变焦。

    如果需要实时控制，可以使用 Web UI 或其他控制方式。
    """
    # 多机场景下暂不支持键盘控制变焦
    # 可以扩展为 Web UI 控制
    pass


def display_live_status():
    """显示所有无人机的直播状态"""
    table = Table(title="[bold cyan]直播状态监控[/bold cyan]",
                  show_header=True, header_style="bold magenta")
    table.add_column("呼号", style="cyan")
    table.add_column("序列号", style="yellow")
    table.add_column("直播状态", style="green")
    table.add_column("推流地址", style="blue")

    for sn, state in uav_states.items():
        callsign = state['config']['callsign']
        status = "🟢 运行中" if state['video_id'] else "🔴 未启动"
        rtmp_url = f"{RTMP_BASE_URL}{state['config']['rtmp_stream_key']}"
        table.add_row(callsign, sn, status, rtmp_url)

    console.print(table)


# ========== 主程序 ==========

def main():
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]DJI 无人机 RTMP 直播工具 - 多机版本[/bold cyan]")
    console.print("=" * 70 + "\n")

    # 步骤 1: 选择无人机
    selected_uavs = select_uavs()

    # 步骤 2: 建立 DRC 连接
    console.print("\n[bold cyan]========== 建立 DRC 连接 ==========[/bold cyan]\n")

    connections = setup_multiple_drc_connections(
        uav_configs=selected_uavs,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=OSD_FREQUENCY,
        hsi_frequency=HSI_FREQUENCY,
        skip_drc_setup=True
    )

    console.print(f"\n[green]✓ 已连接 {len(connections)} 架无人机[/green]\n")

    # 初始化全局状态
    for (mqtt, caller, heartbeat), config in zip(connections, selected_uavs):
        sn = config['sn']
        uav_states[sn] = {
            'mqtt': mqtt,
            'caller': caller,
            'heartbeat': heartbeat,
            'config': config,
            'video_id': None,
            'zoom_level': config.get('zoom', {}).get('initial', 7)
        }

    try:
        # 步骤 3: 并行启动所有直播
        console.print("[bold cyan]========== 启动直播推流 ==========[/bold cyan]\n")

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    start_live_for_uav,
                    state['mqtt'],
                    state['caller'],
                    state['config']
                ): sn
                for sn, state in uav_states.items()
            }

            for future in concurrent.futures.as_completed(futures):
                sn = futures[future]
                try:
                    video_id = future.result()
                    uav_states[sn]['video_id'] = video_id
                except Exception as e:
                    console.print(f"[red]✗ {sn} 启动异常: {e}[/red]")

        # 步骤 4: 显示直播状态
        console.print("\n[bold cyan]========== 直播状态 ==========[/bold cyan]\n")
        display_live_status()

        # 步骤 5: 持续监控
        console.print("\n[bold yellow]所有直播运行中...[/bold yellow]")
        console.print("[dim]按 Ctrl+C 停止直播并退出[/dim]\n")

        while True:
            time.sleep(5)
            # 可以定期更新状态

    except KeyboardInterrupt:
        console.print("\n\n[yellow]收到中断信号[/yellow]")

    finally:
        # 清理资源
        console.print("\n[bold cyan]========== 清理资源 ==========[/bold cyan]\n")

        # 停止所有直播
        if STOP_LIVE_ON_EXIT:
            console.print("[cyan]停止直播推流...[/cyan]")
            for sn, state in uav_states.items():
                if state['video_id']:
                    callsign = state['config']['callsign']
                    try:
                        stop_live(state['caller'], state['video_id'])
                        console.print(f"[green]✓ [{callsign}] 直播已停止[/green]")
                    except Exception as e:
                        console.print(f"[red]✗ [{callsign}] 停止直播失败: {e}[/red]")

        # 停止心跳和 MQTT 连接
        console.print("[cyan]断开连接...[/cyan]")
        for sn, state in uav_states.items():
            callsign = state['config']['callsign']
            try:
                stop_heartbeat(state['heartbeat'])
                state['mqtt'].disconnect()
                console.print(f"[green]✓ [{callsign}] 连接已断开[/green]")
            except Exception as e:
                console.print(f"[red]✗ [{callsign}] 断开失败: {e}[/red]")

        console.print("\n[bold green]✓ 清理完成[/bold green]\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        console.print(f"\n[bold red]程序异常: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
