#!/usr/bin/env python3

import os
import time
from djisdk import stop_heartbeat, setup_multiple_drc_connections
from rich.console import Console
from rich.live import Live
from rich.columns import Columns
from display import create_uav_panel

# 配置
MQTT_CONFIG = {'host': '81.70.222.38', 'port': 1883,
               'username': 'dji', 'password': 'lab605605'}

# UAV 配置 - 9N9CN2J0012CXY (001) | 9N9CN8400164WH (002) | 9N9CN180011TJN (003)
UAV_CONFIGS = [
    # {'sn': '9N9CN2J0012CXY', 'user_id': 'pilot_1', 'callsign': 'Pilot 1'},
    {'sn': '9N9CN8400164WH', 'user_id': 'pilot_2', 'callsign': 'Pilot 2'},
    # {'sn': '9N9CN180011TJN', 'user_id': 'pilot_3', 'callsign': 'Pilot 3'},
]

OSD_FREQUENCY = 100
HSI_FREQUENCY = 10

# 跳过 DRC 连接建立（适用于其他程序已经维持 DRC 状态的场景）
# 设置为 True 时，只连接 MQTT 订阅数据，不请求控制权和进入 DRC 模式
SKIP_DRC_SETUP = True


def main():
    console = Console()

    # 检查是否使用模拟器模式
    USE_MOCK = os.getenv('USE_MOCK_DRONE', '0') == '1'

    # OSD 频率配置

    # 并行设置所有 DRC 连接（自动 3 阶段并行）
    console.rule("[bold cyan]建立多机连接[/bold cyan]")

    if USE_MOCK:
        # 使用模拟器模式
        from djisdk.mock import create_mock_connections
        console.print(
            "[bold yellow]⚠ 模拟器模式已启用（USE_MOCK_DRONE=1）[/bold yellow]")
        console.print("[dim]数据将由模拟器生成，不连接真实无人机[/dim]\n")
        connections = create_mock_connections(UAV_CONFIGS)
    else:
        # 使用真实无人机连接
        connections = setup_multiple_drc_connections(
            UAV_CONFIGS,
            MQTT_CONFIG,
            heartbeat_interval=1.0,
            osd_frequency=OSD_FREQUENCY,
            hsi_frequency=HSI_FREQUENCY,
            skip_drc_setup=SKIP_DRC_SETUP,
        )

    # 构建管理数据
    uav_clients = [
        {'id': str(i+1), 'mqtt': mqtt, 'caller': caller,
         'heartbeat': heartbeat}
        for i, (mqtt, caller, heartbeat) in enumerate(connections)
    ]

    console.print(
        f"\n[bold green]✓ 所有无人机已就绪 ({len(uav_clients)} 架)[/bold green]")

    # 计算 GUI 刷新频率 = max(osd_frequency, 60)
    gui_refresh_rate = max(OSD_FREQUENCY, 60)
    sleep_interval = 1.0 / gui_refresh_rate

    console.print(
        f"[cyan]OSD 频率: {OSD_FREQUENCY} Hz | GUI 刷新频率: {gui_refresh_rate} Hz[/cyan]")
    console.print("[bold yellow]监控运行中... (按 Ctrl+C 退出)[/bold yellow]\n")

    # 实时监控循环
    try:
        start_time = time.time()
        with Live(console=console, refresh_per_second=gui_refresh_rate, screen=True) as live:
            while True:
                elapsed = int(time.time() - start_time)

                # 为每个无人机创建面板
                panels = [
                    create_uav_panel(uav_clients[i], UAV_CONFIGS[i], elapsed)
                    for i in range(len(uav_clients))
                ]

                # 并排显示所有面板
                display = Columns(panels, equal=True, expand=True)
                live.update(display)

                time.sleep(sleep_interval)  # 匹配 GUI 刷新频率

    except KeyboardInterrupt:
        console.print("\n\n[yellow]中断信号收到，正在清理...[/yellow]\n")
    finally:
        # 清理资源
        console.rule("[bold cyan]断开连接[/bold cyan]")
        for i, uav_client in enumerate(uav_clients):
            uav_id = uav_client['id']
            sn = UAV_CONFIGS[i]['sn']
            console.print(f"[cyan]清理无人机 #{uav_id} ({sn})...[/cyan]")
            stop_heartbeat(uav_client['heartbeat'])
            uav_client['mqtt'].disconnect()
            console.print(f"[green]✓ 无人机 #{uav_id} 已断开[/green]")
        console.print(f"\n[bold green]✓ 所有资源已清理完成[/bold green]\n")


if __name__ == "__main__":
    main()
