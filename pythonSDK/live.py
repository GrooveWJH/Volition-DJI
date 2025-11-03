#!/usr/bin/env python3
"""
DJI 无人机 RTMP 直播工具

功能：
1. 连接无人机并进入 DRC 模式
2. 自动检测相机参数 (payload_index, aircraft_sn)
3. 开始 RTMP 直播推流
4. 停止直播推流
5. 键盘控制相机变焦（上下箭头）
"""

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from djisdk import (
    setup_drc_connection,
    stop_heartbeat,
    wait_for_camera_data,
    start_live,
    stop_live,
    zoom_control_loop,
)

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

# 无人机配置列表
UAV_CONFIGS = [
    {
        'name': 'Drone001',
        'sn': '9N9CN2J0012CXY',
        'user_id': 'pilot_1',
        'callsign': 'Pilot 1',
    },
    {
        'name': 'Drone002',
        'sn': '9N9CN8400164WH',
        'user_id': 'pilot_2',
        'callsign': 'Pilot 2',
    },
    {
        'name': 'Drone003',
        'sn': '9N9CN180011TJN',
        'user_id': 'pilot_3',
        'callsign': 'Pilot 3',
    },
]

# RTMP 直播配置
# RTMP_BASE_URL = 'rtmp://192.168.31.73:1935/live/'
RTMP_BASE_URL = 'rtmp://81.70.222.38:1935/live/'  # 基础 URL，会自动拼接无人机名称
VIDEO_INDEX = 'normal-0'  # 视频流索引
VIDEO_QUALITY = 0  # 0=自适应, 1=流畅, 2=标清, 3=高清, 4=超清

# DRC 配置
OSD_FREQUENCY = 1  # Hz
HSI_FREQUENCY = 1  # Hz

# 控制程序结束时是否自动停止直播
STOP_LIVE_ON_EXIT = True

# ========== 工具函数 ==========


def display_uav_list():
    """显示无人机列表"""
    table = Table(title="[bold cyan]可用无人机列表[/bold cyan]",
                  show_header=True, header_style="bold magenta")
    table.add_column("编号", style="cyan", justify="center")
    table.add_column("名称", style="green")
    table.add_column("序列号", style="yellow")

    for i, uav in enumerate(UAV_CONFIGS, 1):
        table.add_row(str(i), uav['name'], uav['sn'])

    console.print(table)


def select_uav():
    """让用户选择无人机"""
    display_uav_list()

    while True:
        choice = Prompt.ask(
            "\n[bold cyan]请选择要连接的无人机编号[/bold cyan]",
            choices=[str(i) for i in range(1, len(UAV_CONFIGS) + 1)],
            default="1"
        )

        index = int(choice) - 1
        selected = UAV_CONFIGS[index]

        console.print(
            f"\n[green]✓ 已选择:[/green] [bold]{selected['name']}[/bold] ({selected['sn']})")
        return selected


# ========== 主程序 ==========

def main():
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]DJI 无人机 RTMP 直播工具[/bold cyan]")
    console.print("=" * 60 + "\n")

    # 步骤 1: 选择无人机
    selected_uav = select_uav()



    # 步骤 3: 建立 DRC 连接
    console.print("\n[bold cyan]========== 建立 DRC 连接 ==========[/bold cyan]\n")

    mqtt, caller, heartbeat = setup_drc_connection(
        gateway_sn=selected_uav['sn'],
        mqtt_config=MQTT_CONFIG,
        user_id=selected_uav['user_id'],
        user_callsign=selected_uav['callsign'],
        osd_frequency=OSD_FREQUENCY,
        hsi_frequency=HSI_FREQUENCY,
        heartbeat_interval=1.0,
        wait_for_user=True
    )

    video_id = None

    try:
        # 步骤 4: 等待相机数据
        wait_for_camera_data(mqtt, max_wait=10)

        # 步骤 5: 开始直播（动态构建 RTMP_URL）
        rtmp_url = f"{RTMP_BASE_URL}{selected_uav['name']}"
        console.print(f"[dim]推流地址: {rtmp_url}[/dim]")
        video_id = start_live(caller, mqtt, rtmp_url, VIDEO_INDEX, VIDEO_QUALITY)

        if video_id:
            # 获取相机参数用于变焦控制
            payload_index = mqtt.get_payload_index() or "88-0-0"

            # 步骤 6: 键盘控制变焦
            console.print("\n[bold yellow]直播运行中...[/bold yellow]")
            zoom_control_loop(mqtt, payload_index, camera_type="zoom")

            # 步骤 7: 停止直播
            if STOP_LIVE_ON_EXIT:
                stop_live(caller, video_id)
            else:
                console.print("[yellow]根据配置保留直播推流[/yellow]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]收到中断信号[/yellow]")
        if video_id:
            if STOP_LIVE_ON_EXIT:
                stop_live(caller, video_id)
            else:
                console.print("[yellow]根据配置保留直播推流[/yellow]")

    finally:
        # 清理资源
        console.print("\n[bold cyan]========== 清理资源 ==========[/bold cyan]")
        console.print("[cyan]停止心跳...[/cyan]")
        stop_heartbeat(heartbeat)
        console.print("[cyan]断开 MQTT 连接...[/cyan]")
        mqtt.disconnect()
        console.print("[bold green]✓ 清理完成[/bold green]\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        console.print(f"\n[bold red]程序异常: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
